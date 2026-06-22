# 24. P1-6 HealthKit and Health Connect Sync

> 상태: 구현 완료 | 기준일: 2026-05-12 | 범위: 모바일 헬스 데이터 일별 집계 sync, 서버 저장, 동의/audit, 대시보드 연결

## 1. 현재 상태

P1-1에서 준비한 `health_sync_batches`, `health_daily_summaries` 테이블과 ORM 모델을 `POST /api/v1/health/sync` 저장 API에 연결했다. P1-5 대시보드는 `health_daily_summaries`를 읽어 활동·체중 summary에 반영한다.

P1-6 구현으로 `501 p1_contract_stub`를 제거했고, 모바일에서 HealthKit 또는 Health Connect로 읽은 일별 집계값을 현재 사용자 owner 범위에 저장한다. 저장 API는 `health_device_data` 동의, `health:write` scope, idempotent retry, audit 기록, mass assignment 차단을 포함한다.

## 2. 공식 문서 기반 전제

1. **HealthKit은 사용자 권한과 데이터 타입별 권한이 필수다.**
   Apple은 HealthKit 사용 전 capability 활성화, 사용 가능 여부 확인, `HKHealthStore` 생성, 데이터 접근 권한 요청 단계를 요구한다. 앱은 `NSHealthShareUsageDescription` 같은 사용 설명도 제공해야 한다.
   출처: https://developer.apple.com/documentation/healthkit/setting-up-healthkit

2. **HealthKit read 권한 거부 여부는 앱이 직접 알 수 없다.**
   Apple은 privacy 보호를 위해 사용자가 읽기 권한을 거부했는지 앱이 알 수 없고, 앱 관점에서는 해당 타입 데이터가 없는 것처럼 보인다고 설명한다. 따라서 P1-6은 “0”과 “권한 거부/데이터 없음”을 구분하려고 추정하지 않는다.
   출처: https://developer.apple.com/documentation/healthkit/protecting_user_privacy

3. **Health Connect는 aggregate API를 우선 사용한다.**
   Android Health Connect는 `aggregate`, `aggregateGroupByPeriod`, `aggregateGroupByDuration`로 집계 읽기를 제공한다. Activity/Sleep aggregate는 사용자가 지정한 앱 우선순위에 따라 중복 데이터가 dedupe될 수 있다.
   출처: https://developer.android.com/health-and-fitness/guides/health-connect/develop/aggregate-data

4. **Health Connect는 기본적으로 권한 부여 이전 30일까지만 읽을 수 있다.**
   더 오래된 데이터나 백그라운드 읽기는 별도 권한 선언이 필요하다. P1-6은 foreground sync와 최근 30일 기본 동작을 우선한다.
   출처: https://developer.android.com/health-and-fitness/health-connect/data-types

5. **Flutter `health` 패키지는 HealthKit과 Health Connect wrapper다.**
   현재 pub.dev 최신 문서 기준 `health` 패키지는 Apple HealthKit과 Google Health Connect를 지원하고, Google Fit API는 deprecated로 안내한다. P1-6 구현 시 프로젝트의 `health` 의존성 버전은 최신 호환 버전으로 재확인한다.
   출처: https://pub.dev/packages/health

## 3. 브레인스토밍 결정

### 3.1 저장 경계

- 서버에는 원천 이벤트 전체를 저장하지 않는다.
- 모바일에서 일별 aggregate로 만든 값만 전송한다.
- 저장 대상은 `steps`, `weight_kg`, `resting_heart_rate_bpm`, `active_energy_kcal` 네 가지로 제한한다.
- 심박 원천 샘플, 운동 route, 위치, 수면 stage, 혈당, 혈압, 생리/민감 주기 데이터는 P1-6 범위에서 제외한다.

### 3.2 모바일 집계 방식

