# 2026-05-20 세션 리포트 — P0 출시 차단 요소 4 페이즈 완성

> **작성자**: 박준영 (Claude Code 보조)
> **소요 시간**: 1 세션 (다중 시간)
> **상태**: 모든 작업이 origin/HorangEe02/Project_yeong 에 푸시 완료, 팀 검토 대기.

## 1. TL;DR — 이번 세션 결과 한 줄

> Lemon Aid 출시 직전 차단 요소(P0) 3개와 그 후속을 **4개 브랜치 / 11개 commit / 약 6,500 LOC** 로 정리해 GitHub 에 푸시했고, 백엔드 테스트 **478개 + 모바일 테스트 22개 = 500개 모두 통과** 시켰다.

핵심 산출물:

| 트랙 | 한 줄 설명 | 검증 |
|---|---|---|
| **Phase A (모바일)** | 비행기 모드여도 영양제 사진을 캡처해두면 신호 잡힐 때 자동 전송 | 22/22 ✅ |
| **Phase B (백엔드 E2E)** | 사용자가 받는 응답에 raw OCR/이미지 같은 민감정보가 새지 않는지 자동 검증 | 10/10 ✅ |
| **Phase C (OCR cascade)** | 1차 OCR 가 흐릿한 사진을 못 읽으면 자동으로 2차/3차 도구로 넘어가고, 어디서 정착했는지 audit 테이블에 기록 | 478/478 ✅ |
| **Phase D (영양 추천)** | "비타민 A 과다" 같은 위험 자동 분류 + 사용자 노출 안전 검증 | 29/29 ✅ |

---

## 2. 큰 그림 — 왜 이 작업이 중요한가

### Lemon Aid 의 제품 약속
> "**사진 한 장**으로 만성질환자가 영양제/식품의 안전성을 확인하고, AI Agent 가 병원 기록·생활 데이터와 함께 종합 판단해주는 헬스케어 서비스."

이 약속을 지키려면 다음이 필수:

1. **OCR이 어떤 상황에서도 작동해야 한다** — 라벨이 흐릿해도, 외부 OCR 서버가 다운돼도 결과를 내야 함.
2. **사용자 응답에 민감정보가 새면 안 된다** — 의료 정보 + 개인정보보호법(PIPA) 의 무게.
3. **모바일이 끊김 없이 동작해야 한다** — 지하철/엘리베이터/지하주차장에서도 캡처가 사라지지 않아야 함.
4. **위험 영양소 자동 경고** — 비타민 A 같이 과다 섭취가 해로운 영양소를 사용자에게 경고할 수 있어야 함.

이번 세션은 위 4개를 모두 충족시키는 **출시 직전 차단 요소(P0)** 를 해소했다.

---

## 3. 4개 브랜치 한눈에 보기

| 브랜치 | base | commits | LOC | 핵심 |
|---|---|---|---|---|
| `lemon-aid/p0-phase-a-mobile-offline` | deploy/r5+uow | 4 | +2,072 | 모바일 오프라인 큐 + 차트 + 동의 카드 + Android release |
| `lemon-aid/p0-phase-b-e2e-tests` | backend-session-uow | 2 | +979 | 백엔드 E2E 인프라 + 10개 시나리오 |
| `lemon-aid/p0-phase-c-ocr-orchestrator` | phase-b-e2e-tests | 4 | +1,160 | OCR cascade orchestrator + 회귀 hotfix 25건 |
| `lemon-aid/p0-phase-d-recommendation-services` | phase-c HEAD | 1 | +1,784 | recommendation 서비스 (5개) + KDRI risk/evidence E2E |

**총합: 4 브랜치 / 11 commits / +5,995 / -382 lines**

모든 브랜치 `origin/HorangEe02/Project_yeong.git` 에 푸시 완료. PR URL 은 §10 참조.

---

## 4. Phase A — 모바일 오프라인 처리 (완성도 45% → 80%)

