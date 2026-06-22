# Vision/Nutrition 파트 — 현 시점 구현 감사 보고서

> 작성일: 2026-05-17
> 대상: 사용자가 담당한 "영양제·보충제 사진 → Vision LLM → DB 프로필 결합 → 경고·추천(진단 아님)" 파이프라인
> 관점: **출시 게이트(앱 스토어 + 한국 PIPA/의료기기법) 감사**
> 톤: 비판적·증거 기반. 자화자찬 금지, 결함 무조건 명시.

---

## 0. TL;DR (Executive Summary)

### 한 줄 평가
**기능 완성도는 의외로 높다(end-to-end 가동 가능, 동의 게이트·금지어 필터·HMAC owner hash·소프트 삭제·임상 disclaimer 상수까지 갖춤). 그러나 출시까지 가려면 보안·컴플라이언스 측면에서 최소 5건의 차단 이슈를 반드시 닫아야 한다.**

### 출시 차단(blocker) Top 3
| # | 항목 | 위치 | 영향 |
|---|------|------|------|
| 1 | **EXIF/GPS 메타데이터 미제거** | `backend/Nutrition-backend/src/services/supplement_intake.py:658-695` | 학습 스토리지·외부 OCR로 위치/단말 정보 누출. PIPA 민감정보 → 앱 스토어 심사 및 법적 리스크 |
| 2 | **`clinical_disclaimer`를 클라이언트로부터 echo** | `backend/Nutrition-backend/src/services/supplement_explanation.py:99` | 의료 disclaimer가 클라이언트 페이로드 조작으로 약화 가능. 의료기기법 위반 소지 |
| 3 | **모바일 cert pinning 부재 + 인앱 토큰** | `mobile/flutter_app/lib/core/api/api_client.dart`, `lib/core/config/app_config.dart:50-78` | MITM·MDM 환경에서 토큰 + 헬스 데이터 가로채기 가능. Apple ATS/의료앱 심사 reviewer가 흔히 지적 |

### 권장 즉시 조치 Top 5 (각 1일 이내)
1. `supplement_intake.py`에 EXIF strip 함수 추가 후 학습 스토어/멀티모달 OCR 진입 전 적용.
2. `supplement_explanation.py:99` 라인을 `clinical_disclaimer=SUPPLEMENT_IMPACT_DISCLAIMER` (상수)로 하드 오버라이트.
3. Flutter `ApiClient`에 SPKI cert pinning 도입 (`http_certificate_pinning` 또는 Dio + 핀).
4. `Image.MAX_IMAGE_PIXELS` 모듈 임포트 시점 일괄 설정 + `.load()` 호출부 `DecompressionBombError` 가드.
5. 응답 미들웨어로 HSTS / nosniff / Referrer-Policy / Permissions-Policy 일괄 부착.

---

## 1. 감사 범위와 방법

### 범위 (in-scope)
- 백엔드: `yeong-Lemon-Aid/backend/Nutrition-backend/src/`
- 모바일: `yeong-Lemon-Aid/mobile/flutter_app/`
- 설정·키: `yeong-Lemon-Aid/api-key/`, `yeong-Lemon-Aid/config/`, `.env`/`.env.example`
- 문서: `PROJECT_GUIDE.md`, `Brand-New-update/` 기존 plan A~E + risk brainstorm

### 범위 외 (out-of-scope)
- Food 분석(`backend/food_image_analysis/` — scaffold only), Chat(`backend/ai_agent_chat/` — scaffold only), 웹 프론트(`frontend/src/` — 비어 있음).
- 사용자가 담당하지 않는 다른 팀원 파트.
- 외부 의존성 설치 / 키 회수.

### 사용 도구
- Read·Grep·Bash (`git ls-files`, `find`, `grep -rn`).
- Explore 서브에이전트 2종, security-reviewer 서브에이전트 1종.
- `pip-audit`/`flutter test` 실제 실행은 환경 부재로 미수행 → "권장 명령" 형태로만 기재.