- iOS는 HealthKit 읽기 권한을 요청한 뒤 일별 집계를 만든다.
- Android는 Health Connect aggregate API 또는 `health` 패키지 wrapper를 통해 일별 집계를 만든다.
- Android는 Health Connect 기본 history 제한을 고려해 첫 sync 기본 범위를 최근 30일로 둔다.
- 앱 활성화 시 foreground sync만 수행한다. 백그라운드 sync는 P2 이후 별도 권한과 배터리 정책 검토 후 진행한다.
- 권한 거부, Health Connect 미설치, 데이터 없음은 수동 입력 폴백으로 보낸다.

### 3.3 서버 API 방향

기존 frozen endpoint를 유지한다.

```http
POST /api/v1/health/sync
```

요청은 기존 `records` 중심 구조를 유지하되, 구현 시 다음 선택 필드를 추가한다.

| 필드 | 위치 | 목적 |
|---|---|---|
| `client_batch_id` | request top-level | 모바일 retry/idempotency |
| `records[].measured_date` | record | 사용자 로컬 날짜 |
| `records[].source_platform` | record | `ios_healthkit`, `android_health_connect`, `manual` |
| `records[].steps` | record | 일별 걸음수 |
| `records[].weight_kg` | record | 해당 일자의 대표 체중 |
| `records[].resting_heart_rate_bpm` | record | 안정시 심박 또는 일별 대표 resting HR |
| `records[].active_energy_kcal` | record | 활동 에너지 kcal |
| `records[].source_record_hash` | record optional | 클라이언트 중복 감지용 hash |

응답은 기존 `HealthSyncResponse`의 `accepted_count`, `rejected_count`, `synced_at`을 유지한다. 필요하면 `batch_id`는 optional field로 추가하되 기존 클라이언트가 깨지지 않게 한다.

### 3.4 검증 정책

- `records`는 1개 이상 366개 이하.
- 각 record는 최소 하나의 metric이 있어야 한다.
- 미래 날짜는 거부한다. 사용자 로컬 날짜 기준 오차를 고려해 서버 날짜 + 1일까지 허용할지 구현 시 선택한다.
- `steps`: 0-200,000.
- `weight_kg`: 20-300.
- `resting_heart_rate_bpm`: 20-240.
- `active_energy_kcal`: 0-20,000.
- request body와 하위 schema는 `extra="forbid"`로 mass assignment를 차단한다.
- `owner_subject`, `synced_at`, `accepted_count`, `rejected_count`는 서버가 계산한다.

### 3.5 Idempotency와 upsert

- `client_batch_id`가 없으면 일반 sync로 처리한다.
- `client_batch_id`가 있으면 `owner_subject + client_batch_id`로 batch 재시도를 식별한다.
- 같은 batch id와 같은 request fingerprint면 기존 batch 결과를 반환한다.
- 같은 batch id지만 record count, date range, source distribution, metric presence가 다르면 `409 idempotency_conflict`로 막는다.
- `health_daily_summaries`는 `owner_subject + measured_date + source_platform` 기준으로 upsert한다.
- 기존 row가 있으면 새 값으로 교체한다. 부분 업데이트 병합은 P1-6에서는 하지 않고 record snapshot을 해당 날짜/platform의 최신 aggregate로 본다.

### 3.6 Audit와 동의

- `health_device_data` 동의가 없으면 저장하지 않고 `health_sync_blocked` audit event를 남긴다.
- 성공 시 `health_sync_completed` audit event를 남긴다.
- audit metadata에는 raw metric 값이 아니라 count, date range, source platform distribution, accepted/rejected count만 저장한다.
- 삭제 요청 all-user-data 경로는 이미 `health_daily_summaries`, `health_sync_batches` 삭제 count를 포함해야 하며 P1-6 테스트에서 재확인한다.

## 4. 보안 평가

