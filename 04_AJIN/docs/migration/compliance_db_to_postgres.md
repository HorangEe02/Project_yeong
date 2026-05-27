# Migration Plan — D 모듈 SQLite `compliance.db` → PostgreSQL (Supabase)

| 항목 | 값 |
|---|---|
| **작성일** | 2026-05-27 |
| **트리거** | 2026-05-27 D 모듈 500 incident (compliance.db 파일 손상) |
| **현재 상태** | Phase 1 진행 중 (설계 + alembic schema migration) |
| **참조 문서** | [2026-05-27 D 모듈 incident postmortem](../reviews/2026-05-27_d_module_compliance_db_postmortem.md) |
| **관련 alembic** | `alembic/versions/20260527_0004_compliance_postgres_migration.py` |

---

## 1. 배경

2026-05-27 incident 에서 호스트의 단일 SQLite 파일 (`data/compliance.db`, 7.5 MB) 이 SQLite 가 아닌 손상 데이터로 변형되어 `/api/compliance/crawl/history/stats` 500 응답. 분석 결과:

- 6개 backend 모듈이 같은 파일 의존 (단일 장애점)
- `.gitignore: data/**/*.db` 이므로 git 백업 불가
- `features/data/compliance.db` 가 git tracked 덕분에 우연히 복구 source 확보
- 동시 쓰기 / partial write / WAL 미동기화 등 SQLite 한계가 누적되면 재발 가능

PostgreSQL/Supabase 로의 마이그레이션이 단일 장애점 + 동시성 + 백업 문제를 동시에 해소.

## 2. 목표

1. compliance.db 8 테이블을 PostgreSQL 스키마로 이관
2. 동시 쓰기 / 트랜잭션 격리 강화
3. Supabase Realtime / RLS 활용 가능 기반
4. `APP_DB_BACKEND=postgres` env 토글로 SQLite/Postgres 양쪽 지원 (cutover 안전)
5. 운영 백업은 Supabase managed (PITR + 일일 dump)

## 3. 이관 대상 테이블 (8개)

| 테이블 | 용도 | 행 수 (현재) | 우선순위 |
|---|---|---|---|
| `regulations` | 외부 9 소스 규제 마스터 | ~수천 | High |
| `crawl_history` | 크롤링 스냅샷 | ~수백 | High |
| `crawl_runs` | 실행 단위 감사 (incident 원인) | ~수십 | **Critical** |
| `http_cache` | ETag / Last-Modified | ~수백 | Medium |
| `draft_user_prefs` | Module B 사용자 prefs | ~수십 | Medium |
| `draft_dept_usage` | 부서별 doc_type 사용 빈도 | ~수십 | Low |
| `draft_user_picks` | 사용자별 doc_type 선호 | ~수십 | Low |
| `draft_agg_runs` | aggregation 작업 감사 | ~수십 | Low |

## 4. 단계별 계획

### Phase 1 — 본 PR (현재 진행)
- ✅ 설계 문서 (본 문서)
- ✅ alembic migration `20260527_0004_compliance_postgres_migration.py` 생성 (schema only)
- ⏳ 본 PR 머지 시점에 alembic head update (Supabase 환경에서 `alembic upgrade head` 자동 실행)

### Phase 2 — Repository Pattern 추상화 (별도 세션, 1-2주)
- 신규 모듈: `backend/services/compliance_repo.py`
- 6 모듈 (`crawl_audit`, `http_cache`, `docs_library`, `draft_dept_agg`, `draft_prefs`, `search/fts_index`) 의 SQLite 직접 호출을 repository 호출로 추상화
- `APP_DB_BACKEND=sqlite|postgres` env 분기
- 단위 테스트 작성

### Phase 3 — 데이터 마이그레이션 + 검증 (별도 세션, 1주)
- 신규 스크립트: `scripts/migrate_compliance_db_to_postgres.py`
  - SQLite → Postgres row-by-row 이관
  - JSON 컬럼 (`content_json`, `favorited_doc_types`) 무결성 검증
  - 체크섬 비교 (이관 전후 row count + sample hash)
- `docker-compose.supabase.yml` 로컬 환경에서 검증

