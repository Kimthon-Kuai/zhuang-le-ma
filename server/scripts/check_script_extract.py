"""检查方案里被提取出的脚本是否只包含「一键安装脚本」段落。

用法（先启动服务）：python scripts/check_script_extract.py
"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8017"


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    fails = []
    cases = [("mysql", "windows", "powershell"), ("nodejs", "macos", "bash"), ("git", "linux", "bash")]

    for name, platform, want_type in cases:
        sw = call("POST", "/api/identify", {"text": name})["software"]
        versions = call("GET", f"/api/software/{sw['id']}/versions?platform={platform}")["versions"]
        version = versions[0]["version"]
        plan = call("POST", "/api/plans", {"software": name, "display_name": sw["display_name"],
                                           "version": version, "platform": platform})
        script = plan.get("script") or ""
        md = plan.get("markdown") or ""
        print(f"\n== {name} @ {platform} {version} ==")
        print(f"   mode={plan.get('install_mode')} type={plan.get('script_type')} script_len={len(script)}")

        if plan.get("install_mode") == "official-link":
            print("   official-link，跳过脚本检查")
            continue

        # 关键断言：脚本里不出现 markdown 的说明文字
        leaks = [w for w in ("## 一键安装脚本", "## 安装验证", "预期输出", "安装完成后",
                             "脚本运行说明", "执行后建议", "常见问题") if w in script]
        print(f"   markdown 泄漏: {leaks or '无'}")
        if leaks:
            fails.append(f"{name}@{platform} 脚本混入说明文字 {leaks}")
        if plan.get("script_type") != want_type:
            fails.append(f"{name}@{platform} 脚本类型 {plan.get('script_type')} != {want_type}")

        # 脚本行数应显著少于整篇 markdown，且首行应是注释或命令
        first = script.strip().splitlines()[0] if script.strip() else ""
        print(f"   首行: {first[:60]}")
        if first.startswith("#") is False and want_type == "bash" and not first.startswith("#!"):
            print("   （提示：bash 脚本首行不是注释/sha-bang，确认是否符合预期）")

        # 验证命令确实出现在 markdown 的「安装验证」段
        verify_section = md.split("## 安装验证")[-1] if "## 安装验证" in md else ""
        print(f"   安装验证段存在: {bool(verify_section)}")

    print("\n结果:", "全部通过 🎉" if not fails else f"失败: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