| 위험 | 평가 | 대응 |
|---|---|---|
| HealthKit/Health Connect 데이터의 민감성 | 높음 | raw sample 미저장, 일별 aggregate만 저장 |
| 권한 거부와 데이터 없음 혼동 | 중간 | 0으로 추정하지 않고 missing/null을 유지 |
| Mass assignment | 높음 | `extra="forbid"`, owner는 JWT에서만 생성 |
| Replay/idempotency 충돌 | 중간 | `client_batch_id` fingerprint 검증, 불일치 409 |
| 과거 데이터 과다 전송 | 중간 | records max 366, P1 모바일 기본 30일 |
| Dashboard 정보 노출 | 중간 | owner-scoped 조회와 `sensitive_health_analysis` 동의 유지 |
| 광고/제3자 사용 오해 | 높음 | 앱 UI와 privacy text에서 분석 목적과 미제공 원칙 명시 |

## 5. 상세 구현 결과

### Phase 1. Contract/schema 정리

1. `backend/src/api/v1/contract.py`
   - `P1_6_HEALTH_SYNC_READY_STATUS = "p1_6_health_sync_ready"` 추가 완료.

2. `backend/src/models/schemas/health.py`
   - `HealthSyncRequest.client_batch_id: str | None` 추가 완료.
   - `HealthDailyAggregate.source_record_hash: str | None` 추가 완료.
   - `ConfigDict(extra="forbid", str_strip_whitespace=True)` 적용 완료.
   - model validator로 “최소 1개 metric 존재”와 서버 UTC 날짜 + 1일 초과 미래 날짜 거부 적용 완료.
   - `HealthSyncResponse.batch_id: UUID | None` optional field 추가 완료.

3. `backend/src/api/v1/examples.py`
   - iOS HealthKit 예시와 Android Health Connect 예시 분리 완료.
   - 409 idempotency conflict 예시 추가 완료.

### Phase 2. Service 구현

1. `backend/src/services/health_sync.py` 신규 생성 완료.
2. 함수 책임:
   - `sync_health_daily_aggregates(session, user, request) -> HealthSyncResult`
   - owner_subject 생성.
   - idempotency fingerprint 생성.
   - existing batch 충돌 확인.
   - daily summary upsert.
   - batch row 저장.
   - accepted/rejected count 산출.
3. snapshot 정책:
   - `input_snapshot`: `date_min`, `date_max`, `record_count`, `source_platform_counts`, `metric_presence_counts`, `request_fingerprint`.
   - `result_snapshot`: `accepted_count`, `rejected_count`, `upserted_count`, `skipped_count`.
   - metric raw value는 batch snapshot에 넣지 않는다.

### Phase 3. API route stub 제거

1. `backend/src/api/v1/health.py`
   - `contract_stub` import 제거 완료.
   - `AsyncSession`, `Request`, `Settings` dependency 추가 완료.
   - `require_user_consent(..., ConsentType.HEALTH_DEVICE_DATA)` 호출 완료.
   - `record_sensitive_audit_event` 성공/차단 기록 완료.
   - service 호출 결과를 `HealthSyncResponse`로 변환 완료.
   - `openapi_extra`에 `contract_status=P1_6_HEALTH_SYNC_READY_STATUS` 적용 완료.
   - 501 response 제거, 409 response 추가 완료.

### Phase 4. Dashboard 연결 회귀 확인

1. P1-5 dashboard service는 이미 `HealthDailySummary`를 읽는다.
2. P1-6 구현 후 sync한 `steps`, `weight_kg`, `resting_heart_rate_bpm`, `active_energy_kcal`가 dashboard read model에서 사용 가능하도록 service helper를 보강했다.
3. dashboard API 응답은 활동 card에 `latest_resting_heart_rate_bpm`, `latest_active_energy_kcal`를 optional field로 노출한다.
4. dashboard read 동의는 `sensitive_health_analysis`, health sync 동의는 `health_device_data`로 분리 유지한다.

### Phase 5. 모바일 구현 계획

1. `mobile/lib/features/health/domain/health_data.dart`
   - `HealthDailyAggregate`, `HealthSyncRequest`, `HealthSyncResponse` 모델 정의.

