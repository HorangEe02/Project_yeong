# 27. OT-S2b Google Vision OCR Review Plan

작성일: 2026-05-13
범위: `GoogleVisionOCRAdapter` 구현 전 검토 항목, 구현 선택지, 수용 기준
상태: 구현 전 검토 문서

## 1. 목적

OT-S2b는 `POST /api/v1/supplements/analyze`에 Google Cloud Vision OCR provider를 추가할지 결정하기 위한 검토 단위다. OT-S2 1차 구현은 `ClovaGeneralOCRAdapter`를 우선하고, Google Vision은 인증 방식, 데이터 처리 위치, SDK 의존성, confidence normalization을 공식 문서 기준으로 확인한 뒤 별도 구현한다.

이 문서의 결론은 다음과 같다.

- `GoogleVisionOCRAdapter`는 기술적으로 구현 가능하다.
- 하지만 기본 provider로 켜지면 외부 OCR 전송이 발생하므로 `ALLOW_EXTERNAL_OCR=true`와 명시 provider 선택 없이는 절대 활성화하지 않는다.
- 운영 환경에서는 서비스 계정 키 파일보다 Google Cloud 실행환경의 attached service account 또는 Workload Identity 계열 인증을 우선 검토한다.
- 라벨 이미지 기본 feature는 먼저 `DOCUMENT_TEXT_DETECTION`으로 검증하고, 짧은 라벨/전면 패키지 샷에서 `TEXT_DETECTION`과 비교하는 작은 benchmark를 거친 뒤 확정한다.
- 공식 성능 수치나 정확도 수치는 현재 문서만으로 확정할 수 없다. 자체 테스트셋으로 측정하기 전까지 accuracy/cost 개선 주장은 금지한다.

## 2. 공식 문서 근거

| 검토 주제 | 공식 문서 확인 내용 | OT-S2b 적용 |
| --- | --- | --- |
| OCR feature | Cloud Vision OCR는 `TEXT_DETECTION`과 `DOCUMENT_TEXT_DETECTION`을 제공한다. `TEXT_DETECTION`은 일반 이미지 텍스트, `DOCUMENT_TEXT_DETECTION`은 조밀한 텍스트와 문서형 구조에 최적화된다. | 영양제 라벨은 성분표처럼 조밀한 영역이 있으므로 `DOCUMENT_TEXT_DETECTION`을 1차 후보로 둔다. |
| request/response | REST `images:annotate`는 image, features, imageContext를 포함한 batch request를 받으며 response는 `textAnnotations`, `fullTextAnnotation`, `error` 등을 제공한다. | adapter는 `fullTextAnnotation.text`를 우선 사용하고 없으면 `textAnnotations[0].description` fallback을 검토한다. |
| confidence | `ImageContext.textDetectionParams.enableTextDetectionConfidenceScore`는 `TEXT_DETECTION` confidence를 활성화할 수 있고, 기본적으로 confidence는 `DOCUMENT_TEXT_DETECTION` result에 포함된다. | confidence normalization은 feature별로 다르게 설계한다. 값이 없으면 `None`으로 둔다. |
| language hints | language hints는 optional이며 빈 값이 자동 감지에 유리한 경우가 많다. Korean `ko`는 supported language 목록에 있다. | 기본값은 language hint 없음이다. `GOOGLE_VISION_LANGUAGE_HINTS=ko`는 실험 플래그로만 둔다. |
| region/data location | Vision OCR는 global endpoint가 기본이며 `us`와 `eu` regional endpoint를 지원한다. global은 특정 region 잔류를 보장하지 않는다. | 미국 사용자/US 배포는 `us-vision.googleapis.com`과 `parent=projects/{project}/locations/us` 사용을 검토한다. |
| image constraints | Vision API 지원 문서는 OCR 권장 크기 `1024 x 768`, 이미지 파일 20MB 이하, JSON request 10MB 이하, OCR image 75M pixels 이하를 명시한다. | 현재 backend image limit은 더 보수적이므로 유지한다. JSON base64 호출은 10MB 제한에 걸리지 않게 normalized PNG 크기를 테스트한다. |
| authentication | ADC는 `GOOGLE_APPLICATION_CREDENTIALS`, local ADC file, attached service account 순서로 credentials를 찾는다. Google은 service account key가 보안 리스크라고 명시한다. | local dev는 `GOOGLE_APPLICATION_CREDENTIALS`를 허용하되 git 금지. production은 attached service account 또는 federation 우선. |
| Python client | `ImageAnnotatorClient`는 credentials, transport, client_options를 받으며, `client_options.api_endpoint`로 endpoint override가 가능하다. `batch_annotate_images`는 timeout parameter를 받는다. | Python client 방식이면 `client_options={"api_endpoint": ...}`와 request timeout을 adapter 설정에 연결한다. |