### 신뢰도 표기 규약
- ✅ 코드 라인 직접 확인.
- ⚠️ 코드 라인 확인했으나 의도/예외 경로 미완전 검증.
- ❓ 추정 — 후속 검증 필요.

---

## 2. 파이프라인 구현 매트릭스

사용자가 설명한 7단계 흐름과 실제 코드 매핑:

| # | 단계 | 실제 구현 위치 | 완성도 | 잔존 위험 |
|---|------|---------------|--------|----------|
| 1 | 사진 업로드 (multipart) | `services/supplement_intake.py` + `POST /supplements/analyze` | ✅ 완성 (MIME magic-byte·바이트·픽셀 한도) | H1 EXIF, H2 디컴프레션 폭탄 |
| 2 | 이미지 ROI/품질 검출 | `vision/yolo.py`, `services/supplement_image_quality.py` | ✅ 완성 (gated by flag) | Image.MAX_IMAGE_PIXELS 미설정 (H2) |
| 3 | OCR 텍스트 추출 (Google Vision / CLOVA / PaddleOCR / Ollama vision fallback) | `ocr/factory.py:77-94`, `services/supplement_image_analysis.py` | ✅ 완성 + 폴백 체인 | 외부 OCR 전송 시 EXIF/GPS 동행 (H1) |
| 4 | 구조화 LLM 파싱 (Ollama) | `llm/ollama.py:22-31`, `services/supplement_parser.py:157-188` | ✅ 완성 (Pydantic 검증) | M5 OCR 텍스트 prompt-injection |
| 5 | 결정론적 영향 분석 (부족/과잉/중복) | `services/supplement_recommendation.py:30-110` | ✅ 완성 (LLM 의존 X) | — |
| 6 | 사용자 DB 결합 (프로필·과거 영양 분석) | `services/supplement_recommendation.py` + DB layer | ✅ 완성 (owner_subject + soft delete + audit) | L1 user-controlled idempotency key |
| 7 | 안전한 LLM 리워딩 + disclaimer | `services/supplement_explanation.py:36-105` | ⚠️ 부분 결함 (M4 disclaimer echo) | M4 |

### 스캐폴드만 있는 영역(말 그대로 빈껍데기)
- `backend/food_image_analysis/__init__.py` (1줄)
- `backend/ai_agent_chat/__init__.py` (1줄)
  → 최근 커밋 "scaffold phase gate flags + LLM/Vision adapter base"의 결과물. **현 시점 사용자 파트 영향 없음**이지만, 다른 팀원 파트 차단이 있을 수 있어 인접 작업과 조율 필요.

### 사용자 청구 스코프 vs 실제(PROJECT_GUIDE.md §1.4–1.7)
- "사진 한 장으로 끝 — 5종 분석 자동 출력" → ✅ 사진→OCR→파싱→권고까지 가동. 단 "5종" 중 일부(체중 예측·활동 권고)는 Food 도메인이며 Vision/Nutrition 파트와는 별개.
- "병원 기록을 기억하는 Agent" → ❌ 사용자 파트(Vision/Nutrition) 한정으로는 **DB의 사용자 프로필·과거 영양 분석만 결합**. LDB(병원 데이터) 실제 연동은 코드 미발견 — `PROJECT_GUIDE.md` 자체가 "독립형 참조 앱"으로 못 박았으므로 의도된 갭으로 보임. 보고서·발표 시 이 점을 정확히 표현하지 않으면 발주처 오해 소지.
- "진단·처방 X, 사용자 결정 주도" → ✅ 시스템 프롬프트 + 금지어 필터(`FORBIDDEN_TERMS = ("진단","치료","처방","복용량 변경")`) + 응답 단계 `_reject_forbidden_response` 적용 확인.

---

## 3. 발견 사항(심각도별)

표기: **C**RITICAL / **H**IGH / **M**EDIUM / **L**OW. 모든 항목은 `file:line` + 영향 + 수정 예시 포함.

---

