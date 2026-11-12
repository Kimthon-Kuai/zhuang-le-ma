"""版本数据源适配：npm / PyPI / GitHub Releases / Maven Central。

所有函数都是「尽力而为」：网络失败返回空列表，由上层决定是否回退到 AI。
每个函数返回 [(version, is_latest), ...]，已按「新版本在前」排序并去重。
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import httpx

TIMEOUT = httpx.Timeout(10.0, connect=6.0)
UA = {"User-Agent": "zhuang-le-ma/1.0"}

_VERSION_RE = re.compile(r"\d+(?:\.\d+){0,3}")

# 部分仓库 tag 形态特殊（HTML 兜底解析与 API 解析都要用）：
#   include: 只保留匹配的 tag；exclude: 排除；convert: 自定义 tag -> 版本号
TAG_PATTERNS: dict[str, dict] = {
    "golang/go": {"include": r"^go\d", "convert": lambda t: re.sub(r"^go", "", t)},
    "mysql/mysql-server": {"include": r"^mysql-\d", "exclude": r"cluster",
                           "convert": lambda t: re.sub(r"^mysql-", "", t)},
    "mongodb/mongo": {"include": r"^r\d", "convert": lambda t: re.sub(r"^r", "", t)},
    "postgres/postgres": {"include": r"^REL_\d+_\d+$",
                          "convert": lambda t: t.replace("REL_", "").replace("_", ".")},
    "rust-lang/rust": {"include": r"^\d+\.\d+\.\d+$"},
    # 须在通用数字转换之前，避免 release-1.31.8 被抠成乱码
    "nginx/nginx": {"include": r"^release-\d+\.\d+\.\d+$",
                    "convert": lambda t: re.sub(r"^release-", "", t)},
    "redis/redis": {"include": r"^\d+\.\d+\.\d+$"},
}


def apply_tag_pattern(repo: str, tag: str) -> str | None:
    """按仓库规则过滤 / 转换 tag，返回版本号或 None。"""
    rule = TAG_PATTERNS.get(repo.lower(), {})
    include, exclude = rule.get("include"), rule.get("exclude")
    if include and not re.search(include, tag):
        return None
    if exclude and re.search(exclude, tag, re.I):
        return None
    convert = rule.get("convert")
    if convert:
        return convert(tag) or None
    return _clean_github_tag(tag)


def ver_key(v: str) -> tuple[int, ...]:
    """对外暴露的版本排序键（供缓存排序复用）。"""
    return _ver_tuple(v)


def _ver_tuple(v: str) -> tuple[int, ...]:
    m = _VERSION_RE.search(v)
    if not m:
        return (0, 0, 0, 0)
    nums = [int(x) for x in m.group(0).split(".")]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def _sort_unique(versions: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    seen: dict[str, bool] = {}
    for v, latest in versions:
        if v and v not in seen:
            seen[v] = latest
    out = sorted(seen.items(), key=lambda kv: _ver_tuple(kv[0]), reverse=True)
    if out and not any(latest for _, latest in out):
        out[0] = (out[0][0], True)
    return out


GITHUB_API = "https://api.github.com"
_github_token: str | None = None


def github_token() -> str:
    global _github_token
    if _github_token is None:
        from .config import settings
        _github_token = settings.github_token
    return _github_token


def _gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "zhuang-le-ma/1.0"}
    tok = github_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


async def _get_json(url: str, headers: dict | None = None) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers={**UA, **(headers or {})})
            if resp.status_code >= 400:
                return None
            return resp.json()
    except Exception:
        return None


async def _get_text(url: str, headers: dict | None = None) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers={**UA, **(headers or {})})
            if resp.status_code >= 400:
                return None
            return resp.text
    except Exception:
        return None


# ---------------------------------------------------------------- npm
async def npm_versions(pkg: str) -> list[tuple[str, bool]]:
    data = await _get_json(f"https://registry.npmjs.org/{pkg}")
    if not isinstance(data, dict):
        return []
    latest = (data.get("dist-tags") or {}).get("latest")
    versions = list((data.get("versions") or {}).keys())
    if not versions:
        return []
    stable = [v for v in versions if re.fullmatch(r"\d+(\.\d+)*", v)]
    pool = stable or versions
    ordered = _sort_unique([(v, False) for v in pool])
    # npm 的 dist-tags.latest 才是权威「最新」，必要时插到首位
    if latest and not any(v == latest for v, _ in ordered):
        ordered = [(latest, True)] + ordered
    return [(v, v == latest) for v, _ in ordered]


async def npm_latest(pkg: str) -> str | None:
    data = await _get_json(f"https://registry.npmjs.org/{pkg}/latest")
    if isinstance(data, dict):
        return data.get("version")
    return None


# ---------------------------------------------------------------- PyPI
async def pypi_versions(pkg: str) -> list[tuple[str, bool]]:
    data = await _get_json(f"https://pypi.org/pypi/{pkg}/json")
    if not isinstance(data, dict):
        return []
    latest = (data.get("info") or {}).get("version")
    releases = data.get("releases") or {}
    stable: list[tuple[str, bool]] = []
    for v, files in releases.items():
        if not files or not re.fullmatch(r"\d+(\.\d+)*", v):
            continue
        stable.append((v, v == latest))
    return _sort_unique(stable)


# ---------------------------------------------------------------- GitHub
def _clean_github_tag(tag: str) -> str | None:
    m = re.search(r"v?(\d+(?:\.\d+){1,3})", tag or "")
    return m.group(1) if m else None


async def github_releases(repo: str, include_prerelease: bool = False, *,
                          tag_pattern: str | None = None,
                          min_major: int | None = None,
                          exclude_pattern: str | None = None) -> list[tuple[str, bool]]:
    data = await _get_json(f"{GITHUB_API}/repos/{repo}/releases?per_page=60", headers=_gh_headers())
    if isinstance(data, list) and data:
        out: list[tuple[str, bool]] = []
        for rel in data:
            if rel.get("draft"):
                continue
            if rel.get("prerelease") and not include_prerelease:
                continue
            tag = rel.get("tag_name") or ""
            ver = extract_tag_version(tag, tag_pattern, repo, exclude_pattern)
            if ver and _major_ok(ver, min_major):
                out.append((ver, False))
        result = _sort_unique(out)
        if result:
            result[0] = (result[0][0], True)
            return result

    # API 不可用（限流 / 无 token）时，退回到公开的 tags 页面解析
    return await github_releases_from_html(repo, tag_pattern=tag_pattern, min_major=min_major,
                                          exclude_pattern=exclude_pattern)


def extract_tag_version(tag: str, tag_pattern: str | None, repo: str | None = None,
                        exclude_pattern: str | None = None) -> str | None:
    """优先用显式正则（能排除非版本 tag），否则回退到内置匹配表 / 通用匹配。"""
    if exclude_pattern and re.search(exclude_pattern, tag or "", re.I):
        return None
    if tag_pattern:
        m = re.search(tag_pattern, tag or "")
        return m.group(1) if m else None
    return apply_tag_pattern(repo or "", tag) or _clean_github_tag(tag)


def _major_ok(ver: str, min_major: int | None) -> bool:
    if min_major is None:
        return True
    try:
        return int(ver.split(".")[0]) >= min_major
    except ValueError:
        return False


async def github_releases_from_html(repo: str, *, tag_pattern: str | None = None,
                                    min_major: int | None = None,
                                    exclude_pattern: str | None = None) -> list[tuple[str, bool]]:
    """解析 /tags 页面（/releases 是前端渲染的，HTML 里没有版本信息）。"""
    from urllib.parse import unquote

    html = await _get_text(f"https://github.com/{repo}/tags")
    if not html:
        return []
    tags = re.findall(r'href="/' + re.escape(repo) + r'/releases/tag/([^"]+)"', html)
    out: list[tuple[str, bool]] = []
    for raw in tags:
        tag = unquote(raw)
        if not tag_pattern and re.search(r"(alpha|beta|rc|dev|preview|nightly|canary)", tag, re.I):
            continue
        ver = extract_tag_version(tag, tag_pattern, repo, exclude_pattern)
        if ver and _major_ok(ver, min_major):
            out.append((ver, False))
    result = _sort_unique(out)
    if result:
        result[0] = (result[0][0], True)
    return result


async def github_latest(repo: str) -> str | None:
    data = await _get_json(f"{GITHUB_API}/repos/{repo}/releases/latest", headers=_gh_headers())
    if isinstance(data, dict):
        tag = _clean_github_tag(data.get("tag_name") or "")
        if tag:
            return tag
    vs = await github_releases(repo)
    return vs[0][0] if vs else None


# ---------------------------------------------------------------- python-build-standalone
async def python_build_standalone_versions(repo: str = "astral-sh/python-build-standalone") -> list[tuple[str, bool]]:
    """astral 用发布日期做 tag，真实 Python 版本藏在 release 名称里。"""
    data = await _get_json(f"{GITHUB_API}/repos/{repo}/releases?per_page=15", headers=_gh_headers())
    found: set[str] = set()
    if isinstance(data, list):
        for rel in data:
            m = re.search(r"Python\s+(\d+\.\d+\.\d+)", rel.get("name") or "")
            if m:
                found.add(m.group(1))
    if not found:
        html = await _get_text(f"https://github.com/{repo}/releases") or ""
        for v in re.findall(r"Python\s+(\d+\.\d+\.\d+)", html):
            found.add(v)
    if not found:
        # releases 页是前端渲染的，退到 tags 页解析日期 tag，再查 release 名称不可行
        # 改用 python.org 的官方版本列表（稳定、结构化）
        data = await _get_json("https://www.python.org/api/v2/downloads/release/")
        if isinstance(data, list):
            for rel in data:
                if rel.get("is_published") and not rel.get("pre_release"):
                    m = re.match(r"Python (\d+\.\d+\.\d+)$", rel.get("name") or "")
                    if m:
                        found.add(m.group(1))
    if not found:
        return []
    out = _sort_unique([(v, False) for v in found])
    if out:
        out[0] = (out[0][0], True)
    return out


# ---------------------------------------------------------------- Node.js 官方发行版
async def nodejs_versions() -> list[tuple[str, bool]]:
    """nodejs.org/dist/index.json 是官方版本清单，带 lts 字段，比 npm 可靠。

    npm 上拿到的 node 包版本并不是 Node.js 发行版，所以预置目录里单独走这个源。
    """
    data = await _get_json("https://nodejs.org/dist/index.json")
    if not isinstance(data, list):
        return []
    stable: list[str] = []
    for item in data:
        v = (item.get("version") or "").lstrip("v")
        if not re.fullmatch(r"\d+\.\d+\.\d+", v):
            continue  # v26.0.0-rc.2 之类直接跳过
        stable.append(v)
    # 只留当前最新主版本和它前面的两个主版本（即主线 + 近两代），
    # 避免刷出几十个大版本让下拉框没法用
    majors = []
    for v in stable:
        m = int(v.split(".")[0])
        if m not in majors:
            majors.append(m)
    majors.sort(reverse=True)
    keep = set(majors[:3])
    picked = [v for v in stable if int(v.split(".")[0]) in keep]
    out = _sort_unique([(v, False) for v in picked])
    if out:
        out[0] = (out[0][0], True)
    return out


async def nginx_versions() -> list[tuple[str, bool]]:
    """nginx.org 的下载页把版本写在文件名里（nginx-1.31.5.tar.gz），主线与稳定版都在同一页。"""
    html = await _get_text("https://nginx.org/en/download.html") or ""
    found = set(re.findall(r"nginx-(\d+\.\d+\.\d+)\.tar\.gz", html))
    out = _sort_unique([(v, False) for v in found])
    if out:
        out[0] = (out[0][0], True)
    return out


# ---------------------------------------------------------------- Adoptium (JDK)
async def adoptium_versions(lts_only: bool = True) -> list[tuple[str, bool]]:
    """api.adoptium.net 返回形如 jdk-25.0.5+8 / jdk-25+35 的 release name。

    只保留 GA 且带补丁号的版本（jdk-25.0.5+8 → 25.0.5），大版本号用 x.y.0 表示。
    """
    url = ("https://api.adoptium.net/v3/info/release_names?"
           f"release_type=ga&sort_order=DESC&page_size=60{'&version=%5B21%2C)' if lts_only else ''}")
    data = await _get_json(url)
    if not isinstance(data, dict):
        return []
    out: list[tuple[str, bool]] = []
    for name in data.get("releases") or []:
        m = re.fullmatch(r"jdk-(\d+)(?:\.(\d+)\.(\d+))?[.\d]*\+\d+", str(name))
        if not m:
            continue
        major, minor, patch = m.group(1), m.group(2) or "0", m.group(3) or "0"
        out.append((f"{major}.{minor}.{patch}", False))
    result = _sort_unique(out)
    if result:
        result[0] = (result[0][0], True)
    return result


# ---------------------------------------------------------------- Maven (repo1 元数据)
def _xml_versions(xml: str) -> list[str]:
    """从 maven-metadata.xml 里取 <version> 列表（标准库解析，无需 lxml）。"""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    return [el.text.strip() for el in root.iter("version") if el.text]


async def maven_versions(spec: str) -> list[tuple[str, bool]]:
    """spec 形如 groupId:artifactId，走 repo1 的 maven-metadata.xml。

    Maven Central 的 Search API 经常超时，而元数据文件稳定、且直接给出全部版本。
    """
    if ":" not in spec:
        return []
    group, artifact = spec.split(":", 1)
    url = (f"https://repo1.maven.org/maven2/{group.replace('.', '/')}/"
           f"{artifact}/maven-metadata.xml")
    xml = await _get_text(url)
    if not xml:
        return []
    candidates = _xml_versions(xml)
    stable = [v for v in candidates
              if re.fullmatch(r"\d+(\.\d+)*(-\d+)?", v)
              and not re.search(r"(alpha|beta|rc|snapshot|M\d|dev)", v, re.I)]
    return _sort_unique([(v, False) for v in stable])[:40]


# ---------------------------------------------------------------- 分发入口
async def fetch_versions(source: str | None, repo: str | None, *,
                         tag_pattern: str | None = None,
                         min_major: int | None = None,
                         exclude_pattern: str | None = None) -> list[tuple[str, bool]]:
    if not source:
        return []
    if not repo and source not in {"nodejs", "nginx", "adoptium"}:
        return []
    try:
        if source == "npm":
            return await npm_versions(repo or "")
        if source == "pypi":
            return await pypi_versions(repo or "")
        if source == "github":
            return await github_releases(repo or "", tag_pattern=tag_pattern, min_major=min_major,
                                         exclude_pattern=exclude_pattern)
        if source == "python-build-standalone":
            return await python_build_standalone_versions(repo or "")
        if source == "nodejs":
            return await nodejs_versions()
        if source == "nginx":
            return await nginx_versions()
        if source == "adoptium":
            return await adoptium_versions()
        if source == "maven":
            return await maven_versions(repo or "")
    except Exception:
        return []
    return []


# ---------------------------------------------------------------- winget 本地源
async def winget_versions(pkg_id: str) -> list[tuple[str, bool]]:
    """调用本机 winget 列出版本（与服务端同机时最准：用户点一下就能装上）。

    使用 --disable-interactivity 避免弹交互提示；输出可能是中文表头，
    所以不解析表头，只从纯版本号行里取。本机没有 winget 时返回空列表。
    """
    import shutil

    exe = shutil.which("winget")
    if not exe:
        return []

    def _run() -> str:
        import subprocess

        proc = subprocess.run(
            [exe, "show", "--id", pkg_id, "-e", "--versions",
             "--accept-source-agreements", "--disable-interactivity"],
            capture_output=True, timeout=40,
        )
        raw = proc.stdout or b""
        for enc in ("utf-8", "gbk"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return ""

    try:
        text = await asyncio.to_thread(_run)
    except Exception:
        return []
    versions = [m.group(1).lstrip("v")
                for m in re.finditer(r"(?m)^\s*(v?\d+(?:\.\d+){0,3})\s*$", text)]
    if not versions:
        return []
    out = _sort_unique([(v, False) for v in versions])
    out[0] = (out[0][0], True)
    return out


async def fetch_latest(source: str | None, repo: str | None) -> str | None:
    if not source or not repo:
        return None
    try:
        if source == "npm":
            return await npm_latest(repo)
        if source == "github":
            return await github_latest(repo)
        vs = await fetch_versions(source, repo)
        return vs[0][0] if vs else None
    except Exception:
        return None


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()
