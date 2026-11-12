"""本地 Mock AI：OpenAI 兼容 /v1/chat/completions，用于在没有真实 Key 时验证 AI 链路。

它会根据提示词判断应该返回「软件识别 JSON」「版本列表 JSON」还是「安装方案 Markdown」，
并返回结构完整、可执行的真实脚本，便于端到端测试。

启动：python scripts/mock_ai.py --port 8899
"""
from __future__ import annotations

import argparse
import json
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Mock AI")


class ChatIn(BaseModel):
    model: str = "mock-model"
    messages: list[dict]
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: dict | None = None


def _system_text(messages: list[dict]) -> str:
    return "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")


def _user_text(messages: list[dict]) -> str:
    return "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")


def _extract(prompt: str, key: str) -> str | None:
    m = re.search(rf"-\s*{key}：(.+)", prompt)
    return m.group(1).strip() if m else None


PLAN_POWERSHELL = r"""## 一键安装脚本

```powershell
# 装了吗 · {name} {version} 安装脚本
# 目标系统：Windows 10/11（PowerShell 5.1+）
# 做什么：用 winget 锁定版本安装，并写入用户级环境变量

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# 1) 检查 winget
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {{
    Write-Host '未找到 winget，请先在 Microsoft Store 安装「应用安装程序」' -ForegroundColor Yellow
    exit 1
}}

# 2) 安装指定版本（失败时自动重试一次，应对网络抖动）
$id = '{winget_id}'
$ver = '{version}'
Write-Host "开始安装 $id $ver ..."
winget install --id $id --version $ver -e --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -ne 0) {{
    Write-Host '第一次失败，正在重试（常见于网络超时）...' -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    winget install --id $id --version $ver -e --accept-package-agreements --accept-source-agreements
}}

# 3) 刷新当前会话的 PATH（winget 已写入用户级环境变量）
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

# 4) 安装验证
Write-Host '验证安装：' -ForegroundColor Cyan
{verify}
```

## 脚本运行说明

脚本会在安装完成后自动刷新本会话的 PATH，直接在 App 里点「一键安装」即可，不需要管理员权限。
如果公司电脑限制了 winget 下载，请先在「设置 → 网络」里放行 `cdn.winget.microsoft.com`。

## 安装验证

```powershell
{verify}
```

预期输出：打印 {name} 的版本号。

## 执行后建议

- 关闭当前终端并重新打开，让环境变量生效。
- 执行 `Get-Command {cmd} -All` 确认只装了一份，避免多版本冲突。
- 如需卸载：`winget uninstall --id {winget_id}`。

## 常见问题

**下载超时**：脚本已内置一次重试；仍失败就换网络或用代理后重跑。
**提示「拒绝访问」**：用管理员身份重新打开终端后再执行。
**命令找不到**：刚装完的 PATH 只在脚本进程里刷新了，重开一个终端即可。
"""

PLAN_BASH = r"""## 一键安装脚本

```bash
#!/usr/bin/env bash
# 装了吗 · {name} {version} 安装脚本
# 目标系统：macOS / Linux
# 做什么：安装指定版本，并把安装目录写入 shell 配置
set -euo pipefail

# 1) 确认 Homebrew（macOS）
if ! command -v brew >/dev/null 2>&1; then
  echo "未找到 Homebrew，正在安装..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# 2) 安装并锁定版本的包
PACKAGE="{brew_pkg}"
brew install "$PACKAGE" || brew upgrade "$PACKAGE" || true

# 3) 写入环境变量（避免重复追加）
BREW_BIN="/opt/homebrew/bin"
[ -d "$BREW_BIN" ] || BREW_BIN="/usr/local/bin"
grep -q "$BREW_BIN" "$HOME/.zshrc" 2>/dev/null || echo "export PATH=\"$BREW_BIN:\$PATH\"" >> "$HOME/.zshrc"
export PATH="$BREW_BIN:$PATH"

# 4) 安装验证
echo "验证安装："
{verify}
```

## 脚本运行说明

需要联网下载，首次运行会提示 Homebrew 安装；不需要 sudo。

## 安装验证

```bash
{verify}
```

预期输出：打印 {name} 的版本号。

## 执行后建议

- 执行 `source ~/.zshrc` 或重开终端。
- 用 `brew services list` 查看是否需要启动后台服务。

## 常见问题

**curl 报证书错误**：系统时间不准会导致证书校验失败，校准时间后重试。
**brew 下载慢**：换用国内镜像 `export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles`。
"""

