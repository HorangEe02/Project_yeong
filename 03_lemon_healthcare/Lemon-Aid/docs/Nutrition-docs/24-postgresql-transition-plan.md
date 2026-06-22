# PostgreSQL Transition Feasibility And Plan

작성일: 2026-05-13

## 결론

“SQLAlchemy에서 PostgreSQL로 변경”은 정확히는 교체 관계가 아니다. SQLAlchemy는 Python ORM/DB toolkit이고 PostgreSQL은 DB 엔진이다. 현재 backend는 이미 SQLAlchemy async ORM 위에서 PostgreSQL `asyncpg` dialect를 사용하도록 설계되어 있다.

따라서 권장 방향은 다음이다.

1. SQLAlchemy ORM과 Alembic은 유지한다.
2. SQLite 같은 대체 개발 DB 경로를 만들지 않고 PostgreSQL을 단일 런타임 DB로 고정한다.
3. CI와 로컬 검증에서 실제 PostgreSQL migration/smoke test를 추가한다.
4. AI/이미지/학습 기능을 붙이기 전 PostgreSQL schema drift를 `alembic check` 또는 live migration smoke로 검증한다.

SQLAlchemy를 제거하고 raw `asyncpg` 또는 SQL 파일 중심으로 전환하는 것은 P1 안정화 단계에서는 비권장이다.

## 공식 문서 확인

- SQLAlchemy PostgreSQL `asyncpg` dialect: <https://docs.sqlalchemy.org/en/20/dialects/postgresql.html>
- SQLAlchemy AsyncIO: <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- Alembic autogenerate/check: <https://alembic.sqlalchemy.org/en/latest/autogenerate.html>
- PostgreSQL JSON/JSONB: <https://www.postgresql.org/docs/16/datatype-json.html>

## 현재 코드 상태

| 항목 | 현재 상태 |
| --- | --- |
| 기본 DB URL | `backend/src/config.py`의 `DEFAULT_DATABASE_URL = "postgresql+asyncpg://lemon:lemon@localhost:5432/lemon"` |
| DB URL guard | `Settings`가 `postgresql+asyncpg` 외 URL을 거부 |
| Engine 생성 | `backend/src/db/session.py`에서 `create_async_engine(settings.database_url, pool_pre_ping=True)` 사용 |
| Session | `async_sessionmaker(..., expire_on_commit=False)` 사용 |
| Migration | Alembic async env 구성, `alembic/env.py`에서 `async_engine_from_config` 사용 |
| Driver dependency | `requirements.txt`에 `sqlalchemy[asyncio]`, `asyncpg`, `alembic` 포함 |
| PostgreSQL 전용 타입 | ORM과 migration에서 `postgresql.UUID`, `postgresql.JSONB` 사용 |
| 테스트 | `tests/unit/db/test_session.py`가 `postgresql+asyncpg` driver를 확인 |
| live DB smoke | 로컬은 `TEST_DATABASE_URL`이 있을 때 실행, backend CI는 PostgreSQL service로 항상 실행 |
| CI migration smoke | backend CI에서 `alembic upgrade head`와 `alembic current` 실행 |

즉, 코드 레벨에서는 이미 PostgreSQL 지향성이 강하다. 이번 보정으로 실제 PostgreSQL을 띄운 migration/DB smoke도 backend CI gate에 포함했다.

## 타당성 평가

### 권장: SQLAlchemy 유지 + PostgreSQL 고정

타당성이 높다.

이유:

- 기존 service layer가 `AsyncSession`과 SQLAlchemy `select()`에 의존한다.
- ORM 모델이 이미 PostgreSQL UUID/JSONB 타입을 사용한다.
- Alembic migration 4개가 SQLAlchemy metadata와 PostgreSQL dialect 기준으로 작성되어 있다.
- P1 API, privacy deletion, audit, health sync, supplement registration이 ORM 모델과 연결되어 있다.
- pgvector/JSONB/GIN index 같은 PostgreSQL 기능은 SQLAlchemy + Alembic으로도 단계적으로 추가 가능하다.

### 비권장: SQLAlchemy 제거 + raw PostgreSQL/asyncpg 전환

P1 안정화 단계에서는 타당성이 낮다.

위험:

- service, API, tests 전반의 `AsyncSession` 계약이 깨진다.
- Alembic autogenerate와 ORM metadata 기반 schema drift 검증을 잃는다.
- 이미 작성된 모델 docstring, constraints, indexes, migration이 대부분 재작성 대상이 된다.
- 보안/동의/삭제 flow의 회귀 범위가 커진다.
- AI 기능 추가 전 기준선 안정화라는 현재 목표와 충돌한다.

raw SQL은 성능 병목, 복잡한 PostgreSQL native query, pgvector similarity search처럼 ORM 표현력이 부족한 좁은 구간에서만 보조적으로 사용한다.

## 수정 방안 플랜

### DB-P0: 용어와 목표 고정

목표: 팀이 “SQLAlchemy 제거”와 “PostgreSQL 런타임 고정”을 혼동하지 않게 한다.

작업:

- docs에 “SQLAlchemy는 ORM, PostgreSQL은 DB 엔진”이라고 명시한다.
- backend 아키텍처 표기에서 “SQLAlchemy -> PostgreSQL 전환” 대신 “SQLAlchemy async + PostgreSQL runtime”이라고 표현한다.
- `docs/Nutrition-docs/23-p1-stabilization-plan.md`와 이 문서를 함께 P1 기준선으로 참조한다.

