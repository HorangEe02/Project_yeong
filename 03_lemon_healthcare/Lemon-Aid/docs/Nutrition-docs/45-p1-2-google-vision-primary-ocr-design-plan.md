# 45. P1-2 Google Vision Primary OCRAdapter 상세 설계 및 구현 플랜

작성일: 2026-05-16
범위: `01_HANDOFF.md` P1-2, Google Vision primary OCR, layout-aware `OCRResult`, CLOVA fallback threshold

## 1. 현재 상태 요약

`01_HANDOFF.md`는 P1-2를 `backend/src/ocr/google_vision.py`의 `GoogleVisionOCR(OCRAdapter)` 구현으로 적고 있다. 현재 실제 backend 경로는 `backend/Nutrition-backend/src`이며, Google Vision provider는 이미 아래 위치에 존재한다.

- `backend/Nutrition-backend/src/ocr/base.py`
- `backend/Nutrition-backend/src/ocr/providers/google_vision.py`
- `backend/Nutrition-backend/src/ocr/providers/google_vision_auth.py`
- `backend/Nutrition-backend/src/ocr/providers/clova.py`
- `backend/Nutrition-backend/src/ocr/factory.py`
- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`

따라서 P1-2는 "무에서 신규 provider 추가"가 아니라 **기존 GoogleVisionOCRAdapter를 layout-aware primary OCR로 확장**하는 작업이다.

| 요구사항 | 현재 구현 | 차이 |
| --- | --- | --- |
| Google Vision primary | `GoogleVisionOCRAdapter` 구현됨 | 클래스명은 `GoogleVisionOCRAdapter`; handoff의 `GoogleVisionOCR` alias는 필요 시 호환 export로 제공 |
| `DOCUMENT_TEXT_DETECTION` | `GOOGLE_VISION_FEATURE_TYPES = {"document_text_detection": "DOCUMENT_TEXT_DETECTION"}` | 충족 |
| 단어별 좌표/confidence/block 구조 | `OCRResult.pages`에 page/block/paragraph/word hierarchy 추가 | 구현 완료 |
| CLOVA fallback | factory가 `enable_clova_ocr`이면 CLOVA를 첫 secondary fallback으로 구성하고, 서비스가 settings threshold에서 secondary fallback 호출 | 구현 완료 |
| 0.85 threshold 외부화 | `Settings.ocr_confidence_threshold`, `.env.example`, local `.env`에 반영 | 구현 완료 |
| Google API mock 테스트 | `test_google_vision_provider.py` 있음 | layout parsing, threshold/fallback 테스트 추가 필요 |

## 2. 공식 문서 기준 확인

아래 공식 문서를 기준으로 설계를 제한한다. 문서에서 확인되지 않은 필드, 성능 수치, 정확도 수치는 만들지 않는다.

| 주제 | 공식 확인 내용 | 설계 반영 |
| --- | --- | --- |
| OCR feature 선택 | Cloud Vision OCR는 `TEXT_DETECTION`과 `DOCUMENT_TEXT_DETECTION`을 제공한다. `DOCUMENT_TEXT_DETECTION`은 dense text/document에 최적화되고 page/block/paragraph/word/break 구조를 포함한다. URL: <https://cloud.google.com/vision/docs/ocr> | 영양제 성분표는 `DOCUMENT_TEXT_DETECTION` 고정 |
| Feature enum | REST `Feature.Type`에서 `TEXT_DETECTION`은 큰 이미지 안의 텍스트 영역에 최적화되고, 문서라면 `DOCUMENT_TEXT_DETECTION`을 쓰라고 설명한다. `DOCUMENT_TEXT_DETECTION`은 dense text document OCR이며 두 feature가 같이 있으면 우선한다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/Feature> | `TEXT_DETECTION` fallback을 섞지 않고 request feature는 하나만 사용 |
| 요청 구조 | `AnnotateImageRequest`는 `image`, `features[]`, `imageContext`를 가진다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageRequest> | 현재 REST payload builder 유지, `imageContext.languageHints`는 설정값이 있을 때만 전달 |
| 응답 구조 | `AnnotateImageResponse.fullTextAnnotation`은 OCR/document OCR이 성공하면 structural hierarchy를 제공한다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse> | `fullTextAnnotation.pages[].blocks[].paragraphs[].words[]`를 internal DTO로 정규화 |
| confidence 위치 | `Page`, `Block` 등 structural component는 confidence를 `0..1` 범위로 가진다. Word와 Symbol도 REST reference의 구조 컴포넌트에 confidence 필드가 있다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse> | 평균 confidence는 word confidence 우선, 없으면 paragraph/block/page confidence fallback |
| language hints | `ImageContext.languageHints[]`는 대부분 비워두는 것이 좋고, 잘못된 hint는 방해가 될 수 있다고 설명한다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/ImageContext> | 기본 빈 배열 유지, `["ko", "en"]`은 fixture report에서 개선 확인 후 opt-in |
| text detection confidence params | `ImageContext.textDetectionParams.enableTextDetectionConfidenceScore`는 기본적으로 `DOCUMENT_TEXT_DETECTION` 결과에는 confidence가 포함된다는 설명과 함께 `TEXT_DETECTION` confidence 포함을 제어한다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/ImageContext> | 이번 범위는 document OCR이므로 별도 flag를 기본 request에 추가하지 않음 |

확인 한계:

- I cannot find the official documentation for a Google-recommended confidence threshold such as `0.85` for supplement labels. 따라서 `0.85`는 Google 공식 권장값이 아니라 프로젝트 운영 후보값이며, fixture 평가 전에는 정확도 주장 근거로 쓰지 않는다.
- CLOVA fallback의 정확도 우위나 개선율도 fixture 평가 전에는 주장하지 않는다.

## 3. 설계 결정

### 3.1 파일 경로와 클래스명

권장 구현은 기존 구조를 따른다.

- 주 구현: `backend/Nutrition-backend/src/ocr/providers/google_vision.py`
- 호환 export 후보: `backend/Nutrition-backend/src/ocr/google_vision.py`

`01_HANDOFF.md`의 `backend/src/ocr/google_vision.py`는 과거 구조 표현으로 보고, 현재 repo에서는 provider package 구조를 유지한다. 필요하면 아래처럼 얇은 alias 파일만 추가한다.

```python
from src.ocr.providers.google_vision import GoogleVisionOCRAdapter as GoogleVisionOCR
```

단, 새 구현 로직은 provider 파일에 둔다. 이렇게 해야 factory와 기존 tests가 깨지지 않는다.

### 3.2 `OCRResult` 확장 방향

현재 `OCRResult`는 provider-level 평균 confidence만 가진다. Layout Parser가 의존하려면 아래 구조가 필요하다.

```python
@dataclass(frozen=True)
class OCRVertex:
    x: int
    y: int

