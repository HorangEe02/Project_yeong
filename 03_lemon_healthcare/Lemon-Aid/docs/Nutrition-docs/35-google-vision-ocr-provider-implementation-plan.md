# 35. Google Vision OCR Provider 상세 설계 및 구현 플랜

작성일: 2026-05-14
최종 보강일: 2026-05-15
상태: Google Vision OCR provider 착수 상세 설계 완료 / 구현 전 플랜
대상 브랜치: `team/yeong-tech` 반영 전용, `main` 직접 커밋/푸시 제외
범위: `POST /api/v1/supplements/analyze`에서 Google Cloud Vision OCR + OCR text parse preview를 한 번에 동작시키기 위한 구현 설계

2026-05-15 착수 결론:

- 운영 인증은 **전용 user-managed service account를 런타임에 attached service account로 붙이고 ADC로 토큰을 받는 방식**을 채택한다. 즉, "OCR 호출 전용 계정"과 "attached service account"를 분리된 대안으로 보지 않고, 전용 계정을 attached 방식으로 운영한다.
- 로컬 개발과 제한된 수동 smoke test는 기존 `.env` 흐름에 맞춰 `GOOGLE_CLOUD_API_KEY`를 허용한다. API key는 서버 환경변수에만 두고, REST URL query parameter가 아니라 `x-goog-api-key` header로만 전달한다.
- service account key JSON은 저장소, fixture, PR 본문, issue, 문서 예시에 두지 않는다. 운영에서는 `GOOGLE_APPLICATION_CREDENTIALS` 파일 경로 방식도 기본 경로로 사용하지 않는다.
- 1차 구현은 Google Vision full-image `DOCUMENT_TEXT_DETECTION` + 기존 `parse_supplement_analysis_ocr_text` preview 연결이다. YOLO ROI, Ollama vision fallback, PaddleOCR/CLOVA fallback은 docs/33 기준 2차 확장으로 둔다.

## 0. 현재 결정 사항

프로젝트 방향은 **성능 우선 OCR**이다. 따라서 영양제 라벨 이미지의 1차 OCR provider는 로컬 OCR이 아니라 **Google Cloud Vision `DOCUMENT_TEXT_DETECTION`** 으로 설계한다.

이미 완료된 사전 작업:

- Google Cloud Project 생성
- Billing 연결
- Cloud Vision API 활성화
- local 개발용 API key `.env` 입력 방식 합의

구현 전 운영 준비 작업:

- `lemon-ocr-vision-*` 형태의 OCR 호출 전용 user-managed service account 생성
- 운영 배포 리소스에 위 service account attach
- attached service account + ADC 방식으로 실제 `images:annotate` smoke test
- local/smoke API key를 Cloud Vision API와 서버 호출 위치로 제한
- API key를 repo, docs, fixture, issue/PR 본문에 남기지 않는 운영 규칙 적용
- Google Vision 사용량 budget/quota alert 설정
- 외부 OCR 이미지 전송에 대한 별도 동의 문구 리뷰
- 한국어+영어 혼합 영양제 라벨 fixture 수집 및 benchmark 기준 확정

## 1. 공식 문서 확인 기준

| 항목 | 공식 문서에서 확인한 내용 | 본 프로젝트 적용 |
| --- | --- | --- |
| OCR feature | Cloud Vision OCR는 `TEXT_DETECTION`과 `DOCUMENT_TEXT_DETECTION`을 제공한다. `DOCUMENT_TEXT_DETECTION`은 dense text와 문서형 구조 OCR에 맞다. | 영양성분표, 원료명, 섭취량처럼 밀집 텍스트가 많은 영양제 라벨은 `DOCUMENT_TEXT_DETECTION`을 기본 feature로 사용한다. |
| REST API | `images:annotate`는 batch image annotation API이며 `POST https://vision.googleapis.com/v1/images:annotate`로 호출한다. Vision request 문서는 해당 REST 요청이 API key 또는 OAuth token으로 인증되어야 한다고 설명한다. | MVP는 REST `images:annotate`에 `x-goog-api-key` header를 붙이는 방식으로 구현한다. 비동기 batch/GCS output 방식은 raw image 보관 복잡도가 커서 제외한다. |
| 인증 | Google REST 인증 문서는 API key를 `x-goog-api-key` header로 전달할 수 있고, query parameter 방식은 URL 노출 위험이 있다고 설명한다. | local dev는 `.env`의 `GOOGLE_CLOUD_API_KEY` 하나만 입력한다. URL query string에는 key를 넣지 않고 header로만 전달한다. |
| 운영 인증 | Google ADC 문서는 Google Cloud compute resource에서 attached service account credential을 프로덕션 권장 방식으로 설명한다. Vision 인증 문서도 Google Cloud에서 실행되는 workload는 compute resource에 attached service account를 사용하는 방식을 preferred authentication method로 설명한다. | 운영은 service account key JSON이 아니라 user-managed OCR service account를 런타임에 attach하고 ADC bearer token으로 REST 호출한다. |
| 서비스 계정 key | ADC 문서는 service account key가 보안 위험이며 권장되지 않는다고 설명한다. | credential JSON은 repo, container image, test fixture, PR/issue, 문서 예시에 저장하지 않는다. `GOOGLE_APPLICATION_CREDENTIALS` 파일 경로 운영은 예외 승인 없이는 사용하지 않는다. |
| 데이터 사용 | online immediate operation인 `BatchAnnotateImages`/`BatchAnnotateFiles`는 image data를 memory에서 처리하고 disk에 persist하지 않는다고 설명한다. Google은 Vision API에 보낸 content를 Vision 기능 학습/개선에 사용하지 않는다고 설명한다. | 그럼에도 외부 provider 전송이므로 별도 consent와 audit gate를 둔다. raw image와 raw OCR text는 우리 DB에 저장하지 않는다. |
| 과금 | Vision pricing은 image 단위, feature 단위 과금이며 `Text Detection`과 `Document Text Detection` 항목이 따로 공시된다. | 운영 전 pricing page 기준으로 예산 알림을 설정한다. 문서에는 내부 cost 절감 수치를 만들지 않는다. |