OFFICIAL_PLAN = r"""## 官方下载链接

[{name} 官方下载页]({homepage})

## 安装步骤

1. 打开上面的官方下载页，选择 **{platform_label}** 版本。
2. 下载安装包 `{version}`，双击运行，一路下一步完成安装。
3. 首次启动时按提示登录或跳过登录。
4. 在设置里打开「命令行工具」选项（如果下载页提供了 `code` 命令）。

## 安装验证

```{lang}
{verify}
```

预期输出：打印 {name} 的版本号。

## 执行后建议

- 把 {name} 添加到系统 PATH，方便在终端直接启动。
- 安装官方推荐的插件/扩展包。

## 常见问题

**安装程序报「已损坏」**：macOS 在「系统设置 → 隐私与安全性」里点「仍要打开」。
**下载很慢**：官方通常提供国内镜像，切换后再下载。
"""

WINGET_IDS = {
    "mysql": "Oracle.MySQL",
    "nodejs": "OpenJS.NodeJS.LTS",
    "python": "Python.Python.3.12",
    "java": "EclipseAdoptium.Temurin.21.JDK",
    "git": "Git.Git",
    "maven": "Apache.Maven",
    "redis": "Redis.Redis",
    "docker": "Docker.DockerDesktop",
    "nginx": "nginx.nginx",
    "go": "GoLang.Go",
    "rust": "Rustlang.Rustup",
    "mongodb": "MongoDB.Server",
    "postgresql": "PostgreSQL.PostgreSQL.16",
    "vscode": "Microsoft.VisualStudioCode",
    "idea": "JetBrains.IntelliJIDEA.Community",
}
BREW_PKGS = {
    "mysql": "mysql", "nodejs": "node", "python": "python@3.12", "java": "temurin@21",
    "git": "git", "maven": "maven", "redis": "redis", "docker": "docker", "nginx": "nginx",
    "go": "go", "rust": "rustup", "mongodb": "mongodb-community",
    "postgresql": "postgresql@16", "vscode": "visual-studio-code", "idea": "intellij-idea-ce",
}
VERIFY = {
    "mysql": "mysql --version", "nodejs": "node -v", "python": "python --version",
    "java": "java -version", "git": "git --version", "maven": "mvn -v",
    "redis": "redis-cli --version", "docker": "docker --version", "nginx": "nginx -v",
    "go": "go version", "rust": "rustc --version", "mongodb": "mongod --version",
    "postgresql": "psql --version", "vscode": "code --version", "idea": "idea --version",
}
CMDS = {"mysql": "mysql", "nodejs": "node", "python": "python", "java": "java", "git": "git",
        "maven": "mvn", "redis": "redis-cli", "docker": "docker", "nginx": "nginx", "go": "go",
        "rust": "rustc", "mongodb": "mongod", "postgresql": "psql", "vscode": "code", "idea": "idea"}


def key_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("(jdk)", "").replace(".js", "js"))