### CRITICAL
*현 시점 직접적인 CRITICAL은 발견하지 못함.* (단, 출시 직전까지 H1·H2·H3·M4는 사실상 CRITICAL로 격상 운용 권고)

---

### HIGH

#### H1. 업로드 이미지의 EXIF/GPS 미제거 — PIPA 민감정보 누출 ✅
- **위치**: `backend/Nutrition-backend/src/services/supplement_intake.py:658-695`
- **현황**: `_validate_decodable_image()`는 `Image.open(...).verify()`만 수행. 이후 raw `image_bytes`가 그대로 `services/supplement_image_analysis.py` → OCR 어댑터(Google Vision/CLOVA 외부 송신) + `learning/object_storage.py`(LocalLearningImageObjectStore.put_image)로 흘러감.
- **확인**: `grep -rn "Image.MAX_IMAGE_PIXELS|DecompressionBombError|exif|EXIF|getexif" backend/...` 결과 EXIF 관련 처리 코드는 **스키마의 "exclude exif" 필드명**(serializer 차원)뿐. 이미지 바이트 차원의 strip은 발견되지 않음. `supplement_intake.py:705` docstring은 "parsed snapshot에 EXIF 미포함"만 약속하며 원본 바이트를 정화하지 않음.
- **영향**: 스마트폰 영양제 사진은 GPS(자택 좌표)·단말 시리얼·촬영 시각을 포함. 외부 OCR API(Google Vision, CLOVA)에 전송 시 제3자에게 위치 데이터가 전달됨 → PIPA 민감정보 처리 동의 별도 필요, 사용자에게 그 사실을 고지하지 않으면 위법.
- **수정 예시**:
  ```python
  from io import BytesIO
  from PIL import Image

  _SUPPORTED = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}

  def strip_image_metadata(data: bytes, mime: str) -> bytes:
      fmt = _SUPPORTED[mime]
      with Image.open(BytesIO(data)) as im:
          im.load()
          clean = Image.new(im.mode, im.size)
          clean.putdata(list(im.getdata()))
          buf = BytesIO()
          clean.save(buf, format=fmt, optimize=True)
          return buf.getvalue()
  ```
  `_validate_decodable_image` 직후 호출하여 다운스트림에는 정화된 바이트만 전달.

#### H2. PIL 디컴프레션 폭탄 방어 부재 ✅
- **위치**: `backend/Nutrition-backend/src/services/supplement_intake.py:680` (선언 dim만 검사 후 `verify()`)
- **현황**: `Image.MAX_IMAGE_PIXELS` 전역 설정 없음. 다운스트림(YOLO 분류, 품질 점검, 학습 큐)에서 `.load()` 호출 시 폭탄 PNG가 디코드 폭주.
- **수정 예시**: 각 이미지 소비자 모듈 임포트 시 `Image.MAX_IMAGE_PIXELS = settings.supplement_image_max_pixels` 설정 + `try: image.load() except Image.DecompressionBombError`.

#### H3. Flutter cert pinning 부재 + Authorization Bearer 평문 헤더 ✅
- **위치**: `mobile/flutter_app/lib/core/api/api_client.dart` 전체, `lib/core/config/app_config.dart:50-78`
- **확인**: `grep -n "pin|SecurityContext|badCertificate" api_client.dart` → 0건. `grep -rn "network_security_config|cleartextTrafficPermitted|NSAppTransportSecurity" mobile/` → 0건.
- **현황**: release 모드 HTTPS 강제는 OK(`app_config.dart:63`). 그러나 cert pinning이 없어 사용자 단말에 신뢰된 임의 루트(MDM, 기업 프록시, 악성 프로필)가 있으면 Authorization 헤더 + 사용자 헬스 정보가 가로채짐. Apple/Google 의료 카테고리 심사에서 흔히 지적되는 항목.
- **수정 예시**: `http_certificate_pinning` 패키지 또는 Dio + `dio_http2_adapter`로 SPKI 핀 설정. Android `network_security_config.xml`을 추가하여 prod flavor `cleartextTrafficPermitted="false"` 명시.

