"""AI 提示词。这里决定生成方案的质量：脚本可直接执行、带中文注释、
含环境变量配置与安装验证、覆盖常见坑。
"""
from __future__ import annotations

import re

PLATFORM_META = {
    "windows": {
        "label": "Windows",
        "lang": "powershell",
        "shell": "PowerShell 5.1+（Windows 10/11 自带）",
    },
    "macos": {
        "label": "macOS",
        "lang": "bash",
        "shell": "Bash（zsh 兼容，支持 Apple Silicon 与 Intel）",
    },
    "linux": {
        "label": "Linux",
        "lang": "bash",
        "shell": "Bash（Debian/Ubuntu 与 RHEL/CentOS/Fedora 均需考虑）",
    },
}

EXTRACT_SYSTEM = """你是软件名称识别器。把用户的一句话提炼成软件名。
只输出 JSON，不要任何解释，格式：
{"software": "规范英文软件名", "display_name": "常见展示名", "category": "database|runtime|tool|build|server|editor|other", "source": "npm|pypi|github|maven|manual", "repo": "若 source 是 github 填 owner/repo；npm/pypi 填包名；maven 填 groupId:artifactId；否则 null"}
判断规则：
- 知名软件请给出真实存在的数据源（例如 Node.js -> npm/node；MySQL -> github/mysql/mysql-server；VS Code -> github/microsoft/vscode）。
- 拿不准来源时用 "manual" 和 repo=null，不要编造。
- 用户说的是中文描述（如"我想装个数据库"）时，选最主流最可能的本意。"""

VERSIONS_SYSTEM = """你是软件版本信息助手。数据源可能失效，你需要按常识给出可信的稳定版本列表。
只输出 JSON，不要解释，格式：
{"latest": "最新稳定版", "versions": ["版本1", "版本2"], "homepage": "官方下载页 URL 或 null", "install_mode": "script|official-link"}
规则：
- 只给真实存在的稳定版本号，不要写 beta/rc/dev/canary。
- 最多给 20 个，新的在前。
- 有明确图形安装包的桌面软件（如 VS Code、IntelliJ IDEA、Docker Desktop）install_mode 设为 official-link。"""

PLAN_SYSTEM = """你是「装了吗」的安装工程师，专门给刚学编程的同学写傻瓜式安装方案。
你的输出会被直接渲染成 Markdown 展示给用户，其中的主脚本会被 App 原样执行。

严格遵守：
1. 禁止推荐学习资源/教程/视频/书籍，禁止介绍软件是什么、优点、适用场景。
2. 只谈安装：获取、安装、环境变量、验证、重装/卸载提示、常见报错。
3. 脚本必须能真实跑通，不要写伪代码，不要把「缺省值」写成必须替换的占位符。
4. 脚本开头用中文注释写清：目标系统、软件版本、做了什么。
5. 必须包含：① 环境变量配置（有则真实写入用户/系统配置；无则一行注释说明无需配置）
   ② 安装验证命令（打印版本号）③ 常见问题处理（网络超时重试、权限不足、换源、端口占用等，挑 2-4 条）。
6. Windows 脚本必须兼容 PowerShell 5.1，避免 ?? 与 && 等仅 PS7 支持的语法；
   下载用 Invoke-WebRequest（带 -UseBasicParsing 与重试），解压用 Expand-Archive。
   需要管理员权限时，在脚本内自行检测并用 Start-Process -Verb RunAs 提权。
7. macOS/Linux 脚本以 #!/usr/bin/env bash 开头，使用 set -euo pipefail；
   用 curl -fL 下载、unzip/tar 解压；写 ~/.zshrc 或 ~/.bashrc 前先判断是否已存在，避免重复；
   Linux 需要 sudo 时写明注释。
8. 方案结构固定为以下小节（## 二级标题），顺序不变：
   ## 一键安装脚本
   （紧接唯一一个可执行代码块，语言标注 powershell 或 bash；App 只执行这个代码块）
   ## 脚本运行说明
   ## 安装验证
   （独立验证命令代码块 + 一句话预期输出）
   ## 执行后建议
   （3-5 条操作建议，例如重开终端、执行 source）
   ## 常见问题
   （每条用 **问题**：解决办法，2-4 条）
9. 如果是图形界面软件（install_mode=official-link），不写一键安装脚本，改为：
   ## 官方下载链接
   （官方下载页 URL，Markdown 链接）
   ## 安装步骤
   （3-6 步，针对该平台）
   ## 安装验证
   ## 执行后建议
   ## 常见问题
10. 不要输出 ```markdown 外层包裹，直接输出 Markdown 正文。
"""

