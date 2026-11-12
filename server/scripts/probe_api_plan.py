"""以真实用户视角请求一次方案，检查是否是 AI 生成。

用法：python scripts/probe_api_plan.py [软件名] [平台]
"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8017"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path: str, body: dict):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "mysql"
    platform = sys.argv[2] if len(sys.argv) > 2 else "windows"

    health = get("/api/health")
    print(f"服务端 AI: configured={health.get('ai_configured')} model={health.get('model')}")

    sw = post("/api/identify", {"text": name})["software"]
    print(f"识别: {sw['display_name']} (id={sw['id']})")

    versions = get(f"/api/software/{sw['id']}/versions?platform={platform}")["versions"]
    version = versions[0]["version"]
    print(f"版本: {version} ({platform})")

    plan = post("/api/plans", {"software": name, "display_name": sw["display_name"],
                               "version": version, "platform": platform})
    md = plan.get("markdown") or ""
    print(f"\n方案 id  : {plan['id']}")
    print(f"生成模型 : {plan.get('model')!r}  <- 不是 None 才是 AI 生成")
    print(f"方案长度 : {len(md)}")
    print(f"模式     : {plan.get('install_mode')} / {plan.get('script_type')}")
    print(f"脚本长度 : {len(plan.get('script') or '')}")

    if plan.get("model") is None:
        print("\n[结果] 仍然是本地兜底方案 —— AI 没被用上")
        return 1
    print("\n[结果] AI 生成成功 🎉")
    print("\n--- 方案前 15 行 ---")
    print("\n".join(md.splitlines()[:15]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