참조 URL:

- Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Cloud Vision authentication: https://cloud.google.com/vision/docs/authentication
- Cloud Vision request/authentication: https://cloud.google.com/vision/docs/request
- Google REST API key authentication: https://cloud.google.com/docs/authentication/rest
- Google Application Default Credentials: https://cloud.google.com/docs/authentication/application-default-credentials
- Cloud Vision REST `images:annotate`: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- Cloud Vision Data Usage FAQ: https://cloud.google.com/vision/docs/data-usage
- Cloud Vision pricing: https://cloud.google.com/vision/pricing

확인 한계:

- I cannot find the official documentation for a Vision-specific predefined runtime caller role for inline `images:annotate` OCR. Vision 인증 문서는 Cloud Storage object를 지정하는 요청에는 `roles/storage.objectViewer`가 보통 필요하다고 설명하지만, MVP는 inline image bytes를 전송하므로 GCS object 접근 권한을 기본 요구사항으로 두지 않는다. 따라서 구현 전 attached service account smoke test로 최소 권한을 확인하고, `Owner`/`Editor`/`Viewer` basic role 부여는 금지한다.

## 2. 기존 문서와의 관계

| 문서 | 이번 문서에서 갱신하는 점 |
| --- | --- |
| [docs/25](./25-ocr-text-supplement-analysis-plan.md) | OCR text를 structured parse preview로 넘기는 흐름은 유지한다. |
| [docs/26](./26-ot-s2-ocr-provider-adapter-implementation-plan.md) | OT-S2 1차 provider 후보가 CLOVA 중심이었으나, 현재 프로젝트 결정은 Google Vision primary이다. adapter 계약은 그대로 사용한다. |
| [docs/27](./27-ot-s2b-google-vision-ocr-review-plan.md) | Google Vision이 "검토 후보"였던 상태를 "1차 구현 대상"으로 승격한다. |
| [docs/31](./31-backend-feature-specifications.md) | 현재 구현 상태는 여전히 `NoopOCRAdapter`만 export한다. Google Vision 구현 후 현행 상태 표를 갱신한다. |
| [docs/33](./33-three-tier-ocr-pipeline-implementation-guide.md) | 3-tier 목표 구조 중 Tier 2를 먼저 구현한다. YOLO ROI와 Ollama vision assist는 2차 단계로 둔다. |

## 3. 브레인스토밍 결론

검토한 OCR pipeline 선택지는 세 가지다.

| 선택지 | 장점 | 리스크 | 결론 |
| --- | --- | --- | --- |
| Google Vision 단독 MVP | 가장 빨리 `/supplements/analyze`에서 실제 OCR+parse preview를 확인할 수 있다. 현재 `OCRAdapter` 경계와 잘 맞는다. | ROI crop이 없어 배경/반사/작은 글씨에서 비용과 품질 편차가 생길 수 있다. | 1차 구현으로 채택 |
| YOLO ROI 후 Google Vision | 라벨 영역만 보내 OCR 노이즈를 줄일 수 있다. docs/33 목표 구조와 일치한다. | YOLO gate, model file, ROI crop 검증이 추가되어 첫 provider 연결이 늦어진다. | 2차 최적화 |
| Google Vision 후 Ollama vision fallback/cross-check | OCR empty/low-confidence 상황에서 사용자 확인 품질을 높일 수 있다. | fallback 판단, 모델 설치 상태, hallucination guard가 추가된다. | 2차 안정화 |

이번 구현 플랜의 1차 목표는 **Google Vision full-image OCR + 기존 OCR text parser preview**다. 즉, `POST /api/v1/supplements/analyze`가 이미 검증한 이미지 intake를 만들고, Google Vision text를 받아 `parse_supplement_analysis_ocr_text`로 이어지게 한다.

