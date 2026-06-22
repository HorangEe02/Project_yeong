# M-3-V.C — 오류 시나리오 e2e 검증 (자동 4 + 매뉴얼 2)

> Track D Phase M-3-V.C — supplement/register 에 대한 backend ↔ mobile 오류 e2e
> 검증. 모바일 측 `_mapDioError` 9 case (단위 테스트 통과) 중 e2e 가능한 6 case 를
> 다룬다. 자동화 가능한 4는 shell script, 시뮬레이터 필요한 2는 매뉴얼.

---

## 0. 매핑 표 — 9 매핑 → 검증 방법

| # | DioException / status | 한국어 메시지 | 검증 방법 |
|---|---|---|---|
| 1 | connection/send/receive Timeout | `네트워크 연결이 느립니다. Wi-Fi 환경에서 시도해주세요.` | (단위 테스트로 충분) |
| 2 | 400 | `이미지 형식 또는 크기에 문제가 있습니다.` | (단위 테스트로 충분) |
| 3 | **401** | `다시 로그인해주세요.` | **자동 — Case 2** |
| 4 | **403 (consent_required)** | `필요한 동의를 다시 확인해주세요.` | **매뉴얼 — Manual 2** |
| 5 | 422 | `영양제 정보를 인식하지 못했습니다. 다른 사진으로 시도해주세요.` | (단위 테스트로 충분) |
| 6 | **429** | `잠시 후 다시 시도해주세요. (분당 요청 한도 초과)` | **자동 — Case 1** |
| 7 | **500/502/503/504** | `서버 오류입니다. 잠시 후 다시 시도해주세요.` | **자동 — Case 3** |
| 8 | **DioException (no status)** | `예상치 못한 오류가 발생했습니다.` | **자동 — Case 4** (connection refused) |
| 9 | **권한 거부 (non-Dio)** | (다이얼로그 — `_showPermissionDeniedDialog`) | **매뉴얼 — Manual 1** |

---

## 1. 자동 4 case — shell script

### 1.1 사전 조건
- backend `uvicorn` 가동 (port 8000)
- Postgres + Redis docker compose healthy
- 유효한 access JWT (`TOKEN` env)
- 영양제 라벨 fixture 1장 (`FIXTURE` env, default: `tests/fixtures/supplement_labels/local-multivitamin-0001.jpg`)
- `ENVIRONMENT=development` (script 가 BASE_URL localhost 강제 가드)

### 1.2 실행
```bash
cd 03_lemon_healthcare/yeong-Vision-Nutrition/backend

# 토큰 발급 (예시 — 실 경로는 backend auth flow 따름)
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"secret"}' \
    | jq -r .access_token)
export TOKEN

# (선택) 만료 토큰 — Case 2b 옵션
# ACCESS_TOKEN_TTL_MINUTES=1 로 재발급 후 90초 대기

# fixture 확보 (없으면 임시 더미)
# [README.md 참조](../../backend/tests/fixtures/supplement_labels/README.md)

# script 실행
bash scripts/m3v_c_error_scenarios.sh
```

### 1.3 4 case 명세

| # | 시나리오 | trigger | expected | mobile notifier 매핑 |
|---|---|---|---|---|
| **1** | Rate limit 429 | 12회 연속 POST `/api/v1/supplements/register` | 11회째 이내 429 | `잠시 후 다시 시도해주세요. (분당 요청 한도 초과)` |
| **2** | 401 invalid token | GET `/api/v1/users/me` with `Bearer invalid.jwt` | 401 | `다시 로그인해주세요.` |
| **3** | 500 server error | `docker compose stop postgres` + GET `/api/v1/users/me` | 500 or 503 | `서버 오류입니다.` |
| **4** | Connection refused | uvicorn 정지 후 curl | curl exit code != 0 (자동 검증 안 함 — 수동 안내) | `예상치 못한 오류가 발생했습니다.` |

### 1.4 결과 기입

| Case | 실행 일자 | Status | 비고 |
|---|---|---|---|
| 1 (Rate limit 429) | YYYY-MM-DD | [PASS/FAIL] | 11회 시도 횟수 / 429 hit 위치 |
| 2 (401 invalid) | | [PASS/FAIL] | |
| 2b (401 expired) — 선택 | | [PASS/FAIL/SKIP] | EXPIRED_TOKEN env 사용 여부 |
| 3 (500 postgres) | | [PASS/FAIL] | docker compose stop/start 안정성 |
| 4 (Connection refused) | | [PASS/FAIL/MANUAL] | 수동 step 결과 |

---

## 2. 매뉴얼 2 case — 시뮬레이터 + DB 조작

### 2.1 Manual 1 — 갤러리 권한 거부