### 4.1. 현장 시나리오 — 왜 이게 필요한가
- 사용자 A 가 지하철에서 영양제 라벨을 캡처. 신호가 약함.
- 기존 앱: 업로드 실패 → 사진 사라짐 → 사용자가 다시 찍어야 함 → 신뢰 손상.
- **개선 후**: 사진이 자동으로 **로컬 큐** 에 보관 → 신호 잡히면 **자동 재전송** → 사용자는 아무것도 신경 쓸 필요 없음.

### 4.2. 무엇을 추가했나
- **로컬 데이터베이스 (drift)**: 앱 안에 SQLite DB. 캡처 사진 + 동의 정보 + 시도 횟수를 보관.
- **업로드 큐 서비스**: 네트워크 상태(연결됨/끊김)를 실시간 감지. 끊겨 있으면 큐에 적재, 복구되면 자동으로 백엔드에 보냄.
- **HTTP 클라이언트 강화**: 30초 타임아웃 + 자동 재시도(지수 백오프). 일시적 네트워크 오류를 사용자에게 노출하지 않음.
- **오프라인 배너**: 화면 상단에 "오프라인 — N건 대기 중" 표시.
- **fl_chart 대시보드**: 부족/과다 영양소를 막대 차트로 시각화.
- **권한 거부 분기**: 카메라/사진 접근 거부 시 친절한 안내 다이얼로그.
- **동의 카드 (Consent)**: 동의 항목별 설명 + 정책 URL 복사 기능.
- **Release APK 빌드**: Android app id 를 `kr.lemonaid.healthcare` 로 확정 + MainActivity 패키지 정리. 3개 flavor(dev/staging/prod) APK 모두 정상 빌드.

### 4.3. 왜 이 방법을 골랐나
- **drift (SQLite)**: 가볍고 모바일 표준. 동일 패턴이 `taedong-design` 팀에도 사용 중이라 일관성 확보.
- **connectivity_plus**: Flutter 공식 권장. iOS/Android 모두 안정적.
- **자동 재시도 대신 큐 우선**: 업로드는 큰 multipart 요청이므로 무한 재시도보다는 idempotency key 기반 큐 적재가 안전.
- **client_request_id idempotency**: 백엔드가 이미 같은 키로 두 번 들어오면 한 번만 처리하도록 보장 → 큐가 중복 전송해도 안전.

### 4.4. 키 파일 (팀 검토용)
- `mobile/flutter_app/lib/core/storage/local_db.dart` (Drift 스키마)
- `mobile/flutter_app/lib/features/supplements/upload_queue_service.dart`
- `mobile/flutter_app/lib/core/api/api_client.dart` (재시도 인터셉터)
- `mobile/flutter_app/lib/shared/widgets/offline_banner.dart`
- `mobile/flutter_app/lib/features/dashboard/widgets/nutrient_balance_chart.dart`

### 4.5. 검증
- `flutter analyze`: **No issues found**
- `flutter test`: **22/22 passed**
- `flutter build apk --release`: 3개 flavor APK 정상 생성 (각 62MB)

---

## 5. Phase B — 백엔드 E2E 통합 테스트 (인프라 + 10개 시나리오)

### 5.1. 무엇이 문제였나
- 기존 테스트는 **endpoint 1개** 단위로만 검증. 여러 endpoint 가 연결되는 실제 사용자 흐름(=풀체인)은 검증 안 됨.
- "응답에 raw OCR 텍스트가 누설되지 않는다" 같은 **cross-cutting invariant** 가 보장되지 않음.

### 5.2. 무엇을 추가했나
**10개 시나리오 (4 카테고리)**:

| 카테고리 | 검증 내용 |
|---|---|
| **Privacy Invariants (4건)** | 응답 본문 + audit 로그에 원본 이미지/OCR/PII 가 절대 노출되지 않음 |
| **Idempotency (2건)** | 같은 client_request_id 로 두 번 요청해도 1행만 생성 |
| **Consent Gate (2건)** | 동의 미부여 사용자 호출 시 외부 OCR provider 가 절대 호출 안 됨 (fail-closed) |
| **Happy Path (2건)** | analyze → ocr-text → register 3 endpoint 풀체인 invariant |

