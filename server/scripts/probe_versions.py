"""逐个软件检查版本源质量：抓到的版本是否像真实发行版。

用法：.venv\\Scripts\\python.exe scripts\\probe_versions.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed import SEED_SOFTWARE  # noqa: E402
from app.version_sources import fetch_versions  # noqa: E402


async def main() -> None:
    for item in SEED_SOFTWARE:
        src, repo = item.get("source"), item.get("repo")
        if src in (None, "manual", "ai"):
            print(f"SKIP {item['display_name']:18} source={src}")
            continue
        vs = await fetch_versions(src, repo,
                                  tag_pattern=item.get("tag_pattern"),
                                  min_major=item.get("min_major"),
                                  exclude_pattern=item.get("exclude_pattern"))
        head = ", ".join(v for v, _ in vs[:5])
        print(f"{len(vs):4d} {item['display_name']:18} [{src}] {head or '(empty)'}")


asyncio.run(main())