2. `mobile/lib/features/health/data/health_repository.dart`
   - `health` 패키지 wrapper.
   - `configure`, permission request, availability check.
   - iOS/Android platform 분기.

3. `mobile/lib/features/health/data/health_sync_service.dart`
   - 최근 30일 aggregate 수집.
   - `client_batch_id` 생성.
   - `POST /api/v1/health/sync` 호출.
   - retry는 같은 `client_batch_id`로 수행.

4. iOS 설정
   - HealthKit capability 활성화.
   - `NSHealthShareUsageDescription` 작성.
   - P1-6은 read-only로 시작하므로 `NSHealthUpdateUsageDescription`은 쓰기 기능을 구현하지 않으면 요구하지 않는다.

5. Android 설정
   - Health Connect 권한 선언.
   - Play Console Health apps declaration 준비.
   - background/history permission은 P1-6에서 제외하거나 별도 feature flag로 둔다.

6. UI
   - health consent screen에서 수집 항목, 목적, 보관 방식, 철회 방법을 명시.
   - 권한 거부/데이터 없음/Health Connect 미설치 상태를 구분해 표시.
   - 수동 입력 fallback 제공.

### Phase 6. 테스트

1. Unit service tests
   - valid sync inserts batch and summaries.
   - duplicate same `client_batch_id` returns existing result.
   - duplicate different payload returns service conflict.
   - same owner/date/platform upserts existing row.
   - dashboard helper exposes synced resting HR and active energy.

2. API integration tests
   - missing `health_device_data` consent -> 403 and audit.
   - valid sync -> 202 and DB rows.
   - mass assignment field -> 422.
   - idempotency conflict -> 409.

3. Contract/OpenAPI tests
   - `/api/v1/health/sync` has `x-contract-status: p1_6_health_sync_ready`.
   - required scope is `health:write`.
   - required consent is `health_device_data`.
   - examples include iOS/Android sync requests and conflict.

4. Dashboard regression
   - dashboard helper returns latest steps, resting HR, active energy, and weight summary from `HealthDailySummary`.

5. Privacy deletion regression
   - all-user-data deletion removes `health_daily_summaries`, `health_sync_batches` and records only counts.

### Phase 7. 검증 명령

```bash
cd yeong-Lemon-Aid/backend
./.venv/bin/python -m pytest -o addopts='' \
  tests/unit/services/test_dashboard.py \
  tests/unit/services/test_health_sync.py \
  tests/unit/services/test_privacy.py \
  tests/integration/api/test_health_sync_api.py \
  tests/integration/api/test_p1_api_contract.py \
  tests/integration/api/test_openapi_examples.py

./.venv/bin/python -m pytest
./.venv/bin/python -m ruff check src tests
./.venv/bin/python -m mypy src
```

검증 결과:

- targeted P1-6 회귀: 24 passed in 1.09s.
- 전체 백엔드 테스트: 193 passed, 1 skipped in 3.73s, coverage 89.47%.
- Ruff: `All checks passed!`.
- mypy: `Success: no issues found in 74 source files`.

## 6. 완료 기준

- `POST /api/v1/health/sync`가 501을 반환하지 않는다.
- 인증된 현재 사용자 기준으로만 health summary가 저장된다.
- `health_device_data` 동의 없이는 저장되지 않는다.
- 같은 batch retry가 중복 row를 만들지 않는다.
- 같은 날짜/platform 재동기화가 dashboard 최신 summary에 반영된다.
- raw HealthKit/Health Connect event는 서버에 저장하지 않는다.
- 전체 백엔드 테스트와 lint/type check가 통과한다.

## 7. 후속 단계

1. P2에서 background sync와 Health Connect history permission을 별도 승인 흐름으로 검토한다.
2. P2에서 HealthKit observer query 또는 Android background read는 앱 심사/배터리 정책을 확인한 뒤 feature flag로 분리한다.
3. P2에서 운동 세션, 수면, 혈당/혈압은 사용자 가치와 규제 리스크를 다시 평가한 뒤 별도 scope/consent로 확장한다.