@dataclass(frozen=True)
class OCRBoundingPoly:
    vertices: tuple[OCRVertex, ...]

@dataclass(frozen=True)
class OCRWord:
    text: str
    confidence: float | None
    bounding_box: OCRBoundingPoly | None
    block_index: int
    paragraph_index: int
    word_index: int

@dataclass(frozen=True)
class OCRParagraph:
    text: str
    confidence: float | None
    bounding_box: OCRBoundingPoly | None
    words: tuple[OCRWord, ...]

@dataclass(frozen=True)
class OCRBlock:
    text: str
    confidence: float | None
    bounding_box: OCRBoundingPoly | None
    block_type: str | None
    paragraphs: tuple[OCRParagraph, ...]

@dataclass(frozen=True)
class OCRPage:
    width: int | None
    height: int | None
    confidence: float | None
    blocks: tuple[OCRBlock, ...]

@dataclass(frozen=True)
class OCRResult:
    text: str
    provider: str
    confidence: float | None = None
    pages: tuple[OCRPage, ...] = ()
```

호환성 원칙:

- `text`, `provider`, `confidence` 필드는 유지한다.
- 기존 fake adapters는 `pages`를 넘기지 않아도 동작한다.
- Layout Parser는 `result.pages`가 비어 있으면 기존 flat text mode로 degrade한다.
- DB에는 raw OCR text와 raw provider payload를 저장하지 않는다. Layout 구조는 당장 DB 저장 대상이 아니라 runtime parser input으로 사용한다. 저장이 필요해지면 allowlisted geometry snapshot만 별도 설계한다.

### 3.3 Google Vision 응답 정규화

정규화 우선순위:

1. `responses[0].error`가 있으면 sanitized `OCRError`
2. `fullTextAnnotation.text`를 전체 OCR text로 사용
3. `fullTextAnnotation.pages`를 `OCRPage -> OCRBlock -> OCRParagraph -> OCRWord`로 변환
4. `fullTextAnnotation`이 없고 `textAnnotations[0].description`만 있으면 text-only `OCRResult`

Word text 조립:

- Google Vision word는 symbol 배열로 구성된다.
- `symbol.text`를 이어 붙여 word text를 만든다.
- `DetectedBreak`는 paragraph/block text 조립에는 반영하되, word text 자체에는 포함하지 않는다.
- `fullTextAnnotation.text`가 있으면 전체 `OCRResult.text`는 provider 원문을 우선한다. layout-derived text는 block/paragraph 내부 검증용이다.

Bounding box:

- `boundingBox.vertices` 또는 `normalizedVertices`를 모두 받을 수 있게 parser helper를 둔다.
- 이미지 OCR은 pixel 단위가 기대값이므로 `vertices` 우선이다.
- 좌표가 누락된 vertex는 `0`을 만들지 말고 해당 vertex의 missing field만 생략하거나 `None` 처리한다. Layout Parser가 좌표를 확신하지 못하게 하는 편이 안전하다.

Confidence aggregation:

- `OCRResult.confidence`: word confidence 평균을 우선 사용
- word confidence가 없으면 paragraph confidence 평균
- paragraph도 없으면 block confidence 평균
- block도 없으면 page confidence 평균
- 아무 confidence도 없으면 `None`

`None` confidence는 "낮음"이 아니라 "provider가 confidence를 제공하지 않음"이다. fallback 트리거 정책에서 별도로 다룬다.

### 3.4 0.85 threshold 외부화

새 설정:

```python
ocr_confidence_threshold: float = Field(
    default=0.85,
    ge=0.0,
    le=1.0,
    description="Primary OCR confidence threshold for fallback/review routing.",
)
```

적용 위치:

- `src/services/supplement_image_analysis.py`
  - `_is_low_confidence(confidence, settings)`로 변경
  - multimodal fallback과 secondary fallback이 모두 `settings.ocr_confidence_threshold`를 사용
- `src/services/supplement_parser.py`
  - `_build_low_confidence_fields(..., settings)`로 변경
  - 기존 `OCR_LOW_CONFIDENCE_THRESHOLD` 상수 의존은 제거하고, 실제 판정은 settings를 사용

정책:

- 기본값 `0.85`는 프로젝트 후보값이다.
- 테스트에서는 threshold를 `0.85`, `0.90`, `0.70` 등으로 바꿔 routing이 설정값을 따르는지 검증한다.
- fixture 평가 전에는 “0.85가 최적”이라고 말하지 않는다.

### 3.5 CLOVA fallback 라우팅

현재 서비스 흐름은 primary OCR 후 다음 순서로 진행한다.

1. multimodal vision assist fallback
2. secondary OCR fallback adapters (`PaddleOCRAdapter`, `ClovaOCRAdapter`)

P1-2 요구는 “신뢰도 0.85 미만 시 CLOVA 폴백”이므로 구현 선택지는 두 가지다.

| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| 기존 fallback order 유지: PaddleOCR -> CLOVA | local-first/privacy-first 흐름 유지 | P1-2의 CLOVA 명시 요구와 다름 | P1-2 primary 범위에는 맞지 않음 |
| Google Vision low confidence에서 CLOVA를 첫 secondary fallback으로 호출 | 요구사항과 일치, 테스트 명확 | CLOVA external OCR 동의/secret 필요 | 채택 |

구현 방식:

- `enable_clova_ocr=true`이면 CLOVA를 Google Vision primary의 confidence fallback 후보로 사용한다.
- `allow_external_ocr=true`, `clova_ocr_api_url`, `clova_ocr_secret`가 모두 없으면 CLOVA adapter는 build하지 않는다.
- CLOVA도 외부 OCR이므로 `EXTERNAL_OCR_PROCESSING` consent가 없는 경우 호출 금지.
- fallback 결과가 text를 반환하면 parser input provider는 `clova_ocr`로 남긴다.
- primary Google Vision 결과와 fallback CLOVA 결과 중 어느 쪽을 선택할지는 첫 구현에서는 단순 정책으로 둔다.
  - Google Vision confidence `< threshold`이고 CLOVA text가 있으면 CLOVA 채택
  - CLOVA 실패 또는 빈 text면 Google Vision 결과 유지
  - 둘 다 있더라도 서로 다른 내용을 자동 병합하지 않는다.

### 3.6 Privacy / audit

- Google Vision과 CLOVA 모두 이미지 bytes가 외부 provider로 전송된다.
- `ALLOW_EXTERNAL_OCR=true`와 사용자 `EXTERNAL_OCR_PROCESSING` consent가 없으면 호출하지 않는다.
- audit에는 provider, confidence presence, fallback attempted/result provider 정도만 저장한다.
- 저장 금지: API key, Authorization header, raw image, raw OCR text, raw provider response, full request body.

## 4. 구현 상세 플랜

### R1. `OCRResult` layout DTO 확장

파일:

- `backend/Nutrition-backend/src/ocr/base.py`
- 관련 fake adapter tests

작업:

- `OCRVertex`, `OCRBoundingPoly`, `OCRWord`, `OCRParagraph`, `OCRBlock`, `OCRPage` dataclass 추가
- `OCRResult.pages: tuple[OCRPage, ...] = ()` 추가
- 기존 생성자 호출 호환 유지

완료 기준:

- 기존 OCR unit/integration tests가 수정 최소로 통과
- `OCRResult(text, provider, confidence)` 기존 사용부가 깨지지 않음

### R2. Google Vision layout parser 구현

파일:

- `backend/Nutrition-backend/src/ocr/providers/google_vision.py`
- `backend/Nutrition-backend/tests/unit/ocr/test_google_vision_provider.py`

작업:

- `_parse_google_vision_response()`가 `pages`를 채워 반환하도록 확장
- `_parse_page`, `_parse_block`, `_parse_paragraph`, `_parse_word`, `_parse_bounding_poly` helper 추가
- word text는 `symbols[].text` 기반으로 조립
- confidence aggregation을 word-first로 변경
- `textAnnotations` only response는 `pages=()` 유지

완료 기준:

- mock `fullTextAnnotation.pages.blocks.paragraphs.words.symbols` fixture에서 단어 text, 좌표, confidence, block index 검증
- provider error sanitize 기존 테스트 유지
- request가 `DOCUMENT_TEXT_DETECTION`만 보내는 테스트 유지

### R3. threshold setting 추가

파일:

- `backend/Nutrition-backend/src/config.py`
- `backend/.env.example`
- `.env` local placeholder
- `backend/Nutrition-backend/tests/unit/test_config.py`

작업:

- `ocr_confidence_threshold: float = Field(default=0.85, ge=0, le=1)` 추가
- `.env.example`에 `OCR_CONFIDENCE_THRESHOLD=0.85` 추가
- local `.env`도 값만 추가하고 기존 key는 노출하지 않음
- default/dotenv/validation tests 추가

완료 기준:

- 기본값 `0.85`
- dotenv override 정상
- `-0.1`, `1.1` validation error

### R4. pipeline fallback threshold 적용

파일:

- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`
- `backend/Nutrition-backend/src/services/supplement_parser.py`
- `backend/Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py`
- parser 관련 unit tests