@app.post("/v1/chat/completions")
def chat(body: ChatIn):
    system, user = _system_text(body.messages), _user_text(body.messages)

    if "软件名称识别器" in system:
        raw = re.sub(r"^用户输入：", "", user).strip()
        m = re.search(r"(mysql|node\.?js|python|java|jdk|git|maven|redis|docker|nginx|go|golang|rust|mongodb|postgres(?:ql)?|vs ?code|idea|homebrew|nvm|pnpm|yarn|conda)", raw, re.I)
        hit = (m.group(1).lower() if m else raw.lower())
        table = {
            "mysql": ("mysql", "MySQL", "database", "github", "mysql/mysql-server"),
            "node.js": ("nodejs", "Node.js", "runtime", "npm", "node"),
            "nodejs": ("nodejs", "Node.js", "runtime", "npm", "node"),
            "node": ("nodejs", "Node.js", "runtime", "npm", "node"),
            "python": ("python", "Python", "runtime", "python-build-standalone", "astral-sh/python-build-standalone"),
            "java": ("java", "Java (JDK)", "runtime", "maven", "io.temurin:temurin"),
            "jdk": ("java", "Java (JDK)", "runtime", "maven", "io.temurin:temurin"),
            "git": ("git", "Git", "tool", "github", "git-for-windows/git"),
            "maven": ("maven", "Maven", "build", "maven", "org.apache.maven:apache-maven"),
            "redis": ("redis", "Redis", "database", "github", "redis/redis"),
            "docker": ("docker", "Docker", "tool", "github", "docker/compose"),
            "nginx": ("nginx", "Nginx", "server", "github", "nginx/nginx"),
            "go": ("go", "Go", "runtime", "github", "golang/go"),
            "golang": ("go", "Go", "runtime", "github", "golang/go"),
            "rust": ("rust", "Rust", "runtime", "github", "rust-lang/rust"),
            "mongodb": ("mongodb", "MongoDB", "database", "github", "mongodb/mongo"),
            "postgres": ("postgresql", "PostgreSQL", "database", "github", "postgres/postgres"),
            "postgresql": ("postgresql", "PostgreSQL", "database", "github", "postgres/postgres"),
            "vs code": ("vscode", "VS Code", "editor", "github", "microsoft/vscode"),
            "vscode": ("vscode", "VS Code", "editor", "github", "microsoft/vscode"),
            "idea": ("idea", "IntelliJ IDEA", "editor", "maven", "com.jetbrains.intellij.idea:ideaIC"),
            "nvm": ("nvm", "nvm", "tool", "manual", None),
            "pnpm": ("pnpm", "pnpm", "tool", "npm", "pnpm"),
            "yarn": ("yarn", "Yarn", "tool", "npm", "yarn"),
        }
        name, display, cat, src, repo = table.get(hit, (raw, raw, "other", "manual", None))
        out = {"software": name, "display_name": display, "category": cat, "source": src, "repo": repo}
        return JSONResponse({"model": "mock-ai-1", "choices": [{"message": {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}}]})

    if "软件版本信息助手" in system:
        name = _extract(user, "软件") or "Software"
        out = {
            "latest": "1.0.0",
            "versions": ["1.0.0", "0.9.0", "0.8.0"],
            "homepage": f"https://example.com/{name.lower()}/download",
            "install_mode": "official-link" if name.lower() in {"vs code", "intellij idea"} else "script",
        }
        return JSONResponse({"model": "mock-ai-1", "choices": [{"message": {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}}]})

    display = _extract(user, "软件") or "Software"
    version = _extract(user, "版本") or "1.0.0"
    platform = _extract(user, "平台") or "Windows"
    homepage = _extract(user, "官方下载页") or "https://example.com"
    mode_line = _extract(user, "模式") or ""
    key = key_of(display)
    verify = VERIFY.get(key, f"{key} --version")

    if "官方下载链接" in mode_line or "official-link" in mode_line:
        md = OFFICIAL_PLAN.format(
            name=display, homepage=homepage, platform_label=platform, version=version,
            lang="powershell" if platform == "Windows" else "bash", verify=verify)
    elif platform == "Windows":
        md = PLAN_POWERSHELL.format(
            name=display, version=version, winget_id=WINGET_IDS.get(key, "Example.App"),
            verify=verify, cmd=CMDS.get(key, key))
    else:
        md = PLAN_BASH.format(
            name=display, version=version, brew_pkg=BREW_PKGS.get(key, key), verify=verify)

    return JSONResponse({"model": "mock-ai-1", "choices": [{"message": {"role": "assistant", "content": md}}]})


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
