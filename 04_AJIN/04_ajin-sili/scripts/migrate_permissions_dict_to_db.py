"""v4.7 PR-E7 — 코드 dict → permissions.db seed migration.

대상 dict (core/auth/permissions.py 의 _CODE_DICT_PERMISSIONS):
  - COMPLIANCE_PERMISSIONS
  - ADMIN_PERMISSIONS
  - EQUIPMENT_PERMISSIONS

동작
----
- ``--dry-run`` 모드: 신규/이미 존재 count 만 출력. DB 쓰기 없음.
- ``--apply`` 모드: 신규 row 만 INSERT. 이미 존재하는 key 는 SKIP (자연키 충돌 회피, 기존 데이터 보존).

멱등성
------
재실행 시 모든 key 가 이미 존재하므로 new=0, skip=N 으로 안전.

사용 예
-------
    python scripts/migrate_permissions_dict_to_db.py --dry-run
    python scripts/migrate_permissions_dict_to_db.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트 sys.path 등록 (scripts/ 직접 실행 호환).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.auth.permissions_db import (
    get_permission,
    init_permissions_db,
    upsert_permission,
)


def collect_all_dict_permissions() -> dict:
    """모든 도메인 권한 dict 통합. Permission dataclass → public dict 변환."""
    from core.auth.permissions import _CODE_DICT_PERMISSIONS

    out: dict = {}
    for key, perm in _CODE_DICT_PERMISSIONS.items():
        out[key] = {
            "key": perm.key,
            "description": perm.description,
            "min_role": perm.min_role,
            "departments": perm.departments,
            "allow_same_division": perm.allow_same_division,
            "min_position_level": perm.min_position_level,
        }
    return out


def run(*, dry_run: bool, apply: bool) -> dict:
    """seed migration 본체. 반환: {"new": N, "skip": N, "mode": "..."}."""
    if dry_run == apply:
        raise SystemExit(
            "정확히 --dry-run 또는 --apply 중 하나를 지정하세요."
        )

    init_permissions_db()
    all_perms = collect_all_dict_permissions()

    new_count = 0
    skip_count = 0
    for key, perm in all_perms.items():
        if get_permission(key) is not None:
            skip_count += 1
            continue
        new_count += 1
        if apply:
            upsert_permission(perm, actor="system:migration")

    mode = "apply" if apply else "dry-run"
    print(f"[{mode}] new={new_count} skip={skip_count}")
    return {"new": new_count, "skip": skip_count, "mode": mode}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="권한 dict → permissions.db seed migration"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, apply=args.apply)


if __name__ == "__main__":
    main()
