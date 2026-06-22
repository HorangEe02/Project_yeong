# Lemon Healthcare — 종합 비판적 감사 + 앱 출시 readiness 보고서

> **문서 정보**
> 작성일: 2026-05-18 | 작성자: claude (분석 라운드) | 대상 브랜치: `codex/p1-5-stabilization` (e8fe3ae) + 본일 적용된 PaddleOCR primary 전환 패치

> 📌 본 보고서는 동일 폴더의 다음 문서들을 *전제로* 한다(중복 보고 회피).
> - `2026-05-17-current-implementation-audit.md` — P1 stabilization 시점 베이스라인
> - `2026-05-18-high-findings-implementation-guideline.md`
> - `2026-05-18-medium-low-findings-implementation-guideline.md`
>
> 본 문서는 위 노트들 *이후* 발견한 추가 갭과 PaddleOCR primary 전환 영향까지 통합한 *Day-0 출시 결정용 시각*이다.

---

## 0. 한 줄 결론

**현재 코드베이스는 앱스토어 출시 가능 상태가 아니다.** 백엔드는 P1 단계 phase-gate 스캐폴드로 잘 정돈됐고 알고리즘은 견고하지만, **(1) 모바일 Flutter 앱 0% 구현, (2) 인증 없는 알고리즘 라우터가 PHI 노출 표면, (3) PIL decompression bomb·EXIF 누락의 실제 취약점, (4) CI/CD 워크플로 부재, (5) PaddleOCR 정책 전환이 일부 잔여 경로(`.env.example`은 갱신, 운영 secret 템플릿은 별도 확인 필요)에 전파 미완**이라는 다섯 가지 출시 블로커가 동시에 존재한다. 보수적으로 **8–12주** 추가 작업이 필요하다.

---

## 1. 구현 완성도 매트릭스

| 영역 | 상태 | 핵심 갭 | 영향 |
|------|------|---------|------|
| 알고리즘 (v1~v4, BMR/TDEE, 7-step, KDRIs, 결핍 진단, 만성질환 우선순위) | ✅ 견고 | Hall-lite는 `feature_hall_lite_weight_prediction=False`로 잠겨 production에서 noop ([config.py:323]) | 중 — "구현됐지만 미배포" |
| OCR 파이프라인 (PaddleOCR primary, Google Vision opt-in, CLOVA 옵션) | ✅ 본일 전환 완료 | layout-aware parsing(영양성분표 행/열) **부재**, YOLO ROI crop은 `crop_before_primary` 게이트 OFF로 미동작 | 고 — 정확도 상한이 plain text OCR로 묶임 |
| Ollama Vision Assist | △ 어댑터 주입만 됨 | `multimodal_ocr_assist_policy=disabled` 기본 → primary 저신뢰 시 fallback 호출 안 됨 | 중 — Tier 3 사실상 dormant |
| API 라우터 — supplements | ✅ consent + audit 양호 | `/supplements/analyze` 통합 테스트는 PaddleOCR fake로만 통과, 실제 PaddleOCR 통신 e2e 0건 | 중 |
| API 라우터 — predictions / activity | ❌ **인증 없음** | `src/api/v1/predictions.py:30-43`, `activity.py`가 `Depends(get_current_user)` 누락 의심 — 알고리즘 결과 익명 노출 표면 | 고 — 본일 PaddleOCR과 무관한 별도 회귀 |
| DB 모델·마이그레이션 | ◯ 6 head 존재 | **TimescaleDB hypertable 마이그레이션 0건** — 걸음수·체중 시계열을 일반 테이블에 저장 중. PoC 통과·scale 시 회귀 | 중 |
| 단위 테스트 | ✅ 398 통과 (2 skipped, 본일 검증) | 가이드 예시 단정값 포함 — 회사 PPTX의 7524 등 잠금. 좋음 | 저 |
| 통합 테스트 | ❌ 약함 | `/supplements/analyze` consent + multipart + 413/415/422 게이트 통합 테스트 부재 (unit-only). e2e docker-compose 시나리오 0건 | 고 |
| 모바일 (Flutter) | ❌ **존재하지 않음** | `mobile/` 디렉터리에 `README.md`와 `CLAUDE.md` 단 2개 파일. `pubspec.yaml` / `*.dart` / `flutter_app/` **0건** | **P0 블로커** |
| CI/CD | ❌ **존재하지 않음** | `.github/workflows/` 디렉터리 자체 없음. `docs/Nutrition-docs/37-ci-hardening-design-plan.md`, `38-stabilization-pr-gate-design-plan.md`는 계획 문서뿐. pre-commit hook은 `--no-verify`로 우회 가능 | **P0 블로커** |