작업:

- `_is_low_confidence(confidence, settings)`로 signature 변경
- `_should_run_multimodal_fallback`, `_should_run_secondary_fallback`에 settings 전달
- parser snapshot의 `low_confidence_fields`도 `settings.ocr_confidence_threshold` 사용
- 기존 `0.70` low confidence 테스트를 threshold 설정 기반으로 조정

완료 기준:

- `confidence=0.84`, threshold `0.85`에서 fallback 호출
- `confidence=0.86`, threshold `0.85`에서 fallback 미호출
- threshold `0.70`이면 `0.80` confidence가 low-confidence로 표시되지 않음

### R5. CLOVA fallback 우선 정책 보정

파일:

- `backend/Nutrition-backend/src/ocr/factory.py`
- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`
- `backend/Nutrition-backend/tests/unit/ocr/test_ocr_factory.py`
- `backend/Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py`

작업:

- P1-2 범위에서는 Google Vision primary의 low confidence fallback으로 CLOVA를 우선 호출
- `enable_clova_ocr=true`일 때 CLOVA adapter가 fallback tuple 첫 번째가 되도록 하거나, service에서 `provider == google_vision_document`일 때 CLOVA 우선 선택
- PaddleOCR fallback은 P1-2 후속 또는 local fallback 정책으로 분리

완료 기준:

- Google Vision confidence `< settings.ocr_confidence_threshold` + CLOVA enabled이면 CLOVA fake adapter 호출
- CLOVA 실패 시 primary Google Vision 결과로 degrade
- 외부 OCR 설정/동의 없으면 CLOVA 호출 없음

### R6. 호환 alias 검토

파일 후보:

- `backend/Nutrition-backend/src/ocr/google_vision.py`

작업:

- handoff 경로와 외부 import 기대가 있다면 `GoogleVisionOCR = GoogleVisionOCRAdapter` alias 제공
- repo 내부 import는 provider path 유지

완료 기준:

- `from src.ocr.google_vision import GoogleVisionOCR` smoke test 통과
- 새 로직 중복 없음

### R7. 문서와 OpenAPI 보정

파일:

- `docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`
- `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`
- 필요 시 `docs/Nutrition-docs/31-backend-feature-specifications.md`

작업:

- Google Vision provider가 이미 존재하며 P1-2는 layout/threshold/fallback 확장임을 문서화
- `0.85`는 프로젝트 후보값이고 fixture 전 정확도 주장이 아님을 명시
- Layout Parser가 `OCRResult.pages`를 사용하고 비어 있으면 flat text로 fallback한다는 계약 추가

완료 기준:

- stale “구현 전” 표현 제거
- 공식 문서 URL 유지

## 5. 테스트 계획

### Unit

- `tests/unit/ocr/test_google_vision_provider.py`
  - `DOCUMENT_TEXT_DETECTION` request shape
  - `fullTextAnnotation.pages.blocks.paragraphs.words.symbols` parsing
  - word bounding box vertices
  - word/block/page confidence aggregation
  - `textAnnotations` fallback remains text-only
  - provider error sanitize
- `tests/unit/ocr/test_ocr_factory.py`
  - Google Vision build gate
  - CLOVA fallback build gate
  - fallback order/policy
- `tests/unit/services/test_supplement_image_analysis.py`
  - threshold `0.85` triggers CLOVA fallback below threshold
  - custom `ocr_confidence_threshold` changes behavior
  - CLOVA failure degrades to primary result
- `tests/unit/test_config.py`
  - default threshold
  - dotenv override
  - validation bounds

### Integration

- `tests/integration/api/test_supplement_analyze_google_vision.py`
  - fake Google Vision layout result propagates provider/confidence
  - raw OCR text still not stored
  - consent gating blocks external OCR
  - fallback provider metadata stays sanitized

### Live smoke

기본 CI에는 넣지 않는다.

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
RUN_GOOGLE_VISION_LIVE_SMOKE=1 .venv/bin/python -m pytest Nutrition-backend/tests/integration/ocr/test_google_vision_smoke.py -q --no-cov
```

