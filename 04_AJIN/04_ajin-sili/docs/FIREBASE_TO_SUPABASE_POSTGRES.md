# Firebase to Supabase/PostgreSQL Migration

## 현재 구현 범위

- Phase 0 비용 차단 기본값을 적용했다.
  - Backend: `FIREBASE_WRITE_ENABLED=false`가 기본이며 Firestore audit, Firestore auth/employee mirror, RTDB alarm push가 이 플래그 뒤에 있다.
  - Frontend: `VITE_FIREBASE_WRITE_ENABLED=false`가 기본이며 Storage upload, RTDB feedback push, Firestore chat/draft/equipment seed write가 차단된다.
  - Firebase read-only fallback은 `FIREBASE_READ_FALLBACK_ENABLED=true` / `VITE_FIREBASE_READ_FALLBACK_ENABLED=true`로 임시 허용한다.

- Phase 1 기반을 추가했다.
  - `APP_DB_BACKEND=sqlite|postgres`와 `DATABASE_URL`을 읽는 `core/db.py`를 추가했다.
  - SQLAlchemy, psycopg, Alembic 의존성을 추가했다.
  - `alembic/versions/20260518_0001_supabase_postgres_foundation.py`에 Supabase/Postgres 1차 테이블을 정의했다.
  - 로컬 Postgres 개발용 `docker-compose.postgres.yml`을 추가했다.

- Phase 2~5 전환 기반을 추가했다.
  - `core/auth/postgres_audit.py`를 추가하고 로그인 audit emit/read 우선순위를 Postgres → legacy Firestore fallback → SQLite fallback으로 정리했다.
  - `features/search/employee/postgres_repository.py`를 추가해 admin/ERP 직원 upsert가 Postgres mirror를 함께 갱신할 수 있게 했다.
  - PLC ingest 알람 표준 경로를 `backend.services.live_events.insert_alarm()` → `live_alarms`로 전환했다.
  - 프론트 feedback RTDB write를 `/api/feedback` 백엔드 API → `feedback_events`로 전환했다.
  - Supabase Storage signed upload/download URL 발급 API를 `/api/storage/*`로 추가하고, 프론트 업로드가 Firebase Storage SDK를 호출하지 않도록 바꿨다.
  - SQLite/Firestore export/RTDB export/Firebase Storage export migration 스크립트를 dry-run/apply 모드로 추가했다.

## 비용 차단 체크리스트

| 영역 | 기본 상태 | 분류 |
| --- | --- | --- |
| `core/auth/firestore_audit.py` | write off, read fallback optional | disabled/fallback |
| `core/auth/database.py` Firestore mirror | write off, read fallback optional | disabled/fallback |
| `features/search/employee/database.py` Firestore mirror | Postgres mirror 우선, Firebase fallback optional | remove-later |
| `backend/services/firebase_rtdb.py` | legacy dry-run/fallback만 유지 | remove-later |
| `backend/services/live_events.py` | Postgres/SQLite `live_alarms` 표준 경로 | active |
| `backend/services/feedback_events.py` | Postgres/SQLite `feedback_events` 표준 경로 | active |
| `frontend/src/api/upload.ts` Firebase Storage | Supabase signed URL flow로 전환 | active |
| `frontend/src/api/feedback.ts` RTDB feedback | `/api/feedback` backend API로 전환 | active |
| `frontend/src/lib/firestore-chat.ts` | write off, read fallback optional | disabled/fallback |
| `frontend/src/lib/firestore-draft.ts` | write off, read fallback optional | disabled/fallback |
| `frontend/src/lib/firestore-equipment.ts` | write off | disabled |
| `frontend/src/hooks/useRTDBValue.ts` / `useEquipmentRTDB.ts` | read fallback optional | fallback |

## Supabase/Postgres 운영 원칙

- AJIN JWT를 유지하고 Supabase Auth는 도입하지 않는다.
- Supabase secret key 또는 legacy service_role key는 frontend에 노출하지 않는다.
- 민감 테이블은 FastAPI를 통해서만 접근한다.
- Realtime은 기본 비활성으로 두고, 필요 시 `live_alarms`만 제한적으로 연결한다.
- Alembic migration은 Supabase 운영 DB와 로컬 Postgres에 동일하게 적용한다.

## 명령

```bash
# 로컬 Postgres 실행
docker compose -f docker-compose.postgres.yml up -d

# Postgres migration 적용
APP_DB_BACKEND=postgres \
DATABASE_URL=postgresql://ajin:ajin@localhost:5432/ajin \
make db-upgrade

# 현재 revision 확인
APP_DB_BACKEND=postgres \
DATABASE_URL=postgresql://ajin:ajin@localhost:5432/ajin \
make db-current

# Firebase 비용 차단 후 export dry-run 예시
.venv/bin/python scripts/migrate_sqlite_to_postgres.py --dry-run
.venv/bin/python scripts/migrate_firestore_export_to_postgres.py --dry-run /path/to/firestore-export.json
.venv/bin/python scripts/migrate_rtdb_export_to_postgres.py --dry-run /path/to/rtdb-export.json
.venv/bin/python scripts/migrate_firebase_storage_to_supabase.py --dry-run --source-dir /path/to/storage-export
```

## 공식 기준 문서

- Firebase Firestore billing: https://firebase.google.com/docs/firestore/pricing
- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase Realtime Postgres Changes: https://supabase.com/docs/guides/realtime/postgres-changes
- Supabase Storage signed upload URL: https://supabase.com/docs/reference/python/storage-from-createsigneduploadurl
- Supabase Storage upload to signed URL: https://supabase.com/docs/reference/javascript/storage-from-uploadtosignedurl
- SQLAlchemy Engine Configuration: https://docs.sqlalchemy.org/en/20/core/engines.html
