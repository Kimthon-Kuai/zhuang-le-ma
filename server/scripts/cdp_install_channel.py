"""通过 CDP 验证 Electron 的 install:start 通道（非提权）+ 日志流。

用一个不触碰系统的脚本（只打印 + 退出码 0），确保不触发 UAC。
用法：python scripts/cdp_install_channel.py
"""
from __future__ import annotations

import json
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
        self.ws = connect(url, max_size=8 * 1024 * 1024, legacy=True)
        self.n = 0

    def eval(self, expr: str, timeout: float = 90):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                 "params": {"expression": expr, "awaitPromise": True,
                                            "returnByValue": True}}))
        import time
        end = time.time() + timeout
        while time.time() < end:
            m = json.loads(self.ws.recv(timeout=max(0.1, end - time.time())))
            if m.get("id") == mid:
                r = m.get("result", {})
                if "exceptionDetails" in r:
                    return {"__error": r["exceptionDetails"].get("text")}
                return r.get("result", {}).get("value")
        raise TimeoutError(expr[:40])


def main() -> int:
    s = S(ws_url())

    # 监听渲染进程里的日志事件
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "Write-Host '[1/3] 打印中文测试：装了吗'",
        "Write-Output '[2/3] stdout 输出'",
        "Write-Host '[3/3] 完成'",
        "Write-Host 'OK 验证通过'",
    ])

    res = s.eval(f"""
(async () => {{
  const zlm = window.zlm;
  if (!zlm) return {{error: 'no bridge'}};
  const logs = [];
  let done = null;
  const offLog = zlm.install.onLog((d) => logs.push(d));
  const offDone = zlm.install.onDone((d) => {{ done = d; }});
  const id = 'verify-' + Date.now();
  await zlm.install.start({{ id, script: {json.dumps(script)}, platform: 'windows', scriptType: 'powershell' }});
  for (let i = 0; i < 60 && !done; i++) await new Promise(r => setTimeout(r, 500));
  offLog(); offDone();
  return {{ count: logs.length, logs: logs.map(l => l.stream + ': ' + l.text).join('\\n'), done }};
}})()
""")
    print(json.dumps(res, ensure_ascii=False, indent=2) if isinstance(res, dict) else res)
    ok = isinstance(res, dict) and res.get("done") and res["done"].get("code") == 0
    s.ws.close()
    print("\n结果:", "install:start 通道正常 🎉" if ok else "需检查")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