인증/credential 운영 선택지는 별도로 검토했다.

| 선택지 | 장점 | 리스크 | 결론 |
| --- | --- | --- | --- |
| API key만 사용 | REST MVP가 가장 단순하고 로컬 `.env` 흐름과 맞는다. | key가 장기 credential이며, 모바일/프론트 노출·URL query 노출·권한 제한 누락 위험이 있다. | 로컬 개발과 수동 smoke test에만 허용 |
| service account key JSON | 서버 간 인증을 명시적으로 구성할 수 있다. | Google ADC 문서가 service account key를 보안 위험으로 설명한다. 저장소/컨테이너/운영 서버에 장기 JSON이 남을 수 있다. | 기본 경로에서 제외 |
| 전용 user-managed service account + attached service account + ADC | 장기 key 파일 없이 운영 런타임 identity로 호출한다. Google Cloud 프로덕션 권장 방식과 맞고, service account를 OCR 호출 범위로 분리할 수 있다. | 배포 리소스에 attach가 필요하고, 로컬에서는 impersonation 또는 API key 별도 경로가 필요하다. | 운영 방식으로 채택 |

따라서 구현은 두 authentication mode를 지원하되 기본은 항상 OFF다.

- `GOOGLE_VISION_AUTH_MODE=api_key`: local 개발과 명시 opt-in smoke test용. `GOOGLE_CLOUD_API_KEY` 필요.
- `GOOGLE_VISION_AUTH_MODE=adc`: staging/production용. attached service account 또는 local impersonation ADC 필요.
- `ENVIRONMENT=production`에서 `OCR_PRIMARY_PROVIDER=google_vision`이면 `GOOGLE_VISION_AUTH_MODE=adc`만 허용한다.

## 4. 목표 실행 흐름

```mermaid
sequenceDiagram
    participant Client as Frontend/Mobile
    participant API as FastAPI /api/v1/supplements/analyze
    participant Consent as Consent Gate
    participant Factory as OCR Adapter Factory
    participant GV as GoogleVisionOCRAdapter
    participant Parser as OCR Text Parser
    participant DB as SupplementAnalysisRun

    Client->>API: multipart supplement label image
    API->>Consent: OCR_IMAGE_PROCESSING 확인
    alt OCR_PRIMARY_PROVIDER=google_vision
        API->>Consent: EXTERNAL_OCR_PROCESSING 확인
    end
    API->>Factory: build_supplement_ocr_adapter(settings)
    Factory-->>API: GoogleVisionOCRAdapter or None
    API->>DB: intake preview 생성(image hash/metadata only)
    API->>GV: DOCUMENT_TEXT_DETECTION(image bytes)
    GV-->>API: OCRResult(text, provider, confidence)
    API->>Parser: parse_supplement_analysis_ocr_text(text)
    Parser->>DB: ocr_text_hash + structured parsed_snapshot 저장
    DB-->>API: requires_confirmation preview
    API-->>Client: OCR+parse preview
```

핵심 원칙:

- API response는 preview이며, 사용자가 확인하기 전에는 건강 조언이나 복용량 변경 안내로 취급하지 않는다.
- 원본 이미지는 DB에 저장하지 않는다. 현재 `SupplementAnalysisRun`은 `image_sha256`, image metadata, `ocr_text_hash`, structured snapshot을 저장하는 구조다.
- raw OCR text는 DB에 저장하지 않는다. parser 단계에서 HMAC hash만 남기는 현행 정책을 유지한다.
- OCR provider 장애는 사용자 확인 가능한 실패/수동 입력 흐름으로 degrade한다.

## 5. 설정 설계

이번 보정으로 backend `Settings`에는 `google_cloud_api_key`가 추가되었다. `Settings`는 프로젝트 루트 `.env`와 `backend/.env`를 모두 읽고, 빈 placeholder 값은 무시한다. provider 선택값과 외부 OCR gate는 아직 구현 전이므로 후속 구현 시 다음 필드를 기준으로 확장한다.

```python
ocr_primary_provider: Literal["none", "google_vision"] = "none"
allow_external_ocr: bool = False
google_vision_auth_mode: Literal["api_key", "adc"] = "api_key"
google_cloud_api_key: SecretStr | None = None
google_cloud_project: str | None = None
google_vision_location: Literal["global", "us", "eu"] = "global"
google_vision_feature: Literal["document_text_detection"] = "document_text_detection"
google_vision_language_hints: list[str] = Field(default_factory=list)
google_vision_timeout_seconds: int = Field(default=15, ge=1, le=60)
google_vision_max_retries: int = Field(default=2, ge=0, le=5)
ocr_confidence_threshold: float = Field(default=0.85, ge=0, le=1)
```

환경변수 예시:

```dotenv
# Local development / explicit smoke only
OCR_PRIMARY_PROVIDER=google_vision
ALLOW_EXTERNAL_OCR=true
GOOGLE_VISION_AUTH_MODE=api_key
GOOGLE_CLOUD_API_KEY=your-google-cloud-api-key
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_VISION_LOCATION=global
GOOGLE_VISION_FEATURE=document_text_detection
GOOGLE_VISION_LANGUAGE_HINTS=[]
GOOGLE_VISION_TIMEOUT_SECONDS=15
GOOGLE_VISION_MAX_RETRIES=2
OCR_CONFIDENCE_THRESHOLD=0.85
```

```dotenv
# Staging / production
OCR_PRIMARY_PROVIDER=google_vision
ALLOW_EXTERNAL_OCR=true
GOOGLE_VISION_AUTH_MODE=adc
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_VISION_LOCATION=global
GOOGLE_VISION_FEATURE=document_text_detection
GOOGLE_VISION_LANGUAGE_HINTS=[]
GOOGLE_VISION_TIMEOUT_SECONDS=15
GOOGLE_VISION_MAX_RETRIES=2
OCR_CONFIDENCE_THRESHOLD=0.85
```

검증 규칙:

- 기본값은 `OCR_PRIMARY_PROVIDER=none`, `ALLOW_EXTERNAL_OCR=false`다.
- `OCR_PRIMARY_PROVIDER=google_vision`인데 `ALLOW_EXTERNAL_OCR=false`이면 startup 또는 dependency 생성 단계에서 fail closed한다.
- `GOOGLE_VISION_AUTH_MODE=api_key`인데 `GOOGLE_CLOUD_API_KEY`가 비어 있으면 adapter factory가 fail closed한다.
- `GOOGLE_VISION_AUTH_MODE=adc`이면 `GOOGLE_CLOUD_API_KEY`를 사용하지 않고 ADC bearer token provider만 사용한다.
- `ENVIRONMENT=production`에서 `OCR_PRIMARY_PROVIDER=google_vision`이면 `GOOGLE_VISION_AUTH_MODE=adc`, `GOOGLE_CLOUD_PROJECT`가 필요하다.
- `GOOGLE_APPLICATION_CREDENTIALS`는 deprecated compatibility field로 남기되, 운영 provider 구현 경로에서는 사용하지 않는다. production validator는 이 값이 설정된 상태에서 Google Vision을 켜는 구성을 차단한다.
- local dev에서는 `.env`에 `GOOGLE_CLOUD_API_KEY` 값만 입력할 수 있다. API key는 Google Cloud Console에서 Cloud Vision API로 제한하고, 서버 env에만 둔다. 모바일/프론트 번들에는 포함하지 않는다.
- `GOOGLE_VISION_LOCATION=us|eu`를 쓰려면 `GOOGLE_CLOUD_PROJECT`가 필요하다. MVP 기본값은 `global`이다. regional endpoint를 쓰는 경우 REST endpoint는 `projects/{project}/locations/{location}/images:annotate` 계열로 전환한다.
- `GOOGLE_VISION_LANGUAGE_HINTS`는 기본 빈 배열이다. `["ko", "en"]`은 fixture benchmark에서 개선이 확인된 경우에만 켠다.
- `GOOGLE_VISION_TIMEOUT_SECONDS`와 `GOOGLE_VISION_MAX_RETRIES`는 provider 장애가 API 전체 지연으로 번지지 않도록 상한을 둔다.
- `OCR_CONFIDENCE_THRESHOLD=0.85`는 fallback/review routing 후보값이다. Google 공식 권장 threshold가 아니며 fixture 평가 전에는 정확도 지표로 해석하지 않는다.

`config/implementation-readiness.settings.json` 보정 방향:

- 현재 `OCR_PRIMARY_PROVIDER.default=google_vision`은 안전 기본값과 맞지 않는다. 코드 구현 시 config manifest는 `none` 기본값, Google Vision은 명시 opt-in으로 맞춘다.
- `OCR_FALLBACK_PROVIDER=clova` 같은 단일 selector 표현은 현재 코드와 맞지 않는다. CLOVA는 `ENABLE_CLOVA_OCR=false` 기본값의 optional backup adapter로 구현되어 있으며, `ALLOW_EXTERNAL_OCR`, `CLOVA_OCR_API_URL`, `CLOVA_OCR_SECRET`와 vendor/security gate가 맞을 때만 factory fallback tuple에 들어간다.
- `GOOGLE_VISION_AUTH_MODE.default=api_key`는 local/smoke 기본값일 뿐이며, production section에는 `adc`를 별도 요구사항으로 명시한다.
- `GOOGLE_APPLICATION_CREDENTIALS`는 "사용 가능 예시"가 아니라 "JSON key 파일 금지/예외 승인 필요" 항목으로 재분류한다.

## 6. Consent / Privacy 설계

현행 `/supplements/analyze`는 `ConsentType.OCR_IMAGE_PROCESSING`만 요구한다. Google Vision은 외부 provider로 이미지 bytes를 전송하므로 기존 OCR 동의와 분리하는 편이 낫다.

권장 변경:

```python
class ConsentType(StrEnum):
    OCR_IMAGE_PROCESSING = "ocr_image_processing"
    EXTERNAL_OCR_PROCESSING = "external_ocr_processing"
```

정책 문구 방향:

- `OCR_IMAGE_PROCESSING`: "영양제 라벨 이미지를 텍스트 추출 및 분석 preview 생성을 위해 처리합니다."
- `EXTERNAL_OCR_PROCESSING`: "텍스트 추출 성능 향상을 위해 영양제 라벨 이미지가 Google Cloud Vision API로 전송될 수 있습니다. 원본 이미지는 서비스 DB에 저장하지 않으며, 분석 결과는 사용자가 확인하기 전까지 preview입니다."

DB 영향:

- `ConsentPolicy.consent_type`과 `ConsentRecord.consent_type`은 `String(64)` 컬럼이므로 enum value 추가 자체는 DB schema migration 없이 가능할 가능성이 높다.
- 다만 active policy seed/sync, consent state response, API contract test는 반드시 추가한다.

API gate:

- `OCR_PRIMARY_PROVIDER=none`: 기존처럼 `OCR_IMAGE_PROCESSING`만 확인한다.
- `OCR_PRIMARY_PROVIDER=google_vision`: `OCR_IMAGE_PROCESSING`과 `EXTERNAL_OCR_PROCESSING`을 모두 확인한 뒤 adapter를 호출한다.
- missing consent response는 `403 consent_required`와 `required_consents` 배열에 누락 동의를 모두 담는다.
- OpenAPI `x-required-consents`는 기본 요구사항인 `OCR_IMAGE_PROCESSING`을 유지하고, `route_contract` helper를 확장해 `x-conditional-consents=["external_ocr_processing"]`를 추가한다. 이렇게 해야 provider OFF 환경에서도 문서가 과도하게 요구사항을 표시하지 않으면서, provider ON 환경의 PR gate가 외부 OCR 동의를 확인할 수 있다.
- route 내부에는 `_required_supplement_analyze_consents(settings)` helper를 추가한다. 이 helper는 provider 설정을 보고 실제 runtime 요구 동의 목록을 계산한다.

Audit:

- provider 호출 전 consent 부족: `supplement_external_ocr_blocked`
- provider 성공: `supplement_ocr_provider_completed`
- provider 실패: `supplement_ocr_provider_failed`
- metadata에는 provider, confidence presence, raw image/text 저장 여부만 남긴다.
- API key, raw OCR text, raw image bytes, Google response 원문은 audit/log에 남기지 않는다.

## 7. Adapter 설계

추가 파일:

- `backend/src/ocr/providers/google_vision.py`
- `backend/src/ocr/providers/google_vision_auth.py`
- `backend/src/ocr/factory.py`
- `backend/tests/unit/ocr/test_google_vision_provider.py`
- `backend/tests/unit/ocr/test_google_vision_auth.py`
- `backend/tests/unit/ocr/test_ocr_factory.py`
- `backend/tests/integration/api/test_supplement_analyze_google_vision.py`

adapter contract:

```python
class GoogleVisionOCRAdapter(OCRAdapter):
    """Google Cloud Vision OCR adapter for supplement label images."""

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Extract dense supplement label text with Google Vision.

        Args:
            image: Validated supplement label image payload.

        Returns:
            OCR text, provider label, and optional normalized confidence.

        Raises:
            OCRError: If Google Vision authentication, quota, timeout, or response parsing fails.
        """
```

request strategy:

- REST `images:annotate` endpoint를 `httpx.AsyncClient`로 호출한다.
- feature는 `DOCUMENT_TEXT_DETECTION`만 MVP에 포함한다.
- image bytes는 base64로 request body에 넣고 API key는 `x-goog-api-key` header로 전달한다.
- `GOOGLE_VISION_AUTH_MODE=adc`에서는 `google-auth` 기반 ADC credential을 refresh해서 `Authorization: Bearer ...` header를 만든다. 테스트는 실제 Google credential을 쓰지 않고 fake auth header provider를 주입한다.
- `GOOGLE_CLOUD_PROJECT`가 설정되어 있으면 ADC REST 호출에는 quota/billing project 구분을 위해 `x-goog-user-project` header를 붙일 수 있게 한다. 단, API key mode에서는 이 header를 기본으로 붙이지 않는다.
- async batch, GCS input/output은 MVP에서 제외한다.
- `httpx.AsyncClient` 또는 request callable은 adapter 생성자에서 주입 가능하게 한다. 테스트는 fake transport/client만 사용한다.

auth provider contract:

```python
class GoogleVisionAuthHeadersProvider(Protocol):
    """Build sanitized request headers for Google Vision REST calls."""

    async def build_headers(self) -> dict[str, str]:
        """Return authentication headers without exposing raw credentials."""
```

구현 후보:

- `GoogleVisionApiKeyAuthHeaders`: `{"x-goog-api-key": "..."}`
- `GoogleVisionADCAuthHeaders`: `{"Authorization": "Bearer ..."}` + optional `x-goog-user-project`