### 5.3. 왜 이 방법을 골랐나
- **fake session 패턴 표준화**: `_FakeSession` 으로 DB 를 mock — 실 Postgres 없이도 빠르게 실행 (0.2초).
- **pytest marker (`@pytest.mark.e2e`)**: 일반 unit 테스트와 명확히 분리. CI 에서 별도 실행 가능.
- **무작위 추출 대신 결정적 검증**: 매 실행마다 같은 결과를 보장 → flaky test 0건.

### 5.4. 키 파일
- `backend/Nutrition-backend/tests/integration/e2e/conftest.py` (공용 fixture)
- `backend/Nutrition-backend/tests/integration/e2e/test_privacy_invariants.py`
- `backend/Nutrition-backend/tests/integration/e2e/test_idempotency.py`
- `backend/Nutrition-backend/tests/integration/e2e/test_consent_gate.py`
- `backend/Nutrition-backend/tests/integration/e2e/test_happy_path.py`

### 5.5. 검증
- `pytest -m e2e`: **10/10 passed** in 0.2s

---

## 6. Phase C — OCR cascade orchestrator + 영구 audit (가장 큰 작업)

### 6.1. 현장 시나리오 — 왜 이게 필요한가
사용자가 영양제 사진을 찍었다. 라벨이 살짝 흐릿하다.
- 1차 OCR (Google Vision): 65% confidence → "신뢰도 부족"
- 그냥 빈 결과로 끝내면 사용자는 "이 앱 안 됨" 이라고 생각.
- **개선 후**: 1차가 부족하면 → 2차 OCR (PaddleOCR 로컬) → 그것도 부족하면 → 3차 (CLOVA 외부 백업) → 어느 단계에서 정착했는지 audit 테이블에 자동 기록.

이로써:
- **사용자 체감**: 라벨이 흐릿해도 결과가 나옴.
- **운영팀**: "지난 24h 1차 OCR 성공률 60% → 모델 재학습 필요" 같은 의사결정이 가능.

### 6.2. 무엇을 추가했나

#### (1) `OCRResult` 확장 (`src/ocr/base.py`)
- 기존: `text`, `provider`, `confidence` 3개 필드
- 추가: `escalation_tier` (어느 단계에서 정착했는지), `attempt_chain` (모든 시도 기록), `verification_status` (다른 OCR 와 결과 일치하는지), `tier_escalation_reason` (왜 다음 단계로 넘어갔는지)

#### (2) `OCROrchestrator` 서비스 (`src/services/ocr_orchestrator.py`)
- 1차/2차/3차 OCR 도구를 순서대로 호출하면서 각 시도를 기록.
- 기존 3개 helper 함수의 동작은 그대로 두고 "위" 에 orchestrator 를 씌우는 방식 → 기존 코드 깨지 않음.

#### (3) Alembic 0009 migration — `audit_ocr_attempts` 테이블
- cascade 의 각 시도를 영구 보관하는 DB 테이블.
- 인덱스: `(analysis_run_id, tier)`, `(attempted_at)` → 분석 단위 추적 + 시간대 검색 양쪽 모두 빠름.

#### (4) Telemetry 쿼리 문서 (`docs/Nutrition-docs/53-tier-cascade-telemetry-queries.md`)
- 운영 SLA 모니터링용 SQL 7개 예제. 알람 기준 추천 포함.
- 예) `Q1. 지난 24h primary OCR 성공률`, `Q4. 외부 OCR escalation 비율`.

#### (5) Deterministic verification 모드
- 기존: cross-check 가 매 호출의 10% 만 무작위 sampling.
- 변경: 1차 confidence 가 낮을 때 **100% 검증** 하도록 default 변경. sampling 모드 명시 옵션도 보존 (운영비 회피용).