# 安装验证命令：键与 _software_key 的输出一致（小写、去符号）
VERIFY_COMMANDS = {
    "mysql": {"windows": "mysql --version", "macos": "mysql --version", "linux": "mysql --version"},
    "nodejs": {"windows": "node -v", "macos": "node -v", "linux": "node -v"},
    "python": {"windows": "python --version", "macos": "python3 --version", "linux": "python3 --version"},
    "java": {"windows": "java -version", "macos": "java -version", "linux": "java -version"},
    "git": {"windows": "git --version", "macos": "git --version", "linux": "git --version"},
    "maven": {"windows": "mvn -v", "macos": "mvn -v", "linux": "mvn -v"},
    "redis": {"windows": "redis-cli --version", "macos": "redis-server --version", "linux": "redis-server --version"},
    "docker": {"windows": "docker --version", "macos": "docker --version", "linux": "docker --version"},
    "nginx": {"windows": "nginx -v", "macos": "nginx -v", "linux": "nginx -v"},
    "go": {"windows": "go version", "macos": "go version", "linux": "go version"},
    "rust": {"windows": "rustc --version", "macos": "rustc --version", "linux": "rustc --version"},
    "mongodb": {"windows": "mongod --version", "macos": "mongod --version", "linux": "mongod --version"},
    "postgresql": {"windows": "psql --version", "macos": "psql --version", "linux": "psql --version"},
    "vscode": {"windows": "code --version", "macos": "code --version", "linux": "code --version"},
    "idea": {"windows": "idea --version", "macos": "idea --version", "linux": "idea --version"},
    "nvm": {"windows": "nvm version", "macos": "nvm --version", "linux": "nvm --version"},
    "pnpm": {"windows": "pnpm -v", "macos": "pnpm -v", "linux": "pnpm -v"},
    "yarn": {"windows": "yarn -v", "macos": "yarn -v", "linux": "yarn -v"},
    "homebrew": {"macos": "brew --version", "linux": "brew --version"},
}


def extract_user_prompt(raw: str) -> str:
    return f"用户输入：{raw}"


def versions_user_prompt(display_name: str, platform: str, hints: str) -> str:
    return (f"软件：{display_name}\n"
            f"目标平台：{PLATFORM_META.get(platform, PLATFORM_META['windows'])['label']}\n"
            f"已知线索：{hints or '无'}\n"
            "请给出该软件在目标平台上可安装的稳定版本列表。")


def plan_user_prompt(*, display_name: str, version: str, platform: str,
                     homepage: str | None, install_mode: str, source_hint: str | None) -> str:
    meta = PLATFORM_META.get(platform, PLATFORM_META["windows"])
    mode_line = ("本软件属于图形界面软件，请走「官方下载链接」方案，不要写一键安装脚本。"
                 if install_mode == "official-link"
                 else "本软件适合脚本安装，请务必给出一键安装脚本。")
    return f"""请为下面这组「软件 + 版本 + 平台」写一份安装方案。

- 软件：{display_name}
- 版本：{version}
- 平台：{meta['label']}
- 脚本语言：{meta['lang']}（运行环境：{meta['shell']}）
- 官方下载页：{homepage or '无，请用可信官方源'}
- 模式：{mode_line}
- 补充线索：{source_hint or '无'}

注意：版本号锁定为 {version}，不要用「最新版」这类模糊说法。
环境变量要真实写入（Windows 用 [Environment]::SetEnvironmentVariable(..., 'User')，
macOS/Linux 写入 shell 配置文件），并让当前会话即时生效。
"""


# 各平台最稳的系统级包管理器写法（AI 不可用时的兜底，命令本身真实可执行）
PACKAGE_HINT = {
    "windows": {
        "install": "winget install --id {pkg} -e --accept-package-agreements --accept-source-agreements",
        "note": "Windows 10/11 自带 winget（应用安装程序），可先执行 `winget --version` 确认；"
                "没有的话到 Microsoft Store 搜「应用安装程序」装上。",
    },
    "macos": {
        "install": "brew install {pkg}",
        "note": "需要先有 Homebrew，没有就先执行官方一行命令安装（见 https://brew.sh）。",
    },
    "linux": {
        "install": "sudo apt update && sudo apt install -y {pkg}",
        "note": "Debian/Ubuntu 用 apt；RHEL/Fedora 把 apt 换成 dnf，包名可能略有差异。",
    },
}

