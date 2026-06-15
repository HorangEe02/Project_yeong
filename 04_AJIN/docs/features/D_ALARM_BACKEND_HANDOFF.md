# AJIN D 모듈(컴플라이언스) 실시간 알람 백엔드 — 구현·검증 완료 기록

> **상태**: ✅ 구현 완료(PR #39) · ✅ E2E 검증 완료 · ✅ 보조 통로 갭 1건 수정 완료
> **갱신일**: 2026-05-30
> **대상 코드베이스**: 중첩 git 저장소 `ajin-ai-assistant-react/` (자체 `.git`, branch `main`).
>   ※ 상위 `04_AJIN/backend`·`04_AJIN/features` 의 옛 사본이 아님. 모든 경로는 `ajin-ai-assistant-react/` 기준.

---

## 0. TL;DR (이 문서의 핵심)
- 본래 핸드오프는 "D 알람 백엔드 **신설**"을 가정했으나, 실제로는 **이미 구현되어 main 에 머지됨**:
  `43a53ec docs+feat(compliance): AJIN 종합 평가 + D 모듈 incident 완전 해결 (P1-P4) (#39)`.
- "푸시 모델 A/B" 의사결정은 무의미 — **A(백엔드→RTDB) + B(폴링) + SSE 의 상위집합**이 모두 구현됨.
- 2026-05-30 세션에서 **E2E 검증을 수행**(실데이터로 알람 생성→집계→ack→dispatch→전달 통로 확인, 커밋된 테스트 17/17 통과, 프론트 `tsc -b` 통과).
- 검증 중 **실제 갭 1건(중요도: 중)** 발견 → **수정 완료**: 보조 "RTDB" 통로의 D 프로듀서가 유휴 상태였음.

---

## 1. 실제 구현된 아키텍처 (검증된 file:line)

### 1-1. 백엔드 — 집계 → 전달
- **집계기** `features/compliance/alerts/alarm_aggregator.py`
  - `collect_recent_alarms()` (L529): 5종 소스 통합 → `ComplianceAlarm[]`.
    소스 1 `law_change` / 2 `impact_score`(시나리오 점수 ≥80) / 3 `dday`(시행일 D-30 이내) /
    4 `unresolved`(action_required 7일+) / 5 `trend`(28일 대비 2σ 급증).
  - `mark_acknowledged()` (L586): `compliance_alarm_acks` 테이블에 ack 영속(멱등).
  - `refresh_all_scenario_scores()` (L127): `scenario_impact_scores` 캐시 재계산(TTL 1h).
  - ※ 모듈 docstring(L5-6) 은 소스 2·4·5 를 "Phase 3 활성 예정"으로 적었으나 **코드는 5종 모두 실행**(문서-코드 드리프트, 무해).
- **REST/SSE 라우트** `backend/routers/compliance.py` (`/api` 프리픽스)
  - `GET /api/compliance/alarms/recent` (L4359) → `collect_recent_alarms`.
  - `POST /api/compliance/alarms/{id}/ack` (L4387, role≥3) → `mark_acknowledged`.
  - `GET /api/compliance/alarms/stream` (L4404, SSE) → 주기적 `collect_recent_alarms`.
  - `POST /api/compliance/alarms/refresh-scenario-scores` (L4457, role≥5).
- **표준 live_alarms 통로(Firebase RTDB 대체)** `backend/services/live_events.py`
  - Postgres/SQLite `live_alarms` 테이블. `insert_alarm(payload, domain=...)` (L84) / `list_recent_alarms(domain=...)` (L150) / `acknowledge_alarm` (L200).
  - 라우터 `backend/routers/live_alarms.py`: `GET /api/live-alarms/recent` (L47) / `POST /api/live-alarms/{id}/ack` (L68). `main.py:533` 에서 `/api` 마운트.
- **D dispatch 파이프라인** `features/compliance/d1_alert/pipeline.py`
  - `dispatch_compliance_alarms_to_rtdb()` (L89): 집계 알람을 신규분만 전달, dedup 상태 `data/_d1_alert_rtdb_pushed.db`.
- **Firebase RTDB writer** `backend/services/firebase_rtdb.py`
  - `push_alarm(payload, path="/live_alarms")` (L108). `FIREBASE_WRITE_ENABLED=true` + 자격증명 있을 때만 실제 write, 기본은 dry-run capture(비용 차단).
- **Celery beat** `backend/celery_app.py`
  - `compliance_alarm_dispatch` (L84, 매 `*/5`분) → `dispatch_compliance_alarms_to_rtdb`.
  - `compliance_scenario_scores` (L76, 매일 03:15 KST) → 점수 재계산.
- **스키마** `backend/schemas/compliance_alarm.py`: `ComplianceAlarm`(module 고정 "D"), `*Response`, `*AckResponse`.

### 1-2. 프론트 — 소비
- 1차 통로(REST/SSE): `useComplianceAlarms`(`GET /api/compliance/alarms/recent`) / `useComplianceAlarmsSse`(`/alarms/stream`), `VITE_COMPLIANCE_ALARMS_SSE` 로 토글. `frontend/src/api/compliance.ts:1768` `fetchComplianceAlarms` / `ackComplianceAlarm`.
- 2차 통로(통합 live_alarms): `useComplianceRTDB` → `GET /api/live-alarms/recent?domain=compliance` 폴링 후 `module==='D'` 필터(`frontend/src/api/liveAlarms.ts:19`).
- 대시보드 `frontend/src/routes/dashboard.tsx`: 1차+2차 id 기준 dedup 머지(L238-241), `topAlarm.module==='D'` → `/compliance` 라우팅.
- 전용 페이지 `frontend/src/routes/compliance.tsx`: 알람 테이블 + ack UI.

---

## 2. E2E 검증 결과 (2026-05-30, 실데이터)
실데이터(`data/compliance_changes.db` 사본, 32 미확인 변경 + 시나리오 점수 SCN-001=88/SCN-002=83)로 실제 프로덕션 코드 경로 실행:

| 검증 | 결과 |
|---|---|
| `collect_recent_alarms()` (실데이터) | **37건** (law_change 32 / impact_score 2 / unresolved 2 / dday 1) · sev HIGH 18·MED 13·CRIT 6 |
| ack → 재집계 | `acknowledged=True` 로 반영 ✓ |
| `dispatch_…to_rtdb()` | run1 push 37 → run2 push 0/skip 37 (dedup) ✓ |
| RTDB/live_alarms payload | `module="D"` + 필수 5필드(severity·title·detail·module·timestamp, `database.rules.json` 계약) ✓ |
| 커밋된 단위/통합 테스트 | `tests/test_compliance_alarm_aggregator.py` **17/17 통과** |
| 프론트 타입체크 | `frontend` `tsc -b` **통과(exit 0)** |

미실행(사유): 실제 Firebase RTDB write(기본 dry-run, 비용 차단 설계) / 전체 FastAPI HTTP 부팅(무거운 의존성 — FlagEmbedding ~600MB, python3-saml/xmlsec). 라우트는 검증된 함수의 얇은 래퍼.

---

## 3. 발견·수정한 갭 (중요도: 중) — ✅ 수정 완료
**증상**: 2차 통로 `useComplianceRTDB` 는 `GET /api/live-alarms/recent?domain=compliance`(Postgres `live_alarms` 테이블)를 읽는데, 그 테이블에 `insert_alarm` 을 호출하는 곳이 **F SPC(`features/equipment/plc_ingest.py:244`)뿐**이었다. D dispatch 는 `firebase_rtdb.push_alarm`(다른 저장소, 기본 dry-run)만 호출 → **D 프로듀서가 표준 통로에 부재 → 2차 통로 유휴**. (대시보드는 1차 REST/SSE 통로로 D 알람을 표시하므로 사용자 영향은 낮았으나, 코드 주석의 "F SPC 와 동일 통로" 의도가 D 에는 미실현.)

**수정** (`features/compliance/d1_alert/pipeline.py`):
- dispatch 루프가 집계 알람을 **`live_events.insert_alarm(payload, domain="compliance", source_system="d1_alert")`** 로 표준 `live_alarms` 테이블에 기록(권위 통로). Firebase `push_alarm` 은 best-effort 로 유지.
- payload 에 `id`(=안정 alarm_id, upsert PK) + `message` 추가 → 멱등 upsert(중복 row 방지).
- 표준 통로 insert 실패 시 dedup 표시 안 함 → 다음 run 재시도.

**수정 검증** (실데이터 + 신규 테스트):
- 실데이터 dispatch → `live_alarms[domain=compliance]` **37 row** = `useComplianceRTDB` module=='D' 필터 후 **37건**(sev CRIT 6·HIGH 18·MED 13). `domain=equipment` 필터엔 0건(누수 없음). 2차 dispatch 시 row 중복 0(멱등). → **PASS**.
- 신규 테스트 `tests/test_d1_alert_dispatch.py`(3건) + 기존 17건 = **20/20 통과**.

---

## 4. 남은 선택적 후속 (필요 시)
- **실시간 운영 활성화**: 프로덕션에서 `live_alarms` 가 Postgres(Alembic 생성)면 별도 작업 불필요. Firebase RTDB 까지 쓰려면 `FIREBASE_WRITE_ENABLED=true` + 자격증명.
- **콘텐츠 변경 재푸시**: 현재 dedup 은 `alarm.id` 기준이라 동일 알람의 severity 상향(예: D-day 임박) 시 재푸시 안 됨(기존 설계 그대로). 필요하면 content-hash dedup 으로 확장.
- **HTTP 스모크/브라우저 E2E**: 전체 스택 부팅이 필요하면 alarm 라우터만 마운트한 최소 FastAPI 앱으로 가능.

## 5. 재현 방법
- 핵심 로직만 빠르게: 최소 venv(`pydantic`, 테스트엔 `pytest`, live_alarms 엔 `sqlalchemy`)로 무거운 `features.compliance.__init__`(LLM/크롤러 스택)을 `sys.modules` 스텁으로 우회해 실제 모듈 실행. (본 세션 검증 하네스 패턴.)
- 정식: 전체 의존성 설치 후 `pytest tests/test_compliance_alarm_aggregator.py tests/test_d1_alert_dispatch.py tests/test_live_events.py`.

## 6. 작업 규칙/컨벤션
- **커밋**: Conventional Commits + 한글 설명. `타입(스코프): 설명`(예: `fix(backend-compliance): D dispatch 를 live_alarms 표준 통로에 연결`). 끝에 Co-Authored-By 트레일러 유지.
- **브랜치**: `ajin-ai-assistant-react` 의 main 에서 분기한 feature 브랜치. 커밋/푸시는 사용자가 요청할 때만.
- **재사용 원칙**: F 모듈(SPC) 패턴 재사용(이번 수정은 `plc_ingest` 의 `insert_alarm(domain=...)` 패턴을 D 에 대칭 적용).
- **검증 우선**: 완료 주장 전 검증 근거 수집(작성/검토 패스 분리, self-approve 금지).