---

### MEDIUM

#### M1. Rate-limiter가 in-memory only — 다중 worker 환경에서 우회 ✅
- **위치**: `backend/Nutrition-backend/src/middleware/rate_limit.py:48-78` (`InMemoryRateLimiter`)
- **현황**: 코드 주석으로 한계 자인. 운영에서 2+ worker/pod 시 클라이언트 분산 fanout으로 한도 우회 → Ollama vision/text 비용 증폭 DoS 가능.
- **수정 권고**: Redis 기반(slowapi-redis, redis-py incr+TTL)으로 교체. prod readiness probe가 limiter store 가용성도 확인하도록 확장.

#### M2. CORS·TrustedHost는 있으나 보안 응답 헤더 일괄 부착 미들웨어 부재 ✅
- **위치**: `backend/Nutrition-backend/src/main.py` (TrustedHost·CORS·RateLimit 3종만 확인)
- **현황**: `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy`, `Cross-Origin-Resource-Policy`, `Permissions-Policy` 부재.
- **수정 예시**: `starlette.middleware.base.BaseHTTPMiddleware`로 `SecureHeadersMiddleware` 작성 후 부착. PIPA 자가진단·앱 스토어 체크리스트 모두 충족.

#### M3. CORS가 staging/development에서 http origin 허용 ⚠️
- **위치**: `backend/Nutrition-backend/src/main.py:52-60`
- **현황**: production validator는 wildcards 차단하지만 `https://` 강제 검증은 미확인. staging 노출 시 인증 흐름 악용 가능.
- **수정 권고**: `allowed_origins` 항목별 prefix 검사를 production validator에 추가.

#### M4. `clinical_disclaimer`가 클라이언트 제공 preview에서 echo ✅
- **위치**: `backend/Nutrition-backend/src/services/supplement_explanation.py:99` (`clinical_disclaimer=preview.clinical_disclaimer`)
- **현황**: `SupplementImpactPreviewResponse.clinical_disclaimer`의 길이 검증이 1자 이상이면 통과 → 공격자/장난기 있는 클라이언트가 "." 한 글자로 호출 시 모든 응답의 disclaimer가 사실상 무력화. 의료기기법상 "진단 아님 / 의·약사 상담" 고지를 서버가 책임지지 않게 됨.
- **수정 예시**: `services/supplement_recommendation.py:24-27`의 상수 `SUPPLEMENT_IMPACT_DISCLAIMER`로 항상 강제 오버라이트:
  ```python
  response = SupplementRecommendationExplainResponse(
      ...,
      clinical_disclaimer=SUPPLEMENT_IMPACT_DISCLAIMER,  # always server-stamped
      ...
  )
  ```
  덧붙여, 클라이언트가 보낸 disclaimer가 SUPPLEMENT_IMPACT_DISCLAIMER와 일치하지 않으면 거부(또는 무시 + 로그)하여 변조 시도를 감시.

#### M5. OCR 텍스트(최대 12,000자)가 Ollama 프롬프트에 직진 — prompt-injection 표면 ✅
- **위치**: `backend/Nutrition-backend/src/services/supplement_parser.py:174-188` → `llm/ollama.py:22-31` (시스템 프롬프트로만 방어)
- **현황**: 라벨 인쇄 텍스트에 "IGNORE PRIOR INSTRUCTIONS..."를 삽입한 가짜 이미지가 Pydantic 스키마 통과 후 `parsed_snapshot.product_name`/`precaution_text`에 저장 → 이후 explanation 프롬프트와 대시보드 카드, 공유 링크에 출력됨.
- **수정 권고**: Pydantic 검증 직후 free-text 필드에 (1) 컨트롤 문자 제거, (2) 길이 캡(product_name ≤120, precaution_text ≤500), (3) `product_name`에 Hangul+ASCII+일반 구두점 외 차단, (4) URL/`http`/SQL 키워드 포함 시 reject. 또한 explanation 단계의 user-quoting을 `repr()` 처리하여 명령어로 해석되지 않도록 한다.