완료 조건:

- 새 작업자가 raw asyncpg 전환을 기본 방향으로 오해하지 않는다.

### DB-P1: PostgreSQL URL Guard 강화

목표: runtime DB URL이 PostgreSQL async dialect가 아니면 명확히 실패하게 한다.

작업:

- [x] `Settings.database_url` validation에 허용 scheme을 명시한다.
- [x] 허용값은 우선 `postgresql+asyncpg`로 제한한다.
- [x] 테스트 추가:
  - default `Settings().database_url`이 `postgresql+asyncpg`인지 확인
  - `sqlite://`, `sqlite+aiosqlite://`, `postgresql://` 같은 비허용 URL 거부

완료 조건:

- [x] PostgreSQL 외 DB URL이 설정되면 앱 boot 또는 settings validation에서 실패한다.

### DB-P2: Live PostgreSQL Test Gate 추가

목표: 실제 PostgreSQL 연결과 기본 query가 CI에서 검증되도록 한다.

작업:

- [x] GitHub Actions backend job에 PostgreSQL service container를 추가한다.
- [x] `TEST_DATABASE_URL=postgresql+asyncpg://...`를 설정한다.
- [x] `tests/integration/db/test_db_session.py`가 CI에서 skip되지 않고 실행되게 한다.
- [x] 최소 query는 `SELECT 1` 유지.

완료 조건:

- [x] CI에서 DB connectivity smoke가 항상 실행된다.
- [x] local에서는 `TEST_DATABASE_URL`이 없으면 기존처럼 skip 가능하다.

### DB-P3: Alembic Migration Smoke

목표: ORM metadata와 migration이 실제 PostgreSQL에 적용 가능한지 확인한다.

작업:

- [x] CI PostgreSQL service에 대해 `alembic upgrade head` 실행.
- [x] 이후 `alembic current` 확인.
- 가능하면 `alembic check`를 추가해 ORM 모델 변경과 migration 누락을 감지한다.
- 단, Alembic autogenerate는 rename/constraint 등 일부 변경을 완벽히 감지하지 못하므로 자동 생성 결과는 항상 수동 리뷰한다.

완료 조건:

- [x] migration head까지 실제 PostgreSQL에 적용 성공하도록 CI smoke를 구성했다.
- 모델 변경 후 migration 누락이 CI에서 드러난다.

### DB-P4: PostgreSQL Native Type/Index 정책 정리

목표: JSONB, UUID, 향후 pgvector 사용을 명확한 규칙으로 관리한다.

작업:

- JSON snapshot 컬럼은 `postgresql.JSONB` 유지.
- 검색 조건이 생긴 JSONB 필드만 GIN index를 별도 migration으로 추가한다.
- UUID는 현재처럼 `postgresql.UUID(as_uuid=True)` 유지.
- pgvector는 `ENABLE_PGVECTOR_STORAGE=false` 기본값 유지 후 별도 migration으로 추가한다.

완료 조건:

- PostgreSQL native feature가 필요한 곳과 아닌 곳이 구분된다.
- index는 쿼리 패턴이 생긴 뒤 추가한다.

### DB-P5: Repository/Service Boundary 유지

목표: PostgreSQL 고정 작업이 서비스 로직을 과도하게 흔들지 않게 한다.

작업:

- API/service 함수 인자는 계속 `AsyncSession`을 받는다.
- service layer 내부 query는 SQLAlchemy `select()` 중심으로 유지한다.
- raw SQL은 다음 조건에서만 허용한다:
  - SQLAlchemy로 표현하기 어렵다.
  - PostgreSQL native 기능이 필요하다.
  - 파라미터 binding을 사용한다.
  - 단위/통합 테스트가 있다.

완료 조건:

- 기존 P1 API test가 유지된다.
- DB 변경이 API contract drift를 만들지 않는다.

## 권장 구현 순서

1. `test(config): reject non-postgresql database URLs`
2. `fix(config): validate database_url uses postgresql+asyncpg`
3. `ci(backend): run PostgreSQL service smoke test`
4. `ci(db): apply Alembic migrations against PostgreSQL`
5. `docs(db): document PostgreSQL runtime policy`

## 검증 명령

로컬 PostgreSQL이 준비된 경우:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
TEST_DATABASE_URL=postgresql+asyncpg://lemon:lemon@localhost:5432/lemon_test \
  .venv/bin/python -m pytest tests/integration/db/test_db_session.py -q

DATABASE_URL=postgresql+asyncpg://lemon:lemon@localhost:5432/lemon_test \
  .venv/bin/alembic upgrade head
```

기본 P1 안정화 검증:

```bash
cd 03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/black --check src tests alembic
.venv/bin/ruff check src tests alembic
.venv/bin/mypy src tests --strict
.venv/bin/python -m pytest --cov-report=xml --cov-report=term-missing
```

## 최종 판단

수정해도 된다. 다만 수정의 방향은 “SQLAlchemy 제거”가 아니라 “PostgreSQL을 유일한 runtime DB로 더 강하게 고정”이어야 한다.

P1 안정화 이후 AI/이미지/학습 파이프라인을 추가하려면 PostgreSQL live test와 Alembic migration smoke를 먼저 CI에 넣는 것이 가장 안전하다.