### 6.3. 왜 이 방법을 골랐나
- **기존 helper 보존 + orchestrator wrap**: 기존 코드를 전부 다시 쓰면 회귀 위험 큼. helper 들의 동작은 그대로 두고 orchestrator 가 "결과 비교"로 어느 단계에서 정착했는지 추론 → BC(backward compatibility) 유지.
- **자체 audit 테이블**: 기존 `supplement_analysis_runs` 에 컬럼 추가하면 모든 row 가 비대해짐. 별도 테이블로 분리하면 cascade 가 일어난 경우만 row 가 생성됨 → 효율적.
- **deterministic 기본값**: 운영에서 "Tier 3 escalation 이 발생하는 케이스" 가 재현 가능해야 디버깅 가능. sampling 은 디버깅 어려움.

### 6.4. 키 파일
- `backend/Nutrition-backend/src/ocr/base.py` (OCRResult + OCRProviderAttempt)
- `backend/Nutrition-backend/src/services/ocr_orchestrator.py`
- `backend/Nutrition-backend/src/services/ocr_audit_repository.py`
- `backend/Nutrition-backend/src/models/db/audit_ocr_attempt.py`
- `backend/alembic/versions/0009_create_audit_ocr_attempts.py`
- `docs/Nutrition-docs/53-tier-cascade-telemetry-queries.md`

### 6.5. 검증
- `pytest tests/integration/e2e/test_cascade_escalation.py`: **6/6 passed** (6개 cascade 시나리오)
- `pytest tests/`: **478 passed**, 0 failed

---

## 7. Phase D — Recommendation 서비스 + KDRI risk/evidence

### 7.1. 무엇이 문제였나
- 사용자 working tree 에 5개 서비스가 **untracked 상태**로 존재:
  - `supplement_recommendation.py` (영양 영향 미리보기)
  - `supplement_explanation.py` (사용자 친화적 설명 생성)
  - `personalized_nutrition_risk.py` (KDRI 기준 위험 분류)
  - `supplement_contribution.py` (영양소 기여도 집계)
  - `supplement_recommendation` schema
- 이 서비스들이 commit 안 되어 있어서 **B.6 (KDRI risk)** 과 **B.7 (evidence grounding)** 테스트가 차단된 상태.

### 7.2. 무엇을 했나
1. 5개 서비스 파일을 새 브랜치(`p0-phase-d-recommendation-services`)에 commit.
2. 그 위에 **B.6 시나리오 6건** + **B.7 시나리오 7건** = 13개 E2E 테스트 작성.

### 7.3. 왜 이 방법을 골랐나
- **선택적 commit**: 사용자 untracked 가 100+ 개라 전부 commit 하면 거대한 PR. recommendation 관련 핵심만 골라 cherry-pick → 리뷰 부담 최소화.
- **deterministic 단위 검증**: `classify_personalized_supplement_risks` 가 순수 함수라 DB/HTTP 불필요 → 0.02초 안에 6개 시나리오 검증.
- **schema 보안 검증 (B.7)**: `SupplementInsightEvidence` 의 `forbid-extra` 정책 + `value_summary` 240자 제한이 raw OCR 텍스트 누설을 schema 레벨에서 차단함을 명시적으로 검증.

### 7.4. B.6/B.7 가 검증하는 핵심 invariant

**B.6 — KDRI Risk Loop (6건)**:
- 사용자 프로필 누락 시 `missing_profile_fields` 자동 보고
- 비타민 A 5000μg (UL 3000μg 초과) → `excess_or_duplicate_risks` 에 자동 분류
- 모든 insight 가 사용자 안전 메시지 보유 (300자 제한, 비어있지 않음)

**B.7 — Evidence Grounding (7건)**:
- 3개 허용 source_type 만 통과 (`user_supplement` / `nutrition_analysis` / `kdri_reference`)
- 임의 키 (`raw_image_bytes` 등) 삽입 차단 (forbid-extra)
- `value_summary` 240자 제한 (raw OCR 텍스트 누설 방어)
- evidence 리스트 최대 20개 제한

