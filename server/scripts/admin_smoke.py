"""管理后台端到端测试：登录 -> 方案查看/编辑/删除/重新生成 -> 反馈处理 -> 统计。

用法（先启动服务）：
    .venv\\Scripts\\python.exe scripts\\admin_smoke.py [base_url]
密码默认从环境变量 ADMIN_PASSWORD 读取，否则 admin123。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8017"
PASSWORD = os.getenv("ADMIN_PASSWORD") or "admin123"
FAILS: list[str] = []
TOKEN: str | None = None


def call(method: str, path: str, body: dict | None = None, auth: bool = True):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if auth and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


def check(label: str, cond: bool, extra: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + label + (f"  <- {extra}" if not cond and extra else ""))
    if not cond:
        FAILS.append(label)


print("== 未登录保护 ==")
st, _ = call("GET", "/api/admin/plans", auth=False)
check("no token -> 401", st == 401, f"st={st}")

print("\n== 登录 ==")
st, r = call("POST", "/api/admin/login", {"password": "definitely-wrong"}, auth=False)
check("wrong password -> 401", st == 401, f"st={st}")
st, r = call("POST", "/api/admin/login", {"password": PASSWORD}, auth=False)
TOKEN = r.get("token")
check("login ok", st == 200 and bool(TOKEN), f"st={st} body={r}")
if not TOKEN:
    print("\n无法登录，后续用例跳过")
    sys.exit(1)

st, me = call("GET", "/api/admin/me")
check("me ok", st == 200 and me.get("ok") is True, f"st={st} {me}")
print(f"     AI: {'已配置 · ' + str(me.get('model')) if me.get('ai_configured') else '未配置（走本地兜底）'}")

print("\n== 造一个方案用于管理 ==")
st, c = call("GET", "/api/software")
items = c.get("items") if isinstance(c, dict) else c
target = next((s for s in items if s.get("name") == "git"), items[0])
st, vs = call("GET", f"/api/software/{target['id']}/versions?platform=windows")
vlist = vs.get("versions") if isinstance(vs, dict) else vs
ver = vlist[0]["version"] if vlist else None
st, plan = call("POST", "/api/plans", {"software": target["name"], "display_name": target["display_name"],
                                       "version": ver, "platform": "windows"}, auth=False)
check("seed plan created", st == 200 and plan.get("id"), f"st={st} {str(plan)[:160]}")
plan_id = plan.get("id")

print("\n== 方案列表 / 详情 ==")
st, listing = call("GET", "/api/admin/plans")
ids = [p.get("id") for p in listing] if isinstance(listing, list) else []
check("plans list contains new plan", st == 200 and plan_id in ids, f"st={st} ids={ids[:10]}")
st, q_list = call("GET", "/api/admin/plans?q=git")
check("plans search works", st == 200 and isinstance(q_list, list) and len(q_list) >= 1, f"st={st}")

st, detail = call("GET", f"/api/admin/plans/{plan_id}")
check("plan detail readable", st == 200 and detail.get("markdown"), f"st={st}")

print("\n== 编辑 Markdown ==")
edited = (detail.get("markdown") or "") + "\n\n<!-- 管理员手动追加 -->\n"
st, upd = call("PUT", f"/api/admin/plans/{plan_id}", {"markdown": edited})
check("plan updated", st == 200, f"st={st} {str(upd)[:160]}")
st, detail2 = call("GET", f"/api/admin/plans/{plan_id}")
check("update persisted", "管理员手动追加" in (detail2.get("markdown") or ""), "未保存")

print("\n== AI 重新生成 ==")
st, regen = call("POST", f"/api/admin/plans/{plan_id}/regenerate")
check("regenerate ok", st == 200 and regen.get("markdown"), f"st={st} {str(regen)[:200]}")
if st == 200:
    check("regen used ai or fallback", regen.get("model") is not None or bool(regen.get("markdown")))
    print(f"     regenerate model={regen.get('model')}")

print("\n== 反馈 ==")
st, fb = call("POST", "/api/feedback", {"plan_id": plan_id, "rating": "invalid",
                                        "content": "管理端联调用反馈"}, auth=False)
check("feedback submitted", st in (200, 201), f"st={st} {fb}")
st, fbs = call("GET", "/api/admin/feedbacks")
fb_items = fbs.get("items") if isinstance(fbs, dict) else fbs
check("feedback listed", st == 200 and isinstance(fb_items, list) and len(fb_items) >= 1, f"st={st}")
if fb_items:
    fid = fb_items[0]["id"]
    st, marked = call("PATCH", f"/api/admin/feedbacks/{fid}?handled=true")
    check("feedback marked handled", st == 200 and marked.get("handled") in (True, 1), f"st={st} {marked}")
    st, pending = call("GET", "/api/admin/feedbacks?handled=false")
    pend = pending.get("items") if isinstance(pending, dict) else pending
    check("handled filtered out", all(f["id"] != fid for f in pend), f"still present: {fid}")

print("\n== 统计 ==")
st, stats = call("GET", "/api/admin/stats")
check("stats readable", st == 200 and isinstance(stats, dict), f"st={st}")
for key in ("total_plans", "total_feedbacks", "software", "platform"):
    if key in stats:
        print(f"     {key}: {str(stats[key])[:90]}")

print("\n== 删除 ==")
st, _ = call("DELETE", f"/api/admin/plans/{plan_id}")
check("plan deleted", st == 200, f"st={st}")
st, _ = call("GET", f"/api/admin/plans/{plan_id}")
check("deleted plan -> 404", st == 404, f"st={st}")

print("\n结果:", "全部通过 🎉" if not FAILS else f"{len(FAILS)} 项失败: {FAILS}")
sys.exit(1 if FAILS else 0)
