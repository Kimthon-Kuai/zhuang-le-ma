"""鍗曠嫭楠岃瘉 Electron 鐨勫畨瑁呮墽琛岄摼璺細renderer -> preload -> main -> PowerShell -> 鏃ュ織娴併€?

鐢ㄤ竴娈垫棤瀹宠剼鏈紙鍙墦鍗颁腑鏂?+ 妫€鏌?winget锛夛紝涓嶄細鐪熺殑瀹夎浠讳綍杞欢銆?
"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets


async def main() -> None:
    pages = [t for t in httpx.get("http://127.0.0.1:9333/json/list", timeout=10).json()
             if t.get("type") == "page"]
    ws_url = pages[0]["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url, max_size=32 * 1024 * 1024) as ws:
        counter = 0

        async def send(method: str, params: dict | None = None):
            nonlocal counter
            counter += 1
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == counter:
                    return msg

        async def js(expr: str):
            r = await send("Runtime.evaluate", {
                "expression": expr, "returnByValue": True, "awaitPromise": True,
            })
            return (r.get("result", {}).get("result", {}) or {}).get("value"), r

        await send("Runtime.enable")
        await send("Runtime.runIfWaitingForDebugger")
        await asyncio.sleep(1)

        # 娉ㄥ唽鐩戝惉 -> 鍚姩鑴氭湰 -> 鏀堕泦鏃ュ織鐩村埌 done锛堟渶澶?40 绉掞級
        result, raw = await js("""(async () => {
            const sleep = (ms) => new Promise(r => setTimeout(r, ms));
            const id = await window.zlm.randomId();
            const logs = [];
            const offLog = window.zlm.install.onLog((d) => { if (d.id === id) logs.push(d.stream + '|' + d.text.trim()); });
            let done = null;
            const offDone = window.zlm.install.onDone((d) => { if (d.id === id) done = d; });
            const begin = await window.zlm.install.start({
                id,
                platform: 'windows',
                scriptType: 'powershell',
                script: "Write-Host '瑁呬簡鍚?IPC 鑷锛氫腑鏂囪緭鍑烘甯?\\nif (Get-Command winget -ErrorAction SilentlyContinue) { Write-Host 'winget 瀛樺湪' } else { Write-Host 'winget 涓嶅瓨鍦? }",
            });
            for (let i = 0; i < 80 && !done; i++) await sleep(500);
            offLog(); offDone();
            return JSON.stringify({ begin, done, logCount: logs.length, logs: logs.slice(0, 20) });
        })()""")
        print("result:", result)
        if not result:
            print("raw:", json.dumps(raw)[:800])


asyncio.run(main())
