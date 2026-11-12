"""在真实 Electron 窗口里走一遍用户流程，确认界面显示 AI 已接通。

用法：python scripts/cdp_verify_ai.py [软件名]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

from websockets.sync.client import connect

CDP = "http://127.0.0.1:9333"


def ws_url() -> str:
    data = json.loads(urllib.request.urlopen(CDP + "/json", timeout=10).read())
    for t in data:
        if t.get("type") == "page" and "index.html" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    raise SystemExit("未找到 Electron 页面")


class S:
    def __init__(self, url: str):
        self.ws = connect(url, max_size=16 * 1024 * 1024, legacy=True)
        self.n = 0

    def eval(self, expr: str, timeout: float = 180):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                 "params": {"expression": expr, "awaitPromise": True,
                                            "returnByValue": True}}))
        end = time.time() + timeout
        while time.time() < end:
            m = json.loads(self.ws.recv(timeout=max(0.1, end - time.time())))
            if m.get("id") == mid:
                r = m.get("result", {})
                if "exceptionDetails" in r:
                    return {"__error": r["exceptionDetails"].get("text")}
                return r.get("result", {}).get("value")
        raise TimeoutError(expr[:50])


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "我想装 MySQL"
    s = S(ws_url())
    fails = []

    s.eval("location.hash = '#/'; 'ok'", timeout=10)
    time.sleep(2)

    badge = s.eval("document.body.innerText.match(/AI[^\\n]{0,30}/)?.[0] || '(未找到)'")
    print(f"界面 AI 标识: {badge}")
    if "未配置" in str(badge):
        fails.append("界面仍显示 AI 未配置")

    print(f"\n输入: {name!r}")
    res = s.eval("""
(async () => {
  const input = document.querySelector('input[placeholder*="装"]') || document.querySelector('input');
  if (!input) return {error: 'no input'};
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(input, NAME);
  input.dispatchEvent(new Event('input', {bubbles: true}));
  const form = input.closest('form');
  if (form) form.requestSubmit();
  else input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 500));
    if ([...document.querySelectorAll('button')].some(b => b.textContent.includes('生成安装方案'))) break;
  }
  return {text: document.body.innerText.slice(0, 300)};
})()
""".replace("NAME", json.dumps(name)), timeout=60)
    print(f"  识别结果: {str(res).splitlines()[0][:120] if isinstance(res, dict) else res}")

    print("\n点击「生成安装方案」并等待 AI 返回…")
    gen = s.eval("""
(async () => {
  const btn = [...document.querySelectorAll('button')].find(b => b.textContent.includes('生成安装方案'));
  if (!btn) return {error: 'no generate button'};
  btn.click();
  const t0 = Date.now();
  for (let i = 0; i < 150; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const hasInstall = [...document.querySelectorAll('button')].some(b => b.textContent.includes('一键安装'));
    const hasOfficial = document.body.innerText.includes('官方下载');
    if (hasInstall || hasOfficial) {
      return {ok: true, seconds: Math.round((Date.now()-t0)/1000),
              installButton: hasInstall, official: hasOfficial,
              text: document.body.innerText.slice(0, 700)};
    }
  }
  return {error: 'timeout', text: document.body.innerText.slice(0, 500)};
})()
""", timeout=200)
    print(json.dumps({k: v for k, v in (gen or {}).items() if k != "text"},
                     ensure_ascii=False) if isinstance(gen, dict) else gen)
    if isinstance(gen, dict) and gen.get("error"):
        fails.append("方案未生成")
    elif isinstance(gen, dict):
        preview = (gen.get("text") or "")[:600].replace("\n", " | ")
        print(f"  方案预览: {preview}")

    s.ws.close()
    print("\n结果:", "通过 🎉" if not fails else f"失败: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
