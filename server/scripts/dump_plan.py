"""打印最近生成的方案，便于人工检查 Markdown 质量。

用法：.venv\\Scripts\\python.exe scripts\\dump_plan.py [platform]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_conn  # noqa: E402

platform = sys.argv[1] if len(sys.argv) > 1 else None
sql = "SELECT * FROM plans"
args: tuple = ()
if platform:
    sql += " WHERE platform = ?"
    args = (platform,)
sql += " ORDER BY id DESC LIMIT 1"

with get_conn() as con:
    row = con.execute(sql, args).fetchone()

if not row:
    print("没有方案记录")
    raise SystemExit(0)

print(f"# {row['software_name']} {row['version']} @ {row['platform']}  "
      f"mode={row['install_mode']} type={row['script_type']}\n")
print(row["markdown"])
print("\n" + "=" * 60)
print("EXTRACTED SCRIPT:\n")
print(row["script"] or "(none)")