참조 URL:

- Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- Cloud Vision REST `images:annotate`: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- Cloud Vision `ImageContext`: https://cloud.google.com/vision/docs/reference/rest/v1/ImageContext
- Cloud Vision OCR language support: https://cloud.google.com/vision/docs/languages
- Cloud Vision supported images: https://cloud.google.com/vision/docs/supported-files
- Google ADC search order and credential risks: https://cloud.google.com/docs/authentication/application-default-credentials
- Python `ImageAnnotatorClient`: https://docs.cloud.google.com/python/docs/reference/vision/latest/google.cloud.vision_v1.services.image_annotator.ImageAnnotatorClient

## 3. OT-S2b 범위

포함:

- `GoogleVisionOCRAdapter` 구현 가능성 검토
- 인증 방식 결정
- SDK 방식과 REST 방식 비교
- OCR feature 선택 기준 설계
- region endpoint와 data location 설정 설계
- confidence normalization 설계
- 테스트와 CI 격리 방식 설계

제외:

- 실제 Google Cloud OCR 호출 구현
- 실제 benchmark 수치 생성
- Google Vision과 CLOVA 자동 fallback 구현
- 처방전/검사표 OCR intake 연결
- Google Vision 결과를 이용한 복용량 변경 추천

## 4. 구현 선택지 비교

| 선택지 | 장점 | 리스크 | 권장 |
| --- | --- | --- | --- |
| Python client `google-cloud-vision` | 공식 client, ADC와 regional endpoint 설정 지원, response proto type 사용 가능 | 새 dependency 추가, sync client를 async FastAPI에서 호출할 때 thread offload 필요 | 1차 권장 |
| REST + `httpx` + OAuth token | async 구현이 단순하고 기존 CLOVA adapter와 형태가 유사 | OAuth token 발급/refresh 구현이 복잡해질 수 있음 | 보류 |
| API key 기반 REST | 초기 호출은 단순할 수 있음 | 서버간 의료성 이미지 처리에는 권한 범위와 키 유출 리스크가 큼 | 비권장 |

권장안:

- `google-cloud-vision` Python client를 사용한다.
- FastAPI async route 내부에서 sync client 호출은 `anyio.to_thread.run_sync` 또는 별도 adapter-level thread offload로 감싼다.
- 테스트에서는 client protocol/fake client를 주입해 실제 Google 네트워크 호출을 차단한다.

## 5. 인증 검토안

### Local development

- 허용: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/local/dev-credential.json`
- 금지: credential JSON을 git, docs, test fixture, issue template에 포함
- 테스트: 실제 호출 테스트는 `RUN_GOOGLE_VISION_OCR_TESTS=true`가 있을 때만 실행

### Production

권장 순서:

1. Google Cloud 실행환경의 attached service account
2. Workload Identity Federation 또는 equivalent federation
3. 서비스 계정 키 파일은 마지막 수단

필수 조건:

- service account는 Vision OCR 호출에 필요한 최소 권한만 가진다.
- production에서 service account key file을 쓸 경우 별도 보안 승인과 key rotation 절차가 필요하다.
- `GOOGLE_APPLICATION_CREDENTIALS` path는 audit metadata에 기록하지 않는다.

## 6. 설정 설계안

OT-S2의 공통 설정을 유지하면서 Google 전용 설정만 추가한다.

```python
supplement_ocr_provider: Literal["none", "clova_general", "google_vision"] = "none"
allow_external_ocr: bool = False
google_cloud_project: str | None = None
google_vision_location: Literal["global", "us", "eu"] = "global"
google_vision_feature: Literal["document_text_detection", "text_detection"] = "document_text_detection"
google_vision_language_hints: list[str] = Field(default_factory=list)
google_vision_enable_text_confidence: bool = False
ocr_timeout_sec: int = Field(default=15, ge=1, le=60)
```

검증 규칙:

- `supplement_ocr_provider != "google_vision"`이면 Google 설정은 adapter를 만들지 않는다.
- `google_vision` 선택 시 `allow_external_ocr`가 반드시 true여야 한다.
- `google_vision_location in {"us", "eu"}`이면 `google_cloud_project`가 필요하다.
- `google_vision_feature == "text_detection"`이고 confidence가 필요하면 `google_vision_enable_text_confidence=true`를 요구한다.
- `google_vision_language_hints`는 빈 배열을 기본값으로 둔다. `ko`는 허용하지만 기본 강제값으로 두지 않는다.

환경변수 예시:

```dotenv
SUPPLEMENT_OCR_PROVIDER=google_vision
ALLOW_EXTERNAL_OCR=true
GOOGLE_CLOUD_PROJECT=project-id
GOOGLE_VISION_LOCATION=us
GOOGLE_VISION_FEATURE=document_text_detection
GOOGLE_VISION_LANGUAGE_HINTS=[]
OCR_TIMEOUT_SEC=15
```

## 7. Adapter 설계안

파일:

- `backend/src/ocr/providers/google_vision.py`
- `backend/tests/unit/ocr/test_google_vision_provider.py`

class:

```python
class GoogleVisionOCRAdapter(OCRAdapter):
    """Google Cloud Vision OCR adapter for supplement label images."""