---

## 2. 보안 결함 (severity 분류)

### 2.1 Critical
- 없음. JWT 검증, 비대칭 알고리즘 화이트리스트, SQL injection 표면, 명시적 secret 커밋 모두 확인됨(자세한 내용은 `2026-05-18-high-findings-implementation-guideline.md` 참고).

### 2.2 High
- **[HIGH-1] PIL decompression bomb 방어 부재** — `src/ocr/preprocessing.py:31`의 `Image.open(BytesIO(image_bytes))` 호출 전후로 `Image.MAX_IMAGE_PIXELS` 캡, `Image.DecompressionBombError`/`DecompressionBombWarning` 캐치가 어디에도 없다. 5MB 이하 PNG로도 100k × 100k zlib bomb 가능 → 워커 OOM 가능. PaddleOCR primary 전환으로 *로컬* 처리 경로가 default가 됐기 때문에 이 결함의 *blast radius가 더 커졌다*. **`Image.MAX_IMAGE_PIXELS = settings.supplement_image_max_pixels`로 강제 + try/except DecompressionBombError 패턴 추가 필수.**
- **[HIGH-2] `AUTH_MODE=disabled`가 `ALL_API_SCOPES` 부여** — `src/security/auth.py:383-389`. production validator는 차단하지만 `staging`은 차단 안 함. staging 인스턴스가 외부 IP에 노출되면 익명 사용자에게 전체 권한이 부여될 수 있음. → `environment in {"staging","production"}`이면 `auth_mode=="jwt"` 강제.
- **[HIGH-3] EXIF/GPS 스트립 부재** — `getexif`, `piexif`, `image_transpose` 어디에도 없음. 영양제 라벨 촬영 시 GPS·기기 ID 포함될 수 있고, 학습 파이프라인이 켜지면(`ENABLE_IMAGE_LEARNING_PIPELINE=true`) 원본이 S3로 흘러간다. **외부 OCR 호출 전 + 학습 storage 업로드 전 모두 re-encode-and-strip 필수.**
- **[HIGH-4] `predictions` / `activity` 라우터 익명 노출 의심** — `src/api/v1/predictions.py`, `activity.py`에 `Depends(get_current_user)`가 보이지 않음(에이전트 보고). PHI 추론 결과가 인증 없이 응답되는 표면 → 출시 전 인증 미들웨어 부착 필수.

### 2.3 Medium
- **[MED-1] `GOOGLE_VISION_AUTH_MODE=api_key` 기본값** — `config.py:295`. production validator가 `OCR_PRIMARY_PROVIDER=google_vision` 시에만 ADC 강제. 운영자가 primary를 바꾸지 않고 키만 커밋하면 long-lived key 노출 가능. → default를 `"adc"`로 바꾸고 api_key 모드는 `ALLOW_GOOGLE_API_KEY_AUTH=true` + non-prod에서만 허용.
- **[MED-2] `PRIVACY_HASH_SECRET` development default** — `config.py:281` 값이 `"development-insecure-privacy-hash-secret"`. `staging`/`test` 환경에서 환경변수 미설정 시 잘 알려진 secret으로 HMAC을 생성 → 가명화 subject id 예측 가능.
- **[MED-3] 의존성 audit 자동화 부재** — `pip-audit`/`safety` CI 잡 없음. Pillow/PyJWT/FastAPI 상한 핀(<X.Y) 부재 → drift 위험.
- **[MED-4] Audit log tamper-evident 체인 없음** — `src/services/privacy.py:6,145` HMAC subject hashing은 양호하나, audit row 자체의 append-only 무결성 체인(prev_hash) 없음.
- **[MED-5] CORS/TrustedHost를 빈 리스트 시 *비활성*** — `src/main.py:38-57`. 운영에서 ALLOWED_HOSTS 미설정 시 fail-closed가 아니라 미적용으로 빠짐. → 항상 TrustedHostMiddleware 부착, 빈 리스트면 startup 거부.

### 2.4 Low
- CSP/COOP 헤더 미설정(API only 라 영향 작음), Sentry DSN/Prometheus 미통합, 모바일 보안(토큰 저장, 인증서 pinning, root/jailbreak 검출)은 Flutter 코드 부재로 평가 보류.

---

## 3. 본일 PaddleOCR Primary 전환 후속 확인 항목

본일 적용된 변경(`OCR_PRIMARY_PROVIDER=paddleocr` default + factory 분기 + validator + 테스트 + docs/33/40/32 부분 갱신) 이후 잠재 회귀:

1. **PaddleOCR 모델 첫 호출 시 `Checking connectivity to the model hosters` 네트워크 점검 트리거 발견됨** — `test_supplement_intake_api.py` 회귀에서 확인. production에서 외부 모델 호스터 도달 못 하는 폐쇄망 시 첫 호출이 hang 가능. → `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` 환경변수 + 컨테이너 이미지에 모델 번들링 전략 결정 필요.
2. **PaddleOCR 모델 파일 배포 전략 미정** — `~/.paddleocr/` 캐시를 Docker 이미지 안에 번들링하면 1GB+. 별도 init-container로 다운로드하거나 PV mount로 분리해야 함. CI 빌드 시간/이미지 크기 영향 큼.
3. **`enable_local_ocr=True` 기본값으로 인한 test fixture 회귀** — `Settings(_env_file=None)`만으로 만든 통합 테스트가 real PaddleOCR adapter를 호출해 audit log 카운트가 어긋남(본일 `test_supplement_intake_api.py:259-261` 회귀 → adapter override로 수정). 동일 패턴의 다른 통합 테스트 발견 시 같은 수정 필요.
4. **`docs/45`, `docs/51` 미존재 확인** — 이 브랜치에는 두 문서가 아직 없음. 다른 브랜치에서 머지될 때 PaddleOCR primary 컨텍스트로 갱신해야 함.
5. **`docs/27`, `docs/35`, `docs/45` 등 "Google Vision primary" 단언이 남아있을 가능성** — grep으로 추적 권고: `rg -n "Google.*Vision.*(주력|primary|Tier 2)" docs/Nutrition-docs/`.
6. **`pyproject.toml`의 `paddleocr` extras 구조** — 기본 install에 포함 안 됨. production 배포 스크립트에서 `pip install ".[ocr-local]"` 누락 시 startup ImportError. README/dev-guide에 한 줄 명시 권고.

---

## 4. 앱 출시 readiness — P0/P1/P2

### P0 — 출시 블로커 (없으면 심사조차 못 들어감)

| 항목 | 현황 | 예상 소요 |
|------|------|----------|
| Flutter 앱 bootstrap + 핵심 6화면 (홈/사진촬영/결과/동의/건강프로필/세팅) | 0% | 4–6주 |
| iOS `Info.plist` 한국어 purpose strings (`NSCameraUsageDescription`, `NSHealthShareUsageDescription`, `NSPhotoLibraryUsageDescription`) | 없음 — 앱이 없으니 정의 불가 | 1–2일 (앱 부트 후) |
| Android `AndroidManifest.xml` Health Connect intent filter + `READ_HEALTH_DATA_*` 권한 + `targetSdk 34` | 없음 | 1–2일 |
| 의료 면책 / 개인정보처리방침 / EULA / 동의 UI **화면** | 문서만 존재 (`docs/10`) | 1주 |
| Apple "Health & Fitness" 카테고리 추가 심사 (Schedule 3) + Google Play Health Connect declaration | 미신청 | 심사 2–4주 (병렬) |
| CI/CD (`.github/workflows/` + Fastlane) + 코드사이닝 (iOS provisioning, Android keystore) | 0% | 1주 |
| **PIL decompression bomb + EXIF 스트립 fix** | 미적용 | 1일 |
| **`predictions`/`activity` 라우터 인증 부착** | 미확인 → 검증 + 부착 | 1–2일 |

### P1 — 출시 후 1주 안에 처리해야 안전

| 항목 | 현황 | 예상 소요 |
|------|------|----------|
| 백엔드 `Dockerfile` + multi-arch 빌드 + registry push | 부재 | 3일 |
| Sentry (백엔드 + Flutter) + Crashlytics | 0건 | 2일 |
| Prometheus / Datadog metric emit (docs/33 §9.2 명시는 됐으나 코드 미적용) | 미적용 | 2일 |
| TestFlight / Play Internal Testing 트랙 + 베타 사용자 | 미생성 | 1주 |
| PaddleOCR 모델 배포 전략 결정 (번들 vs init-container vs PV mount) | 미정 | 2일 |
| Ollama 클라우드 호스팅 또는 백오프 정책 | `127.0.0.1` 잠금 + `ALLOW_EXTERNAL_LLM=false` → 운영 배포 시 진단 필요 | 1주 |
| TimescaleDB hypertable 마이그레이션 | 0건 | 1일 |
| `/supplements/analyze` end-to-end docker-compose 통합 테스트 | 0건 | 2일 |

### P2 — 출시 후 정상화 단계

