"""CDP 诊断：逐步打印每一步，定位卡在哪里。"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets


async def main() -> None:
    pages = [t for t in httpx.get("http://127.0.0.1:9333/json/list", timeout=10).json()
             if t.get("type") == "page"]
    print("page:", pages[0]["url"], flush=True)
    async with websockets.connect(pages[0]["webSocketDebuggerUrl"],
                                  max_size=32 * 1024 * 1024, open_timeout=10) as ws:
        print("connected", flush=True)
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable", "params": {}}))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.runIfWaitingForDebugger", "params": {}}))
        for _ in range(6):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                print("recv timeout", flush=True)
                continue
            if msg.get("id"):
                print("resp:", msg.get("id"), json.dumps(msg.get("result", msg.get("error")))[:200], flush=True)
        print("sending evaluate", flush=True)
        await ws.send(json.dumps({"id": 99, "method": "Runtime.evaluate",
                                  "params": {"expression": "1+1", "returnByValue": True}}))
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                if msg.get("id") == 99:
                    print("evaluate result:", msg, flush=True)
                    break
        except asyncio.TimeoutError:
            print("evaluate TIMEOUT", flush=True)


asyncio.run(main())