adapter는 raw secret을 log, exception, audit metadata에 포함하지 않는다. provider error body도 code/status/message만 sanitize해서 `OCRError`로 변환한다.

response normalization:

1. `response.error`가 있으면 sanitized `OCRError`로 변환한다.
2. `full_text_annotation.text`를 우선 사용한다.
3. 없으면 `text_annotations[0].description`을 fallback 후보로 사용한다.
4. `fullTextAnnotation.pages[].blocks[].paragraphs[].words[]`는 `OCRResult.pages`에 page/block/paragraph/word hierarchy로 정규화한다.
5. 둘 다 없으면 `OCRResult(text="", provider="google_vision_document", confidence=None, pages=())`을 반환한다.
6. confidence는 word confidence 평균을 우선 사용하고, 없으면 paragraph/block/page confidence로 fallback한다. 값이 없으면 `None`으로 둔다. 임의 confidence를 만들지 않는다.

provider label:

- `google_vision_document`

factory:

```python
def build_supplement_ocr_adapter(settings: Settings) -> OCRAdapter | None:
    if settings.ocr_primary_provider == "none":
        return None
    if settings.ocr_primary_provider == "google_vision":
        if not settings.allow_external_ocr:
            raise OCRConfigurationError("ALLOW_EXTERNAL_OCR=true is required for Google Vision.")
        if settings.google_vision_auth_mode == "api_key" and settings.google_cloud_api_key is None:
            raise OCRConfigurationError("GOOGLE_CLOUD_API_KEY is required for Google Vision.")
        if settings.google_vision_auth_mode == "adc" and settings.google_cloud_project is None:
            raise OCRConfigurationError("GOOGLE_CLOUD_PROJECT is required for Google Vision ADC mode.")
        if settings.environment == "production" and settings.google_vision_auth_mode != "adc":
            raise OCRConfigurationError("GOOGLE_VISION_AUTH_MODE=adc is required in production.")
        return GoogleVisionOCRAdapter(auth_headers=..., ...)
```

## 8. API 연결 설계

현재 `analyze_supplement_image(..., adapters=None)`는 adapter가 없으면 intake-only로 동작한다. 따라서 API route는 다음 dependency를 추가하는 방식이 가장 작다.

```python
def get_supplement_image_analysis_adapters(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementImageAnalysisAdapters:
    return SupplementImageAnalysisAdapters(
        ocr=build_supplement_ocr_adapter(settings),
    )
```

route 변경:

- `analyze_supplement_label`에서 settings 기준으로 필요한 consent 목록을 계산한다.
- Google Vision provider가 선택된 경우 `EXTERNAL_OCR_PROCESSING`도 확인한다.
- `analyze_supplement_image(..., adapters=adapters)`로 adapter를 전달한다.
- `OCRError`와 provider 설정 오류를 안정적인 HTTP error로 mapping한다.
- provider 설정 오류는 이미지 파일을 읽거나 intake row를 만들기 전에 503으로 반환한다.
- Google Vision runtime 오류는 사용자에게 직접 입력을 계속할 수 있게 intake-only preview로 degrade한다. 이 경우 raw OCR text는 없고, `warnings`에 자동 텍스트 추출 실패 안내만 남긴다.
- parser 오류도 image-flow에서는 수동 확인 가능 preview로 degrade하는 쪽을 우선 검토한다. 기존 `/analyses/{analysis_id}/ocr-text` 수동 endpoint의 502 정책과 다르므로 테스트에서 분기 의도를 고정한다.

HTTP error 후보:

| 상황 | HTTP | code |
| --- | --- | --- |
| 외부 OCR 동의 없음 | 403 | `consent_required` |
| Google Vision 설정 누락 또는 gate 불일치 | 503 | `ocr_provider_unconfigured` |
| Google auth/quota/timeout/5xx | 202 | intake preview 유지, `automatic_ocr_unavailable` warning 추가 |
| OCR text empty | 202 | intake preview 유지, `ocr_text_empty` warning 추가 |
| OCR text parse 실패 | 202 | intake preview 유지, `ocr_parse_preview_unavailable` warning 추가 |

서비스 변경 후보:

- `SupplementImageAnalysisResult`에 `ocr_warning_code: str | None` 또는 `warnings: list[str]`를 추가한다.
- `_extract_ocr_if_configured`는 `OCRError`를 그대로 전파하지 않고 recoverable result로 변환할지, route에서 catch할지 한 곳으로 통일한다. 현재 `create_supplement_analysis_intake`가 OCR보다 먼저 commit될 수 있으므로, preview warning을 남기려면 service 내부에서 처리하는 편이 더 일관적이다.
- audit에는 `supplement_ocr_provider_failed`를 기록하되, raw provider response, API key, raw OCR text, image bytes는 포함하지 않는다.

## 9. 프론트/모바일 UX 문구

Google Vision 연결 후에도 결과는 확정 정보가 아니라 preview다.

상태별 문구:

| 상태 | 사용자 표시 문구 |
| --- | --- |
| OCR 진행 중 | `라벨에서 텍스트를 추출하고 있어요.` |
| OCR 성공 + parse preview | `추출된 성분과 섭취 정보를 확인해 주세요.` |
| low confidence | `일부 글자가 불확실해요. 저장 전 라벨과 비교해 주세요.` |
| OCR empty | `텍스트를 자동으로 읽지 못했어요. 직접 입력하거나 다시 촬영해 주세요.` |
| provider unavailable | `현재 자동 텍스트 추출을 사용할 수 없어요. 직접 입력으로 계속할 수 있습니다.` |
| external consent missing | `외부 OCR 처리를 허용하면 더 정확한 텍스트 추출을 사용할 수 있습니다.` |

표시 금지:

- "정확히 판독했습니다"
- "복용량을 변경하세요"
- "의학적으로 안전합니다"
- Google Vision confidence를 의료적 신뢰도로 해석하는 문구

## 10. 학습 데이터 저장 정책

Google Vision 도입과 학습 데이터 저장은 분리한다.

- `ENABLE_IMAGE_LEARNING_PIPELINE=false` 기본값 유지
- `ConsentType.IMAGE_LEARNING_DATASET` 별도 opt-in 유지
- Google Vision OCR 호출 성공 여부와 관계없이 원본 이미지 학습 저장은 하지 않는다.
- 학습 데이터 저장은 동의/익명화/보관기간/삭제 요청 정책 리뷰 후 별도 PR로만 활성화한다.

## 11. 단계별 구현 플랜

### GVO-0. 문서 확정

- 이 문서를 팀 리뷰 기준 문서로 사용한다.
- docs/26의 CLOVA 우선순위와 docs/27의 Google 후보 상태를 이번 결정으로 갱신한다.
- `main` 병합은 제외하고 `team/yeong-tech` 기준으로 리뷰한다.

### GVO-1. Settings / config gate

- `Settings`에 OCR provider 필드 추가
- `GOOGLE_VISION_AUTH_MODE=api_key|adc` 추가
- `.env.example`에 Google Vision opt-in 예시 추가
- `implementation-readiness.settings.json` 기본값을 fail-closed로 보정
- `test_config.py`에 기본 OFF, gate mismatch, production preflight 정책 테스트 추가
- production에서 `OCR_PRIMARY_PROVIDER=google_vision` + `GOOGLE_VISION_AUTH_MODE!=adc` 조합을 거부하는 테스트 추가
- production에서 `GOOGLE_APPLICATION_CREDENTIALS` 파일 경로 기반 Google Vision 구성을 거부하는 테스트 추가

### GVO-2. Consent contract

- `ConsentType.EXTERNAL_OCR_PROCESSING` 추가
- `ACTIVE_CONSENT_POLICIES`에 외부 OCR 정책 추가
- `/api/v1/privacy/consents` response 테스트 보강
- `/supplements/analyze` missing consent response에 required consent 배열 검증
- `route_contract`에 `conditional_consents` 또는 별도 `x-conditional-consents` 지원 추가
- `/supplements/analyze` OpenAPI는 기본 `ocr_image_processing`, 조건부 `external_ocr_processing`을 모두 노출하도록 테스트 보강

### GVO-3. GoogleVisionOCRAdapter

- `backend/src/ocr/providers/google_vision.py` 추가
- `backend/src/ocr/providers/google_vision_auth.py` 추가
- 직접 ADC token refresh를 구현하면 `google-auth`를 명시 dependency로 추가한다. `google-cloud-vision`의 transitive dependency에 기대지 않는다.
- API key auth header provider와 ADC auth header provider를 분리
- fake HTTP transport 기반 unit test 작성
- response parsing, empty result, provider error, timeout mapping 테스트
- confidence가 없을 때 `None`을 유지하는 테스트 추가
- request body가 `DOCUMENT_TEXT_DETECTION`과 base64 image content를 포함하는지 검증
- API key mode에서 URL query에 key가 들어가지 않는지 검증
- ADC mode에서 fake auth provider가 `Authorization` header를 공급하는지 검증

### GVO-4. Adapter factory + API route wiring

- `backend/src/ocr/factory.py` 추가
- `providers/__init__.py` export 업데이트
- `/supplements/analyze` dependency에서 adapter 주입
- settings 기반 `_required_supplement_analyze_consents(settings)` helper 추가
- `analyze_supplement_image`는 기존 adapter contract 그대로 사용
- OCR 성공 시 parser가 호출되어 preview가 `requires_confirmation`으로 반환되는 integration test 추가
- external consent가 없으면 fake Google adapter가 호출되지 않는 integration test 추가
- Google provider runtime failure가 intake-only preview warning으로 degrade되는 integration test 추가
- raw image bytes와 raw OCR text가 DB row, audit metadata, log-safe error detail에 저장되지 않는 테스트 추가

### GVO-5. Manual Google smoke test

