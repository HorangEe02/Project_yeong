# 수정된 백엔드 파일 구조 설명

> 작성일: 2026-05-13
> 상태: 현재 구현 구조 설명
> 관련 문서: [20-backend-file-structure-plan.md](./20-backend-file-structure-plan.md), [17-image-collection-consent-plan.md](./17-image-collection-consent-plan.md), [12-local-llm-ollama-migration.md](./12-local-llm-ollama-migration.md)

## 1. 구조 변경 목적

이번 구조 변경의 목적은 기존 FastAPI layer 구조를 유지하면서, 영양제 이미지 분석 기능을 OCR, local LLM, YOLO, 학습 데이터 파이프라인으로 안전하게 확장할 수 있도록 경계를 나누는 것이다.

핵심 원칙은 다음과 같다.

- 기존 API 경로와 응답 계약은 유지한다.
- `api/`는 HTTP 계약만 담당한다.
- `services/`는 유스케이스 orchestration만 담당한다.
- OCR, LLM, vision, learning 기능은 각각 독립 adapter 모듈로 분리한다.
- 의료 판단, 복용량 변경 안내, 외부 LLM 전송, 이미지 학습 재사용은 기본 비활성화한다.
- 실제 모델 호출 전에는 기능 플래그와 사용자 동의 게이트를 통과해야 한다.

## 2. 현재 백엔드 구조

```text
backend/src/
  api/
    v1/
      supplements.py

  services/
    supplement_image_analysis.py
    supplement_intake.py
    supplement_parser.py
    supplement_registration.py
    supplement_matching.py

  ocr/
    __init__.py
    base.py
    preprocessing.py
    providers/
      __init__.py
      noop.py

  llm/
    __init__.py
    base.py
    ollama.py

  vision/
    __init__.py
    base.py
    preprocessing.py
    taxonomy.py
    yolo.py

  learning/
    __init__.py
    consent_gate.py
    embeddings.py
    retention.py
    vector_store.py

  models/
    schemas/
      supplement.py
      supplement_parser.py
      supplement_image.py
      learning.py
      privacy.py
    db/
      supplement.py
      privacy.py

  privacy/
    consent_policies.py

  config.py
```

## 3. 계층별 책임

| 계층 | 주요 파일 | 책임 |
|------|-----------|------|
| API | `api/v1/supplements.py` | `/api/v1/supplements/analyze` 계약 유지, 인증·동의·HTTP error 변환 |
| Orchestration | `services/supplement_image_analysis.py` | 이미지 intake, 선택적 vision/OCR, OCR text parser 연결 |
| Intake | `services/supplement_intake.py` | 이미지 MIME/크기/픽셀 검증, SHA-256 hash, preview row 저장 |
| Parser | `services/supplement_parser.py` | OCR text 정규화, HMAC hash, Ollama structured parser 결과 저장 |
| Registration | `services/supplement_registration.py` | 사용자 확인 후 영양제 최종 저장 |
| OCR | `ocr/base.py`, `ocr/preprocessing.py`, `ocr/providers/noop.py` | OCR provider 인터페이스와 전처리 |
| LLM | `llm/base.py`, `llm/ollama.py` | local Ollama structured output parser |
| Vision | `vision/base.py`, `vision/yolo.py` | 라벨 ROI 탐지 인터페이스와 fail-closed YOLO scaffold |
| Learning | `learning/consent_gate.py`, `learning/vector_store.py` | 학습 재사용 동의 게이트와 vector-store 계약 |
| Schema | `models/schemas/*.py` | API/서비스 간 Pydantic schema |
| Privacy | `privacy/consent_policies.py`, `models/schemas/privacy.py` | 동의 타입과 active policy 정의 |

## 4. `/supplements/analyze` 처리 흐름

```text
Client
  -> api/v1/supplements.py
  -> require_user_consent(OCR_IMAGE_PROCESSING)
  -> services/supplement_image_analysis.py
     -> supplement_intake.read_and_validate_supplement_image()
     -> supplement_intake.create_supplement_analysis_intake()
     -> optional VisionAdapter.detect_label_region()
     -> optional OCRAdapter.extract_text()
     -> optional supplement_parser.parse_supplement_analysis_ocr_text()
  -> supplement_analysis_run_to_preview()
  -> SupplementAnalysisPreview response
```

기본 동작은 intake-only다. OCR adapter를 주입하지 않으면 raw image는 저장하지 않고, 이미지 hash와 preview metadata만 남긴다. OCR text가 생긴 경우에만 기존 `OllamaSupplementParser` 기반 구조화 parsing으로 넘어간다.

## 5. 새로 추가된 모듈 설명

### 5.1 `services/supplement_image_analysis.py`

이미지 분석 파이프라인의 중앙 orchestration 서비스다. 기존 `supplement_intake.py`와 `supplement_parser.py`를 직접 대체하지 않고, 둘을 순서대로 연결한다.

현재 역할:

- 이미지 검증과 preview 저장 호출
- `enable_vision_classifier=true`일 때 vision adapter 요구
- OCR adapter가 주입된 경우 OCR 실행
- OCR text가 존재할 때 structured parser 실행
- audit metadata에 `ocr_provider`, `parser_used`, `vision_roi_used` 기록 가능

주의할 점:

- 실제 OCR provider는 기본 연결되어 있지 않다.
- 실제 YOLO inference는 기본 연결되어 있지 않다.
- 실제 pgvector 저장은 이 서비스에서 아직 실행하지 않는다.