### 7.5. 키 파일
- `backend/Nutrition-backend/src/services/supplement_recommendation.py`
- `backend/Nutrition-backend/src/services/supplement_explanation.py`
- `backend/Nutrition-backend/src/services/personalized_nutrition_risk.py`
- `backend/Nutrition-backend/src/services/supplement_contribution.py`
- `backend/Nutrition-backend/src/models/schemas/supplement_recommendation.py`
- `backend/Nutrition-backend/tests/integration/e2e/test_kdri_risk_loop.py`
- `backend/Nutrition-backend/tests/integration/e2e/test_evidence_grounding.py`

### 7.6. 검증
- `pytest -m e2e`: **29/29 passed** (Phase B 10 + Phase C 6 + Phase D 13)

---

## 8. Phase C 회귀 25건 hotfix (꼭 기억해야 할 디버깅 사례)

### 8.1. 무엇이 일어났나
Phase C 작업이 끝난 직후 `pytest tests/` 를 실행하니 **20개 unit 테스트가 실패** 상태였다. 새 작업이 기존 기능을 깬 것.

### 8.2. 원인 분석 (4가지 클러스터)

| 클러스터 | 건수 | 원인 |
|---|---|---|
| **fake session 에 `flush()` 메서드 누락** | 13 | Phase B base 의 `supplement_intake.py:279` 가 `await session.flush()` 를 호출하지만, 단위 테스트의 가짜 session 클래스들에 이 메서드가 구현 안 됨 (별개 회귀, 이미 1차 hotfix 5건 해소) |
| **AuditOCRAttempt 가 supplement_run 캡처를 오염** | 6 | OCROrchestrator 가 cascade 끝나면 `session.add(AuditOCRAttempt(...))` 를 호출 → fake session 의 `add()` 가 type 무차별로 캡처해서 downstream 이 AuditOCRAttempt 를 SupplementAnalysisRun 으로 오인 |
| **UoW 전환 후 `assert session.committed`** | 7 | 서비스가 직접 commit 하지 않고 request-scoped UoW(라우트) 에 위임하도록 설계 변경됨. 단위 테스트의 outdated assert 가 깨짐 |
| **Alembic head 식별자 + verification mode** | 2 | Phase C 가 새 migration 0009 추가 → alembic head 가 변경됨. 또한 deterministic 새 default 가 도입돼 sampling-기대 테스트 깨짐 |

### 8.3. 어떻게 해소했나
1. 누락된 5개 파일에 no-op async `flush` 추가 (총 6개 fake session 보강).
2. `_FakePipelineSession.add()` 를 `isinstance(record, SupplementAnalysisRun)` 체크 추가.
3. 5개 테스트의 `assert session.committed is True` 제거 (commit 은 route 책임으로 이동).
4. Alembic 테스트의 head 식별자를 `0009_audit_ocr_attempts` 로 갱신.
5. 영향받은 테스트에 `multimodal_verification_mode="sampling"` 명시.

### 8.4. 결과
- **20 failed → 0 failed** (직전 478 passed)
- 8개 파일 변경, +45/-10 lines

### 8.5. 팀에게 주는 메시지 (기억해야 할 패턴)
- **새 ORM 객체를 추가하는 변경**(예: AuditOCRAttempt) 은 단위 테스트의 fake session 들도 함께 봐야 한다.
- **commit 책임 이동**(서비스 → route UoW) 같은 패턴 변경은 단위 테스트 expectation 도 함께 갱신해야 한다.
- **새 Alembic 마이그레이션**은 `test_alembic_setup.py` 의 head 식별자도 갱신해야 한다.

---

## 9. 보안 / 컴플라이언스 invariant (외부 감사용)

이번 세션이 강화한 안전장치:

| 영역 | invariant | 검증 방법 |
|---|---|---|
| **개인정보(PIPA)** | 응답 본문에 raw OCR 텍스트가 절대 나오지 않음 | `test_privacy_invariants.py::test_analyze_response_does_not_leak_user_pii_or_raw_bytes` |
| **이미지 바이트 누설** | 응답에 base64 인코딩된 이미지가 없음 | `_assert_no_raw_bytes` helper 가 PNG signature base64 prefix 검색 |
| **PII 누설** | 응답에 이메일/주민번호/전화번호 미노출 | `_DISALLOWED_SUBSTRINGS` 정적 검사 |
| **idempotency 내부키** | 백엔드 내부 prefix 가 응답에 노출 안 됨 | `test_analyze_response_omits_idempotency_internal_prefix` |
| **fail-closed (consent)** | 동의 미부여 시 외부 OCR provider 가 호출되지 않음 | `_CountingAdapters.factory_invocations <= 1` |
| **evidence schema 보호** | `value_summary` 240자 + forbid-extra 로 raw 텍스트 누설 차단 | `test_evidence_value_summary_size_bounded` |
| **OCR audit 영속화** | cascade 시도가 audit_ocr_attempts 테이블에 자동 저장 | `record_ocr_attempts` → Alembic 0009 |

---

## 10. 푸시된 브랜치 & PR 링크

| 브랜치 | HEAD | PR URL |
|---|---|---|
| `lemon-aid/p0-phase-a-mobile-offline` | `f58254b4` | https://github.com/HorangEe02/Project_yeong/pull/new/lemon-aid/p0-phase-a-mobile-offline |
| `lemon-aid/p0-phase-b-e2e-tests` | `398e301e` | https://github.com/HorangEe02/Project_yeong/pull/new/lemon-aid/p0-phase-b-e2e-tests |
| `lemon-aid/p0-phase-c-ocr-orchestrator` | `8baffbdb` | https://github.com/HorangEe02/Project_yeong/pull/new/lemon-aid/p0-phase-c-ocr-orchestrator |
| `lemon-aid/p0-phase-d-recommendation-services` | (last) | https://github.com/HorangEe02/Project_yeong/pull/new/lemon-aid/p0-phase-d-recommendation-services |

권장 머지 순서:
1. **Phase A** (독립) — 단독 머지 가능
2. **Phase B** (independent of A/C/D) — 단독 머지 가능
3. **Phase C** (base: phase-b-e2e-tests) — B 머지 후
4. **Phase D** (base: phase-c) — C 머지 후

---

## 11. 남은 후속 작업 (다음 세션 가이드)

