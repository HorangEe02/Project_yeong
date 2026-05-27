# Incident Postmortem — D 모듈 `/compliance` 500 오류

| 항목 | 값 |
|---|---|
| **발생일** | 2026-05-27 |
| **신고 시점** | 사용자가 `https://ajin-ai-assistant-frontend.vercel.app/compliance` 화면에서 "백엔드 연결 실패: Request failed with status code 500" 발견 |
| **해결 일자** | 2026-05-27 |
| **심각도** | 중간 (D 모듈 진입 자체는 가능, KPI/feed/alarms는 정상. 빨간 배너로 사용자 신뢰 저하) |
| **사용자 영향** | SYS_ADMIN(L5) 포함 모든 사용자가 `/compliance` 페이지에서 오류 메시지 노출 |
| **데이터 손실** | 없음 (백업 보존, git tracked DB로 복원) |
| **재발 위험** | 중간 (근본 원인인 호스트 `compliance.db` 파일 손상 메커니즘 미확정) |

---

## 1. 한 줄 요약

호스트의 `data/compliance.db` 파일이 SQLite 포맷이 아닌 손상 데이터로 변형되어, 이 파일을 여는 6개 backend 모듈 중 `backend/services/crawl_audit.py` 의 `ensure_table()` 이 500 응답.

## 2. 사용자 가시 증상

- `/compliance` 진입 시 `RUN ALL` 버튼 옆에 빨간색 "백엔드 연결 실패: Request failed with status code 500" 메시지 노출
- KPI 카드는 모두 0으로 표시 (실제로는 데이터가 비어있어서 정상, 그러나 사용자는 "전부 다 깨졌다"고 인식)
- 변경 피드 / 주요 알람 / 시스템 라벨은 정상

## 3. 근본 원인

`data/compliance.db` 파일의 첫 바이트가 SQLite 매직 바이트(`53 51 4c 69 74 65 20 66 6f 72 6d 61 74 20 33 00` = `"SQLite format 3\0"`)가 아닌 **`0d 00 00 00 05 0f 9e 00 ...`** 로 시작.

```
$ file data/compliance.db
data/compliance.db:         data       ← "data" = 알려진 형식 아님

$ file data/compliance_changes.db
data/compliance_changes.db: SQLite 3.x database, ...   ← 정상
```

같은 디렉토리의 다른 13개 `.db` 파일은 모두 정상 SQLite. **이 한 파일만 손상**.

손상 원인은 확정되지 않음. 가능한 시나리오:
- 동시 쓰기 충돌 (여러 프로세스가 같은 파일 동시 write)
- 비정상 종료 중 partial write
- 외부 도구(백업 스크립트, 동기화 도구)가 SQLite WAL 미인지 상태로 파일 truncate
- `.gitignore` 로 인해 git이 변경 추적하지 못해 오랜 시간 손상이 누적됨

## 4. 영향 범위

`data/compliance.db` 를 여는 backend 모듈 7개:

```
backend/services/crawl_audit.py:24    ← 500 직접 발생
backend/services/http_cache.py:20
backend/services/docs_library.py:12
backend/services/draft_dept_agg.py:19
backend/services/draft_prefs.py:14
backend/services/search/fts_index.py:18
features/compliance/infra/compliance_db.py:17
```

`/compliance` 페이지 진입 시 5개 API를 `Promise.all` 로 병렬 호출:

| API | 결과 | 비고 |
|---|---|---|
| `GET /api/compliance/changes/kpi?window_days=30` | 200 OK | `compliance_changes.db` 사용 (다른 파일) |
| `GET /api/compliance/changes/feed` | 200 OK | 동일 |
| `GET /api/compliance/alarms/recent` | 200 OK | 동일 |
| `GET /api/compliance/crawl-results` | 200 OK | (메모리 + 별도 DB) |
| **`GET /api/compliance/crawl/history/stats`** | **500 FAIL** | `compliance.db` 의 `crawl_runs` 테이블 (`ensure_table` 실패) |

`Promise.all` 은 하나라도 reject되면 전체 catch로 빠지므로, 단일 endpoint 실패가 전체 페이지 오류 메시지로 노출됨.

## 5. Timeline

| 시각 | 이벤트 |
|---|---|
| (이전, 정확 시점 불명) | `data/compliance.db` 파일이 손상된 형식으로 변형 |
| 2026-05-27 03:17 | broken `compliance.db` 의 호스트 mtime 마지막 변경 |
| 2026-05-27 (시연 직전) | 사용자가 `/compliance` 진입 → 빨간 오류 메시지 확인 → 조사 요청 |
| 2026-05-27 22:35 ~ | 근본 원인 분석 시작 (docker logs / file 명령 / 파일 헤더 hex 검사) |
| 2026-05-27 22:55 ~ | `features/data/compliance.db` (15.8 MB, git tracked, 정상 SQLite) 발견 |
| 2026-05-27 23:30 | broken 파일 backup → `features/data/compliance.db` 로 복원 → 백엔드 재시작 |
| 2026-05-27 23:30 | `ensure_table()` + `stats_24h()` 직접 호출 검증 통과 |

## 6. 해결 절차 (적용된 Option A)

