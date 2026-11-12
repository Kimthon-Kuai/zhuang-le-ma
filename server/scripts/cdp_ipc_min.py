"""最小 IPC 探测：确认 window.zlm 调用是否卡住，并定位是哪一步。"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets


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
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
                if msg.get("id") == seq:
                    return msg

        await send("Runtime.enable")
        await send("Runtime.runIfWaitingForDebugger")

        for expr, label in [
            ("window.zlm.info()", "info"),
            ("window.zlm.randomId()", "randomId"),
            ("(async()=>{const a=await new Promise(r=>setTimeout(()=>r('timer-ok'),300));return a})()", "timer"),
        ]:
            r = await send("Runtime.evaluate",
                           {"expression": f"Promise.resolve({expr})", "returnByValue": True,
                            "awaitPromise": True})
            print(label, "->", json.dumps(r.get("result", {}).get("result", {}), ensure_ascii=False)[:300])

        # 真实的安装调用，但用最短脚本
        r = await send("Runtime.evaluate", {
            "expression": """(async () => {
                const id = await window.zlm.randomId();
                const t0 = Date.now();
                const res = await window.zlm.install.start({
                    id, platform: 'windows', scriptType: 'powershell',
                    script: "Write-Host 'hello'",
                });
                return JSON.stringify({ res, ms: Date.now() - t0 });
            })()""",
            "returnByValue": True, "awaitPromise": True,
        })
        print("install:start ->", json.dumps(r.get("result", {}).get("result", {}), ensure_ascii=False)[:400])


asyncio.run(main())
