"""backend/routers/directory.py — v4.8 F 트랙.

조직 부서 트리 endpoint. UsersCategory 좌측 DeptTree 가 소비한다.
core.auth.department_config + core.directory.canonical 의 user_count 사용.

L1+ 이면 조회 가능 (드롭다운 옵션 역할도 겸함).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/directory", tags=["directory"])


class DirectoryNode(BaseModel):
    id: str           # `${division}::${department}` 또는 `__div::${division}`
    name: str
    parent_id: Optional[str] = None
    level: int        # 0=division, 1=department
    user_count: int = 0


class DirectoryTreeResponse(BaseModel):
    nodes: list[DirectoryNode]
    total_users: int


_AUTH_DB = Path("data/auth.db")


def _user_counts_by_department() -> dict[str, int]:
    """auth.db users 테이블에서 부서별 활성 사용자 수."""
    if not _AUTH_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(_AUTH_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT department, COUNT(*) AS cnt FROM users
                WHERE is_active = 1 AND IFNULL(department, '') != ''
                GROUP BY department"""
        ).fetchall()
        conn.close()
        return {(r["department"] or ""): int(r["cnt"] or 0) for r in rows}
    except Exception as e:  # noqa: BLE001
        logger.warning("[directory] user_counts query failed: %s", e)
        return {}


@router.get("/tree", response_model=DirectoryTreeResponse)
async def directory_tree(user=Depends(get_current_user)):  # noqa: ARG001 — user kept for auth guard
    """본부 → 부서 평면 트리.

    Returns:
        nodes: [{id, name, parent_id, level, user_count}]. 평면 리스트.
                프론트(DeptTree.tsx)가 parent_id 로 트리 재구성.
        total_users: 모든 부서 합계.
    """
    from core.auth.department_config import DEPARTMENT_CATEGORIES

    counts = _user_counts_by_department()
    nodes: list[DirectoryNode] = []
    total = 0

    for div, depts in DEPARTMENT_CATEGORIES.items():
        div_id = f"__div::{div}"
        div_total = 0
        dept_nodes: list[DirectoryNode] = []
        for dept_name in depts:
            cnt = int(counts.get(dept_name, 0))
            div_total += cnt
            total += cnt
            dept_nodes.append(
                DirectoryNode(
                    id=f"{div}::{dept_name}",
                    name=dept_name,
                    parent_id=div_id,
                    level=1,
                    user_count=cnt,
                ),
            )
        nodes.append(
            DirectoryNode(
                id=div_id,
                name=div,
                parent_id=None,
                level=0,
                user_count=div_total,
            ),
        )
        nodes.extend(dept_nodes)

    return DirectoryTreeResponse(nodes=nodes, total_users=total)