---

### LOW

#### L1. `client_request_id` 클라이언트 임의 문자열 사용 ✅
- **위치**: `mobile/flutter_app/lib/features/supplements/supplement_repository.dart:88` (`'mobile-${microsecondsSinceEpoch}'`)
- **위험**: 다른 사용자의 ID 재사용 시 idempotency 충돌 노이즈 발생 (소유자 격리되어 데이터 노출은 아님).
- **수정**: 서버에서 owner-subject hash prefix 강제.

#### L2. `noqa: S105` 처리된 기본 비밀 ⚠️
- **위치**: `backend/Nutrition-backend/src/config.py:23 + 321 + model_validator(line 727)` (security-reviewer 보고 인용)
- **위험**: 향후 Settings 리팩터링 시 model_validator가 분리되면 기본 비밀이 prod에서 사용될 수 있음.
- **수정**: 단위 테스트 `assert raises` 추가하여 `Settings(environment="production", privacy_hash_secret=SecretStr(DEFAULT_PRIVACY_HASH_SECRET))` 시 실패하는지 자동 회귀.

#### L3. 빌드 산출물 / 대용량 자산 트래킹 점검 ✅
- **확인**: `git ls-files | grep -E '^\.env$|^backend/\.env$|api-key/.*\.(json|key|pem)'` → **0건** (트래킹 안됨, OK).
- **그러나**: `yeong-Lemon-Aid/PaddleOCR-main.zip` = **112 MB**가 작업 트리에 잔존. git에는 없지만 디스크/배포 이미지 부하 + 실수로 `git add .` 시 즉시 사고. → `.gitignore`에 명시적으로 추가 + 로컬에서 삭제 권장.

#### L4. 로그 PII 마스킹 필터 부재 ⚠️
- **위치**: `backend/Nutrition-backend/src/utils/logger.py` (security-reviewer 보고 인용)
- **위험**: 향후 누군가 `logger.info(user.subject)` / `Bearer ...` / OCR 텍스트 로깅 시 평문 노출.
- **수정**: `logging.Filter`로 `Bearer\s+\S+`, 이메일, `*subject*` 키 마스킹.

---

## 4. PIPA / 의료기기법 컴플라이언스

### 잘 되어 있는 부분 (그러나 잔존 리스크 있음)
- 금지어 필터: `nutrition/deficiency_analysis.py:21` `FORBIDDEN_TERMS = ("진단","치료","처방","복용량 변경")`. 적용처 4곳 검증됨 — `supplement_explanation.py:104,133`, `supplement_recommendation.py:227`, `nutrition_diagnosis.py:112`. ✅
  - 잔존 리스크: 영어/한자/오타("진단"이 아니라 "diagnosis"·"診斷"·"진ㄴ단") 우회 가능. 정규식·소문자화·NFC 정규화 추가 필요.
- 동의 게이트: OCR_IMAGE_PROCESSING / EXTERNAL_OCR_PROCESSING / SENSITIVE_HEALTH_ANALYSIS 3중 (`services/supplements.py:559-570`).
  - 잔존 리스크: H1(EXIF) 미해결이면 외부 OCR 동의를 받았더라도 GPS는 별도 항목으로 분리 동의를 받아야 함.
- HMAC owner hash(`privacy_hash_secret`), soft delete(`deleted_at`), audit log(`AuditEventService`), 보유기간(`retained_until`).

### 차단·즉시 조치
- H1: 외부 OCR 송신 전 EXIF 제거 — PIPA "민감정보(위치)" 별도 동의 불이행 리스크.
- M4: disclaimer 서버 강제 — 의료기기법 "진단 아님" 고지 책임을 서버가 보장하지 않으면 광고법·표시광고법까지 연쇄.
- 개인정보 처리방침(앱 내) 노출 여부 미확인 — 모바일 화면 `SupplementFlowScreen`에 진입 전 또는 첫 동의 시점에 PIPA 제30조 고지 7대 항목 표시 필요.