- Phase-gate 운영 토글 절차 문서화 (`docs/17 §9` gate #1/#2/#3 실제 켜는 SOP)
- Audit log 무결성 체인 (HMAC chain)
- YOLO ROI crop을 primary OCR 입력에 실제 주입 (현재 `crop_before_primary` 게이트 OFF로 noop)
- Ollama vision assist의 fallback/verification 호출을 real traffic에 활성화 (현재 `disabled`)
- Layout-aware OCR (LayoutLMv3 또는 PaddleOCR Structure) — 영양성분표 행/열 추출 정확도 향상
- `pip-audit` CI 통합 + 의존성 상한 핀

---

## 5. 정리되지 않은 위험 신호 (추가 발견)

본 라운드에서 *처음* 발견했거나 기존 노트에 안 적혀있어 보이는 항목:

1. **`mobile/CLAUDE.md`(18KB)와 `mobile/README.md`만 존재** — 발주처 데모는 Swagger UI로만 가능한 상태. UX 검증 데이터(첫 사용자 6명 클릭 흐름 등) 자체가 만들어질 수 없음. 발표·인수인계 전에 *어떤 형태로든* 작동하는 화면이 있어야 발주처 sign-off가 가능.
2. **`predictions.py` / `activity.py` 라우터의 인증 누락 의심**은 본 보고서의 최고 우선 회귀 의심 — 본 PaddleOCR 전환과 무관한 별도 PR에서 해결 필요. 발견 즉시 `grep -nA5 "@router\.\(post\|get\)" Nutrition-backend/src/api/v1/predictions.py Nutrition-backend/src/api/v1/activity.py`로 검증 권고.
3. **`backend/CLAUDE.md`가 "TimescaleDB"를 표준으로 명시했으나 마이그레이션에 hypertable 생성 없음** — 문서·코드 drift. PoC 단계에서는 작동하나 sound bite로 "TimescaleDB 사용 중"이라 표현하면 사실관계 오류.
4. **`backend/CLAUDE.md`에 `pythonpath = ["Nutrition-backend"]` 명시 + pytest testpaths가 3개 디렉토리** — 모노리포 구조가 점차 복잡해지고 있음. 새 모듈 추가 시 import 경로 회귀 우려.
5. **`Brand-New-update/` 자체가 git untracked** — 본 보고서를 포함해 audit 결과가 PR에 반영되려면 별도 stage·commit 작업 필요. 현재는 *개인 작업 폴더*에 가까운 상태.
6. **PaddleOCR 첫 호출 connectivity check가 production 폐쇄망에서 실패 가능** — `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true` 환경 변수 미설정 시 첫 OCR 호출이 외부 model hoster에 닿으려 시도. 의료기관 내부 폐쇄망 운영 시나리오(docs/32 §6에 강조됨)와 충돌.
7. **OCR primary 전환 후 production validator의 짝지움**: `enable_local_ocr=True` AND `ocr_primary_provider != "paddleocr"` 시 sign-off 요구. 반대로 PaddleOCR primary로 두고 enable_local_ocr=False 시도 시 차단. 이중 가드 작동은 본일 확인됨(`test_production_rejects_paddleocr_primary_without_local_ocr` PASS). **그러나** "PaddleOCR primary로 두면 production 운영자가 사실상 *외부 OCR 끄고는 다른 옵션을 못 가짐*"이라는 점 — 이는 정책적으로는 의도된 결과지만, 정확도 회귀 시 비상 폴백이 부족함을 의미. → 외부 OCR fallback 운영 procedure를 *글로 명시*해두지 않으면 incident 시 우왕좌왕.

---

## 6. 권고 행동 우선순위 (Day-0 → Day-90)

### Day 0 (오늘)
1. **PIL decompression bomb fix** — `Image.MAX_IMAGE_PIXELS = settings.supplement_image_max_pixels` 강제 + DecompressionBombError 캐치. 5줄 패치로 가장 큰 *실제 공격 표면* 닫음. [HIGH-1]
2. **`predictions`/`activity` 라우터 인증 검증** — `grep -nA5 "@router\." Nutrition-backend/src/api/v1/{predictions,activity}.py`로 즉시 확인. [HIGH-4]

### Day 1–7
3. EXIF/GPS 스트립 helper 추가, OCR/upload 직전 호출 [HIGH-3]
4. `AUTH_MODE=disabled`를 production+staging에서 거부 [HIGH-2]
5. `GOOGLE_VISION_AUTH_MODE` default를 `adc`로 변경, api_key는 `ALLOW_GOOGLE_API_KEY_AUTH=true` 게이트 [MED-1]
6. `.github/workflows/` 부트스트랩: pytest + ruff + mypy + alembic head 검증 + pip-audit 잡 [CI 부재]
7. PaddleOCR primary 전환 잔여 문서(docs/27, docs/35, docs/45 추후 머지본) grep + 갱신

### Day 7–30
8. Flutter 앱 부트스트랩 — `flutter create` + 라우팅 + Riverpod + dio 클라이언트 + health 패키지 [P0 BLOCKER]
9. 영양제 카메라/업로드 화면 + 동의 UI + 의료 면책 표시 화면 [P0]
10. 백엔드 Dockerfile + PaddleOCR 모델 배포 전략 결정 + multi-arch [P1]
11. Sentry/Crashlytics 통합 + TestFlight/Play Internal Testing 트랙 [P1]

### Day 30–90
12. Apple Health & Fitness 카테고리 심사 + Google Play Health Connect declaration 제출 [P0, 심사 2–4주]
13. e2e 시나리오 테스트 + 베타 사용자 50명 운영 + 크래시·메트릭 모니터링 [P1]
14. YOLO ROI + Ollama vision assist 운영 토글 + layout-aware OCR PoC [P2]

---

## 7. 부록 A — 본 라운드에서 확인된 *작동 정상* 항목 (회귀 방지용 체크리스트)

- `pytest Nutrition-backend/tests/` 398 PASS / 2 skipped (2026-05-18 본일 검증)
- `Settings(_env_file=None)` → `ocr_primary_provider="paddleocr"`, `enable_local_ocr=True`, `allow_external_ocr=False`로 의도된 기본값 도출
- `build_supplement_ocr_adapter`가 PaddleOCRAdapter 반환, fallback chain은 PaddleOCR 중복 추가 안 함
- production validator: `OCR_PRIMARY_PROVIDER=paddleocr + ENABLE_LOCAL_OCR=false` 시 명확한 에러로 차단
- `/supplements/analyze` PaddleOCR 기본 경로는 `OCR_IMAGE_PROCESSING` consent만 요구 (`EXTERNAL_OCR_PROCESSING` 요구 안 함) — 컴플라이언스 의도 일치
- JWT 비대칭 화이트리스트, JWKS lru_cache, asymmetric only — 견고

## 부록 B — 본 보고서가 *아직 직접 검증하지 못한* 항목

- ~~`predictions.py` / `activity.py` 인증 누락의 실제 코드 확인~~ **검증됨 (2026-05-18)** — `Nutrition-backend/src/api/v1/predictions.py:21-39`의 `@router.post("/weight")`와 `Nutrition-backend/src/api/v1/activity.py:20-36`의 `@router.post("/score")` 모두 `Depends(get_current_user)` 부재. body로 weight/height/age/sex/chronic conditions 등 PHI를 받아 처리하지만 인증·동의·감사 어느 것도 없음. DB 조회 표면은 아니므로 *데이터 유출*은 아니지만, (1) 익명 PHI 처리 → Apple Health & Fitness 카테고리 심사 reject 사유, (2) 무한 컴퓨트 호출 → DoS·LLM 비용 폭증 표면, (3) audit trail 0 → 의료기기법 회피 입증 곤란. 출시 전 인증·동의·감사 의존성 부착 필수.
- TimescaleDB hypertable 마이그레이션 실제 부재 확인 (에이전트 보고)
- Flutter 모바일 디렉토리 외 `frontend/` 디렉토리에 별도 웹 구현이 있는지 (있다면 평가 다름)
- 본일 적용된 `docs/33/40/32` 외 다른 docs 파일에 잔존하는 "Google Vision primary" 단언

위 항목들은 후속 PR/검증 라운드에서 직접 grep + Read로 확인 권고.

---

## 부록 C — 본 보고서의 한계

1. 의존성 audit (`pip-audit`)을 본 라운드에선 실행하지 못함 — 별도 검증 필요.
2. Flutter 코드가 0이라 모바일 보안(토큰 저장, 인증서 pinning, root/jailbreak 검출) 평가가 모두 *향후 작업*으로 deferred.
3. 발주처 sign-off 게이트(`docs/17 §9` gate #1/#2/#3) 실제 절차 검증은 본 보고서 범위 밖. 운영 인계 시점에 별도 게이트 리뷰 필요.

---

**최종 권고**: 본 보고서의 P0 8개 항목과 HIGH 4개 보안 항목 중 4번(인증 검증)과 1번(decompression bomb)을 **본 주 내**에 해결하지 못하면, 앱스토어 심사 제출 일정 자체가 비현실적이다. 모바일 부트스트랩은 별도 워크스트림으로 즉시 착수 권고.