**시뮬레이션**:
1. iOS / Android sim 가동 → Lemon 앱 진입
2. 회원가입 + 로그인 → 홈 → "영양제 등록" → 캡처 화면 진입
3. **시뮬레이터 시스템 설정** 또는 첫 권한 다이얼로그에서 "거부" 선택
4. 앱에서 "갤러리에서 선택" 탭

**기대 결과**:
- mobile `_showPermissionDeniedDialog` 호출 (`supplement_capture_screen.dart:120-148`)
- 다이얼로그 노출:
  - 타이틀: `사진 보관함 권한이 필요합니다` (또는 `카메라 권한이 필요합니다`)
  - 본문: `사진 보관함 사용을 허용하면 영양제 라벨 사진을 등록할 수 있습니다. 설정에서 권한을 변경해주세요.`
  - 버튼: `취소` / `설정으로 이동`
- "설정으로 이동" 탭 → `openAppSettings()` → 시스템 설정 진입

**캡처**: `m3v-permission-denied-dialog-<ios|and>.png`, `m3v-permission-settings-<ios|and>.png`

**결과**:
| Platform | Status | 캡처 | 비고 |
|---|---|---|---|
| iOS | [PASS/FAIL] | | |
| Android | [PASS/FAIL] | | |

---

### 2.2 Manual 2 — 동의 누락 (DB consent_records 삭제)

**시뮬레이션**:
1. 사용자 회원가입 + 로그인 완료 상태
2. **DB 직접 접근**:
   ```bash
   docker compose exec postgres psql -U lemon -d lemon
   ```
3. 사용자 ID 확인:
   ```sql
   SELECT id, email FROM users WHERE email = 'test@example.com';
   -- → <user_uuid>
   ```
4. consent_records 삭제 (또는 일부만 false 로 갱신):
   ```sql
   DELETE FROM consent_records WHERE user_id = '<user_uuid>';
   ```
5. sim 에서 영양제 등록 시도

**기대 결과**:
- backend: 403 + `{"detail": {"code": "consent_required", "missing": [...]}}`
- mobile notifier `_mapDioError` (`supplement_notifier.dart:80-106`) → 403 branch
- `SupplementError('필요한 동의를 다시 확인해주세요.')` 상태 진입
- 결과 화면 대신 `AppError` 위젯 노출 (또는 ConsentMatrix 재진입 — Phase M-4 의 옵션)

**캡처**: `m3v-consent-missing-<ios|and>.png`

**복구**:
```bash
# consent 다시 활성화 (회원가입 flow 재실행 또는)
INSERT INTO consent_records (user_id, type, granted_at, ...)
VALUES ('<user_uuid>', 'data_collection', NOW()), ...;
# 또는 sim 에서 logout → 재로그인 → 동의 매트릭스 재진입
```

**결과**:
| Platform | Status | 캡처 | 비고 |
|---|---|---|---|
| iOS | [PASS/FAIL] | | detail.code=consent_required 확인 |
| Android | [PASS/FAIL] | | |

---

## 3. 전체 DoD

- [ ] `scripts/m3v_c_error_scenarios.sh` 실행 — 자동 4 case PASS
- [ ] Manual 1 (권한 거부) iOS + Android 결과 기입
- [ ] Manual 2 (동의 누락) iOS + Android 결과 기입
- [ ] FAIL case 별 후속 (issue 생성 / 코드 수정 / plan 조정)
- [ ] 결과 commit: `docs(track-d): M-3-V.C error scenario results YYYY-MM-DD`

---

## 4. 위험 / 주의

- **운영 환경 금지**: script 의 `docker compose stop postgres` 는 dev 한정. BASE_URL
  localhost 가드 + ENVIRONMENT 확인.
- **DB 직접 조작 (Manual 2)**: 테스트 user 만 영향. 운영 user 절대 사용 금지.
  복구 어려우므로 회원가입 → 동의 → 검증 → 회원탈퇴 순서 권장.
- **rate limit 잔량**: Case 1 실행 후 분 단위 카운터가 남음. 다른 테스트 영향
  방지 위해 다른 user 사용 또는 1분 대기.
- **uvicorn 종료/재가동 (Case 4)**: script 가 직접 못 함. 사용자가 수동.

---

## 5. 참조

- mobile notifier `_mapDioError`: [supplement_notifier.dart:80-106](../../mobile/lib/features/supplement/presentation/providers/supplement_notifier.dart)
- 권한 다이얼로그: [supplement_capture_screen.dart:120-148](../../mobile/lib/features/supplement/presentation/screens/supplement_capture_screen.dart)
- backend rate limit: [deps.py:134-159](../../backend/src/api/deps.py)
- backend auth 401: [deps.py:94-131](../../backend/src/api/deps.py)
- 안전 위젯: [shared/widgets/](../../mobile/lib/shared/widgets/)
- Plan: [twinkly-splashing-hejlsberg.md](/Users/yeong/.claude/plans/twinkly-splashing-hejlsberg.md) Phase M-3-V.C