live smoke 산출물은 redacted summary만 허용한다.

저장 금지:

- API key
- raw image
- raw OCR text
- raw Google/CLOVA response

## 6. 검증 명령

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/ocr/test_google_vision_provider.py Nutrition-backend/tests/unit/ocr/test_ocr_factory.py Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py Nutrition-backend/tests/unit/test_config.py -q --no-cov
.venv/bin/python -m pytest Nutrition-backend/tests/integration/api/test_supplement_analyze_google_vision.py -q --no-cov
.venv/bin/python -m ruff check Nutrition-backend/src/ocr Nutrition-backend/src/services/supplement_image_analysis.py Nutrition-backend/src/services/supplement_parser.py Nutrition-backend/tests/unit/ocr Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py
.venv/bin/python -m black --check Nutrition-backend/src/ocr Nutrition-backend/src/services/supplement_image_analysis.py Nutrition-backend/src/services/supplement_parser.py Nutrition-backend/tests/unit/ocr Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py
git diff --check
```

## 7. 권장 구현 순서

1. `OCRResult` layout DTO를 backward-compatible하게 확장한다.
2. Google Vision mock response에서 word/block/page layout parsing을 구현한다.
3. `Settings.ocr_confidence_threshold=0.85`를 추가하고 env/test를 맞춘다.
4. image analysis와 parser의 low-confidence 판정을 settings 기반으로 변경한다.
5. Google Vision low confidence 시 CLOVA fallback이 먼저 호출되도록 정책을 고정한다.
6. handoff 호환 import가 필요하면 `src/ocr/google_vision.py` alias를 추가한다.
7. docs/33, docs/35의 stale 구현 상태 표현을 보정한다.
8. unit/integration tests와 `git diff --check`를 통과시킨다.

## 8. 권장 커밋 단위

1. `docs(ocr): design layout-aware Google Vision primary OCR`
   - Why: P1-2 요구사항과 현재 provider 구현 차이를 명확히 해서 layout/fallback 구현 범위를 고정한다.
2. `feat(ocr): expose layout structure in OCRResult`
   - Why: Layout Parser가 flat text가 아니라 단어 좌표와 block hierarchy에 의존할 수 있게 한다.
3. `feat(ocr): parse Google Vision document layout`
   - Why: Google Vision `fullTextAnnotation` 구조를 내부 DTO로 정규화해 provider 교체 가능성을 유지한다.
4. `feat(config): externalize OCR confidence threshold`
   - Why: 0.85를 코드 상수가 아니라 fixture 기반으로 조정 가능한 runtime 설정으로 둔다.
5. `feat(ocr): route low-confidence Google Vision results to CLOVA`
   - Why: primary OCR이 낮은 신뢰도일 때 수동 입력 전에 백업 OCR로 회복할 수 있게 한다.

## 9. 구현 전 체크리스트

- [x] 현재 Google Vision provider 파일 위치 확인
- [x] Google Vision `DOCUMENT_TEXT_DETECTION` 공식 문서 확인
- [x] `fullTextAnnotation` page/block/paragraph/word 구조 확인
- [x] 현재 `OCRResult`가 평균 confidence만 가진다는 차이 확인
- [x] 현재 low confidence threshold가 `0.80` 상수라는 차이 확인
- [x] `OCRResult.pages` DTO 추가
- [x] Google Vision layout parser 구현
- [x] `OCR_CONFIDENCE_THRESHOLD=0.85` 설정 추가
- [x] CLOVA fallback trigger를 settings threshold 기반으로 변경
- [x] layout parser consumer가 빈 pages에서 flat text로 degrade하는지 확인

## 10. 2026-05-16 구현 반영 결과

구현 파일:

- `backend/Nutrition-backend/src/ocr/base.py`: layout-aware OCR DTO 추가
- `backend/Nutrition-backend/src/ocr/providers/google_vision.py`: `fullTextAnnotation.pages[].blocks[].paragraphs[].words[]` parser와 word-first confidence aggregation 추가
- `backend/Nutrition-backend/src/ocr/google_vision.py`: handoff 호환 alias `GoogleVisionOCR` 추가
- `backend/Nutrition-backend/src/config.py`, `backend/.env.example`, `.env`: `OCR_CONFIDENCE_THRESHOLD=0.85` 설정 추가
- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`: multimodal/secondary fallback threshold를 `Settings.ocr_confidence_threshold`로 통일
- `backend/Nutrition-backend/src/services/supplement_parser.py`: parser snapshot의 `ocr_text` low-confidence 표시도 settings threshold 사용
- `backend/Nutrition-backend/src/ocr/factory.py`: P1-2 confidence fallback에서 CLOVA를 PaddleOCR보다 먼저 구성

검증 메모:

- mock Google Vision 응답 기준으로 단어 text, 좌표, block hierarchy, confidence aggregation을 검증한다.
- `textAnnotations` only 응답은 `pages=()`로 degrade한다.
- `OCR_CONFIDENCE_THRESHOLD`는 공식 권장값이 아니라 프로젝트 운영 후보값이며, fixture 평가 전에는 정확도 주장 근거로 사용하지 않는다.
