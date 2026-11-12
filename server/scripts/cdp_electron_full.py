"""通过 CDP 直连 Electron 主窗口，验证 preload 桥 + 一键安装全流程。

用法：python scripts/cdp_electron_full.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

try:
    from websockets.sync.client import connect
except ImportError:
    print("需要 websockets：pip install websockets")
    raise SystemExit(1)

CDP = "http://127.0.0.1:9333"


def target():
    data = json.loads(urllib.request.urlopen(CDP + "/json", timeout=10).read())
    for t in data:
        if t.get("type") == "page" and "index.html" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    raise SystemExit("未找到 Electron 页面")


class Session:
    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=8 * 1024 * 1024, legacy=True)
        self.seq = 0

    def call(self, method: str, params: dict | None = None, timeout: float = 30):
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(self.ws.recv(timeout=max(0.1, deadline - time.time())))
            if msg.get("id") == mid:
                return msg.get("result")
        raise TimeoutError(method)

    def eval(self, expr: str, await_promise: bool = True, timeout: float = 60):
        r = self.call("Runtime.evaluate", {
            "expression": expr, "awaitPromise": await_promise, "returnByValue": True,
        }, timeout=timeout)
        if "exceptionDetails" in (r or {}):
            return {"__error": r["exceptionDetails"].get("text"),
                    "detail": str(r["exceptionDetails"].get("exception", {}))[:300]}
        return r.get("result", {}).get("value")

    def close(self):
        self.ws.close()


def main() -> int:
    s = Session(target())
    fails = []

    print("== preload 桥 ==")
    bridge = s.eval("({has: typeof window.zlm, keys: window.zlm ? Object.keys(window.zlm) : null, platform: navigator.platform})")
    print("   ", bridge)
    if not (isinstance(bridge, dict) and bridge.get("has") == "object"):
        fails.append("preload bridge missing")

    print("\n== 重置到首页 ==")
    s.eval("location.hash = '#/'; 'ok'", await_promise=False)
    time.sleep(1.5)
    home = s.eval("document.body.innerText.slice(0, 400)")
    print("   ", (home or "")[:200].replace("\n", " | "))

    print("\n== 搜索并生成方案（走真实 API） ==")
    res = s.eval("""
(async () => {
  const input = document.querySelector('input[placeholder*="装"]') || document.querySelector('input');
  if (!input) return {error: 'no input'};
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(input, '我想装 MySQL');
  input.dispatchEvent(new Event('input', {bubbles: true}));
  const form = input.closest('form');
  if (form) form.requestSubmit();
  else input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
  await new Promise(r => setTimeout(r, 6000));
  return {text: document.body.innerText.slice(0, 500)};
})()
""", timeout=90)
    print("   ", str(res).replace("\n", " | ")[:400])

    print("\n== 生成方案 ==")
    gen = s.eval("""
(async () => {
  const btn = [...document.querySelectorAll('button')].find(b => b.textContent.includes('生成安装方案'));
  if (!btn) return {error: 'generate button not found'};
  btn.click();
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 1000));
    if ([...document.querySelectorAll('button')].some(b => b.textContent.includes('一键安装'))) {
      return {ok: true, waited: i + 1};
    }
  }
  return {error: 'no install button after 60s', text: document.body.innerText.slice(-600)};
})()
""", timeout=120)
    print("   ", json.dumps(gen, ensure_ascii=False)[:600])
    if isinstance(gen, dict) and gen.get("error"):
        fails.append("plan generation")

    print("\n== 一键安装：触发真实 IPC ==")
    run = s.eval("""
(async () => {
  const btns = [...document.querySelectorAll('button')];
  const install = btns.find(b => b.textContent.includes('一键安装'));
  if (!install) return {error: 'install button not found', buttons: btns.map(b => b.textContent.slice(0,15)).slice(0,20)};
  install.click();
  const seen = [];
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const log = document.querySelector('[role=region]')?.innerText || '';
    seen.push(log.length);
    const text = document.body.innerText;
    if (/安装成功|执行完成|完成|失败|退出码/.test(text) && i > 3) break;
  }
  const region = document.querySelector('[role=region]')?.innerText || '';
  return {logLen: region.length, tail: region.slice(-1200), growth: seen.slice(0, 12)};
})()
""", timeout=180)
    print("   ", json.dumps(run, ensure_ascii=False, indent=2)[:2500] if isinstance(run, dict) else str(run)[:1500])

    s.close()
    print("\n结果:", "通过 🎉" if not fails else f"失败: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
