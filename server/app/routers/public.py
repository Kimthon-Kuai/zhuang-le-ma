"""用户端（桌面 App）调用的公开 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import ai, services
from ..prompts import PLATFORM_META
from ..schemas import (FeedbackIn, IdentifyIn, IdentifyOut, PlanIn, PlanOut, SoftwareOut,
                       StatIn, VersionItem, VersionsOut)

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health():
    return {
        "ok": True,
        "ai_configured": ai.ai_configured(),
        "model": ai.settings.ai_model if ai.ai_configured() else None,
        "slogan": "今天你装了吗？",
    }


@router.get("/platforms")
def platforms():
    return [{"key": k, "label": v["label"], "lang": v["lang"]} for k, v in PLATFORM_META.items()]


@router.get("/software")
def software_list():
    return services.list_software()


@router.post("/identify", response_model=IdentifyOut)
async def identify(payload: IdentifyIn):
    try:
        sw, matched, used_ai = await services.identify(payload.text)
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    services.record_stat("software", sw.display_name, sw.display_name, None)
    return IdentifyOut(software=sw, matched=matched, ai_used=used_ai)


@router.get("/software/{software_id}/versions", response_model=VersionsOut)
async def versions(software_id: int, platform: str = Query("windows"),
                   refresh: bool = Query(False)):
    if platform not in PLATFORM_META:
        raise HTTPException(status_code=400, detail="平台只能是 windows / macos / linux")
    sw = services.get_software(software_id)
    items, source = await services.get_versions(sw, platform, refresh=refresh)
    if items:
        latest = next((i["version"] for i in items if i["is_latest"]), items[0]["version"])
        services.record_stat("version", f"{sw.display_name}@{latest}", sw.display_name, platform)
    return VersionsOut(
        software=sw,
        versions=[VersionItem(**i) for i in items],
        source=source,
        cached=source == "cache",
    )


@router.post("/plans", response_model=PlanOut)
async def create_plan(payload: PlanIn):
    try:
        sw, _, _ = await services.identify(payload.software)
        if payload.display_name:
            sw.display_name = payload.display_name
        if payload.homepage:
            sw.homepage = payload.homepage
        plan, cached = await services.generate_plan(sw, payload.version, payload.platform,
                                                    force=payload.force)
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    services.record_stat("platform", payload.platform, sw.display_name, payload.platform)
    out = PlanOut(**{k: v for k, v in plan.items() if k in PlanOut.model_fields})
    out.cached = cached
    return out


@router.get("/plans/lookup", response_model=PlanOut)
def lookup_plan(software_id: int, version: str, platform: str):
    """按 软件 + 版本 + 平台 查询已有方案（未生成时 404）。

    必须注册在 /plans/{plan_id} 之前，否则 "lookup" 会被当成 plan_id。
    """
    plan = services.get_plan_by_key(software_id, version, platform)
    if not plan:
        raise HTTPException(status_code=404, detail="该组合还没有生成过方案")
    return PlanOut(**{k: v for k, v in plan.items() if k in PlanOut.model_fields})


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int):
    try:
        return PlanOut(**{k: v for k, v in services.get_plan(plan_id).items()
                          if k in PlanOut.model_fields})
    except services.ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/feedback")
def feedback(payload: FeedbackIn):
    return services.add_feedback(payload.model_dump())


@router.post("/stats")
def stats(payload: StatIn):
    services.record_stat(payload.kind, payload.key, payload.software_name, payload.platform)
    return {"ok": True}
