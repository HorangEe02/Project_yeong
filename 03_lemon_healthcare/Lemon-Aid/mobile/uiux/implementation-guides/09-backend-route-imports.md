# 09. 백엔드 보강 — 팀원 라우트 선별 임포트 + 일일 점수 영속화

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

대상: `user_medications` / `food_records` / `notifications` API 라우트를 팀원 워크트리에서 선별 임포트하고(P1-1), 일일 건강 점수 영속화(보류 결정 #7)의 백엔드 옵션을 정의한다. 이 문서는 백엔드 작업 가이드이며, 프런트 소비 측 작업(홈 복약 카드 P1-2, 복약 알림 P1-5, 추이 차트 P1-8)은 각 화면 가이드에서 다룬다.

- 팀원 워크트리(읽기 전용 스냅샷): `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/external/Lemon-sin-ai-agent-branch`
- 로컬 백엔드 루트: `backend/Nutrition-backend` (alembic은 `backend/alembic`)
- 경로에 공백이 있으므로 모든 셸 명령에서 **항상 따옴표**로 감싼다.

---

## ① 범위 / 목표

| 항목 | 포함 | 비고 |
|---|---|---|
| 라우트 임포트 3종 | `src/api/v1/user_medications.py`, `food_records.py`, `notifications.py` | 팀원 워크트리에 구현 존재, 로컬에 라우트 파일만 부재 |
| 의존 스키마 1종 | `src/models/schemas/notification.py` | 로컬에 없음 (user_medication/food_record 스키마는 이미 존재) |
| router 등록 | `src/api/v1/router.py`에 3줄 추가 | **로컬 슈퍼셋 보존 — 덮어쓰기 금지** |
| 팀원 테스트 동반 | 통합 3파일 + 단위 1파일 (총 12 테스트) | DB 불필요한 self-contained 테스트 |
| 점수 영속화(옵션) | `AnalysisType.DAILY_HEALTH_SCORE` + store 함수 + 대시보드 저장 훅 | 보류 결정 #7 채택 시 — P1-8 추이 차트의 선행 조건 |
| 제외 | `/auth/*`(P2, 백엔드 공백), 리워드(범위 외), 서버 푸시 발송(P2) | `notifications`는 **리마인더 설정 저장**만 — 발송 워커는 없음 |

목표 상태: 백엔드 라우트 55개 → 67개(+12 오퍼레이션), 홈 복약 카드·복약 알림 서버 동기화·오늘의 분석 4주 추이의 백엔드 선행 조건 해소.

## ② 디자인 스펙 (이 라우트를 소비하는 화면)

백엔드 문서이므로 토큰/레이아웃 상세는 화면별 가이드에 위임하고, 어떤 프레임이 어떤 라우트에 의존하는지만 고정한다 (프레임 ID: `mobile/uiux/figma/_frames_index.md`).

| figma 프레임 | 의존 라우트 | 소비 방식 |
|---|---|---|
| S-07 Main (홈) `268:24` — 복약/영양제 관리 섹션, 상호작용 주의 카드 3상태 | `GET/POST /me/medications` | '약 미등록' 기본 상태 → 등록 후 실제 약 기준 상호작용 점검 (P1-2) |
| 복약 알림 설정 `916:76` (10-④, 시간 휠 16-①) | `GET/POST/PATCH /notifications/reminders` | 로컬 알림 스케줄(P1-5)의 서버 동기화 사본 |
| 설정 · 알림 설정 `957:63` (15-②) | `PATCH /notifications/reminders/{id}`, `POST …/disable` | 토글 on/off |
| S · 알림 `761:24` / 알림 빈 `951:24` | `GET /notifications/reminders` | 알림 센터 P1은 로컬 이력, 서버 설정은 보조 |
| S-09 오늘의 분석 `800:23` — 4주 추이 라인차트 | `GET /analysis-results?analysis_type=daily_health_score` | 점수 영속화(아래 ③·④의 C 파트) 채택 시 잠금 해제 (P1-8) |
| 오늘의 기록 `947:108` (12-⑤) | `GET /me/food-records` | 수동 기록 병합 표시(보조 — 주 소스는 `GET /meals`) |

UI 구현 시 토큰은 design_tokens_v2(`AppColor`/`AppText`/`AppSpace`/`AppRadius`)만 참조 — 본 문서의 화면 작업 없음.

## ③ 현재 코드 상태

2026-06-12 기준, 팀원 워크트리와 `diff` 전수 비교로 확인한 결과다. **의존성 클로저의 대부분은 직전 백엔드 통합(커밋 `eea3be7c`·`30f56e8d`·`85124b35`) 때 이미 들어와 있다.**

### 이미 로컬에 존재 (팀원 파일과 diff 동일 — 재복사 불필요)

| 파일 (`backend/Nutrition-backend/`) | 내용 |
|---|---|
| `src/models/db/user_medication.py`, `food_record.py`, `notification.py` | ORM 3종. `src/models/db/__init__.py`에 `FoodRecord`/`ReminderPreference`/`UserMedication` export 완료 |
| `src/models/schemas/user_medication.py` | Create/Update/Response + `ALLOWED_MEDICATION_CLASSES`(16종)·`ALLOWED_CONDITION_TAGS`(8종) 화이트리스트 |
| `src/models/schemas/food_record.py` | Create/Update/Response + `ALLOWED_MEAL_TYPES`(5종)·`ALLOWED_FOOD_RECORD_SOURCES`(3종) |
| `src/services/user_medications.py`, `src/services/food_records.py` | list/create/update/deactivate(or delete) 서비스 |
| `src/api/v1/contract.py` | `P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS` 상수(라우트 3종이 import) 존재 |
| `src/api/v1/examples.py` | `UNAUTHORIZED_EXAMPLE` / `CONSENT_REQUIRED_EXAMPLE` / `UNPROCESSABLE_ENTITY_EXAMPLE` 존재 |
| `backend/alembic/versions/0031_create_reminder_preferences.py`, `0037_create_user_medications.py`, `0038_create_food_records.py` | 테이블 3종 마이그레이션 (리베이스 완료분) |
| `backend/alembic/versions/0041_harden_ai_agent_chat_table_security.py` | RLS 강화 — `HASHED_OWNER_TABLES`에 `user_medications`/`food_records`(owner_subject_hash, 0023b Type B), `PLAINTEXT_OWNER_TABLES`에 `reminder_preferences`(Type A). ENABLE+FORCE ROW LEVEL SECURITY 모두 포함 |

### 로컬에 없음 (이번에 임포트할 것)

| 파일 | 상태 |
|---|---|
| `src/api/v1/user_medications.py` | 없음 — 팀원 파일 그대로 복사 가능 |
| `src/api/v1/food_records.py` | 없음 — 〃 |
| `src/api/v1/notifications.py` | 없음 — 〃 (서비스 함수가 라우트 파일에 내장돼 있어 별도 services 파일 불필요) |
| `src/models/schemas/notification.py` | 없음 — `ReminderCategory`(4종)·`FORBIDDEN_REMINDER_TERMS` 금칙어 검증 포함 |
| `src/api/v1/router.py` 등록 | 로컬 router에 3종 미등록. **로컬에는 `meals`·`medical_records`가 있고 팀원 router에는 없음** → 팀원 router.py를 복사하면 라우트 2종이 증발한다. 반드시 수동 3줄 추가 |
| 테스트 4파일 | `tests/integration/api/test_user_medications_api.py`(3) / `test_food_records_api.py`(3) / `test_notifications_api.py`(4) / `tests/unit/services/test_food_records.py`(2) — 로컬에 전무 |

### 점수 영속화 관련 (C 파트)

- `src/models/schemas/analysis_result.py` — `AnalysisType`은 현재 `ACTIVITY_SCORE`/`WEIGHT_PREDICTION`/`NUTRITION_ANALYSIS` 3종. `DAILY_HEALTH_SCORE` 없음
- `src/services/analysis_results.py` — `_persist_result()` 공통 영속화 + `store_activity_score_result()` 등 store 3종(인용 패턴)
- `src/services/daily_health_score.py` — `DAILY_HEALTH_SCORE_ALGORITHM_VERSION = "daily-health-score-v1.0.0"`, `build_daily_health_score()`는 계산만 하고 저장 안 함
- `src/services/dashboard.py` — `build_dashboard_summary()`가 `build_daily_health_score()` 호출 후 응답에 포함. 저장 훅 없음
- `GET /analysis-results`(`src/api/v1/analysis_results.py`)는 이미 `analysis_type` 쿼리 필터·`limit(≤100)`·`offset` 지원 — 조회 측 추가 작업 없음

### 운영 전제

⚠️ 마이그레이션 0030~0041은 **리포에는 있으나 라이브 DB에 아직 미적용**(2026-06-11 세션 기준 체인 검증만 완료). 모든 수동 검증 전에 `alembic upgrade head` 선행 필수.

## ④ 구현 단계

작업 디렉토리 변수 (예시):

```bash
EXT="/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/external/Lemon-sin-ai-agent-branch/backend/Nutrition-backend"
LOC="/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/Nutrition-backend"
```

### A. 라우트 선별 임포트 (P1-1)

1. [ ] **사전 동결 확인** — 팀원 워크트리와 로컬의 공유 의존 파일이 여전히 동일한지 재확인 (드리프트 가드):
   ```bash
   for f in src/models/schemas/user_medication.py src/models/schemas/food_record.py \
            src/services/user_medications.py src/services/food_records.py \
            src/models/db/user_medication.py src/models/db/food_record.py src/models/db/notification.py; do
     diff -q "$LOC/$f" "$EXT/$f" || echo "DRIFT: $f"
   done
   ```
   DRIFT가 나오면 복사 전에 내용 비교 후 **로컬 우선**으로 판단(로컬 슈퍼셋 보존 원칙).
2. [ ] `src/models/schemas/notification.py` 복사 (`$EXT` → `$LOC`)
3. [ ] `src/api/v1/user_medications.py` / `food_records.py` / `notifications.py` 3파일 복사
4. [ ] **`src/api/v1/router.py` 수동 편집** (파일 교체 금지 — 로컬에만 있는 `meals`·`medical_records` 보존):
   - import 블록에 `food_records, notifications, user_medications` 3개 추가 (알파벳 순 유지)
   - `api_router.include_router(...)` 3줄 추가:
     ```python
     api_router.include_router(notifications.router)
     api_router.include_router(food_records.router)
     api_router.include_router(user_medications.router)
     ```
5. [ ] 의존 클로저 검증 — import만으로 닫히는지 확인:
   ```bash
   cd "/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend" \
     && .venv/bin/python -c "from src.api.v1.router import api_router; print(len(api_router.routes))"
   ```
   (PYTHONPATH에 `Nutrition-backend`와 `ai_agent_chat/src` 필요 — 기존 pytest 설정과 동일 조건)
6. [ ] 팀원 테스트 4파일 복사:
   - `tests/integration/api/test_user_medications_api.py` — CRUD current-user 스코핑 / 동의 403 / **원본 OCR·용량 필드 거부**(스키마가 `extra="forbid"`) 3건
   - `tests/integration/api/test_food_records_api.py` — CRUD / 동의 403 / 미확정 필드 거부 3건
   - `tests/integration/api/test_notifications_api.py` — CRUD / 동의 403 / disable 후 dispatch 제외 / **금칙어(진단·치료·처방) 거부** 4건
   - `tests/unit/services/test_food_records.py` — 한국어 음식명 태그 추정 / snapshot v1 미래 필드 nullable 2건
   - 모두 `app.dependency_overrides` + `monkeypatch` 기반(가짜 세션·동의 no-op) — 라이브 DB 불필요, 수정 없이 통과해야 정상
7. [ ] (DB 검증 시) `alembic upgrade head` 첫 실행 → `\d user_medications` 등으로 0041 FORCE RLS 정책(`lemon_app_owner_rw`) 적용 확인

### B. 신규 라우트 동작 확인 (수동 스모크 — 선택)

- `uvicorn src.main:app --port 8000` 기동 후 `GET /openapi.json`에서 `/api/v1/me/medications`·`/api/v1/me/food-records`·`/api/v1/notifications/reminders` 노출 확인
- 동의 미부여 토큰으로 `POST /api/v1/me/medications` → 403 `consent_required` 응답 형식 확인 (⑥ 참조)

### C. 일일 점수 영속화 (보류 결정 #7 — 채택 시에만)

기존 `analysis_results` 패턴을 그대로 따른다. 단, 기존 store 3종과 달리 **요청 본문으로 계산하는 게 아니라 대시보드가 이미 계산한 결과를 저장**하는 형태다.

1. [ ] `src/models/schemas/analysis_result.py` — `AnalysisType`에 추가:
   ```python
   DAILY_HEALTH_SCORE = "daily_health_score"
   ```
   ⚠️ **마이그레이션 필요(0042)** — 컬럼은 문자열이지만 `analysis_results`에 `ck_analysis_results_analysis_type_allowed` CHECK 제약(0002에서 3종 고정)이 있어, 제약을 4종으로 재생성하는 마이그레이션과 ORM `__table_args__`의 CheckConstraint 갱신이 함께 필요하다. (2026-06-12 구현: `0042_allow_daily_health_score_analysis_type.py` — downgrade는 daily_health_score 행 삭제 후 구 제약 복원)
2. [ ] `src/services/analysis_results.py` — `store_daily_health_score_result()` 추가. `algorithm_version`은 `daily_health_score.DAILY_HEALTH_SCORE_ALGORITHM_VERSION`(현 `daily-health-score-v1.0.0`) 재사용, `input_snapshot`은 `{summary_date, weights}` 수준, `result_snapshot`은 `health_score` 블록 직렬화 그대로.
   - ⚠️ **트랜잭션 주의**: 기존 `_persist_result()`는 `async with session.begin()`을 연다. `GET /dashboard/summary` 경로는 같은 세션으로 이미 SELECT를 수행(autobegin)한 뒤라 `session.begin()`이 충돌한다. 대시보드 훅에서 쓸 store 함수는 `session.add()` + `commit()` 방식(팀원 `notifications.py` 서비스 함수와 동일 패턴)으로 작성하거나, `_persist_result`에 트랜잭션 개시 여부 분기를 추가할 것.
3. [ ] `src/services/dashboard.py` — `build_dashboard_summary()`에서 `health_score = await build_daily_health_score(...)` 직후 저장 호출(옵션 플래그 뒤에):
   - `data_status == "not_ready"`면 **저장 금지** (점수 날조 금지 원칙의 영속 버전)
   - **1일 1회 중복 가드**: 같은 owner의 당일(`summary_date`) `daily_health_score` 행이 이미 있으면 skip (대시보드는 호출 빈도가 높음 — 무가드 시 행 폭증)
   - settings 플래그(예: `persist_daily_health_score: bool = False`)로 켜고 끌 수 있게 — 기본 off로 들어가면 회귀 리스크 없음
4. [ ] 조회는 기존 라우트 그대로: `GET /analysis-results?analysis_type=daily_health_score&limit=28` → S-09 4주 추이(P1-8). `result_snapshot.score`/`label`/`created_at`만 사용.
5. [ ] 테스트: not_ready 미저장 / 당일 중복 미생성 / 저장 행의 `algorithm_version`·`analysis_type` 검증 / `message`·`label_text` 금칙어 부재 assert(기존 daily_health_score 테스트 관례 따름)

## ⑤ 엔드포인트 계약 표

> ApiClient 표기 규칙: baseUrl에 `/api/v1`이 포함되므로 아래 경로는 접두사 제거 형태. 모든 라우트 401 응답 공통.
> ⚠️ 플랜 문서의 "DELETE user-medications" 표현과 달리 **실제 구현은 hard DELETE가 없고 `deactivate`(소프트 삭제)다.**

### user-medications (`/me/medications`)

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| GET `/me/medications` | — | `items[]`: `id`, `display_name`, `normalized_name?`, `medication_class?`, `condition_tags[]`, `confirmation_status`, `is_active`, `last_confirmed_at` | sensitive_health_analysis / analysis:read |
| POST `/me/medications` (201) | `display_name`(≤160 필수), `normalized_name?`, `medication_class?`(화이트리스트 16종: `statin`·`warfarin`·`diabetes_medication`·`other` 등), `condition_tags[≤8]`(화이트리스트 8종: `hypertension`·`diabetes` 등), `is_active`(기본 true) | `UserMedicationResponse` 단건 | sensitive_health_analysis / analysis:write |
| PATCH `/me/medications/{medication_id}` | 위 필드 전부 optional(부분 갱신) | 〃 / 404 `user_medication_not_found` | 〃 |
| POST `/me/medications/{medication_id}/deactivate` | (본문 없음) | `is_active=false`인 단건 / 404 | 〃 |

### food-records (`/me/food-records`) — 수동 식단 기록(카메라 `meals` 파이프라인과 별도 보조 채널)

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| GET `/me/food-records` | query: `date_from?`, `date_to?`, `limit`(기본 50), `offset` | `items[]`: `id`, `recorded_date`, `meal_type`, `display_items[]`, `amount_text?`, `source`, `match_confidence?`, `nutrient_estimates?` | sensitive_health_analysis / analysis:read |
| POST `/me/food-records` (201) | `recorded_date`(필수), `meal_type`(`breakfast`/`lunch`/`dinner`/`snack`/`extra`), `display_items[1..12]`(필수), `amount_text?`, `estimated_tags?[≤16]`, `user_confirmed`(기본 true), `source`(`manual`/`food_user_input`/`food_ocr_confirmed`), `food_db_match_id?`, `match_confidence?`(0~1), `nutrient_estimates?` | `FoodRecordResponse` 단건 | sensitive_health_analysis / analysis:write |
| PATCH `/me/food-records/{food_record_id}` | 위 필드 전부 optional | 〃 / 404 `food_record_not_found` | 〃 |
| DELETE `/me/food-records/{food_record_id}` | — | 204 No Content / 404 | 〃 |

### notifications (`/notifications/reminders`) — 리마인더 **설정 저장**(발송 워커 없음, 클라이언트 로컬 알림이 실행 주체)

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| GET `/notifications/reminders` | — | `items[]`: `id`, `category`, `time_of_day`, `timezone`, `enabled`, `message`, `disabled_at?` | (동의 불필요) / analysis:read |
| POST `/notifications/reminders` (201) | `category`(`supplement_reminder`/`meal_check_in`/`daily_coaching_prompt`/`safety_follow_up`), `time_of_day`(`HH:MM`, 00–23시 검증), `timezone`(기본 `Asia/Seoul`), `enabled`(기본 true), `message`(1~240자, **금칙어 서버 검증 내장**), `metadata{}` | `ReminderPreferenceResponse` 단건 | sensitive_health_analysis / analysis:write |
| PATCH `/notifications/reminders/{reminder_id}` | 위 필드 optional (`enabled=false` 시 서버가 `disabled_at` 기록) | 〃 / 404 `reminder_not_found` | 〃 |
| POST `/notifications/reminders/{reminder_id}/disable` | (본문 없음) | `enabled=false` 단건 / 404 | 〃 |

### 점수 영속화 (기존 라우트 — C 파트 채택 시 타입만 추가)

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| GET `/analysis-results` | query: `analysis_type=daily_health_score`, `limit`(≤100), `offset` | `results[]`: `id`, `analysis_type`, `algorithm_version`, `created_at` (스냅샷 본문은 단건 조회) | sensitive_health_analysis / analysis:read |
| GET `/analysis-results/{result_id}` | — | `result_snapshot`(health_score 블록: `score`, `label`, `label_text`, `message`, `source_citations[]`) | 〃 |

## ⑥ 상태 / 에러 처리

백엔드 응답 계약과 프런트 소비 규칙(상세 UI는 각 화면 가이드의 StatusStateView·모달 템플릿 활용):

| 상황 | 백엔드 응답 | 프런트 처리 |
|---|---|---|
| 동의 미부여 | 403 `{"detail": {"code": "consent_required", "message": …, "required_consents": ["sensitive_health_analysis"]}}` + 차단 감사 이벤트 기록 | `chat_repository.dart`(`mobile/lib/features/chat/chat_repository.dart`)의 기존 패턴 재사용: 동의 시트 1회 표출 → `POST /me/privacy/consents/sensitive_health_analysis` → 원요청 1회 재시도 |
| 미인증 | 401 | 토큰 화면 유도 (P2 auth 전까지 dev 토큰) |
| 검증 실패 | 422 (사유: `medication_class`/`condition_tags` 화이트리스트 밖, `meal_type` 비허용, `time_of_day` 형식, **리마인더 message 금칙어**) | 입력 필드 인라인 에러 (해요체: "지원하지 않는 분류예요" 등 — 서버 영문 메시지 그대로 노출 금지) |
| 대상 없음 | 404 안정 코드: `user_medication_not_found` / `food_record_not_found` / `reminder_not_found` | 목록 재조회 + 토스트 ("이미 삭제된 항목이에요") |
| 빈 목록 | 200 `{"items": []}` | StatusStateView 빈 상태 변형 (홈 복약 카드는 '약 미등록' 3상태 중 기본 상태) |
| 네트워크/5xx | — | StatusStateView 실패 변형 + 재시도 CTA |
| 점수 `not_ready` | `health_score.score = null`, `data_status="not_ready"` | 점수 미표시·기록 유도 placeholder (영속화 시에도 **저장 안 함**) |

의료 안전 계약: 리마인더 `message`는 서버 스키마(`FORBIDDEN_REMINDER_TERMS`: 진단·처방·치료 + 영문 동의어)가 금칙어를 거부한다. 프런트 기본 문구도 권유형 해요체로 작성한다 (예: "영양제 챙길 시간이에요"). 신뢰도 % 직접 노출 금지(등급 칩)·분석 화면 하단 면책 푸터 규칙은 이 라우트를 소비하는 모든 화면에 동일 적용.

## ⑦ 테스트 계획

### 백엔드 (이번 작업의 검증 게이트)

1. [ ] **임포트 테스트 12개 통과** — 복사한 4파일 우선 실행:
   ```bash
   cd "/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend" \
     && .venv/bin/python -m pytest \
        "Nutrition-backend/tests/integration/api/test_user_medications_api.py" \
        "Nutrition-backend/tests/integration/api/test_food_records_api.py" \
        "Nutrition-backend/tests/integration/api/test_notifications_api.py" \
        "Nutrition-backend/tests/unit/services/test_food_records.py" -q -o addopts=""
   ```
2. [ ] **전체 스위트 회귀** — `.venv/bin/python -m pytest Nutrition-backend/tests -q -o addopts=""`. 허용 실패 = **사용자 WIP 2건만**(.mcp.json supabase 테스트, OCR readiness). 신규 실패 0건이 게이트 (2026-06-11 기준 2017 통과 → 2029+ 기대)
3. [ ] `ruff check` 변경 파일 클린 (복사 파일 포함 — 팀원 코드도 로컬 ruff 설정으로 재검사)
4. [ ] **의료법 금칙어 가드** — `test_reminder_text_avoids_medical_diagnosis_treatment_or_prescription` 통과 유지. 점수 영속화(C) 시 `result_snapshot` 내 `message`/`label_text` 금칙어(진단/처방/치료/효능) 부재 assert를 신규 테스트에 동반
5. [ ] **RLS 회귀(0041 패턴)** — 새 테이블 3종은 0041에 이미 정책 적용 대상으로 포함됨(`user_medications`/`food_records`=hashed Type B, `reminder_preferences`=plaintext Type A). 추가 마이그레이션 불필요. `alembic upgrade head` 후 정책 존재(`lemon_app_owner_rw`, FORCE RLS)를 psql로 1회 확인하고, 기존 RLS 관련 테스트 무회귀 확인
6. [ ] `ai_agent_chat` 패키지 129 통과(10 skip) 유지 — router 변경이 챗 라우트에 영향 없는지

### 모바일 (후속 가이드 소관 — 여기서는 계약 고정만)

- P1-2/P1-5 위젯 테스트는 위 ⑤ 계약 표의 필드명을 기준으로 작성 (fixture JSON을 이 표와 일치시켜 드리프트 방지)
- 금칙어 가드: 신규 사용자 문구 추가 시 부재 assert 동반 (P1 체크리스트 공통 규칙)

## ⑧ 플랫폼 노트 (Pixel 10 Pro · Android 17 / iPhone 17 Pro · iOS 26.5)

- **dev 스택**: `uvicorn src.main:app --port 8000` (PYTHONPATH에 `ai_agent_chat/src` 포함 — 베어메탈 실행 시 환경변수 필요). **최초 1회 `alembic upgrade head`(0030~0041) 선행** — 미적용 시 신규 라우트가 500(테이블 없음)
- **Android 에뮬레이터**: `--dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` — debug 전용 cleartext loopback 오버레이 적용 완료(`784687ce`), release 차단 유지(`release_security_config_test` 게이트)
- **iOS 시뮬레이터**: `http://127.0.0.1:8000/api/v1` — ATS `NSAllowsLocalNetworking=true` 확인됨
- **리마인더의 실행 주체는 클라이언트 로컬 알림**(P1-5): Android `POST_NOTIFICATIONS` 런타임 권한 + 정확한 알람 정책, iOS 로컬 알림 권한(한국어 목적 문구). 서버 `reminder_preferences`는 설정의 동기화 사본이며 푸시 발송 없음 — 기기 변경 시 복원 용도
- `timezone` 기본 `Asia/Seoul` — 기기 시간대와 다를 수 있으므로 클라이언트가 명시 전송 권장

## ⑨ 완료 기준 (DoD)

- [ ] 신규 파일 8개만 추가(라우트 3 + 스키마 1 + 테스트 4), `router.py` 3줄 등록 — **기존 로컬 파일 덮어쓰기 0건**(특히 router.py의 `meals`/`medical_records` 보존), git diff로 확인
- [ ] `GET /openapi.json`에 12개 신규 오퍼레이션 노출 + 각 라우트의 `route_contract` 메타(scopes/consents/`p1_7_ai_agent_daily_coaching_ready`) 정상
- [ ] 임포트 테스트 12개 통과 + 전체 스위트 신규 실패 0건(허용 실패 = 사용자 WIP 2건) + ruff 클린
- [ ] `alembic upgrade head` 성공, 신규 테이블 3종 FORCE RLS 정책 확인
- [ ] 동의 게이트 수동 스모크: 동의 없는 토큰 → 403 `consent_required` → 동의 후 재시도 성공 (차단/성공 감사 이벤트 기록 확인)
- [ ] (C 채택 시) `AnalysisType.DAILY_HEALTH_SCORE` + store 함수 + 대시보드 훅(기본 off 플래그·not_ready 미저장·당일 1회 가드) + 테스트 동반, `GET /analysis-results?analysis_type=daily_health_score` 조회 확인
- [ ] (C 미채택 시) 본 문서 C 파트를 "보류 유지"로 갱신하고 P1-8을 차단 상태로 표시
- [ ] 커밋 분리: ① 라우트 임포트+테스트 ② router 등록 ③ (옵션) 점수 영속화 — 직전 백엔드 통합과 동일한 경로 단위 가져오기 관례 유지