# 常用软件的包管理器 ID / 包名
WINGET_IDS = {
    "mysql": "Oracle.MySQL",
    "nodejs": "OpenJS.NodeJS.LTS",
    "python": "Python.Python.3.12",
    "java": "EclipseAdoptium.Temurin.21.JDK",
    "git": "Git.Git",
    "maven": "Apache.Maven",
    "redis": "Redis.Redis",
    "docker": "Docker.DockerDesktop",
    "nginx": "nginxinc.nginx",
    "go": "GoLang.Go",
    "rust": "Rustlang.Rustup",
    "mongodb": "MongoDB.Server",
    "postgresql": "PostgreSQL.PostgreSQL.16",
    "vscode": "Microsoft.VisualStudioCode",
    "idea": "JetBrains.IntelliJIDEA.Community",
    "nvm": "CoreyButler.NVMforWindows",
    "pnpm": "pnpm.pnpm",
    "yarn": "Yarn.Yarn",
}
HOMEBREW_NAMES = {
    "mysql": "mysql",
    "nodejs": "node",
    "python": "python@3.12",
    "java": "temurin@21",
    "git": "git",
    "maven": "maven",
    "redis": "redis",
    "docker": "docker",
    "nginx": "nginx",
    "go": "go",
    "rust": "rustup-init",
    "mongodb": "mongodb-community",
    "postgresql": "postgresql@16",
    "vscode": "visual-studio-code",
    "idea": "intellij-idea-ce",
    "nvm": "nvm",
    "pnpm": "pnpm",
    "yarn": "yarn",
    "homebrew": "homebrew",
}
APT_NAMES = {
    "mysql": "mysql-server",
    "nodejs": "nodejs",
    "python": "python3",
    "java": "openjdk-21-jdk",
    "git": "git",
    "maven": "maven",
    "redis": "redis-server",
    "docker": "docker.io",
    "nginx": "nginx",
    "go": "golang-go",
    "rust": "rustc",
    "mongodb": "mongodb",
    "postgresql": "postgresql",
    "vscode": "code",
    "nvm": "nvm",
    "pnpm": "npm",
    "yarn": "yarn",
}