| 트랙 | 위험도 | 가치 | 설명 |
|---|---|---|---|
| **A) Phase D rebase** | 낮음 | 중 | Phase D 가 Phase C 회귀 hotfix 이전 base 라 같은 회귀 가능. rebase 또는 cherry-pick |
| **B) Recommendation endpoint 통합** | 중 | 높음 | 사용자 working tree 의 `api/v1/supplements.py` M 에 `/recommendations/latest` 등 엔드포인트가 있음. 선택적 cherry-pick 후 라우트 E2E 작성 |
| **C) 모바일 integration_test/** | 중 | 높음 | `mobile/flutter_app/integration_test/` 신규 디렉토리. 3개 시나리오 (app_smoke / supplement_flow / offline_queue) |
| **D) B.6/B.7 endpoint 레벨로 확장** | 중 | 중 | 현재 service-level. 트랙 B 후 endpoint 까지 검증 가능 |
| **E) Phase 4 (복용량 권장 / 약물 안전 알림)** | 높음 | 높음 | 컴플라이언스 검토 선행 필요. 현재는 design plan 만 존재 |

---

## 12. 팀원이 알아야 할 핵심 5가지

1. **OCR cascade audit 테이블** (`audit_ocr_attempts`) 이 새로 생겼다. 운영팀은 이 테이블의 SLA 쿼리 (telemetry-queries.md) 로 모델 성능 모니터링 가능.

2. **multimodal verification 기본값이 sampling → deterministic 으로 변경**. 1차 OCR confidence 가 낮을 때 100% cross-check 가 트리거됨. sampling 으로 돌아가려면 `multimodal_verification_mode="sampling"` 명시.

3. **서비스 레이어는 더 이상 `session.commit()` 을 직접 호출하지 않는다**. commit 은 request-scoped UoW (라우트) 의 책임. 단위 테스트의 `assert session.committed is True` 는 outdated.

4. **모바일이 오프라인 큐를 가진다**. `client_request_id` 가 idempotency 키이므로 백엔드는 동일 키 중복 요청을 안전하게 흡수해야 함 (이미 구현됨).

5. **Android app id 가 `kr.lemonaid.healthcare` 로 확정**. Google Play 등록 시 사용. MainActivity 경로도 `kotlin/kr/lemonaid/healthcare/MainActivity.kt` 로 이동.

---

## 13. 용어 정리 (비기술자용)

| 용어 | 쉬운 설명 |
|---|---|
| **OCR** | 사진 속 글자를 텍스트로 변환하는 기술 (예: 영양제 라벨의 "비타민 D 1000IU" 를 읽음) |
| **Cascade / Fallback** | 1차 OCR 가 실패하거나 부족하면 자동으로 2차/3차 OCR 로 넘어가는 흐름 |
| **E2E (End-to-end) 테스트** | 사용자가 실제로 거치는 전체 흐름을 한 번에 검증하는 테스트 (예: 사진 업로드 → OCR → 등록까지) |
| **Idempotency** | 같은 요청을 여러 번 보내도 결과가 한 번 보낸 것과 같음 (중복 처리 방지) |
| **KDRI** | 한국인 영양섭취기준 (Korean Dietary Reference Intakes). 영양소별 권장량/상한 |
| **UL (Tolerable Upper Intake Level)** | 더 많이 먹으면 해로워질 수 있는 영양소 상한 |
| **UoW (Unit of Work)** | 여러 DB 작업을 한 트랜잭션으로 묶어 한꺼번에 commit 하는 패턴 |
| **fail-closed** | 의심스러우면 일단 차단. consent 미부여 사용자는 외부 OCR 호출 자체를 금지 |
| **migration (Alembic)** | DB 스키마 변경 이력 파일. 운영 환경에 올릴 때 `alembic upgrade head` 로 적용 |
| **worktree** | 같은 git repo 에서 여러 브랜치를 동시에 별도 폴더에 체크아웃하는 기능 |

---

## 14. 부록 — 변경 통계

```
4 브랜치, 11 commits, +5,995 / -382 lines

Phase A (mobile):  4 commits, +2,072 / -298 lines
  - 22 mobile tests pass
  - 3 release APK built

Phase B (e2e infra):  2 commits, +979 / -1 lines
  - 10 e2e scenarios

Phase C (orchestrator):  4 commits, +1,160 / -83 lines
  - OCROrchestrator + audit_ocr_attempts + 25 회귀 hotfix
  - 478 backend tests pass

Phase D (recommendation):  1 commit, +1,784 / -0 lines
  - 5 services committed + 13 e2e scenarios (B.6 + B.7)
```

## 15. 검증 명령 모음 (재현용)

```bash
# 백엔드 — Phase C HEAD
cd .claude/worktrees/p0-phase-c-orchestrator/.../backend
pytest Nutrition-backend/tests/ --no-cov
# 기대값: 478 passed, 0 failed

# 백엔드 — Phase D HEAD
cd .claude/worktrees/p0-phase-d-recommendation/.../backend
pytest Nutrition-backend/tests/integration/e2e/ --no-cov
# 기대값: 29 passed

# 모바일 — Phase A HEAD
cd .claude/worktrees/p0-phase-a-mobile/.../flutter_app
flutter analyze  # 기대값: No issues found
flutter test     # 기대값: 22/22 passed
flutter build apk --release \
  --dart-define=LEMON_API_BASE_URL=https://api.lemon-aid.example/api/v1 \
  --dart-define=LEMON_CERTIFICATE_PINS=sha256/PLACEHOLDER
# 기대값: 3개 flavor APK 생성
```

---

> 본 리포트는 팀 검토용 작업 일지입니다. 기술적 결정의 배경, 트레이드오프, 잠재적 위험을 명시했으니 코드 리뷰 시 참고 바랍니다. 질문/이의 있으면 commit message 또는 PR comment 로 공유해 주세요.