```bash
REACT=/Users/yeong/99_me/00_github/04_AJIN/ajin-ai-assistant-react

# 1. 백업 (롤백 보존)
cp -v "$REACT/data/compliance.db" "$REACT/data/compliance.db.broken_2026-05-27"

# 2. git tracked 정상 복사본에서 복원
cp -v "$REACT/features/data/compliance.db" "$REACT/data/compliance.db"

# 3. 무결성 검증
file "$REACT/data/compliance.db"            # → SQLite 3.x database
sqlite3 "$REACT/data/compliance.db" ".tables"            # → crawl_history, regulations
sqlite3 "$REACT/data/compliance.db" "PRAGMA integrity_check;"  # → ok

# 4. 백엔드 재시작
docker restart ajin-compliance-backend-1

# 5. 직접 함수 호출로 검증
docker exec ajin-compliance-backend-1 python -c "
from backend.services import crawl_audit
crawl_audit.ensure_table()
print(crawl_audit.stats_24h())
"
# → ensure_table: OK
# → stats_24h: {'window': '24h', 'total_runs': 0, ...}
```

`crawl_runs` 테이블은 복원된 파일에 없었으나, 코드가 `CREATE TABLE IF NOT EXISTS` 이므로 첫 호출 시 자동 생성됨 (정상 동작).

## 7. 검증 결과

| 검증 항목 | 결과 |
|---|---|
| `file data/compliance.db` | SQLite 3.x database ✅ |
| `PRAGMA integrity_check` | `ok` ✅ |
| `ensure_table()` 직접 호출 | OK ✅ |
| `stats_24h()` 직접 호출 | 정상 JSON 반환 ✅ |
| `docker exec curl http://localhost:8080/api/compliance/crawl/history/stats` | HTTP 401 (인증 헤더 없이 호출 → 정상 인증 차단. **이전엔 인증 통과 후 500이었음**) ✅ |
| 백엔드 로그 (직후 30s) | 새 에러/예외 없음 ✅ |

## 8. 예방·후속 조치

### 즉시 (이번 fix에 포함)
- ✅ `data/compliance.db.broken_2026-05-27` 백업 파일 보존 (포렌식·롤백용)
- ✅ Postmortem 문서화

### 단기 (1~2주)
- [ ] **자동 복원 헬퍼 스크립트** — `scripts/restore-compliance-db.sh` 작성 (이번 절차 자동화)
- [ ] **`crawl_audit.ensure_table()` 가드 강화** — `sqlite3.DatabaseError` 명시 catch + 의미 있는 로그 (예: "compliance.db 파일이 SQLite 포맷이 아님 — 운영자 확인 필요") + Sentry/감사 로그 적재
- [ ] **`/api/admin/system/health-extended` 에 compliance.db 무결성 체크 추가** — `PRAGMA quick_check` 호출하여 손상 조기 발견
- [ ] **Cloud Run (production) 의 `data/compliance.db` 무결성 확인** — 로컬과 다른 mount이지만 같은 코드 path이므로 같은 손상 가능성 점검

### 중기 (1개월)
- [ ] **`compliance.db` 일일 자동 백업** — Celery beat에 `dump_compliance_db_daily` 추가, `data/backup/compliance.db.YYYYMMDD` 생성, 최근 7일 보존
- [ ] **DB 쓰기 경로 직렬화** — 6개 모듈이 동시 write 시 SQLite WAL 모드 확인 (`PRAGMA journal_mode=WAL`)
- [ ] **Frontend `Promise.all` → `Promise.allSettled` 전환** — 한 endpoint 실패가 전체 페이지를 깨뜨리지 않도록 부분 실패 허용 (사용자 체감 신뢰도 향상)

### 장기 (분기)
- [ ] **D 모듈을 SQLite → PostgreSQL/Supabase로 마이그레이션** — 동시성·내구성 강화. 이미 `docker-compose.supabase.yml` 인프라 존재
- [ ] **운영 환경에서 `*.db` 파일 백업 정책 표준화** — `.gitignore`라 git이 추적하지 못하므로 별도 백업 sink 필요

## 9. 교훈 / Lessons Learned

1. **gitignored 운영 DB는 backup 정책이 없으면 잠재적 단일 장애점** — `.gitignore: data/**/*.db` 가 보안상 옳지만, 백업 sink가 없어 손상 시 복구 불가 상태가 될 뻔함. `features/data/compliance.db` 가 git에 있어서 다행이지만 이건 우연.

2. **`Promise.all` 의 함정** — 5개 API 중 1개가 실패하면 사용자에게는 "전체 페이지 깨짐"으로 보임. `Promise.allSettled` + 부분 실패 메시지가 UX 측면에서 우월.

3. **`file` 명령은 SQLite 손상 즉시 진단 도구** — 다음에 비슷한 증상이 나오면 가장 먼저 `file *.db` 로 형식 매트릭스 확인.

4. **두 코드 베이스(04_AJIN vs ajin-ai-assistant-react)의 명확한 분리 필요** — 같은 데이터 디렉토리·같은 파일명으로 두 곳 존재. 디버깅 시 매우 혼란. 운영 가이드에 명시할 것.

## 10. 참조

- 손상 파일 (포렌식용 보존): `ajin-ai-assistant-react/data/compliance.db.broken_2026-05-27`
- 정상 복원 source: `ajin-ai-assistant-react/features/data/compliance.db` (git tracked)
- 영향 받은 코드: `backend/services/crawl_audit.py:24,36`
- Frontend 호출 위치: `frontend/src/api/compliance.ts:1728` (`fetchCrawlHistoryStats`)
- Frontend 진입점: `frontend/src/routes/compliance.tsx:211`

---

*문서 작성: 2026-05-27 23:35 KST | 작성 도구: Claude Opus 4.7 | 형식: Markdown Postmortem*