---

## 5. 테스트 커버리지·품질 점검

| 영역 | 파일 수 | 비고 |
|------|--------|------|
| 백엔드 `tests/unit/` | 20 | 적절. |
| 백엔드 `tests/integration/` | 7 | OCR 파이프라인 + LLM 인터페이스 보장에는 부족할 수 있음. |
| 백엔드 `tests/fixtures/` | (확인됨) | 픽스처 디렉터리 존재 — 라벨 이미지 sample 가용 추정. |
| 모바일 `test/unit/` | 3 (+ widget_test 1) | **현저히 부족**: app_config, api_error, supplement_models만. 업로드·권한·에러 UI·디스클레이머 렌더링 통합 테스트 없음. |
| E2E | ❌ 발견 못 함 | 모바일 → 백엔드 → Ollama 라운드트립 자동 테스트 없음. |

### 권장 추가 테스트
- `tests/integration/test_supplement_intake_exif.py`: GPS 있는 JPEG 업로드 시 응답·학습 스토어 산출물에 EXIF 부재 검증.
- `tests/integration/test_clinical_disclaimer_stamping.py`: `/recommendations/explain` 호출 시 클라이언트가 `clinical_disclaimer=""` 보내도 응답은 SUPPLEMENT_IMPACT_DISCLAIMER 그대로 반환되는지 회귀.
- `tests/unit/test_forbidden_terms_normalization.py`: "Diagnosis"·"진ㄴ단"·"진​단" 같은 우회 시도가 차단되는지.
- 모바일 `test/integration/upload_flow_test.dart` (mockServer 기반): 권한 거부·네트워크 실패·202 응답·진행률 표시 시나리오.

### 실행 명령
```bash
cd yeong-Lemon-Aid/backend/Nutrition-backend
uv run pytest --collect-only          # 카운트 확인
uv run pytest -m "not slow" -q        # 빠른 회귀

cd yeong-Lemon-Aid/mobile/flutter_app
flutter test --coverage
```

---

## 6. 의존성 CVE 스캔

본 감사 환경에는 `pip-audit`/`uv`/`flutter pub outdated` 실행 결과를 보장할 수 없어 **권장 명령과 핵심 패키지 가드라인만 기재**한다.

### 백엔드
```bash
cd backend/Nutrition-backend
uv pip compile --upgrade pyproject.toml -o requirements-lock.txt
pip-audit -r requirements-lock.txt --strict
```
핵심 최소 버전 권장:
- `Pillow >= 10.4` (CVE-2024-28219, CVE-2024-22195 등 디컴프레션·텍스트 처리 결함 다수)
- `pyjwt >= 2.8` (알고리즘 혼동 CVE)
- `fastapi >= 0.115`, `starlette >= 0.41` (다중 file-upload DoS)
- `cryptography >= 43`
- `python-multipart >= 0.0.18` (CVE-2024-53981 ReDoS)

### 모바일
```bash
cd mobile/flutter_app
flutter pub outdated --mode=null-safety
dart pub deps --json | jq '.packages[] | {name, version}'
```
`image_picker`, `http`, `flutter_secure_storage` 최신 안정버전 유지. `http` → 가능하면 cert pinning 친화적인 `dio`로 마이그레이션 검토.

---

## 7. 앱 스토어 출시 체크리스트

