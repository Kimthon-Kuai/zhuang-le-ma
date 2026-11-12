"""首次启动预置常见软件目录。

source 决定版本从哪里拉：
  github  -> GitHub Releases（repo 必填）
  npm     -> npm registry（repo 填包名）
  pypi    -> PyPI（repo 填包名）
  maven   -> Maven Central（repo 填 groupId:artifactId）
  manual  -> 官方下载页（不拉版本，AI 兜底）
  ai      -> 完全交给 AI 给出版本列表
"""
from __future__ import annotations

import json

from .db import get_conn, now_iso

SEED_SOFTWARE: list[dict] = [
    dict(name="mysql", display_name="MySQL", aliases=["mysql server", "mysql数据库", "mysql8"],
         category="database", source="github", repo="mysql/mysql-server",
         tag_pattern=r"^mysql-(\d+\.\d+\.\d+)$",
         homepage="https://dev.mysql.com/downloads/mysql/"),
    dict(name="nodejs", display_name="Node.js", aliases=["node", "nodejs", "node.js", "nodejs环境"],
         category="runtime", source="nodejs", repo="nodejs/node",
         homepage="https://nodejs.org/zh-cn/download"),
    dict(name="python", display_name="Python", aliases=["python3", "py", "python解释器", "py环境"],
         category="runtime", source="python-build-standalone", repo="astral-sh/python-build-standalone",
         homepage="https://www.python.org/downloads/"),
    dict(name="java", display_name="Java (JDK)", aliases=["jdk", "java", "openjdk", "java开发环境", "jdk17", "jdk21"],
         category="runtime", source="adoptium", repo=None,
         homepage="https://adoptium.net/temurin/releases/"),
    dict(name="git", display_name="Git", aliases=["git版本控制", "git-scm"],
         category="tool", source="github", repo="git-for-windows/git",
         homepage="https://git-scm.com/downloads"),
    dict(name="maven", display_name="Maven", aliases=["apache maven", "mvn"],
         category="build", source="maven", repo="org.apache.maven:apache-maven",
         homepage="https://maven.apache.org/download.cgi"),
    dict(name="redis", display_name="Redis", aliases=["redis server"],
         category="database", source="github", repo="redis/redis",
         exclude_pattern=r"-rc|-beta|RC\d",
         homepage="https://redis.io/downloads/"),
    dict(name="docker", display_name="Docker", aliases=["docker desktop", "docker engine"],
         category="tool", source="manual", repo=None,
         homepage="https://www.docker.com/products/docker-desktop/"),
    dict(name="nginx", display_name="Nginx", aliases=["nginx server", "niginx"],
         category="server", source="nginx", repo="nginx/nginx",
         homepage="https://nginx.org/en/download.html"),
    dict(name="go", display_name="Go", aliases=["golang", "go语言", "go环境"],
         category="runtime", source="github", repo="golang/go",
         homepage="https://go.dev/dl/"),
    dict(name="rust", display_name="Rust", aliases=["rustup", "rust语言", "cargo"],
         category="runtime", source="github", repo="rust-lang/rust",
         homepage="https://www.rust-lang.org/tools/install"),
    dict(name="mongodb", display_name="MongoDB", aliases=["mongo", "mongodb server", "mongodb社区版"],
         category="database", source="github", repo="mongodb/mongo",
         homepage="https://www.mongodb.com/try/download/community"),
    dict(name="postgresql", display_name="PostgreSQL", aliases=["postgres", "pgsql", "postgresql数据库"],
         category="database", source="github", repo="postgres/postgres",
         homepage="https://www.postgresql.org/download/"),
    dict(name="vscode", display_name="VS Code", aliases=["vs code", "visual studio code", "vscode", "code"],
         category="editor", source="github", repo="microsoft/vscode",
         homepage="https://code.visualstudio.com/download"),
    dict(name="idea", display_name="IntelliJ IDEA", aliases=["intellij idea", "idea", "intellij", "idea社区版"],
         category="editor", source="manual", repo=None,
         homepage="https://www.jetbrains.com/idea/download/"),
    dict(name="homebrew", display_name="Homebrew", aliases=["brew", "homebrew"],
         category="tool", source="manual", repo=None, homepage="https://brew.sh/",
         platforms=["macos", "linux"]),
    dict(name="nvm", display_name="nvm", aliases=["node version manager", "nvm-windows", "node版本管理"],
         category="tool", source="manual", repo=None, homepage="https://github.com/nvm-sh/nvm",
         platforms=["macos", "linux", "windows"]),
    dict(name="pnpm", display_name="pnpm", aliases=["pnpm包管理器"],
         category="tool", source="github", repo="pnpm/pnpm",
         tag_pattern=r"^v(\d+\.\d+\.\d+)$", homepage="https://pnpm.io/installation"),
    dict(name="yarn", display_name="Yarn", aliases=["yarn包管理器"],
         category="tool", source="github", repo="yarnpkg/berry",
         tag_pattern=r"^@yarnpkg/cli/(\d+\.\d+\.\d+)$",
         homepage="https://yarnpkg.com/getting-started/install"),
    dict(name="conda", display_name="Miniconda", aliases=["conda", "miniconda", "anaconda"],
         category="tool", source="manual", repo=None, homepage="https://docs.conda.io/en/latest/miniconda.html"),
]


def seed_if_empty() -> int:
    """仅在软件表为空时写入预置数据；返回新增条数。"""
    ts = now_iso()
    added = 0
    with get_conn() as conn:
        exists = conn.execute("SELECT COUNT(*) AS c FROM software").fetchone()["c"]
        if exists:
            return 0
        for item in SEED_SOFTWARE:
            conn.execute(
                """INSERT INTO software (name, display_name, aliases, category, source, repo,
                                         homepage, tag_pattern, exclude_pattern, min_major, platforms,
                                         created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["name"], item["display_name"], json.dumps(item.get("aliases", []), ensure_ascii=False),
                    item.get("category"), item.get("source"), item.get("repo"), item.get("homepage"),
                    item.get("tag_pattern"), item.get("exclude_pattern"), item.get("min_major"),
                    json.dumps(item.get("platforms", ["windows", "macos", "linux"])), ts, ts,
                ),
            )
            added += 1
    return added


def sync_preset_sources() -> int:
    """把预置目录里的版本源配置同步到已有数据库（老安装也能拿到修复后的源）。

    只同步 source / repo / homepage 三个字段，不覆盖用户手动改过的显示信息。
    """
    ts = now_iso()
    changed = 0
    with get_conn() as conn:
        for item in SEED_SOFTWARE:
            row = conn.execute("SELECT * FROM software WHERE name = ?", (item["name"],)).fetchone()
            if not row:
                continue
            want = (item.get("source"), item.get("repo"), item.get("homepage"),
                    item.get("tag_pattern"), item.get("exclude_pattern"), item.get("min_major"))
            have = (row["source"], row["repo"], row["homepage"],
                    row["tag_pattern"], row["exclude_pattern"], row["min_major"])
            if want != have:
                conn.execute(
                    """UPDATE software SET source = ?, repo = ?, homepage = ?, tag_pattern = ?,
                                           exclude_pattern = ?, min_major = ?, updated_at = ?
                       WHERE id = ?""",
                    (*want, ts, row["id"]),
                )
                if want[0] != have[0]:
                    # 版本源换了，旧缓存作废
                    conn.execute("DELETE FROM versions WHERE software_id = ?", (row["id"],))
                changed += 1
    return changed