실제 Google 호출은 CI 기본 job에서 실행하지 않는다.

```bash
GOOGLE_CLOUD_API_KEY=your-google-cloud-api-key \
OCR_PRIMARY_PROVIDER=google_vision \
ALLOW_EXTERNAL_OCR=true \
GOOGLE_VISION_AUTH_MODE=api_key \
RUN_GOOGLE_VISION_SMOKE=1 \
GOOGLE_VISION_SMOKE_IMAGE_PATH=/absolute/path/to/local-label.png \
pytest yeong-Lemon-Aid/backend/tests/integration/ocr/test_google_vision_smoke.py -q
```

운영 ADC 경로 smoke test는 배포 런타임 또는 service account impersonation ADC 환경에서만 수행한다.

```bash
OCR_PRIMARY_PROVIDER=google_vision \
ALLOW_EXTERNAL_OCR=true \
GOOGLE_VISION_AUTH_MODE=adc \
GOOGLE_CLOUD_PROJECT=your-project-id \
RUN_GOOGLE_VISION_SMOKE=1 \
GOOGLE_VISION_SMOKE_IMAGE_PATH=/absolute/path/to/local-label.png \
pytest yeong-Lemon-Aid/backend/tests/integration/ocr/test_google_vision_smoke.py -q
```

필수 확인:

- sample label image에서 non-empty OCR text 반환
- raw image file이 repo/DB에 저장되지 않음
- raw OCR text가 DB에 저장되지 않고 `ocr_text_hash`만 저장됨
- `/api/v1/supplements/analyze`가 OCR+parse preview를 한 번에 반환
- Google API key 또는 ADC bearer token이 URL, log, audit에 남지 않음

### GVO-6. Team review and branch strategy

- 작업 브랜치: `codex/google-vision-ocr-provider` 또는 현재 안정화 브랜치에서 분리
- 반영 대상: `team/yeong-tech`
- 제외: `main` 직접 커밋/푸시/merge
- PR/리뷰 기준:
  - settings fail-closed
  - consent 없이 provider 호출 불가
  - raw image/raw OCR text 미저장
  - fake client 테스트가 기본 CI에서 통과
  - real Google smoke는 opt-in manual job만 실행

## 12. 테스트 수용 기준

unit:

- `OCR_PRIMARY_PROVIDER=none`이면 factory가 `None` 반환
- `OCR_PRIMARY_PROVIDER=google_vision` + `ALLOW_EXTERNAL_OCR=false`이면 설정 오류
- `GOOGLE_VISION_AUTH_MODE=api_key` + 빈 `GOOGLE_CLOUD_API_KEY`이면 설정 오류
- `GOOGLE_VISION_AUTH_MODE=adc` + 빈 `GOOGLE_CLOUD_PROJECT`이면 production 설정 오류
- production에서 `GOOGLE_VISION_AUTH_MODE=api_key`이면 설정 오류
- Google fake response full text -> `OCRResult.text`
- empty response -> empty text + `confidence=None`
- provider error/timeout -> `OCRError`
- response confidence가 없으면 임의 점수 생성 금지
- API key mode request가 `x-goog-api-key` header를 쓰고 URL query에 key를 넣지 않음
- ADC mode request가 fake bearer header provider를 통해 `Authorization` header를 받음

integration:

- 외부 OCR 동의 없으면 Google fake client가 호출되지 않음
- 동의 2종이 모두 있으면 `/supplements/analyze`가 OCR adapter와 parser를 호출
- OCR text가 있으면 `ocr_provider`, `ocr_confidence`, `ocr_text_hash`, `parsed_snapshot`이 저장됨
- raw OCR text는 저장되지 않음
- raw image bytes는 저장되지 않음
- Google provider 장애 시 `202` intake-only preview와 수동 확인/입력 가능한 warning 반환
- OpenAPI가 `x-required-consents=["ocr_image_processing"]`와 `x-conditional-consents=["external_ocr_processing"]`를 함께 노출

manual smoke:

- 실제 Google credential로 최소 1장 sample image에서 non-empty text 확인
- sample image와 credential은 repo에 커밋하지 않음
- 사용량/과금은 Cloud Console에서 확인

## 13. 구현 전 체크리스트

- [x] production 인증은 전용 user-managed service account + attached service account + ADC로 결정
- [ ] credential JSON을 저장소에 두지 않는 운영 규칙 재확인
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` 운영 경로 금지 또는 예외 승인 정책 재확인
- [ ] Google Cloud budget/quota alert 설정
- [ ] `EXTERNAL_OCR_PROCESSING` consent 문구 팀 리뷰
- [ ] OCR sample fixture 5장 이상 준비
- [ ] `OCR_PRIMARY_PROVIDER=none` fail-closed 기본값 확정
- [ ] fake client test 설계 완료
- [ ] real Google smoke test는 opt-in으로만 실행되도록 marker/env gate 설계
- [ ] `team/yeong-tech` 리뷰 후 반영, `main` 작업 제외