| 항목 | 현황 | 조치 |
|------|------|------|
| iOS ATS — `NSAllowsArbitraryLoads=false` | ❓ Info.plist 미검증 | 명시적으로 false + 예외 도메인 0개로 유지 |
| Android `network_security_config.xml` (prod) | ❌ 부재 확인 | 추가 + `cleartextTrafficPermitted="false"` |
| Camera·Photos 권한 rationale UI | ❌ 코드상 부재 | 첫 진입 시 한국어로 "라벨 인식에만 사용, 외부 OCR 전송 동의는 별도" 명시 |
| 진행률 인디케이터 | ❌ 부재 | 업로드/분석/LLM 3단계 stepper |
| 에러 복구 UI | ⚠️ SnackBar만 | 카테고리별 메시지 + 재시도/다른 사진 선택 |
| 개인정보 처리방침 in-app 링크 | ❓ 미확인 | 첫 진입·설정·동의 화면 3곳 노출 |
| 의료앱 reviewer 키워드 회피 | ✅ "진단 아님" 디스클레이머 + 금지어 필터 | M4 해결 전엔 안심 금지 |
| 인앱 결제·구독 — 없음 | n/a | — |
| Account deletion 기능 | ❓ 미확인 | iOS 5.1.1(v) 의무, Android 정책 동등. owner_subject 기반 soft+hard delete 흐름 필수 |
| Crash reporting (Sentry/Firebase) | ❓ 미확인 | 도입 시 PII redaction 필터 동시 적용 (L4 참고) |

---

## 8. 기존 brainstorm 문서와의 관계

`Brand-New-update/` 폴더 기존 6개 문서 vs 현 구현:

| 기존 문서 | 제안 핵심 | 현 구현 매핑 | 갭 |
|-----------|----------|-------------|----|
| `2026-05-17-paddleocr-learning-accuracy-design-plan.md` | PaddleOCR 폴백 + 픽스처 평가 | ✅ `ocr/factory.py`에 PaddleOCR 어댑터 + Ollama vision fallback 포함 | 픽스처 기반 자동 평가 루프 미발견 |
| `2026-05-17-plan-a-paddleocr-local-layout-normalization-detail-plan.md` | PaddleOCR 단어 좌표·라인 파서 | ⚠️ `services/supplement_layout_context.py` 존재. 단어 좌표 풀 활용 여부 확인 필요 | 시각화·디버그 export 부재 |
| `2026-05-17-plan-b-roi-image-quality-learning-implementation.md` | 블러·글레어·해상도 품질 평가 | ✅ `services/supplement_image_quality.py` + retake reason 트래킹 | 학습 데이터 자동 큐레이션 미확인 |
| `2026-05-17-plan-c-paddleocr-finetuning-detail-plan.md` | 도메인 fine-tuning | ⚠️ `learning/paddleocr_finetuning.py` 존재, 실제 학습 파이프라인 실행 여부 미확인 | 학습 결과 평가·롤백 게이트 부재 |
| `2026-05-17-plan-d-parser-domain-correction-learning-detail-plan.md` | 사용자 피드백 + 규칙 학습 | ⚠️ `services/parser_domain_correction.py` 존재 | 사용자→교정→재학습 UX 모바일에 미반영 |
| `2026-05-17-plan-e-cross-cutting-governance-detail-plan.md` | 멀티 이미지 패키지·역할 분류 | ⚠️ `services/governance.py` 존재 | governance 정책 enforcement test 부재 |
| `2026-05-17-supplement-label-image-risk-brainstorm.md` | 15개 실패 시나리오 + 완화 | ⚠️ `services/supplement_image_risk_actions.py` 존재 | 시나리오별 회귀 테스트 매핑표 부재 |

**관찰**: 설계 의도는 폴더 구조 + 서비스 파일에 대부분 반영. **실제 enforcement·자동 회귀 테스트가 미흡**한 것이 공통 패턴. → 다음 sprint는 "신규 기능 추가"보다 "기존 서비스 enforcement 테스트화"가 우선.

---

## 9. 액션 플랜 (24h / 1주 / 4주)

### 24시간 이내 (출시 차단 해소)
1. **EXIF strip**: `services/supplement_intake.py`에 `strip_image_metadata()` 추가 + 호출. 회귀 테스트 1건 추가.
2. **disclaimer 서버 강제**: `services/supplement_explanation.py:99` 하드 오버라이트. 회귀 테스트 1건.
3. **`Image.MAX_IMAGE_PIXELS`** 전역 설정 + `.load()` 가드 추가 (영향 모듈: `vision/preprocessing.py`, `services/supplement_image_quality.py`, `learning/object_storage.py`).
4. **`PaddleOCR-main.zip` 삭제** + `.gitignore` 추가.