### 5.2 `ocr/`

OCR provider를 교체 가능하게 만들기 위한 모듈이다.

```text
ocr/base.py
  OCRAdapter
  OCRImageInput
  OCRResult
  OCRError

ocr/preprocessing.py
  normalize_image_for_ocr()

ocr/providers/noop.py
  NoopOCRAdapter
```

`NoopOCRAdapter`는 외부 provider를 호출하지 않고 빈 OCR 결과를 반환한다. 이는 기본 OFF 환경과 테스트용으로 사용한다.

### 5.3 `vision/`

YOLO 같은 object detection 모델을 직접 API에 붙이지 않고, 라벨 영역 ROI 탐지 adapter로 격리한 모듈이다.

```text
vision/base.py
  VisionAdapter
  BoundingBox
  VisionError

vision/preprocessing.py
  clamp_bounding_box()
  crop_image_to_bounding_box()
  select_best_label_region()

vision/taxonomy.py
  VisionLabel
  VISION_DETECTION_LABELS

vision/ultralytics_runner.py
  UltralyticsYoloRunner

vision/yolo.py
  YoloLabelDetector
```

`YoloLabelDetector`는 gated YOLO ROI helper다. `ENABLE_VISION_CLASSIFIER=false`가 기본값이며, true로 설정된 경우에만 optional `UltralyticsYoloRunner`를 lazy-load 한다. 반환값은 OCR 전처리용 `BoundingBox` metadata로 제한되며, 제품명/성분명/함량 추출은 담당하지 않는다.

### 5.4 `learning/`

이미지 학습 재사용과 vector DB 저장을 API나 parser와 분리하기 위한 모듈이다.

```text
learning/consent_gate.py
  evaluate_image_learning_gate()
  ImageLearningGateDecision

learning/embeddings.py
  EmbeddingProvider
  DisabledEmbeddingProvider

learning/vector_store.py
  VectorStore
  DisabledVectorStore

learning/retention.py
  should_retain_learning_image()
  image_retention_deadline()
```

현재 구현은 계약과 fail-closed 구조까지다. 실제 embedding model 실행, pgvector table, Alembic migration, vector similarity query는 아직 구현하지 않았다.

학습 재사용 게이트는 다음 조건을 모두 요구한다.

- `enable_image_learning_pipeline=true`
- `enable_pgvector_storage=true`
- `image_retention_days > 0`
- `ocr_image_processing` 동의
- `data_retention` 동의
- `image_learning_dataset` 별도 동의

### 5.5 `models/schemas/`

새 schema는 pipeline metadata를 명시하기 위해 추가했다.

```text
models/schemas/supplement_image.py
  SupplementImagePipelineMetadata

models/schemas/learning.py
  ImageLearningGateStatus
  ImageEmbeddingRecordPreview
```

기존 `supplement.py`와 `supplement_parser.py`는 API 응답과 Ollama structured parser 결과를 계속 담당한다.

## 6. 동의와 기능 플래그

관련 설정은 `backend/src/config.py`의 `Settings`에서 관리한다.

| 설정 | 기본값 | 의미 |
|------|--------|------|
| `enable_multimodal_llm` | `false` | Ollama multimodal 보조 채널 |
| `enable_vision_classifier` | `false` | YOLO ROI 탐지 |
| `enable_image_learning_pipeline` | `false` | 이미지 학습 데이터셋 적재 |
| `enable_pgvector_storage` | `false` | pgvector 기반 embedding 저장 |
| `image_retention_days` | `0` | 이미지 보유 기간. 0이면 즉시 삭제 원칙 |

`ConsentType.IMAGE_LEARNING_DATASET`이 추가되었고, active policy는 `privacy/consent_policies.py`에 정의되어 있다.

## 7. 테스트 구조

```text
backend/tests/unit/
  services/
    test_supplement_image_analysis.py
    test_supplement_intake.py
    test_supplement_parser.py
  learning/
    test_consent_gate.py
```

검증 포인트:

- 기본 `/supplements/analyze` 경로는 intake-only 동작을 유지한다.
- OCR adapter가 주입되면 OCR text가 기존 parser 서비스로 전달된다.
- 학습 재사용은 별도 동의와 feature flag를 모두 요구한다.
- raw image bytes와 raw OCR text는 기본 저장하지 않는다.

## 8. 아직 구현하지 않은 범위

아래 항목은 구조만 준비되었고, 실제 운영 기능으로 구현하지 않았다.

- 실제 OCR provider adapter
- Ollama multimodal image-to-text adapter
- Ultralytics YOLO inference runner
- image object storage
- pgvector Alembic migration과 실제 vector table
- embedding model 실행
- 학습 데이터셋 labeling/review UI
- k-anonymity 또는 결합 위험 검증 스크립트

이 범위는 docs/17의 발주처 리뷰 게이트와 별도 동의 UI가 확정된 뒤 구현해야 한다.

## 9. 공식 문서 기준

구조와 후속 구현은 아래 공식 문서를 기준으로 검증한다.

- FastAPI larger applications and `APIRouter`: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Ollama API: https://docs.ollama.com/api
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ultralytics YOLOv8: https://docs.ultralytics.com/models/yolov8/
- pgvector: https://github.com/pgvector/pgvector
- Python 3.13: https://docs.python.org/3.13/
- GitHub `actions/setup-python`: https://github.com/actions/setup-python
