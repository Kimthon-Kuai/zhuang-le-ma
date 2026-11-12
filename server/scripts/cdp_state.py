"""检查 Electron 渲染进程当前状态（是否被弹窗/阻塞卡住）。"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets

PROBE = """JSON.stringify({
  ready: document.readyState,
  visibility: document.visibilityState,
  dialog: !!document.querySelector('[role="dialog"]'),
  dialogText: (document.querySelector('[role="dialog"]') || {}).textContent?.slice(0, 100) || '',
  buttons: [...document.querySelectorAll('button')].map(b => b.textContent.trim()).slice(0, 12),
  text: document.body.innerText.slice(0, 160),
})"""


async def main() -> None:
    pages = [t for t in httpx.get("http://127.0.0.1:9333/json/list", timeout=10).json()
             if t.get("type") == "page"]
    async with websockets.connect(pages[0]["webSocketDebuggerUrl"], max_size=2 ** 25) as ws:
        seq = 0

        async def send(method: str, params: dict | None = None):
            nonlocal seq
            seq += 1
            await ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                if msg.get("id") == seq:
                    return msg

        await send("Runtime.enable")
        await send("Runtime.runIfWaitingForDebugger")
        res = await send("Runtime.evaluate",
                         {"expression": PROBE, "returnByValue": True})
        print(res.get("result", {}).get("result", {}).get("value"))


asyncio.run(main())
