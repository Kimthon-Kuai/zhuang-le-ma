"""SQLite 数据层：建表、连接、少量通用工具。使用标准库 sqlite3，无额外依赖。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS software (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,          -- 规范名称（小写去空格），唯一检索键
    display_name  TEXT NOT NULL,                 -- 展示名称，如 MySQL
    aliases       TEXT NOT NULL DEFAULT '[]',    -- JSON 数组，别名 / 中文名
    category      TEXT,                          -- 软件类型，用于选择版本源
    source        TEXT,                          -- npm / pypi / github / maven / manual / ai
    repo          TEXT,                          -- 例如 mysql/mysql-server、nodejs/node
    homepage      TEXT,                          -- 官方下载页
    platforms     TEXT NOT NULL DEFAULT '["windows","macos","linux"]',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    software_id  INTEGER NOT NULL REFERENCES software(id) ON DELETE CASCADE,
    version      TEXT NOT NULL,
    is_latest    INTEGER NOT NULL DEFAULT 0,
    source       TEXT,
    fetched_at   TEXT NOT NULL,
    UNIQUE (software_id, version)
);

CREATE TABLE IF NOT EXISTS plans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    software_id  INTEGER NOT NULL REFERENCES software(id) ON DELETE CASCADE,
    software_name TEXT NOT NULL,
    version      TEXT NOT NULL,
    platform     TEXT NOT NULL,
    markdown     TEXT NOT NULL,
    script       TEXT,                            -- 提取出的主安装脚本，用于一键安装
    script_type  TEXT,                            -- powershell / bash / none
    install_mode TEXT NOT NULL DEFAULT 'script',  -- script / official-link
    model        TEXT,
    valid_count      INTEGER NOT NULL DEFAULT 0,
    invalid_count    INTEGER NOT NULL DEFAULT 0,
    regenerate_count INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (software_id, version, platform)
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id      INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    software_name TEXT,
    version      TEXT,
    platform     TEXT,
    rating       TEXT NOT NULL,                   -- valid / invalid
    content      TEXT,
    handled      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    handled_at   TEXT
);

CREATE TABLE IF NOT EXISTS stats (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,                   -- software / version / platform / plan_generate / install_run
    key          TEXT NOT NULL,
    software_name TEXT,
    platform     TEXT,
    count        INTEGER NOT NULL DEFAULT 1,
    updated_at   TEXT NOT NULL,
    UNIQUE (kind, key)
);

CREATE INDEX IF NOT EXISTS idx_plans_sw ON plans(software_id);
CREATE INDEX IF NOT EXISTS idx_versions_sw ON versions(software_id);
CREATE INDEX IF NOT EXISTS idx_stats_kind ON stats(kind);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def get_conn():
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


# 老库补列：新增字段时在这里追加，避免用户升级后报错
_MIGRATIONS: list[tuple[str, str]] = [
    ("software", "tag_pattern TEXT"),   # GitHub tag → 版本号 的正则，如 mysql-(\d+\.\d+\.\d+)
    ("software", "exclude_pattern TEXT"),  # 排除的 tag（-rc / beta 等）
    ("software", "min_major INTEGER"),  # 过滤过老的大版本
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, ddl in _MIGRATIONS:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        col = ddl.split()[0]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def bump_stat(conn: sqlite3.Connection, kind: str, key: str,
              software_name: str | None = None, platform: str | None = None) -> None:
    conn.execute(
        """INSERT INTO stats (kind, key, software_name, platform, count, updated_at)
           VALUES (?, ?, ?, ?, 1, ?)
           ON CONFLICT(kind, key) DO UPDATE SET
               count = count + 1,
               updated_at = excluded.updated_at,
               software_name = COALESCE(excluded.software_name, stats.software_name),
               platform = COALESCE(excluded.platform, stats.platform)""",
        (kind, key, software_name, platform, now_iso()),
    )
