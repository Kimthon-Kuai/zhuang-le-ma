"""把 ~/.claude/settings.json 里的 AI 凭据同步到 server/.env。

规则：
  env.ANTHROPIC_AUTH_TOKEN -> AI_API_KEY
  env.ANTHROPIC_BASE_URL   -> AI_BASE_URL
  env.ANTHROPIC_MODEL / AI_MODEL -> AI_MODEL（默认 claude-sonnet-4-5）

用法：
  python scripts/sync_env.py              # 读取并写入 .env
  python scripts/sync_env.py --settings 路径
  python scripts/sync_env.py --dry-run    # 只打印掩码后的结果

文件不存在时给出明确提示，并写入可用模板（AI_API_KEY 留空，服务端会自动回退到兜底方案）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = SERVER_DIR / ".env"


def default_settings_paths() -> list[Path]:
    home = Path.home()
    paths = [home / ".claude" / "settings.json"]
    if os.name == "nt" and os.getenv("USERPROFILE"):
        paths.append(Path(os.environ["USERPROFILE"]) / ".claude" / "settings.json")
    return paths


def mask(value: str) -> str:
    if not value:
        return "(空)"
    if len(value) <= 10:
        return value[:2] + "***"
    return f"{value[:6]}...{value[-4:]}（长度 {len(value)}）"


def load_env_block(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    env = data.get("env") or {}
    if not isinstance(env, dict):
        raise SystemExit(f"{path} 中的 env 字段不是对象")
    return env


def pick(env: dict, *keys: str) -> str:
    for k in keys:
        v = env.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def write_env(api_key: str, base_url: str, model: str, force: bool = False) -> None:
    values = {
        "AI_API_KEY": api_key,
        "AI_BASE_URL": base_url or "https://api.openai.com/v1",
        "AI_MODEL": model or "claude-sonnet-4-5",
        "AI_TIMEOUT": "180",
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD") or "admin123",
        "JWT_SECRET": os.getenv("JWT_SECRET") or "zhuang-le-ma-change-me",
        "HOST": "127.0.0.1",
        "PORT": "8017",
        "DB_PATH": "data/zhuang.db",
    }
    existing: dict[str, str] = {}
    if ENV_PATH.exists() and not force:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    # 已有非 AI 配置优先保留；AI 配置以本次同步为准
    for k, v in existing.items():
        if k not in {"AI_API_KEY", "AI_BASE_URL", "AI_MODEL"} and v:
            values[k] = v

    lines = ["# 由 scripts/sync_env.py 生成，可手工修改",
             f"# 来源：{ENV_PATH.parent}", ""]
    for k, v in values.items():
        if k == "AI_API_KEY" and not v:
            lines.append("# AI_API_KEY 为空时，服务端使用本地兜底方案")
        lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 Claude 设置的 AI 凭据到 server/.env")
    parser.add_argument("--settings", type=Path, default=None, help="settings.json 路径")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="覆盖已有 .env")
    args = parser.parse_args()

    candidates = [args.settings] if args.settings else default_settings_paths()
    settings_path = next((p for p in candidates if p and p.exists()), None)

    if not settings_path:
        print("[sync_env] 未找到 ~/.claude/settings.json", file=sys.stderr)
        print("[sync_env] 已写入模板 .env，请手工填写 AI_API_KEY / AI_BASE_URL", file=sys.stderr)
        if not args.dry_run:
            write_env("", "https://api.openai.com/v1", "claude-sonnet-4-5", force=args.force)
        return 1

    try:
        env = load_env_block(settings_path)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[sync_env] 解析 {settings_path} 失败: {exc}", file=sys.stderr)
        return 2

    token = pick(env, "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
    base_url = pick(env, "ANTHROPIC_BASE_URL", "AI_BASE_URL")
    model = pick(env, "ANTHROPIC_MODEL", "AI_MODEL") or "claude-sonnet-4-5"

    print(f"[sync_env] 来源: {settings_path}")
    print(f"[sync_env] AI_API_KEY = {mask(token)}")
    print(f"[sync_env] AI_BASE_URL = {base_url or '(未设置，使用 https://api.openai.com/v1)'}")
    print(f"[sync_env] AI_MODEL = {model}")

    if not token:
        print("[sync_env] settings.json 的 env 中没有 ANTHROPIC_AUTH_TOKEN，跳过写入", file=sys.stderr)
        return 3
    if not args.dry_run:
        write_env(token, base_url, model, force=args.force)
        print(f"[sync_env] 已写入 {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
