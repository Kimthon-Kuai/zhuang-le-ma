# 装了吗 · zhuang-le-ma

> 今天你装了吗？
> 用一句大白话说出你想装什么（"帮我搞 Node"、"我想装 MySQL"），它帮你选版本、生成安装方案，一键装好开发环境。

## 这是什么

给不熟悉命令行的同学用的开发环境安装助手。你说人话，它干活：

1. **说人话** —— 输入"我想装 MySQL"，自动识别成 MySQL
2. **挑版本** —— 从 npm / PyPI / GitHub / Maven Central / winget 等真实数据源拉版本列表，最新稳定版默认选中
3. **出方案** —— AI 生成带中文注释的分步安装方案，每个代码块可单独复制
4. **一键装** —— 内置安装控制台，脚本输出实时滚动；需要管理员权限时弹 UAC / sudo 提权
5. **能反馈** —— 方案好不好用，一键反馈给后台

## 目录结构

```
zhuang-le-ma/
├── server/   FastAPI + SQLite 服务端（识别 / 版本 / 方案 / 反馈 / 统计 + 管理后台 API）
├── admin/    React 管理后台（方案管理 / 反馈处理 / 数据统计），构建后挂在服务端 /admin/
└── desktop/  Electron + React 桌面端（vite + electron-builder）
```

## 快速开始

### 1. 服务端

```powershell
cd server
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 复制配置模板并填入你的 AI Key
Copy-Item .env.example .env
# 编辑 .env：填 ANTHROPIC_AUTH_TOKEN（支持 DeepSeek / Anthropic 等 OpenAI 兼容接口）

.venv\Scripts\python.exe -m uvicorn app.main:app --port 8017
```

服务地址 <http://127.0.0.1:8017>，接口文档 `/docs`。

### 2. 管理后台

```powershell
cd admin
npm install
npm run build          # 产物需部署到服务端挂载的 /admin/ 目录
```

浏览器打开 <http://127.0.0.1:8017/admin/>，用 `.env` 里的 `ADMIN_PASSWORD` 登录。

### 3. 桌面端

```powershell
cd desktop
npm install
npm run electron:dev       # 开发模式
npm run dist               # 打包安装包（electron-builder）
```

> 桌面端目前连接 `127.0.0.1:8017`，即需要在本机同时跑服务端。

## 配置项（server/.env）

| 键 | 说明 |
|---|---|
| `ANTHROPIC_AUTH_TOKEN` | AI 接口的 Key，**切勿提交** |
| `ANTHROPIC_BASE_URL` | AI 接口地址，如 `https://api.deepseek.com` |
| `AI_MODEL` | 模型名，如 `deepseek-chat` |
| `AI_ENABLED` | 关闭 AI 后走本地兜底稿 |
| `AI_MAX_TOKENS` | 单次输出上限 |
| `ADMIN_PASSWORD` / `ADMIN_SECRET` | 后台登录密码与 token 签名密钥，**上线前务必改掉** |
| `HOST` / `PORT` | 服务监听地址，默认 `127.0.0.1:8017` |

## 支持的版本数据源

npm · PyPI · GitHub Releases/Tags · Maven Central · Node.js · Nginx · Adoptium(JDK) · winget（Windows 实时版本）

## 自检脚本

```powershell
cd server
.venv\Scripts\python.exe scripts\e2e_smoke.py       # 接口全链路
.venv\Scripts\python.exe scripts\admin_smoke.py     # 管理后台
.venv\Scripts\python.exe scripts\check_ai.py        # AI 连通性
```

## 安全说明

- `.env`、数据库、日志、构建产物均已在 `.gitignore` 中排除
- 仓库里只保留 `.env.example` 模板，不含任何真实密钥
- 如果你在别处复用过本项目的 Key，请去平台后台重新生成

## 许可

MIT
<!-- verify commit test -->
