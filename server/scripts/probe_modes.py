"""验证 GUI 软件走「官方下载链接」方案，脚本型软件走脚本方案。

用法：.venv\\Scripts\\python.exe scripts\\probe_modes.py
"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8017"


def post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


CASES = [
    ("vscode", "1.146.0", "windows", "official-link"),
    ("idea", "2026.2", "windows", "official-link"),
    ("git", "2.56.1", "windows", "script"),
    ("mysql", "9.7.4", "macos", "script"),
    ("python", "3.14.8", "linux", "script"),
]

bad = 0
for sw, ver, plat, want in CASES:
    st, plan = post("/api/plans", {"software": sw, "version": ver, "platform": plat, "force": True})
    mode = plan.get("install_mode")
    script = (plan.get("script") or "").strip()
    ok = st == 200 and mode == want and ((want == "script") == bool(script))
    bad += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} {sw:8} {ver:10} {plat:8} -> mode={mode} "
          f"script_type={plan.get('script_type')} script_len={len(script)}")
    if not ok:
        print("   body:", str(plan)[:300])

print("\n结果:", "全部通过 🎉" if not bad else f"{bad} 项失败")
sys.exit(1 if bad else 0)
