"""사용자용 협업 시나리오 라우터.

엔드포인트:
  GET    /scenarios                          — 사용자 부서/언어 컨텍스트 활성 목록
  GET    /scenarios/favorites                — 내 즐겨찾기
  POST   /scenarios/{id}/favorite            — 즐겨찾기 추가
  PUT    /scenarios/{id}/favorite            — 메모 업데이트
  DELETE /scenarios/{id}/favorite            — 즐겨찾기 해제
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_current_user
from backend.schemas.scenarios import (
    FavoriteItem,
    FavoriteListResponse,
    FavoriteRequest,
    ScenarioItem,
    ScenarioListResponse,
)
from core.scenarios import repository

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=ScenarioListResponse)
async def list_user_scenarios(
    division: str = Query("", description="비어있으면 user.division 자동 사용"),
    lang: str = Query("ko"),
    user=Depends(get_current_user),
):
    """현재 사용자 부서/언어에 맞춰 활성 시나리오 목록."""
    div = division or getattr(user, "division", "") or ""
    items = repository.list_for_user(division=div, lang=lang)
    return ScenarioListResponse(total=len(items), items=[ScenarioItem(**it) for it in items])


@router.get("/favorites", response_model=FavoriteListResponse)
async def list_my_favorites(user=Depends(get_current_user)):
    employee_id = getattr(user, "employee_id", "") or ""
    if not employee_id:
        raise HTTPException(401, "employee_id 가 없습니다.")
    items = repository.list_favorites(employee_id)
    return FavoriteListResponse(total=len(items), items=[FavoriteItem(**it) for it in items])


@router.post("/{scenario_id}/favorite")
async def add_to_favorites(
    scenario_id: str,
    req: FavoriteRequest,
    user=Depends(get_current_user),
):
    employee_id = getattr(user, "employee_id", "") or ""
    if not employee_id:
        raise HTTPException(401, "employee_id 가 없습니다.")
    if not repository.get(scenario_id):
        raise HTTPException(404, f"존재하지 않는 scenario_id: {scenario_id}")
    return repository.add_favorite(employee_id, scenario_id, note=req.note)


@router.put("/{scenario_id}/favorite")
async def update_favorite_note_endpoint(
    scenario_id: str,
    req: FavoriteRequest,
    user=Depends(get_current_user),
):
    employee_id = getattr(user, "employee_id", "") or ""
    if not employee_id:
        raise HTTPException(401, "employee_id 가 없습니다.")
    return repository.update_favorite_note(employee_id, scenario_id, note=req.note)


@router.delete("/{scenario_id}/favorite")
async def remove_from_favorites(scenario_id: str, user=Depends(get_current_user)):
    employee_id = getattr(user, "employee_id", "") or ""
    if not employee_id:
        raise HTTPException(401, "employee_id 가 없습니다.")
    n = repository.remove_favorite(employee_id, scenario_id)
    return {"removed": n}