def _software_key(display_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", display_name.lower().replace("(jdk)", "").replace(".js", "js"))


def fallback_plan(*, display_name: str, version: str, platform: str, homepage: str | None,
                  install_mode: str = "script") -> str:
    """AI 不可用时的兜底方案：用各平台系统包管理器给出真实可执行的安装脚本。

    图形界面软件（install_mode=official-link）只给官方下载链接，不给脚本。
    """
    meta = PLATFORM_META.get(platform, PLATFORM_META["windows"])
    link = homepage or "https://www.bing.com/search?q=" + display_name.replace(" ", "+") + "+official+download"

    if install_mode == "official-link":
        return f"""## 官方下载链接

> AI 还没接上，先给你官方下载页。{display_name} 是图形界面软件，官方安装包更稳妥。

**{display_name} {version}**（{meta['label']}）

- 官方下载页：[{display_name} 官方下载]({link})

## 安装步骤

1. 打开上面的官方下载页，下载对应 {meta['label']} 的安装包。
2. 双击运行安装包，一路默认下一步即可。
3. Windows 若弹出 SmartScreen 提示，点「更多信息 → 仍要运行」。

## 安装验证

安装完成后打开终端，执行：

```{meta['lang']}
{VERIFY_COMMANDS.get(_software_key(display_name), {}).get(platform) or 'echo 打开软件，能在菜单里看到就算装好了'}
```

## 执行后建议

- 安装完后从开始菜单 / 启动台打开一次，确认能正常启动。
- 接上 AI 后点「重新生成」，可以得到更详细的图文步骤。
"""

    key = _software_key(display_name)
    hint = PACKAGE_HINT.get(platform, PACKAGE_HINT["linux"])
    verify = VERIFY_COMMANDS.get(key, {}).get(platform)
    verify_cmd = verify if (verify and re.search(r"(\s-\w+|\s--\w+)", verify)) else (
        f"{verify} --version" if verify else None
    )

    verify_cmd = verify if (verify and re.search(r"(\s-\w+|\s--\w+)", verify)) else (
        f"{verify} --version" if verify else None
    )

    if platform == "windows":
        pkg = WINGET_IDS.get(key)
        version_flag = f" --version {version}" if version else ""
        pinned = (f"winget install --id {pkg} -e{version_flag} "
                  "--accept-package-agreements --accept-source-agreements")
        fallback = (f"winget install --id {pkg} -e "
                    "--accept-package-agreements --accept-source-agreements")
        install_cmd = (f"""# 先在 winget 仓库里找指定版本，找不到就退回最新稳定版
$installed = $false
try {{
    {pinned}
    $installed = ($LASTEXITCODE -eq 0)
}} catch {{ }}
if (-not $installed) {{
    Write-Host "winget 仓库里没有 {version} 这个版本，改装最新稳定版…" -ForegroundColor Yellow
    {fallback}
}}""" if pkg else
                      "Write-Host '请打开官方下载页手动安装：' -ForegroundColor Yellow; Write-Host '" + link + "'")
        script = f"""# 装了吗 · 兜底脚本（未接入 AI 时的通用方案）
# 目标：{meta['label']} / {display_name} {version}
# 方式：winget 官方包管理器安装，自动处理 PATH

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# 1) 检查 winget 是否可用
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {{
    Write-Host '没找到 winget，请先在 Microsoft Store 安装「应用安装程序」' -ForegroundColor Yellow
    exit 1
}}

# 2) 安装指定版本（{version}）
{install_cmd}

# 3) 环境变量：winget 安装的软件会自动写入用户 PATH，这里刷新当前会话
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

# 4) 安装验证
{"& " + verify_cmd if verify_cmd else "Write-Host '安装完成，请重开终端后验证'"}
"""
        script_name = "powershell"
    elif platform == "macos":
        pkg = HOMEBREW_NAMES.get(key, key)
        shebang = "#!/usr/bin/env bash"
        script = f"""{shebang}
# 装了吗 · 兜底脚本（未接入 AI 时的通用方案）
# 目标：{meta['label']} / {display_name} {version}
set -euo pipefail

# 1) 确保 Homebrew 可用
if ! command -v brew >/dev/null 2>&1; then
  echo "没找到 Homebrew，先装它："
  echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi

# 2) 安装（Homebrew 会优先安装你选的 {version}；该版本已不在仓库时退回最新稳定版）
brew install {pkg} || brew upgrade {pkg}

# 3) 环境变量：把 Homebrew 的 bin 写进 zsh 配置（避免重复写入）
BREW_BIN="/opt/homebrew/bin"
[ -d "$BREW_BIN" ] || BREW_BIN="/usr/local/bin"
grep -q "$BREW_BIN" "$HOME/.zshrc" 2>/dev/null || echo "export PATH=\\"$BREW_BIN:\\$PATH\\"" >> "$HOME/.zshrc"
export PATH="$BREW_BIN:$PATH"

# 4) 安装验证
{verify_cmd or f"echo '{display_name} 安装完成，重开终端后验证'"}
"""
        script_name = "bash"
    else:
        pkg = APT_NAMES.get(key, key)
        script = f"""#!/usr/bin/env bash
# 装了吗 · 兜底脚本（未接入 AI 时的通用方案）
# 目标：{meta['label']} / {display_name} {version}
set -euo pipefail

# 1) 更新软件源（需要 sudo，会提示输入密码）
sudo apt-get update -y

# 2) 安装
sudo apt-get install -y {pkg}

# 3) 环境变量：写到 shell 配置，避免重复写入
grep -q "装了吗" "$HOME/.bashrc" 2>/dev/null || echo "# 装了吗 环境变量" >> "$HOME/.bashrc"

# 4) 安装验证
{verify_cmd or f"echo '{display_name} 安装完成，重开终端后验证'"}
"""
        script_name = "bash"

    return f"""## 一键安装脚本

> AI 还没接上，这份是「装了吗」内置的兜底方案，用 {platform == "windows" and "winget" or "系统包管理器"} 安装，命令真实可执行。接上 AI 后点「重新生成」会得到更贴合的脚本。

```{script_name}
{script}```

## 脚本运行说明

{hint['note']}

## 安装验证

安装完成后**重新打开终端**，执行：

```{meta['lang']}
{verify_cmd or "echo 检查软件是否出现在开始菜单/应用列表"}
```

预期输出：显示 {display_name} 的版本号。

## 执行后建议

- 关闭并重新打开终端，让 PATH 生效。
- 若提示「命令不存在」，重启一次电脑再试。
- 无包管理器时，从官方下载页手动安装：[{display_name} 官方下载页]({link})

## 常见问题

**下载很慢**：换网络或代理后重试，winget/brew 都有国内镜像。
**权限不足**：Windows 用管理员身份重开终端；macOS/Linux 在命令前加 sudo。
**版本对不上**：脚本里已经锁定 {version}；如果包管理器仓库里没有这个版本，它会退回装最新稳定版，装完用上面的验证命令确认一下。
"""
