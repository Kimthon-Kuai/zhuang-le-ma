"""强制重新生成某个软件某个平台的方案（绕过缓存），并打印结果。"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8017"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


name = sys.argv[1] if len(sys.argv) > 1 else "vscode"
platform = sys.argv[2] if len(sys.argv) > 2 else "windows"

sw = post("/api/identify", {"text": name})["software"]
version = get(f"/api/software/{sw['id']}/versions?platform={platform}")["versions"][0]["version"]
plan = post("/api/plans", {"software": name, "display_name": sw["display_name"],
                           "version": version, "platform": platform, "force": True})
print(f"{sw['display_name']} {version} {platform}")
print(f"  model       = {plan.get('model')!r}")
print(f"  install_mode= {plan.get('install_mode')}")
print(f"  script_type = {plan.get('script_type')}")
print(f"  script      = {len(plan.get('script') or '')} 字符")
print(f"  markdown    = {len(plan.get('markdown') or '')} 字符")
