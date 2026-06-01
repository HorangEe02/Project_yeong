"""협업 시나리오 관리 라우터 (HR_ADMIN+ 전용).

엔드포인트:
  GET    /admin/scenarios                       — 전체 목록 (비활성 포함 옵션)
  GET    /admin/scenarios/{id}                  — 단건
  POST   /admin/scenarios                       — 신규 추가
  PUT    /admin/scenarios/{id}                  — 수정
  POST   /admin/scenarios/{id}/reset            — 시드 기본값 복구
  DELETE /admin/scenarios/{id}                  — 비활성화 / 영구 삭제
  GET    /admin/scenarios/{id}/history          — 변경 이력
  POST   /admin/scenarios/{id}/restore/{hid}    — 특정 버전 복구
  GET    /admin/scenarios/usage-stats           — 사용 통계 (Phase 3)
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth_middleware import log_api_access
from backend.dependencies import get_current_user
from backend.routers.admin import _require_hr_admin
from backend.schemas.scenarios import (
    ScenarioCreateRequest,
    ScenarioHistoryEntry,
    ScenarioHistoryResponse,
    ScenarioItem,
    ScenarioListResponse,
    ScenarioUpdateRequest,
    UsageStatsResponse,
)
from core.scenarios import repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/scenarios", tags=["admin-scenarios"])


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    include_inactive: bool = Query(True),
    user=Depends(get_current_user),
):
    _require_hr_admin(user)
    items = repository.list_all(include_inactive=include_inactive)
    return ScenarioListResponse(total=len(items), items=[ScenarioItem(**it) for it in items])


@router.get("/usage-stats", response_model=UsageStatsResponse)
async def scenarios_usage_stats(
    days: int = Query(30, ge=1, le=365),
    user=Depends(get_current_user),
):
    _require_hr_admin(user)
    data = repository.usage_stats(days=days)
    return UsageStatsResponse(**data)


@router.get("/{scenario_id}", response_model=ScenarioItem)
async def get_scenario(scenario_id: str, user=Depends(get_current_user)):
    _require_hr_admin(user)
    item = repository.get(scenario_id)
    if not item:
        raise HTTPException(404, f"존재하지 않는 scenario_id: {scenario_id}")
    return ScenarioItem(**item)


@router.post("", response_model=ScenarioItem, status_code=201)
async def create_scenario(req: ScenarioCreateRequest, user=Depends(get_current_user)):
    _require_hr_admin(user)
    try:
        item = repository.create(req.model_dump(), actor=getattr(user, "employee_id", "") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))

    log_api_access(
        endpoint="/api/admin/scenarios",
        method="POST",
        user=user,
        detail=f"create scenario_id={req.scenario_id}",
    )
    return ScenarioItem(**item)


@router.put("/{scenario_id}", response_model=ScenarioItem)
async def update_scenario(
    scenario_id: str,
    req: ScenarioUpdateRequest,
    user=Depends(get_current_user),
):
    _require_hr_admin(user)
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        item = repository.update(scenario_id, patch, actor=getattr(user, "employee_id", "") or "")
    except ValueError as e:
        raise HTTPException(404, str(e))

    log_api_access(
        endpoint=f"/api/admin/scenarios/{scenario_id}",
        method="PUT",
        user=user,
        detail=f"update fields={list(patch.keys())}",
    )
    return ScenarioItem(**item)


@router.post("/{scenario_id}/reset", response_model=ScenarioItem)
async def reset_scenario(scenario_id: str, user=Depends(get_current_user)):
    _require_hr_admin(user)
    try:
        item = repository.reset_to_default(scenario_id, actor=getattr(user, "employee_id", "") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))

    log_api_access(
        endpoint=f"/api/admin/scenarios/{scenario_id}/reset",
        method="POST",
        user=user,
        detail="reset to system default",
    )
    return ScenarioItem(**item)


@router.delete("/{scenario_id}")
async def delete_scenario_endpoint(scenario_id: str, user=Depends(get_current_user)):
    _require_hr_admin(user)
    try:
        result = repository.delete_scenario(scenario_id, actor=getattr(user, "employee_id", "") or "")
    except ValueError as e:
        raise HTTPException(404, str(e))

    log_api_access(
        endpoint=f"/api/admin/scenarios/{scenario_id}",
        method="DELETE",
        user=user,
        detail=f"delete is_seed={result['is_system_default']}",
    )
    return result


@router.get("/{scenario_id}/history", response_model=ScenarioHistoryResponse)
async def get_scenario_history(
    scenario_id: str,
    limit: int = Query(50, ge=1, le=500),
    user=Depends(get_current_user),
):
    _require_hr_admin(user)
    rows = repository.get_history(scenario_id, limit=limit)
    return ScenarioHistoryResponse(
        scenario_id=scenario_id,
        total=len(rows),
        history=[ScenarioHistoryEntry(**r) for r in rows],
    )


@router.post("/{scenario_id}/restore/{history_id}", response_model=ScenarioItem)
async def restore_version_endpoint(
    scenario_id: str,
    history_id: int,
    user=Depends(get_current_user),
):
    _require_hr_admin(user)
    try:
        item = repository.restore_version(
            scenario_id,
            history_id,
            actor=getattr(user, "employee_id", "") or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    log_api_access(
        endpoint=f"/api/admin/scenarios/{scenario_id}/restore/{history_id}",
        method="POST",
        user=user,
        detail="restore to history version",
    )
    return ScenarioItem(**item)
