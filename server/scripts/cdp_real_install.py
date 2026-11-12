"""真实安装测试（轮询版）：用服务端生成的真实方案，通过 Electron IPC 在本机执行安装。

默认安装 git（幂等、低风险）。脚本里的输出逐条打印。
用法：.venv\\Scripts\\python.exe scripts\\cdp_real_install.py [software] [version]
"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8017"
CDP_PORT = 9333
software = sys.argv[1] if len(sys.argv) > 1 else "git"
version = sys.argv[2] if len(sys.argv) > 2 else "2.56.1"

plan = httpx.post(f"{BASE}/api/plans",
                  json={"software": software, "version": version, "platform": "windows",
                        "force": True},
                  timeout=120).json()
script = plan.get("script") or ""
print("plan mode:", plan.get("install_mode"), "script len:", len(script))
assert plan.get("install_mode") == "script" and script, "该软件没有可执行脚本"
print("---- 脚本前 6 行 ----")
print("\n".join(script.splitlines()[:6]))


async def main() -> None:
    pages = [t for t in httpx.get(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=10).json()
             if t.get("type") == "page"]
    async with websockets.connect(pages[0]["webSocketDebuggerUrl"], max_size=2 ** 25) as ws:
        seq = 0

        async def send(method: str, params: dict | None = None):
            nonlocal seq
            seq += 1
            await ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
                if msg.get("id") == seq:
                    return msg

        async def js(expr: str):
            r = await send("Runtime.evaluate",
                           {"expression": expr, "returnByValue": True, "awaitPromise": True})
            return (r.get("result", {}).get("result", {}) or {}).get("value")

        await send("Runtime.enable")
        await send("Runtime.runIfWaitingForDebugger")

        # 把日志/完成事件收集到全局对象，避免长表达式阻塞
        await js("""(() => {
            window.__t = { id: null, logs: [], done: null };
            if (!window.__t.hooked) {
              window.zlm.install.onLog((d) => {
                if (window.__t && d.id === window.__t.id) window.__t.logs.push([d.stream, d.text]);
              });
              window.zlm.install.onDone((d) => {
                if (window.__t && d.id === window.__t.id) window.__t.done = d;
              });
              window.__t.hooked = true;
            }
            return 'hooked';
        })()""")

        started = await js(f"""(async () => {{
            const id = await window.zlm.randomId();
            window.__t = {{ id, logs: [], done: null, hooked: true }};
            await window.zlm.install.start({{ id, platform: 'windows', scriptType: 'powershell',
                                              script: {json.dumps(script)} }});
            return id;
        }})()""")
        print("started:", started)

        printed = 0
        for _ in range(200):  # 最多 200 秒
            await asyncio.sleep(1)
            snap = json.loads(await js("JSON.stringify({ logs: window.__t.logs.map(x => x[0] + '|' + x[1]), done: window.__t.done })"))
            for line in snap["logs"][printed:]:
                print(f"   {line[:220]}")
            printed = len(snap["logs"])
            if snap["done"]:
                print("\ndone:", snap["done"])
                return
        print("\n超时：脚本 200 秒内没有结束")


asyncio.run(main())
