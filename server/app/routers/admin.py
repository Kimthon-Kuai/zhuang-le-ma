"""管理后台 API：密码登录 + Bearer token 保护。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .. import ai, services
from ..config import settings
from ..schemas import LoginIn, PlanAdminIn, PlanOut, PlanUpdateIn

router = APIRouter(prefix="/api/admin", tags=["admin"])

TOKEN_TTL = 12 * 3600


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token() -> str:
    payload = json.dumps({"sub": "admin", "exp": int(time.time()) + TOKEN_TTL}).encode()
    sig = hmac.new(settings.jwt_secret.encode(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def verify_token(token: str) -> None:
    try:
        payload_b64, sig_b64 = token.split(".")
        payload = _unb64(payload_b64)
        expected = hmac.new(settings.jwt_secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig_b64)):
            raise ValueError("bad signature")
        if json.loads(payload).get("exp", 0) < time.time():
            raise ValueError("expired")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录") from exc


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    verify_token(authorization.split(" ", 1)[1].strip())


@router.post("/login")
def login(payload: LoginIn):
    if not hmac.compare_digest(payload.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="密码不对哦，再想想？")
    return {"token": make_token(), "expires_in": TOKEN_TTL}


@router.get("/me", dependencies=[Depends(require_admin)])
def me():
    return {"ok": True, "ai_configured": ai.ai_configured(), "model": settings.ai_model}


@router.get("/plans", dependencies=[Depends(require_admin)])
def plans(limit: int = Query(100, le=500), offset: int = 0, q: str | None = None):
    items = services.list_plans(limit=limit, offset=offset, q=q)
    return [{k: v for k, v in p.items() if k in PlanOut.model_fields}
            | {"created_at": p.get("created_at")} for p in items]


@router.get("/plans/{plan_id}", dependencies=[Depends(require_admin)])
def plan_detail(plan_id: int):
    try:
        return services.get_plan(plan_id)
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.put("/plans/{plan_id}", dependencies=[Depends(require_admin)])
def plan_update(plan_id: int, payload: PlanUpdateIn):
    try:
        return services.update_plan_markdown(plan_id, payload.markdown)
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.delete("/plans/{plan_id}", dependencies=[Depends(require_admin)])
def plan_delete(plan_id: int):
    try:
        services.delete_plan(plan_id)
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/plans/{plan_id}/regenerate", dependencies=[Depends(require_admin)])
async def plan_regenerate(plan_id: int):
    try:
        plan = services.get_plan(plan_id)
        sw = services.get_software(plan["software_id"])
        new_plan, _ = await services.generate_plan(sw, plan["version"], plan["platform"], force=True)
        return new_plan
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/plans/generate", dependencies=[Depends(require_admin)])
async def plan_generate(payload: PlanAdminIn):
    try:
        sw, _, _ = await services.identify(payload.software)
        plan, _ = await services.generate_plan(sw, payload.version, payload.platform, force=True)
        return plan
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.get("/feedbacks", dependencies=[Depends(require_admin)])
def feedbacks(limit: int = Query(200, le=1000), handled: bool | None = None):
    return services.list_feedbacks(limit=limit, handled=handled)


@router.patch("/feedbacks/{feedback_id}", dependencies=[Depends(require_admin)])
def feedback_update(feedback_id: int, handled: bool = True):
    try:
        return services.mark_feedback(feedback_id, handled)
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.get("/stats", dependencies=[Depends(require_admin)])
def stats():
    return services.stats_overview()
