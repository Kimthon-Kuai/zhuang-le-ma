"""业务逻辑：软件识别、版本获取、方案生成与缓存。"""
from __future__ import annotations

import asyncio
import json
import re
import shutil

from . import ai, prompts, version_sources
from .db import bump_stat, get_conn, now_iso
from .schemas import SoftwareOut

VERSION_CACHE_TTL_SECONDS = 6 * 3600  # 版本缓存 6 小时

OFFICIAL_LINK_HINT = {"vscode", "idea", "docker", "intellij idea"}


class ServiceError(RuntimeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- 软件目录
def _row_to_software(row) -> SoftwareOut:
    return SoftwareOut(
        id=row["id"],
        name=row["name"],
        display_name=row["display_name"],
        category=row["category"],
        source=row["source"],
        repo=row["repo"],
        tag_pattern=row["tag_pattern"] if "tag_pattern" in row.keys() else None,
        exclude_pattern=row["exclude_pattern"] if "exclude_pattern" in row.keys() else None,
        min_major=row["min_major"] if "min_major" in row.keys() else None,
        homepage=row["homepage"],
        platforms=json.loads(row["platforms"] or "[]"),
        aliases=json.loads(row["aliases"] or "[]"),
    )


def list_software() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM software ORDER BY display_name").fetchall()
        return [_row_to_software(r).model_dump() for r in rows]


def _find_software(conn, needle: str):
    key = normalize_name(needle)
    if not key:
        return None
    # 口语句子（还有填充词残留 / 过长 / 含中文）不允许被视为目录命中，
    # 否则一次兜底写库就会污染后续所有识别
    if len(key) > 24 or strip_filler(needle).lower() != (needle or "").lower().strip():
        return None
    row = conn.execute("SELECT * FROM software WHERE name = ?", (key,)).fetchone()
    if row:
        return row
    # 遍历别名做模糊匹配
    for row in conn.execute("SELECT * FROM software").fetchall():
        candidates = [row["name"], row["display_name"].lower()]
        try:
            candidates += [str(a).lower() for a in json.loads(row["aliases"] or "[]")]
        except json.JSONDecodeError:
            pass
        for c in candidates:
            c_key = normalize_name(c)
            if key == c_key or (len(key) >= 3 and key in c_key):
                return row
    return None


def normalize_name(name: str) -> str:
    return re.sub(r"[\s\-_.]+", "", (name or "").lower())


# 口语填充词：中文整词替换成空格（保留英文与数字），英文口语整词删除
_FILLER_CN = re.compile(r"(我想|我要|帮我|给我|帮我装|请|麻烦|你能|能不能|可以|怎么|如何|安装|装上|装个|装一下|"
                        r"一下|一个|什么|吗|吧|呢|啊|呀|的|个|搞个|搞|弄|整)")
_FILLER_EN = re.compile(r"\b(i\s+want|i\s+need|please|help\s+me|install|setup|set\s+up|to|the|a|an|want|need)\b",
                        re.I)


def strip_filler(text: str) -> str:
    out = _FILLER_CN.sub(" ", text or "")
    out = _FILLER_EN.sub(" ", out)
    return re.sub(r"\s+", " ", out).strip()


def get_software(software_id: int) -> SoftwareOut:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM software WHERE id = ?", (software_id,)).fetchone()
        if not row:
            raise ServiceError("软件不存在", 404)
        return _row_to_software(row)


def _upsert_software(name: str, display_name: str, category: str | None,
                     source: str | None, repo: str | None, homepage: str | None) -> SoftwareOut:
    key = normalize_name(name)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM software WHERE name = ?", (key,)).fetchone()
        ts = now_iso()
        if row:
            # 已存在时补全缺失字段（例如 AI 识别出了 homepage）
            if homepage and not row["homepage"]:
                conn.execute("UPDATE software SET homepage = ?, updated_at = ? WHERE id = ?",
                             (homepage, ts, row["id"]))
            if repo and not row["repo"] and source in {"npm", "pypi", "github", "maven"}:
                conn.execute("UPDATE software SET source = ?, repo = ?, updated_at = ? WHERE id = ?",
                             (source, repo, ts, row["id"]))
            row = conn.execute("SELECT * FROM software WHERE id = ?", (row["id"],)).fetchone()
            return _row_to_software(row)
        cur = conn.execute(
            """INSERT INTO software (name, display_name, aliases, category, source, repo, homepage,
                                     platforms, created_at, updated_at)
               VALUES (?, ?, '[]', ?, ?, ?, ?, '["windows","macos","linux"]', ?, ?)""",
            (key, display_name or name, category, source, repo, homepage, ts, ts),
        )
        row = conn.execute("SELECT * FROM software WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_software(row)


# ---------------------------------------------------------------- 软件识别
async def identify(text: str) -> tuple[SoftwareOut, bool, bool]:
    """返回 (软件, 是否命中目录, 是否用了 AI)。

    策略：先本地目录匹配（快、准），再由 AI 提炼补全。
    本地命中时仍然调 AI 仅用于丰富别名之外的信息没必要，直接返回。
    """
    raw = (text or "").strip()
    if not raw:
        raise ServiceError("说点什么吧，比如「我想装 MySQL」")

    # 口语可出现在任意位置（"帮我搞 Node"、"想装个 Redis 玩玩"）。
    # 优先用剥离填充词后的候选匹配，最后才用完整输入兜底。
    # 注意：完整输入里可能夹着脏数据（历史上被兜底写进库的口语句子），
    # 所以要先把剥离后的候选放在前面，避免脏记录劫持正常识别。
    cleaned = strip_filler(raw)
    ordered: list[str] = []
    for candidate in [cleaned, *re.findall(r"[A-Za-z][A-Za-z0-9.+_\-]{1,}", cleaned), raw]:
        if candidate and candidate.lower() not in [x.lower() for x in ordered]:
            ordered.append(candidate)
    for candidate in ordered:
        with get_conn() as conn:
            hit = _find_software(conn, candidate)
        if hit:
            return _row_to_software(hit), True, False

    ai_used = False
    if ai.ai_configured():
        try:
            result = await ai.chat(
                [{"role": "system", "content": prompts.EXTRACT_SYSTEM},
                 {"role": "user", "content": prompts.extract_user_prompt(raw)}],
                temperature=0.1, max_tokens=300, json_mode=True,
            )
            data = ai.extract_json(result.content)
            ai_used = True
            name = (data.get("software") or cleaned or raw).strip()
            display = (data.get("display_name") or name).strip()
            source = data.get("source") or "manual"
            repo = data.get("repo") if source in {"npm", "pypi", "github", "maven"} else None
            homepage = data.get("homepage")
            sw = _upsert_software(name, display, data.get("category"), source, repo, homepage)
            with get_conn() as conn:
                again = _find_software(conn, display)
                if again and again["id"] != sw.id:
                    return _row_to_software(again), True, ai_used
            return sw, False, ai_used
        except (ai.AIError, json.JSONDecodeError, KeyError):
            ai_used = False

    # 兜底：直接用用户输入当软件名
    name = cleaned or raw
    sw = _upsert_software(name, name, "other", "manual", None, None)
    return sw, False, ai_used


# ---------------------------------------------------------------- 版本获取
def _cached_versions(software_id: int) -> list[dict]:
    """按语义版本降序返回缓存版本（最新标记永远排第一）。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, version, is_latest, fetched_at FROM versions WHERE software_id = ?",
            (software_id,),
        ).fetchall()
    items = [dict(r) for r in rows]
    items.sort(key=lambda r: version_sources.ver_key(r["version"]), reverse=True)
    items.sort(key=lambda r: not r["is_latest"])
    return items


def _cache_fresh(rows: list[dict]) -> bool:
    if not rows:
        return False
    from datetime import datetime, timezone

    latest_ts = max(r["fetched_at"] for r in rows)
    try:
        dt = datetime.fromisoformat(latest_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() < VERSION_CACHE_TTL_SECONDS
    except (ValueError, TypeError):
        return False


def _save_versions(software_id: int, versions: list[tuple[str, bool]], source: str) -> None:
    ts = now_iso()
    with get_conn() as conn:
        for version, is_latest in versions[:60]:
            conn.execute(
                """INSERT INTO versions (software_id, version, is_latest, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(software_id, version) DO UPDATE SET
                     is_latest = excluded.is_latest, source = excluded.source, fetched_at = excluded.fetched_at""",
                (software_id, str(version), int(bool(is_latest)), source, ts),
            )


async def get_versions(software: SoftwareOut, platform: str, refresh: bool = False) -> tuple[list[dict], str]:
    """三级策略：服务端缓存 → 数据源 → AI。返回 (版本列表, 来源说明)。"""
    cached = _cached_versions(software.id) if software.id else []
    if cached and not refresh and _cache_fresh(cached):
        ordered = sorted(cached, key=lambda r: (not r["is_latest"], r["id"]))
        return [{"version": r["version"], "is_latest": bool(r["is_latest"])} for r in ordered], "cache"

    # Windows 上用 winget 本地源兜底：其它来源（GitHub Releases 等）的版本号
    # 往往在 winget 仓库里不存在，用户选了也装不上，所以优先给「装得上的版本」。
    source_label = software.source or "remote"
    if platform == "windows":
        pkg_id = prompts.WINGET_IDS.get(prompts._software_key(software.display_name))
        if pkg_id:
            local = await version_sources.winget_versions(pkg_id)
            if local:
                if software.id:
                    _save_versions(software.id, local, "winget")
                return [{"version": v, "is_latest": l} for v, l in local], "winget"

    fetched = await version_sources.fetch_versions(
        software.source, software.repo,
        tag_pattern=software.tag_pattern, min_major=software.min_major,
        exclude_pattern=software.exclude_pattern,
    )
    fetched = [v for v in fetched if v[0]]
    if fetched:
        if software.id:
            _save_versions(software.id, fetched, software.source or "remote")
        return [{"version": v, "is_latest": l} for v, l in fetched], software.source or "remote"

    if cached:
        ordered = sorted(cached, key=lambda r: (not r["is_latest"], r["id"]))
        return [{"version": r["version"], "is_latest": bool(r["is_latest"])} for r in ordered], "cache"

    if ai.ai_configured():
        try:
            hints = f"source={software.source}, repo={software.repo}, homepage={software.homepage}"
            result = await ai.chat(
                [{"role": "system", "content": prompts.VERSIONS_SYSTEM},
                 {"role": "user", "content": prompts.versions_user_prompt(software.display_name, platform, hints)}],
                temperature=0.2, max_tokens=800, json_mode=True,
            )
            data = ai.extract_json(result.content)
            versions = [str(v) for v in (data.get("versions") or []) if v]
            latest_ai = str(data.get("latest") or (versions[0] if versions else ""))
            pairs = [(v, v == latest_ai) for v in versions]
            if pairs:
                if software.id:
                    _save_versions(software.id, pairs, "ai")
                return [{"version": v, "is_latest": l} for v, l in pairs], "ai"
        except (ai.AIError, json.JSONDecodeError):
            pass

    # 最后兜底：给一个 latest 占位，让方案生成还能进行
    return [{"version": "latest", "is_latest": True}], "fallback"


# ---------------------------------------------------------------- 方案生成
SCRIPT_BLOCK_RE = re.compile(r"```(powershell|ps1|bash|sh|shell)[^\n]*\n(.*?)```", re.S)
SCRIPT_SECTION_RE = re.compile(r"##\s*(一键安装脚本|安装脚本|安装步骤)")


def extract_script(markdown: str) -> tuple[str | None, str | None]:
    """取出「一键安装脚本」章节里的 powershell/bash 代码块作为可执行脚本。

    只认安装章节，避免把「安装验证」里的一行 code --version 当成安装脚本。
    """
    text = markdown or ""
    section = SCRIPT_SECTION_RE.search(text)
    scope = text[section.end():] if section else text
    # 章节内遇到下一个二级标题就截断
    nxt = re.search(r"\n##\s", scope)
    if section and nxt:
        scope = scope[:nxt.start()]
    m = SCRIPT_BLOCK_RE.search(scope)
    if not m:
        return None, None
    lang = m.group(1)
    script_type = "powershell" if lang in {"powershell", "ps1"} else "bash"
    body = m.group(2).strip()
    return body, script_type


def detect_install_mode(software: SoftwareOut, markdown: str = "") -> str:
    """只有「确实是图形安装包」或「生成的方案里没有可执行脚本」才走官方链接模式，
    兜底稿因为不含脚本，不能被误判成 official-link（否则界面上不显示脚本）。"""
    gui_hint = normalize_name(software.name) in {normalize_name(x) for x in OFFICIAL_LINK_HINT}
    if markdown:
        script, _ = extract_script(markdown)
        # 有一键安装脚本 → 一定能装脚本（除非成品就是官方链接方案）
        if script and "## 一键安装脚本" in markdown:
            return "script"
        # 官方下载方案（AI 生成或兜底生成）
        if "## 官方下载链接" in markdown:
            return "official-link"
        return "script" if script else ("official-link" if gui_hint else "script")
    return "official-link" if gui_hint else "script"


def _store_plan(*, software: SoftwareOut, version: str, platform: str, markdown: str,
                model: str | None, regenerate: bool = False) -> dict:
    script, script_type = extract_script(markdown)
    mode = detect_install_mode(software, markdown)
    # official-link 模式下不提供「一键安装」：AI 偶尔会顺手写一段「配置 PATH」之类的补丁，
    # 直接执行会让用户以为软件已经装好了。这类片段只在方案正文里展示。
    if mode == "official-link":
        script, script_type = None, None
    ts = now_iso()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM plans WHERE software_id = ? AND version = ? AND platform = ?",
            (software.id, version, platform),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE plans SET markdown = ?, script = ?, script_type = ?, install_mode = ?,
                   model = ?, updated_at = ?,
                   regenerate_count = regenerate_count + ? WHERE id = ?""",
                (markdown, script, script_type, mode, model, ts, 1 if regenerate else 0, existing["id"]),
            )
            plan_id = existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO plans (software_id, software_name, version, platform, markdown, script,
                                      script_type, install_mode, model, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (software.id, software.display_name, version, platform, markdown, script,
                 script_type, mode, model, ts, ts),
            )
            plan_id = cur.lastrowid
        bump_stat(conn, "plan_generate", f"{software.display_name}::{version}::{platform}",
                  software.display_name, platform)
        row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    return dict(row)


def _plan_dict(row) -> dict:
    d = dict(row)
    d["script_type"] = d.get("script_type")
    return d


def get_plan_by_key(software_id: int, version: str, platform: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM plans WHERE software_id = ? AND version = ? AND platform = ?",
            (software_id, version, platform),
        ).fetchone()
        return _plan_dict(row) if row else None


def get_plan(plan_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            raise ServiceError("方案不存在", 404)
        return _plan_dict(row)


async def generate_plan(software: SoftwareOut, version: str, platform: str,
                        *, force: bool = False) -> tuple[dict, bool]:
    """返回 (方案, 是否命中缓存)。"""
    if not force:
        cached = get_plan_by_key(software.id, version, platform)
        if cached:
            return cached, True

    install_mode = detect_install_mode(software)
    source_hint = f"source={software.source}, repo={software.repo}" if software.repo else None
    model = None
    markdown: str | None = None

    if ai.ai_configured():
        try:
            result = await ai.chat(
                [{"role": "system", "content": prompts.PLAN_SYSTEM},
                 {"role": "user", "content": prompts.plan_user_prompt(
                     display_name=software.display_name, version=version, platform=platform,
                     homepage=software.homepage, install_mode=install_mode,
                     source_hint=source_hint)}],
                temperature=0.25, max_tokens=7000,
            )
            markdown = strip_outer_fence(result.content)
            # 输出被截断时补一句提示，避免用户拿到半截脚本还以为是完整方案
            if (result.finish_reason or "") == "length":
                markdown = (markdown.rstrip() + "\n\n> ⚠️ 方案较长，AI 输出可能被截断。"
                            "可以把 server/.env 的 AI_MAX_TOKENS 调大（DeepSeek 上限 8000），"
                            "或在管理后台手动补全。\n")
            model = result.model
        except ai.AIError as exc:
            if force:
                raise ServiceError(str(exc), 502) from exc

    if not markdown:
        markdown = prompts.fallback_plan(
            display_name=software.display_name, version=version,
            platform=platform, homepage=software.homepage,
            install_mode=install_mode,
        )

    plan = _store_plan(software=software, version=version, platform=platform,
                       markdown=markdown, model=model, regenerate=force)
    return plan, False


def strip_outer_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```$", text, re.S)
    return m.group(1).strip() if m else text


def update_plan_markdown(plan_id: int, markdown: str) -> dict:
    plan = get_plan(plan_id)
    script, script_type = extract_script(markdown)
    with get_conn() as conn:
        conn.execute(
            "UPDATE plans SET markdown = ?, script = ?, script_type = ?, updated_at = ? WHERE id = ?",
            (markdown, script, script_type, now_iso(), plan_id),
        )
    return get_plan(plan_id)


def delete_plan(plan_id: int) -> None:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        if cur.rowcount == 0:
            raise ServiceError("方案不存在", 404)


def list_plans(limit: int = 200, offset: int = 0, q: str | None = None) -> list[dict]:
    sql = "SELECT * FROM plans"
    params: list = []
    if q:
        sql += " WHERE software_name LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_plan_dict(r) for r in rows]


# ---------------------------------------------------------------- 反馈
def add_feedback(data: dict) -> dict:
    ts = now_iso()
    plan = None
    if data.get("plan_id"):
        try:
            plan = get_plan(int(data["plan_id"]))
        except ServiceError:
            plan = None
    with get_conn() as conn:
        if plan and data.get("rating") in {"valid", "invalid"}:
            col = "valid_count" if data["rating"] == "valid" else "invalid_count"
            conn.execute(f"UPDATE plans SET {col} = {col} + 1 WHERE id = ?", (plan["id"],))
        cur = conn.execute(
            """INSERT INTO feedbacks (plan_id, software_name, version, platform, rating, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (plan["id"] if plan else None,
             (plan or {}).get("software_name") or data.get("software_name"),
             (plan or {}).get("version") or data.get("version"),
             (plan or {}).get("platform") or data.get("platform"),
             data["rating"], data.get("content"), ts),
        )
        row = conn.execute("SELECT * FROM feedbacks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_feedbacks(limit: int = 200, handled: bool | None = None) -> list[dict]:
    sql = "SELECT * FROM feedbacks"
    params: list = []
    if handled is not None:
        sql += " WHERE handled = ?"
        params.append(int(handled))
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def mark_feedback(plan_id: int, handled: bool) -> dict:
    with get_conn() as conn:
        cur = conn.execute("UPDATE feedbacks SET handled = ?, handled_at = ? WHERE id = ?",
                           (int(handled), now_iso() if handled else None, plan_id))
        if cur.rowcount == 0:
            raise ServiceError("反馈不存在", 404)
        return dict(conn.execute("SELECT * FROM feedbacks WHERE id = ?", (plan_id,)).fetchone())


# ---------------------------------------------------------------- 统计
def record_stat(kind: str, key: str, software_name: str | None, platform: str | None) -> None:
    with get_conn() as conn:
        bump_stat(conn, kind, key, software_name, platform)


def stats_overview() -> dict:
    with get_conn() as conn:
        by_kind: dict[str, list[dict]] = {}
        for row in conn.execute("SELECT * FROM stats ORDER BY count DESC").fetchall():
            by_kind.setdefault(row["kind"], []).append(dict(row))
        totals = {
            "plans": conn.execute("SELECT COUNT(*) c FROM plans").fetchone()["c"],
            "software": conn.execute("SELECT COUNT(*) c FROM software").fetchone()["c"],
            "feedbacks": conn.execute("SELECT COUNT(*) c FROM feedbacks").fetchone()["c"],
            "pending_feedbacks": conn.execute("SELECT COUNT(*) c FROM feedbacks WHERE handled = 0").fetchone()["c"],
        }
        plan_stats = [dict(r) for r in conn.execute(
            "SELECT software_name, version, platform, valid_count, invalid_count, updated_at "
            "FROM plans ORDER BY valid_count DESC LIMIT 20").fetchall()]
    return {
        "totals": totals,
        "software": by_kind.get("software", [])[:50],
        "version": by_kind.get("version", [])[:50],
        "platform": by_kind.get("platform", []),
        "install_run": by_kind.get("install_run", [])[:50],
        "plan_generate": by_kind.get("plan_generate", [])[:50],
        "plans": plan_stats,
    }