### Phase 4 — Dual-Write Canary (별도 세션, 1주)
- 5% traffic 부터 dual-write (SQLite + Postgres 동시 기록)
- 결과 비교 (drift detection job)
- 100% 도달 후 read 도 Postgres 로 전환

### Phase 5 — Cutover + SQLite Archive (별도 세션, 0.5주)
- `APP_DB_BACKEND=postgres` traffic 100%
- SQLite 파일 archive (`data/archive/compliance.db.YYYYMMDD`)
- 6 모듈에서 SQLite 코드 제거 (repository pattern 만 남김)

## 5. 위험 / 롤백

| Phase | 위험 | 롤백 절차 |
|---|---|---|
| 1 (본 PR) | alembic migration fail (Postgres 에 이미 같은 테이블 존재 시) | `alembic downgrade 20260526_0003` |
| 2 | repository 추상화에서 SQL dialect 차이 (`AUTOINCREMENT` vs `SERIAL` 등) | 코드 revert, SQLite 직접 호출로 복원 |
| 3 | 데이터 이관 중 무결성 오류 | Postgres 테이블 truncate + 재실행 |
| 4 | dual-write 성능 저하 (latency 2배) | `DUAL_WRITE_ENABLED=false` 즉시 토글 |
| 5 | cutover 후 Postgres 장애 | SQLite 파일 mount + `APP_DB_BACKEND=sqlite` 환경변수 즉시 복귀 (10 분 RTO) |

## 6. 스키마 매핑 노트

대부분 SQLite TEXT → Postgres `VARCHAR(N)` 또는 `TEXT`. 주요 차이:

| SQLite 컬럼 | Postgres 컬럼 | 비고 |
|---|---|---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `Integer PRIMARY KEY` (SERIAL 자동) | alembic 처리 |
| `ok INTEGER DEFAULT 1` (1/0) | `ok Boolean DEFAULT true` | 데이터 이관 시 1→true, 0→false |
| `created_at TEXT DEFAULT (datetime('now'))` | `created_at DateTime(timezone=True) DEFAULT CURRENT_TIMESTAMP` | timezone aware |
| `content_json TEXT` | `content_json Text` 또는 `JSONB` (향후 검토) | Phase 2 에서 JSONB 도입 검토 |

`http_cache.url` 은 SQLite 에서 `TEXT PRIMARY KEY` 였으나 Postgres 에서 긴 URL (4KB+) 가능성 고려해 `Text` 유지. B-tree index size 한도(8 KB) 이내.

## 7. RLS (Row Level Security) 정책

본 migration 의 `_enable_rls()` 가 8 테이블 모두 RLS enable. 초기 정책은 deny-all (Supabase data-api 직접 접근 차단). backend 만 service role 로 read/write 한다.

향후 Supabase Realtime 활용 시 read-only policy 추가 가능 (e.g. role_level>=3 사용자에게 `regulations` read).

## 8. 모니터링

- `pg_stat_user_tables.n_tup_ins / n_tup_upd / n_tup_del` 로 write 빈도 확인
- `pg_stat_activity` 로 long-running query 추적
- Supabase dashboard 의 query performance + slow query log

## 9. 후속 결정 필요 사항

- [ ] Supabase pro plan 의 connection pooler (pgbouncer) 모드 결정 — transaction vs session
- [ ] FTS5 → Postgres `tsvector` 또는 별도 Meilisearch 인덱스 전환 결정
- [ ] `regulations.content_json` JSONB 전환 시점 (Phase 2 또는 Phase 5)
- [ ] Cloud Run cold start 시 alembic migration auto-run 정책 (idempotent 보장 필요)

## 10. 참조

- [Postmortem 2026-05-27](../reviews/2026-05-27_d_module_compliance_db_postmortem.md)
- [docker-compose.supabase.yml](../../docker-compose.supabase.yml)
- [alembic env.py](../../alembic/env.py)
- [Supabase docs — RLS](https://supabase.com/docs/guides/auth/row-level-security)

---

*문서 작성: 2026-05-27 | Phase 1 alembic schema: `20260527_0004_compliance_postgres_migration`*
