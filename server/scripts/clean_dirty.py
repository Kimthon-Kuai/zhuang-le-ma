"""清理历史脏数据：把兜底逻辑误写进 software 表的口语句子删掉，并回归测试识别功能。

用法（在 server 目录下）：
    .venv\\Scripts\\python.exe scripts\\clean_dirty.py
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.seed import SEED_SOFTWARE  # noqa: E402
from app.services import identify, normalize_name, strip_filler  # noqa: E402

print("db:", settings.db_path)

preset = {normalize_name(p["name"]) for p in SEED_SOFTWARE}
removed = []
with get_conn() as con:
    tables = {r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for r in con.execute("SELECT id, name, display_name FROM software").fetchall():
        n = r["name"]
        if n in preset:
            continue
        if re.search(r"[\u4e00-\u9fff]", n) or strip_filler(n).lower() != n \
                or re.search(r"(cool|cooltool|test|dummy|lorem|xyz)", n):
            removed.append((r["id"], r["display_name"]))
            con.execute("DELETE FROM software WHERE id = ?", (r["id"],))
print("removed:", removed or "none")

CASES = [
    "帮我搞 Node", "我想装MySQL", "要不要装 Docker", "想装个 Redis 玩玩",
    "nginx", "安装一下 Python", "Git", "mongodb", "整一个 Go 语言",
]


async def main() -> None:
    for text in CASES:
        sw, matched, ai = await identify(text)
        flag = "OK " if sw.name != normalize_name(text) else "BAD"
        print(f"{flag} {text!r:22} -> {sw.display_name!r:18} matched={matched} ai={ai}")


asyncio.run(main())