```

생성자 후보:

```python
GoogleVisionOCRAdapter(
    project_id: str | None,
    location: Literal["global", "us", "eu"],
    feature: Literal["document_text_detection", "text_detection"],
    language_hints: Sequence[str],
    enable_text_confidence: bool,
    timeout_sec: int,
    client: GoogleVisionClientProtocol | None = None,
)
```

request 생성:

- normalized PNG bytes를 `vision.Image(content=image.image_bytes)`로 전달
- `DOCUMENT_TEXT_DETECTION` 또는 `TEXT_DETECTION` feature 선택
- language hints는 설정값이 있을 때만 `ImageContext.language_hints`에 넣음
- `TEXT_DETECTION` confidence가 필요하면 `TextDetectionParams(enable_text_detection_confidence_score=True)` 검토
- regional endpoint 사용 시 client 생성 단계에서 `client_options={"api_endpoint": "us-vision.googleapis.com"}` 또는 `"eu-vision.googleapis.com"` 적용
- REST `parent=projects/{project}/locations/{location}`와 client-library endpoint 설정 중 어떤 조합이 필요한지는 구현 직전 공식 sample과 client request type으로 재확인한다.

response normalization:

1. `response.error.message`가 있으면 `OCRProviderUnavailableError`
2. `response.full_text_annotation.text`가 있으면 우선 사용
3. 없으면 `response.text_annotations[0].description` 사용
4. 둘 다 없으면 empty OCR result
5. confidence:
   - `DOCUMENT_TEXT_DETECTION`: page/block/paragraph/word confidence 중 어떤 aggregate를 쓸지 테스트 전에는 확정하지 않는다.
   - 1차 구현은 page confidence 평균을 후보로 두되, 값이 없으면 `None`
   - `TEXT_DETECTION`: confidence score를 명시 활성화한 경우만 confidence 후보로 사용

## 8. 기존 OT-S2와의 연결

`build_supplement_ocr_adapter(settings)`는 다음 순서를 따른다.

```text
provider none          -> None
provider clova_general -> ClovaGeneralOCRAdapter
provider google_vision -> GoogleVisionOCRAdapter, 단 OT-S2b 검토 완료 후에만
```

OT-S2 1차 구현 중에는 `google_vision`을 enum에 남기더라도 다음처럼 fail closed 처리한다.

```text
OCRConfigurationError("google_vision adapter is not implemented; see docs/27 OT-S2b review.")
```

OT-S2b 구현이 승인되면 factory에서만 adapter를 연결한다. API route와 `analyze_supplement_image` service 계약은 수정하지 않는다.

## 9. 검토 체크리스트

구현 전에 반드시 확정할 항목:

- [ ] Google Cloud 프로젝트와 billing owner가 확정되어 있다.
- [ ] 외부 OCR 이미지 전송에 대한 개인정보 처리 검토가 완료되어 있다.
- [ ] `ALLOW_EXTERNAL_OCR=true`를 켤 운영 환경이 명시되어 있다.
- [ ] production 인증 방식이 attached service account 또는 federation으로 확정되어 있다.
- [ ] local dev용 `GOOGLE_APPLICATION_CREDENTIALS` 파일 관리 규칙이 문서화되어 있다.
- [ ] `google_vision_location` 기본값을 `global`, `us`, `eu` 중 하나로 결정했다.
- [ ] 한국 사용자 이미지 처리 위치 요구사항이 있으면 `us` endpoint가 충분한지 법무/보안 검토를 완료했다.
- [ ] `DOCUMENT_TEXT_DETECTION` vs `TEXT_DETECTION` 비교 기준이 정해져 있다.
- [ ] language hint 기본값을 빈 배열로 둘지 `["ko"]`로 둘지 자체 테스트로 확인했다.
- [ ] confidence aggregation 규칙을 parser confidence와 섞지 않도록 정했다.
- [ ] 실제 API smoke test를 CI 기본 job에서 실행하지 않도록 gate를 만들었다.

## 10. 소규모 benchmark 설계

정확도 수치는 공식 문서만으로 확정하지 않는다. OT-S2b 구현 승인 전 최소 benchmark를 별도로 수행한다.

데이터:

- 실제 사용자 데이터가 아닌 팀 내부 샘플 또는 공개 가능 mock 라벨 이미지
- 한국어 중심 10장 이상
- 성분표가 조밀한 이미지와 전면 제품명 중심 이미지 분리
- 흐림, 반사, 회전, crop 누락 샘플 포함

비교군:

- `document_text_detection` + no language hint
- `document_text_detection` + `ko`
- `text_detection` + no language hint
- `text_detection` + `ko`

측정:

- OCR text non-empty rate
- key ingredient string recall
- serving size string recall
- parser preview 생성 성공률
- 평균 latency
- provider error rate
- raw text 저장 여부 검증

금지:

- benchmark 없이 "Google Vision이 더 정확하다" 같은 문구 작성
- 소규모 benchmark 결과를 일반 성능 보장처럼 표현

## 11. 테스트 플랜

단위 테스트:

- provider disabled -> factory returns `None`
- `google_vision` + `ALLOW_EXTERNAL_OCR=false` -> configuration error
- `google_vision` + location `us` + missing project -> configuration error
- fake client full text response -> `OCRResult.text`
- fake client text annotations fallback -> `OCRResult.text`
- fake client empty response -> empty OCR result
- fake client error message -> `OCRProviderUnavailableError`
- confidence out of range -> `OCRProviderResponseError`
- regional endpoint option is passed to client factory

통합 테스트:

- dependency override로 fake `GoogleVisionOCRAdapter` 주입 시 `/api/v1/supplements/analyze`가 one-shot OCR+parse preview를 반환
- 실제 Google 호출 테스트는 `RUN_GOOGLE_VISION_OCR_TESTS=true`, credential, project가 모두 있을 때만 skip 해제
- CI 기본 job에서는 외부 네트워크 호출 없음

검증 명령:

```bash
cd yeong-Lemon-Aid/backend
.venv/bin/python -m pytest tests/unit/ocr/test_google_vision_provider.py
.venv/bin/python -m pytest tests/integration/api/test_supplement_analyze_ocr_provider_api.py
.venv/bin/python -m black --check src tests alembic
.venv/bin/python -m ruff check src tests alembic
.venv/bin/python -m mypy src tests --strict
```

## 12. 수용 기준

OT-S2b 구현 착수 승인 조건:

- 공식 문서 기준으로 request, auth, endpoint, confidence 처리 방식이 이 문서와 일치한다.
- 외부 OCR 전송에 대한 privacy review가 완료되어 있다.
- production credential 방식이 service account key file 중심이 아니다.
- `SUPPLEMENT_OCR_PROVIDER=google_vision`과 `ALLOW_EXTERNAL_OCR=true` 없이는 절대 호출되지 않는다.
- CI 기본 테스트에서 Google 네트워크 호출이 발생하지 않는다.
- benchmark 없이 provider 정확도 우위 주장을 하지 않는다.

OT-S2b 구현 완료 조건:

- `GoogleVisionOCRAdapter`가 `OCRAdapter` 계약만 구현하고 API/service 계층을 흔들지 않는다.
- `/api/v1/supplements/analyze` one-shot OCR+parse preview가 fake Google adapter로 검증된다.
- 실제 Google 호출 smoke test는 명시 gate에서만 실행된다.
- raw image와 raw OCR text는 DB, response, audit log에 저장되지 않는다.
- provider 실패는 `502 ocr_unavailable`로 드러난다.

## 13. 권장 commit 분리

1. `docs(ocr): add Google Vision OT-S2b review plan`
   - 왜: Google Vision OCR을 구현하기 전 인증, 데이터 위치, confidence 정책을 공식 문서 기준으로 고정하기 위해.

2. `feat(config): add Google Vision OCR settings`
   - 왜: 외부 OCR provider 선택과 data location 설정을 명시적으로 관리하기 위해.

3. `feat(ocr): implement Google Vision OCR adapter`
   - 왜: Google Vision request/response 차이를 `OCRAdapter` 경계 안에 격리하기 위해.

4. `test(ocr): cover Google Vision adapter normalization`
   - 왜: 실제 API 없이 response parsing, confidence, error mapping을 검증하기 위해.

5. `test(api): verify one-shot Google OCR parse preview`
   - 왜: `/analyze` route가 provider 주입 시 OCR+parse preview까지 연결되는지 회귀 방지하기 위해.
