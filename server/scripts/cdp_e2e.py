"""鐢?Chrome DevTools Protocol 椹卞姩 Electron 娓叉煋杩涚▼锛屽仛鐪熷疄鐜鐨勭鍒扮妫€鏌ャ€?

鍏堜互 --remote-debugging-port=9333 鍚姩 Electron锛岀劧鍚庯細
    .venv\\Scripts\\python.exe scripts\\cdp_e2e.py
"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets

CDP = "http://127.0.0.1:9333"


async def main() -> None:
    targets = httpx.get(f"{CDP}/json/list", timeout=10).json()
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        print("娌℃湁鎵惧埌椤甸潰:", targets)
        return
    ws_url = pages[0]["webSocketDebuggerUrl"]
    print("target:", pages[0].get("title"), pages[0].get("url"), flush=True)

    async with websockets.connect(ws_url, max_size=32 * 1024 * 1024) as ws:
        print("ws connected", flush=True)
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
        # Electron 鍦?--remote-debugging-port 涓嬩細鏆傚仠绛夊緟璋冭瘯鍣紝蹇呴』鏄惧紡鏀捐
        await send("Runtime.runIfWaitingForDebugger")
# 缁欓〉闈竴鐐规椂闂村畬鎴愰甯?
        await asyncio.sleep(1.5)
        print("runtime enabled", flush=True)

        # 1) preload 妗ユ帴鏄惁娉ㄥ叆
        info, _ = await js("JSON.stringify({ zlm: typeof window.zlm, "
                           "keys: window.zlm ? Object.keys(window.zlm) : [], "
                           "platform: window.zlm ? window.zlm.info ? 'has-info' : 'no-info' : 'none' })")
        print("bridge:", info)

        # 2) 鍦ㄧ湡瀹?Electron 閲岃蛋涓€閬嶏細杈撳叆妗嗚緭鍏?-> 鎼滅储
        await js("""(() => {
            const input = document.querySelector('input[aria-label="杈撳叆鎯冲畨瑁呯殑杞欢"]');
            if (!input) return 'no-input';
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(input, '鎴戞兂瑁?MySQL');
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.closest('form').requestSubmit();
            return 'submitted';
        })()""")
        await asyncio.sleep(6)

        state, _ = await js("""(() => {
            const h = [...document.querySelectorAll('h2')].map(e => e.textContent.trim());
            const btns = [...document.querySelectorAll('button')].map(b => b.textContent.trim()).filter(Boolean);
            return JSON.stringify({ headings: h, hasGenerate: btns.some(b => b.includes('鐢熸垚瀹夎鏂规')),
                                    hasInstall: btns.some(b => b.includes('涓€閿畨瑁?)) });
        })()""")
        print("after search:", state)

        # 3) 鐢熸垚鏂规
        clicked, _ = await js("""(() => {
            const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('鐢熸垚瀹夎鏂规'));
            if (!b) return 'no-generate';
            b.click();
            return 'clicked';
        })()""")
        print("generate:", clicked)
        await asyncio.sleep(8)

        plan_state, _ = await js("""(() => {
            const btns = [...document.querySelectorAll('button')].map(b => b.textContent.trim());
            const h2 = [...document.querySelectorAll('h2')].map(e => e.textContent.trim());
            return JSON.stringify({ headings: h2, hasInstallBtn: btns.some(b => b.includes('涓€閿畨瑁?)),
                                    hasCopy: btns.some(b => b.includes('澶嶅埗浠ｇ爜')),
                                    hasValid: btns.some(b => b.startsWith('鏈夋晥')) });
        })()""")
        print("plan:", plan_state)

        # 4) 鐐广€屼竴閿畨瑁呫€嶁€斺€旂湡璺戜細瑁?MySQL锛岃繖閲屽彧楠岃瘉 IPC 閫氳矾锛氱敤绀轰緥鑴氭湰鏇夸唬
        ipc, _ = await js("""(async () => {
            const id = await window.zlm.util.randomId();
            const logs = [];
            const off = window.zlm.install.onLog((d) => logs.push([d.stream, d.text.trim()]));
            const done = new Promise((res) => {
                const offDone = window.zlm.install.onDone((d) => { offDone(); res(d); });
                setTimeout(() => res({ ok: false, timeout: true }), 30000);
            });
            await window.zlm.install.start({
                id,
                platform: 'windows',
                scriptType: 'powershell',
                script: "Write-Host '瑁呬簡鍚?IPC 鑷锛氫腑鏂囪緭鍑烘甯?\\nWrite-Host 'winget '; (Get-Command winget -ErrorAction SilentlyContinue) -ne $null",
            });
            const d = await done;
            off();
            return JSON.stringify({ done: d, logs: logs.slice(0, 12) });
        })()""")
        print("ipc:", ipc)

        # 5) 鎴浘璇佹槑鐣岄潰鐪熺殑娓叉煋鍑烘潵浜?
        shot = await send("Page.captureScreenshot", {"format": "png"})
        data = shot.get("result", {}).get("data")
        if data:
            import base64
            from pathlib import Path
            out = Path(__file__).resolve().parents[1] / "data" / "electron-shot.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(data))
            print("screenshot:", out)


asyncio.run(main())
