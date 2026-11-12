"""装了吗 - 服务端入口。

启动：server/.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8017
或直接：server/.venv/Scripts/python -m app.main
"""
from __future__ import annotations

from pathlib import Path

import mimetypes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Windows 注册表常把 .js 映射成 text/plain，导致浏览器拒绝执行 <script type="module">
# 这里显式声明 MIME，跨平台一致
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

from . import ai
from .config import settings
from .db import init_db
from .routers import admin, public
from .seed import seed_if_empty, sync_preset_sources

app = FastAPI(title="装了吗 API", version="1.0.0", description="今天你装了吗？")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地工具：桌面端与后台都从本地访问
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(admin.router)

ADMIN_DIST = Path(__file__).resolve().parent.parent.parent / "admin" / "dist"


@app.on_event("startup")
def startup() -> None:
    init_db()
    added = seed_if_empty()
    synced = sync_preset_sources()
    print(f"[装了吗] 数据库就绪: {settings.db_path}（新增预置软件 {added} 个，同步版本源 {synced} 个）")
    print(f"[装了吗] AI: {'已配置 ' + settings.ai_model if ai.ai_configured() else '未配置（将回退到本地兜底方案）'}")
    if ADMIN_DIST.exists():
        app.mount("/admin", StaticFiles(directory=ADMIN_DIST, html=True), name="admin")


@app.get("/", include_in_schema=False)
def root():
    if (ADMIN_DIST / "index.html").exists():
        return FileResponse(ADMIN_DIST / "index.html")
    return {"app": "装了吗 API", "slogan": "今天你装了吗？", "docs": "/docs",
            "hint": "管理后台未构建：cd admin && npm run build"}


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
