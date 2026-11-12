"""查看库里最近几条方案的关键字段与脚本片段。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "zhuang.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, software_name, version, platform, model, install_mode, script_type, "
    "LENGTH(script) AS sl, LENGTH(markdown) AS ml FROM plans ORDER BY id"
).fetchall()
print("== 方案列表 ==")
for r in rows:
    print(f"  #{r['id']:>3} {r['software_name']:<12} {r['version']:<10} {r['platform']:<8} "
          f"model={str(r['model']):<16} mode={r['install_mode']:<14} "
          f"type={str(r['script_type']):<12} script={r['sl']} md={r['ml']}")

target = sys.argv[1] if len(sys.argv) > 1 else "macos"
print(f"\n== {target} 最近的脚本 ==")
r = conn.execute(
    "SELECT id, software_name, script, markdown FROM plans WHERE platform = ? "
    "ORDER BY id DESC LIMIT 1", (target,)
).fetchone()
if not r:
    print("  (没有)")
else:
    print(f"  #{r['id']} {r['software_name']}")
    print("  --- script ---")
    print((r["script"] or "(空)")[:1600])