### 1주 이내 (보안 기본기)
5. SecureHeadersMiddleware 작성·등록 (HSTS, nosniff, Referrer-Policy, Permissions-Policy).
6. Flutter ApiClient → cert pinning 도입 + Android `network_security_config.xml` + iOS ATS 명시.
7. OCR free-text 필드 sanitization + 길이 캡 (`services/supplement_parser.py`).
8. 모바일 권한 rationale UI + 진행률 인디케이터.
9. `pip-audit` CI 단계 추가.

### 4주 이내 (스토어 제출 직전)
10. Rate-limiter Redis 백엔드 + readiness probe 통합 (M1).
11. CORS production validator에 https-only 검증 추가 (M3).
12. PII 마스킹 logging.Filter 도입 (L4).
13. Account deletion 흐름 (soft + hard) + 모바일 진입점.
14. Crash reporting (Sentry) + PII scrubber.
15. 모바일 integration 테스트 스위트 (업로드/권한/에러/disclaimer 렌더링).
16. PIPA 자가진단표 + 의료기기 해당성 검토서(식약처 가이드라인 기준) 문서화.
17. 금지어 필터 NFC 정규화·다국어·zero-width 우회 대응.

---

## 10. 부록

### A. 직접 읽은 파일 (인용 신뢰도 ✅)
- `backend/Nutrition-backend/src/services/supplement_intake.py:650-695, 705`
- `backend/Nutrition-backend/src/services/supplement_explanation.py:85-105`
- `backend/Nutrition-backend/src/main.py` (보안 미들웨어 grep)
- `mobile/flutter_app/lib/core/config/app_config.dart:50-78`
- `mobile/flutter_app/lib/core/api/api_client.dart` (cert pinning grep)
- `PROJECT_GUIDE.md:1-120`

### B. 서브에이전트 보고서로 보강한 영역 (신뢰도 ⚠️ — 표본 검증함)
- 파이프라인 7단계 흐름 매핑 (Explore 에이전트 1)
- 모바일·docs 인벤토리 (Explore 에이전트 2)
- 보안 18건 종합 (security-reviewer 에이전트)

### C. 미검토 영역 (다음 라운드 권고)
- 백엔드 `tests/integration/` 7개 파일의 실제 커버리지(라인/브랜치).
- `vision/yolo.py` 모델 가중치 출처·라이선스.
- Ollama 모델 라이선스 (예: llama 계열) — 상업 배포 시 EULA 검증 필요.
- LDB 인터페이스 설계서(있다면) — 발주처와의 약속 일치 여부.
- 모바일 빌드 산출물 사이즈·proguard·R8 설정.

### D. 사용 도구
- Read·Grep·Bash (git, find, grep)
- Explore subagent × 2, security-reviewer subagent × 1
- pip-audit / flutter test — 미실행 (권장 명령만 기재)

---

## 결론

**좋은 소식**: 사용자 파트는 "scaffold만 있는 사이드 프로젝트"가 아니라 동의 게이트·금지어 필터·HMAC·audit log·결정론적 disclaimer 상수·OCR 폴백 체인까지 갖춘 **소형 production-grade 시스템**이다. 8주 MVP 일정 대비 실구현이 앞서 있다.

**나쁜 소식**: 그렇기 때문에 **남은 결함이 더 부각된다**. EXIF·disclaimer echo·cert pinning은 모두 "있는데 안 닫힌" 갭으로, 스토어 reviewer·법무·발주처 모두 가장 먼저 짚는 항목이다. 위 §9 24시간 조치 4건이 사실상 출시 게이트의 입구다.

다음 단계 권고: 본 보고서의 §9.1~9.4를 즉시 티켓화하여 다음 sprint 시작 전 머지. §9 1주 이내 항목은 sprint 백로그 1순위로 편성.

— *감사 종료* —
