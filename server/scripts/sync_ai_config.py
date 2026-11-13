#!/usr/bin/env python
"""从 ~/.claude/settings.json 同步 AI 配置到 server/.env。

用法：
    python scripts/sync_ai_config.py            # 写入 .env
    python scripts/sync_ai_config.py --dry-run  # 只看结果，不落盘
    python scripts/sync_ai_config.py --path /custom/settings.json

读取的字段：
    env.ANTHROPIC_AUTH_TOKEN  -> ANTHROPIC_AUTH_TOKEN
    env.ANTHROPIC_BASE_URL    -> ANTHROPIC_BASE_URL
可选：
    env.ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_SONNET_MODEL -> AI_MODEL

已有的 .env 不会被整体覆盖，只更新这几个键，其余保持不变。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = SERVER_DIR / ".env"
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"

KEY_MAP = {
    "ANTHROPIC_AUTH_TOKEN": "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL": "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL": "AI_MODEL",
}

DEFAULT_ENV = """# ========== 「装了吗」服务端配置 ==========
# 由 scripts/sync_ai_config.py 生成/更新；也可以手工编辑

# ---- AI（OpenAI 兼容 Chat Completions 接口）----
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_BASE_URL=https://api.anthropic.com
AI_MODEL=claude-sonnet-4-5-20250929
AI_ENABLED=true
AI_TIMEOUT=120
AI_MAX_TOKENS=6000

# ---- 管理后台 ----
ADMIN_PASSWORD=change-me
ADMIN_SECRET=change-me-to-a-long-random-string
ADMIN_TOKEN_TTL=43200

# ---- 服务 ----
HOST=127.0.0.1
PORT=8017
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:4173
"""


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def upsert_env(values: dict[str, str]) -> None:
    if not ENV_PATH.is_file():
        ENV_PATH.write_text(DEFAULT_ENV, encoding="utf-8")

    text = ENV_PATH.read_text(encoding="utf-8")
    for key, value in values.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.M)
        line = f"{key}={value}"
        if pattern.search(text):
            text = pattern.sub(line, text, count=1)
        else:
            if not text.endswith("\n"):
                text += "\n"
            text += line + "\n"
    ENV_PATH.write_text(text, encoding="utf-8")


def mask(value: str) -> str:
    if not value:
        return "(空)"
    if len(value) <= 10:
        return value[:2] + "*" * (len(value) - 2)
    return f"{value[:6]}…{value[-4:]} (len={len(value)})"


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 Claude 设置中的 AI 配置到 .env")
    parser.add_argument("--path", default=str(DEFAULT_SETTINGS), help="settings.json 路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = parser.parse_args()

    settings_path = Path(os.path.expandvars(os.path.expanduser(args.path)))
    if not settings_path.is_file():
        print(f"[!] 没找到 {settings_path}")
        print("    请确认已安装 Claude Code 并登录，或手工在 server/.env 里填写：")
        print("      ANTHROPIC_AUTH_TOKEN=<your token>")
        print("      ANTHROPIC_BASE_URL=<your base url>")
        return 2

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[!] {settings_path} 不是合法 JSON：{exc}")
        return 3

    env_section = payload.get("env") or {}
    if not isinstance(env_section, dict):
        print("[!] settings.json 里 env 字段不是对象")
        return 3

    updates: dict[str, str] = {}
    for src, dst in KEY_MAP.items():
        value = env_section.get(src)
        if isinstance(value, str) and value.strip():
            updates[dst] = value.strip()

    if "ANTHROPIC_AUTH_TOKEN" not in updates:
        print("[!] settings.json 的 env 里没有 ANTHROPIC_AUTH_TOKEN")
        print("    env 里现有键：" + ", ".join(sorted(env_section.keys())))
        return 4

    merged = {**read_env(ENV_PATH), **updates}
    print("将写入 server/.env：")
    for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "AI_MODEL"):
        if key in updates:
            print(f"  {key} = {mask(merged.get(key, ''))}")
        else:
            print(f"  {key} = (保持原值 {mask(merged.get(key, ''))})")

    if args.dry_run:
        print("\n[dry-run] 未写入文件")
        return 0

    upsert_env(updates)
    print(f"\n[ok] 已更新 {ENV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
