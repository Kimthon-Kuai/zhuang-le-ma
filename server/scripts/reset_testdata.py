"""清理开发期测试数据：mock 方案、测试反馈、统计记录，保留预置软件目录。

用法：
  python scripts/reset_testdata.py          # 查看将删除的内容
  python scripts/reset_testdata.py --apply  # 实际执行
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
DB_PATH = SERVER_DIR / "data" / "zhuang.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正执行删除")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[reset] 数据库不存在：{DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("== 当前数据 ==")
    for table in ("software", "plans", "feedbacks", "stats"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n}")

    # mock-ai-1 来自 scripts/mock_ai.py；model 为 NULL 的是本地兜底稿（开发期造的数据）
    mock_rows = conn.execute(
        "SELECT id, software_name, version, platform, model FROM plans "
        "WHERE model = 'mock-ai-1' OR model IS NULL "
        "ORDER BY id"
    ).fetchall()
    print("\n== 将被清理的方案（非真实 AI 生成）==")
    for r in mock_rows:
        print(f"  #{r['id']} {r['software_name']} {r['version']} {r['platform']} model={r['model']}")

    if not args.apply:
        print("\n[reset] 预演模式，未做修改。加 --apply 执行。")
        return 0

    ids = [r["id"] for r in mock_rows]
    if ids:
        conn.executemany("DELETE FROM plans WHERE id = ?", [(i,) for i in ids])
    conn.execute("DELETE FROM feedbacks")
    conn.execute("DELETE FROM stats")
    conn.commit()

    left = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("software", "plans", "feedbacks", "stats")}
    conn.close()
    print("\n[reset] 已清理，剩余：", left)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
