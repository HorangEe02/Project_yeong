# Category Seed DB Target Preflight

## Summary

- category seed DB apply 직전 DB target safety preflight를 추가했습니다.
- 이 preflight는 SQLAlchemy URL parser로 설정값을 분류하지만 DB connection을 열지 않습니다.
- 실제 실행 결과는 `ready_for_local_category_seed_apply`입니다.
- `category_seed_db_apply_target_allowed=true`이지만, 제품/브랜드/product-category DB write는 계속 차단 상태입니다.

## Implemented

- `backend/scripts/preflight_supplement_category_seed_db_target.py`
  - prior gate schema와 status를 확인합니다.
  - `category_seed_db_apply_allowed=true`, product apply flags false, prior `db_write_performed=false`를 확인합니다.
  - runtime environment가 `development`인지 확인합니다.
  - DB driver가 `postgresql+asyncpg`인지 확인합니다.
  - DB host class가 `local`인지 확인합니다.
  - DB URL 원문, 사용자명, 비밀번호, DB 이름은 출력하지 않습니다.

- `backend/Nutrition-backend/tests/unit/scripts/test_preflight_supplement_category_seed_db_target.py`
  - local development target allow.
  - remote host block.
  - production environment block.
  - product write flag block.
  - prior DB write claim block.
  - unsafe raw DB URL key rejection.
  - CLI JSON/Markdown redaction.

## Actual Result

- Schema: `supplement-category-seed-db-target-preflight-v1`
- Status: `ready_for_local_category_seed_apply`
- Runtime environment: `development`
- Database driver: `postgresql+asyncpg`
- Database host class: `local`
- Database target kind: `local_postgres`
- Target apply allowed: `true`
- DB connection opened: `false`
- DB write performed: `false`
- Product DB apply allowed: `false`
- Product-category DB apply allowed: `false`

## Conditions

- `category_seed_apply_gate_status_ready=true`
- `category_seed_apply_gate_ready=true`
- `product_apply_blocked=true`
- `product_category_apply_blocked=true`
- `apply_gate_performed_no_db_write=true`
- `environment_is_development=true`
- `driver_is_postgresql_asyncpg=true`
- `database_host_is_local=true`

## Verification

- `cd backend && .venv/bin/python -m ruff check scripts/preflight_supplement_category_seed_db_target.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_category_seed_db_target.py scripts/gate_supplement_category_seed_db_apply.py Nutrition-backend/tests/unit/scripts/test_gate_supplement_category_seed_db_apply.py`
  - Result: pass.
- `cd backend && .venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_preflight_supplement_category_seed_db_target.py Nutrition-backend/tests/unit/scripts/test_gate_supplement_category_seed_db_apply.py`
  - Result: 11 passed.
- Actual preflight run:
  - Result: `ready_for_local_category_seed_apply`.
  - DB connection/write: not performed.

## References

- SQLAlchemy database URL parsing: https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls
- SQLAlchemy `make_url`: https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.make_url
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html

## Next Step

- category seed apply를 실행하려면 같은 로컬 개발 DB target에서만 진행합니다.
- apply 이후에는 category table verifier를 실행해 43개 category seed row가 기대 schema로 저장됐는지 검증합니다.
- brand/product/product-category DB write는 operator review와 approved product manifest가 통과할 때까지 진행하지 않습니다.
