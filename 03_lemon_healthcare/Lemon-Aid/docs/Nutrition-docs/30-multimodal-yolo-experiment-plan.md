# 30. Multimodal Ollama / YOLO Experiment Plan

작성일: 2026-05-13
범위: 영양제 이미지 분석의 보조 실험 경로. 기존 OCR text -> structured parse -> user confirmation 주 경로는 유지한다.
상태: 상세 설계 및 구현 플랜

## 1. 결론

권장 방향은 **OCR-first + optional ROI + optional vision assist**다.

- 주 경로는 계속 `OCR text -> structured supplement parse -> user confirmation`이다.
- Ollama multimodal은 OCR이 실패하거나 confidence가 낮을 때만 **visible text 후보 추출**에 사용한다.
- YOLO는 영양제 병, 라벨, 성분표, 섭취방법, 주의사항 같은 **영역 탐지(ROI)** 보조에만 사용한다.
- YOLO 결과를 제품명, 성분명, 함량, 복용법 추출의 주 근거로 사용하지 않는다.
- 모든 결과는 사용자 확인 전 preview이며, 원본 이미지와 raw OCR/model response는 기본 저장하지 않는다.

## 2. 현재 구현 기준선

현재 backend에는 확장 경계가 이미 나뉘어 있다.

| 영역 | 현재 파일 | 상태 |
| --- | --- | --- |
| 이미지 intake | `backend/src/services/supplement_image_analysis.py` | 이미지 검증, preview 저장, optional adapter orchestration 구현 |
| OCR adapter contract | `backend/src/ocr/base.py` | `OCRImageInput`에 optional `label_region` 전달 가능 |
| OCR text parser | `backend/src/services/supplement_parser.py` | OCR text 정규화, HMAC hash, Ollama parser 호출 |
| Ollama parser | `backend/src/llm/ollama.py` | local `/api/chat`, structured output, Pydantic 재검증 구현 |
| LLM base | `backend/src/llm/base.py` | multimodal method는 계약만 있고 런타임 미연결 |
| Vision contract | `backend/src/vision/base.py` | `BoundingBox`, `VisionAdapter.detect_label_region()` 계약 |
| YOLO ROI helper | `backend/src/vision/yolo.py`, `backend/src/vision/ultralytics_runner.py` | gated ROI-only helper 구현. optional Ultralytics runtime은 lazy-load |
| Config flags | `backend/src/config.py` | `enable_multimodal_llm=false`, `enable_vision_classifier=false`, `vision_classifier_model="yolo26n.pt"` |

중요한 현재 제약:

- `/api/v1/supplements/analyze` 기본 호출은 intake-only다.
- OCR provider adapter가 주입되면 OCR text parser로 이어질 수 있다.
- `YoloLabelDetector`는 gated ROI helper이며, 실제 모델 실행은 optional `UltralyticsYoloRunner`로 격리된다.
- `OllamaSupplementParser`는 OCR text parser이며 이미지 입력을 받지 않는다.

## 3. 공식 문서 확인 결과

| 대상 | 확인 내용 | 설계 반영 |
| --- | --- | --- |
| Ultralytics YOLO docs | YOLO는 detection, segmentation, classification, pose 등 vision task를 지원한다. object detection은 이미지 내 객체의 위치와 class를 bounding box, class label, confidence로 반환하는 task다. | YOLO 산출물은 ROI metadata로만 사용한다. 텍스트 이해나 성분 추론으로 사용하지 않는다. |
| YOLOv8 docs | YOLOv8은 detection, segmentation, pose, oriented detection, classification 모델 변형을 제공하며 inference/validation/training/export mode를 지원한다. | 1차 실험은 detection variant만 사용한다. classification model이나 segmentation model을 제품/성분 추출로 오용하지 않는다. |
| Ultralytics predict docs | Python API는 `YOLO(...)`로 모델을 로드하고 predict 결과의 `boxes`, `xyxy/xywh`, class name, confidence에 접근한다. | adapter 내부에서 bbox/class/confidence만 표준화해 `BoundingBox`로 변환한다. |
| Ultralytics license docs | Ultralytics는 AGPL-3.0과 Enterprise license 옵션을 제공한다. | 상용/운영 전에는 라이선스 검토를 게이트 #2 산출물로 둔다. |
| Ollama API docs | 설치 후 기본 local API는 `http://localhost:11434/api`이고, cloud API도 별도 base URL이 있다. | 식별 가능 health data는 local host만 허용하고 cloud base URL은 차단한다. |
| Ollama vision docs | Vision model은 text와 image를 함께 입력받으며 REST API는 base64 image를 `images` 배열로 전달한다. | multimodal adapter는 validated/cropped image bytes를 base64로 보내되 raw image를 저장하지 않는다. |
| Ollama structured outputs | `format`에 JSON schema를 전달할 수 있고, Pydantic schema 전달 후 `model_validate_json()`으로 검증하는 예시가 있다. Ollama Cloud는 structured outputs를 지원하지 않는다고 문서화되어 있다. | vision assist 결과도 JSON schema + Pydantic 재검증을 강제한다. |

참조 URL:

- Ultralytics Docs: https://docs.ultralytics.com/
- Ultralytics Object Detection: https://docs.ultralytics.com/tasks/detect/
- Ultralytics Predict Mode: https://docs.ultralytics.com/modes/predict/
- YOLOv8 Models: https://docs.ultralytics.com/models/yolov8/
- Ollama API: https://docs.ollama.com/api
- Ollama Vision: https://docs.ollama.com/capabilities/vision
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs

주의: 현재 공식 Ollama vision 문서 예시는 `gemma3`를 사용한다. 프로젝트 설정의 `ollama_vision_model="gemma4:e4b"`는 local runtime 후보값일 뿐, 구현 시 `GET /api/tags` readiness로 실제 설치 여부를 확인해야 한다. 이 문서에서는 특정 Gemma 4 tag의 공식 가용성을 단정하지 않는다.

## 4. 브레인스토밍

### 후보 A: YOLO로 제품명/성분을 직접 추출

- 장점: 겉보기에는 이미지 하나로 모든 결과를 얻는 것처럼 보인다.
- 문제: YOLO detection은 객체 위치와 class confidence를 반환하는 모델이다. 라벨 텍스트를 읽거나 성분 함량을 이해하는 모델이 아니다.
- 판정: **금지**. 제품명/성분/함량 추출의 주 경로로 YOLO를 쓰지 않는다.

### 후보 B: Ollama multimodal을 OCR 대신 주 경로로 사용

- 장점: OCR provider 없이도 이미지에서 후보 텍스트를 얻을 수 있다.
- 문제: vision LLM 결과는 OCR보다 재현성과 위치 기반 검증이 약하고, 보이지 않는 정보를 그럴듯하게 보강할 위험이 있다.
- 판정: **보류**. OCR 실패 보조나 후보 추출로만 시작한다.

### 후보 C: YOLO ROI -> OCR crop -> 기존 text parser

- 장점: YOLO의 강점인 localization만 사용한다.
- 장점: 기존 `OCRImageInput.label_region`과 `SupplementImageAnalysisAdapters.vision` 구조에 잘 맞는다.
- 장점: OCR text parser와 사용자 확인 흐름을 그대로 유지한다.
- 판정: **1차 YOLO 실험 권장안**.

### 후보 D: OCR 실패/저신뢰 시 Ollama vision 후보 생성

- 장점: OCR이 빈 결과를 내거나 낮은 confidence를 반환할 때 UX fallback을 제공할 수 있다.
- 문제: candidate hallucination 방지를 위해 "보이는 텍스트 조각만" 반환하도록 schema와 prompt를 제한해야 한다.
- 판정: **1차 multimodal 실험 권장안**.

## 5. 실험 범위

### 5.1 In Scope

- YOLO ROI class:
  - `supplement_bottle`
  - `supplement_label`
  - `blister_pack`
- YOLO output:
  - bbox
  - class label
  - confidence
  - model tag
  - preprocessing metadata
- Multimodal Ollama output:
  - visible label text fragment candidates
  - possible product name candidate only if visibly present
  - uncertainty warnings
  - image crop/full-image source metadata
- Existing parser reuse:
  - multimodal candidate text는 별도 확정 데이터가 아니라 기존 text parser 입력 후보로만 사용한다.
  - 최종 저장 전 사용자 확인은 필수다.

### 5.2 Out of Scope

- YOLO로 성분명, 함량, 복용량, 주의사항을 직접 추출
- YOLO class confidence를 제품 identity confidence로 해석
- multimodal output을 사용자 확인 없이 `UserSupplement`로 저장
- raw image, raw OCR text, raw LLM response 저장
- 처방전/검사표 이미지에 이 실험 플로우 재사용
- 외부 LLM 또는 Ollama Cloud 전송
- pgvector 학습 적재와 같은 장기 학습 파이프라인 자동 연결

## 6. 목표 아키텍처

```text
POST /api/v1/supplements/analyze
  -> auth + ocr_image_processing consent
  -> read_and_validate_supplement_image
  -> create_supplement_analysis_intake
  -> optional YOLO ROI detector
      -> supplement_bottle/supplement_label/blister_pack bbox 후보
      -> best label ROI를 OCRImageInput.label_region에 전달
  -> OCR adapter
      -> OCR text + confidence
  -> if OCR text usable
      -> parse_supplement_analysis_ocr_text
      -> OllamaSupplementParser text structured output
  -> else if enable_multimodal_llm and policy allows fallback
      -> Ollama vision assist: image -> visible text candidates
      -> normalize/hash candidate text
      -> parse candidate text with existing structured parser
  -> SupplementAnalysisPreview(status=requires_confirmation)
```

설계 핵심:

- `services/supplement_image_analysis.py`는 orchestration만 담당한다.
- YOLO runtime은 `src/vision/` 내부에 둔다.
- Ollama vision assist는 `src/llm/` 내부에 둔다.
- 기존 `OllamaSupplementParser`는 text parser로 유지한다.
- API response contract는 당장 확장하지 않고, 필요한 metadata는 `parsed_snapshot`/warnings/audit metadata에 제한적으로 넣는다.

## 7. YOLO ROI 상세 설계

### 7.1 Adapter

`YoloLabelDetector`는 public entry point로 유지하고, 실제 runner는 별도 module에 좁게 추가한다.

후보:

```text
backend/src/vision/
  yolo.py                      # public detector class
  ultralytics_runner.py         # optional dependency import 격리
  taxonomy.py                   # 허용 class와 label normalization
  preprocessing.py              # bbox clamp/crop helper
```

구현 상태(2026-05-13):

- `UltralyticsYoloRunner`가 `boxes.xyxy`, `boxes.cls`, `boxes.conf`를 내부 `BoundingBox`로 정규화한다.
- `YoloLabelDetector`는 flag가 꺼져 있으면 fail closed 하고, flag가 켜진 경우에도 허용 class와 confidence 기준을 통과한 ROI만 반환한다.
- `supplement_image_analysis.py`는 vision 실패 시 OCR full image fallback을 유지한다.
- 단위 테스트는 `tests/unit/vision/test_yolo_detector.py`, `tests/unit/vision/test_preprocessing.py`에 추가되어 있다.

원칙:

- `ultralytics` import는 `enable_vision_classifier=true`일 때 실제 runner 초기화 시점에만 한다.
- production에서는 모델 자동 다운로드를 허용하지 않는다. 모델 파일 경로, checksum, license 검토 기록을 게이트 #2 산출물로 고정한다.
- pretrained COCO `yolo26n.pt`는 supplement facts/precautions/intake method custom class를 바로 제공하지 않는다. 1차 PoC에서는 import/runner 구조와 fake runner test를 먼저 만들고, custom dataset이 준비된 뒤 fine-tuned weight를 붙인다.
- bbox는 이미지 경계 안으로 clamp한다.
- 여러 box가 나오면 우선순위는 `supplement_facts` > `precautions` > `intake_method` > `ingredients` > `supplement_label` > `supplement_bottle` > `blister_pack`이다.
- ROI confidence가 기준 미만이면 OCR full image path로 fallback한다.

### 7.2 YOLO가 반환하면 안 되는 것

- 제품명
- 브랜드명
- 성분명
- 함량
- 복용량
- 건강 효과
- 위험성 판단

YOLO adapter의 domain output은 `BoundingBox` 또는 `DetectedRegion`까지만 허용한다.

### 7.3 Evaluation

측정 항목:

- ROI detection:
  - per-class precision/recall
  - IoU distribution
  - false crop rate
  - no-detection fallback rate
- OCR impact:
  - full image OCR 대비 crop OCR text length 변화
  - OCR confidence 변화
  - parser success rate 변화
- Runtime:
  - local CPU latency
  - memory peak
  - timeout/failure rate

공식 문서나 현재 데이터로 권장 임계값을 찾을 수 없으므로, 활성화 기준은 PoC dataset에서 팀이 측정한 결과와 발주처 게이트 #2 리뷰로 결정한다.

## 8. Ollama Multimodal 상세 설계

### 8.1 역할

Ollama vision assist는 OCR이 실패했을 때 "보이는 텍스트 후보"를 생성하는 보조 채널이다.

실행 조건:

- `enable_multimodal_llm=true`
- `allow_external_llm=false`
- `ollama_base_url`이 local host
- `ollama_vision_model`이 `GET /api/tags`에 존재
- OCR 결과가 비어 있거나 confidence가 낮음
- 이미지 크기/픽셀/보유 정책 검증 완료

### 8.2 Output Schema

초기 schema 후보:

```json
{
  "type": "object",
  "properties": {
    "visible_text_fragments": {
      "type": "array",
      "items": {"type": "string"},
      "maxItems": 30
    },
    "possible_product_name": {"type": ["string", "null"]},
    "source_region": {"type": "string", "enum": ["full_image", "yolo_roi"]},
    "low_confidence_fields": {
      "type": "array",
      "items": {"type": "string"}
    },
    "warnings": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": [
    "visible_text_fragments",
    "possible_product_name",
    "source_region",
    "low_confidence_fields",
    "warnings"
  ],
  "additionalProperties": false
}
```

검증 규칙:

- `visible_text_fragments`는 OCR-like text 후보일 뿐이다.
- 모델이 보이지 않는 성분명이나 효능을 추론하면 schema 검증 후 warning 또는 rejection으로 처리한다.
- `possible_product_name`은 명확히 보이는 경우에만 허용하고, 사용자 확인 전 저장 확정하지 않는다.
- 결과 text 후보를 조합해 기존 `parse_supplement_analysis_ocr_text`로 전달하되, source는 `ollama_vision_assist`로 표시한다.

### 8.3 Prompt Guard

프롬프트 요구사항:

- "이미지에 보이는 텍스트 조각만 추출"
- "성분, 함량, 복용법을 보이지 않으면 null 또는 생략"
- "영양·의료 조언 금지"
- "이미지 밖 지식으로 제품 정보를 보강하지 말 것"
- "JSON schema 외 출력 금지"

### 8.4 Storage Policy

- raw image bytes 저장 금지
- base64 image payload 저장 금지
- raw multimodal response 저장 금지
- visible text candidate는 raw OCR text와 동일하게 HMAC hash만 저장하고, sanitized snapshot만 preview에 보관
- audit metadata에는 `raw_multimodal_response_stored=false`, `raw_image_stored=false`, `source=ollama_vision_assist`를 기록

## 9. Feature Flags and Gates

| Flag | 기본값 | 사용 조건 | 비고 |
| --- | --- | --- | --- |
| `enable_multimodal_llm` | `false` | 게이트 #1 통과 | OCR 실패/저신뢰 fallback만 허용 |
| `ollama_vision_model` | `gemma4:e4b` | local model readiness 통과 | 공식 tag 가용성 단정 금지 |
| `enable_vision_classifier` | `false` | 게이트 #2 통과 | YOLO ROI 보조만 허용 |
| `vision_classifier_model` | `yolo26n.pt` | 검증된 local weight path 또는 tag | production 자동 다운로드 금지 |
| `image_retention_days` | `0` | 학습 동의 전 즉시 삭제 | 실험에서도 raw image 저장 금지 |

추가 설정 후보:

```python
multimodal_ocr_assist_policy: Literal["disabled", "ocr_empty_only", "low_confidence"] = "disabled"
vision_roi_min_confidence: float = 0.50
vision_roi_allowed_classes: list[str] = ["supplement_label", "supplement_bottle", "blister_pack"]
```

위 후보 설정값은 구현 전후 테스트로 고정해야 하며, 운영 기본값은 여전히 disabled다.

## 10. 상세 구현 플랜

### MMY-0. 기준선 고정

목표:

- 기존 OCR text parser와 supplement intake API가 변하지 않는지 고정한다.

작업:

- `test_supplement_intake_api.py` 기존 intake-only 동작 유지
- `test_supplement_ocr_text_api.py` OCR text parse 주 경로 유지
- `test_config.py`에서 multimodal/vision flags 기본 false 유지
- `test_openapi_examples.py` 금지 표현 회귀 유지

### MMY-1. YOLO ROI runner 격리

상태: 구현 완료. `src/vision/ultralytics_runner.py`, `src/vision/yolo.py`, `src/vision/taxonomy.py`, `src/vision/preprocessing.py` 기준.

목표:

- Ultralytics optional dependency를 안전하게 감싼 runner를 추가한다.

작업:

- `src/vision/ultralytics_runner.py` 추가
- `YoloLabelDetector`가 gate 통과 시 runner를 주입받거나 lazy-load
- `ultralytics` 미설치 시 `VisionError`로 fail closed
- bbox clamp와 class allowlist 적용
- YOLO 결과는 `BoundingBox`까지만 반환

테스트:

- flag false면 runner import 없음
- `ultralytics` 미설치 시 fail closed
- 허용 class 외 box는 무시
- bbox가 이미지 범위를 넘으면 clamp
- YOLO result에 text-like field가 있어도 parser로 직접 전달하지 않음

### MMY-2. ROI -> OCR 연결

상태: 구현 완료. `OCRImageInput.label_region` 전달과 vision failure -> full image OCR fallback 테스트 추가.

목표:

- YOLO ROI가 OCR adapter input에만 영향을 주도록 한다.

작업:

- `OCRImageInput.label_region` 사용 경로를 fake OCR test로 고정
- `supplement_image_analysis.py`에서 vision result가 있으면 OCR input에 ROI 전달
- ROI 실패 시 full image OCR로 fallback

테스트:

- fake vision + fake OCR에서 `label_region` 전달 확인
- vision failure는 500이 아니라 OCR full image fallback 또는 stable preview warning으로 처리할지 결정 후 테스트
- `ENABLE_VISION_CLASSIFIER=true`인데 adapter가 없으면 현재처럼 configuration error

### MMY-3. Ollama vision assist adapter

상태: 구현 완료. `src/llm/ollama_vision.py` 기준. local host guard, base64 image payload, schema validation, readiness check 테스트 추가.

목표:

- OCR 실패/저신뢰 시 local Ollama vision model로 visible text candidates만 생성한다.

작업:

- `src/llm/ollama_vision.py` 또는 `src/llm/ollama.py` 내 얇은 vision client 추가
- `/api/chat` payload에 `messages[].images=[base64]`, `stream=false`, `format=schema`, `think=false`
- `ollama_vision_model` readiness check 추가
- local host guard 재사용
- Pydantic schema로 재검증

테스트:

- payload가 base64 image를 포함하고 raw image를 로그/DB에 저장하지 않음
- remote `OLLAMA_BASE_URL` 차단
- malformed JSON, extra field, invented advice field reject
- schema-valid output만 candidate로 통과

### MMY-4. OCR fallback orchestration

상태: 구현 완료. `ocr_empty_only`, `low_confidence`, `disabled` policy 기준으로 기존 OCR 성공 경로를 우선한다.

목표:

- OCR 결과가 비어 있거나 confidence가 낮은 경우에만 vision assist를 호출한다.

작업:

- `SupplementImageAnalysisAdapters`에 multimodal assist adapter 후보 추가
- `OCR_LOW_CONFIDENCE_THRESHOLD`와 충돌하지 않게 policy를 명시
- candidate text를 `parse_supplement_analysis_ocr_text`로 전달할 때 provider/source를 `ollama_vision_assist`로 표기
- preview warning에 "이미지 보조 추출 후보입니다. 모든 필드를 확인하세요." 추가

테스트:

- OCR success + high confidence -> multimodal 호출 없음
- OCR empty + flag true -> multimodal 호출
- OCR low confidence + policy low_confidence -> multimodal 호출
- flag false -> multimodal 호출 없음
- multimodal 실패 -> preview는 intake-only 또는 stable error로 처리

### MMY-5. 실험 리포트와 게이트 산출물

목표:

- 기능 활성화 전에 측정 결과와 규제 검토를 남긴다.

작업:

- `scripts/evaluate_yolo_roi.py` 또는 test-only evaluation harness 설계
- dataset manifest schema 정의
- 원본 이미지 저장 없이 파일 경로, consent id, hash, annotation metadata만 사용
- PoC report template 작성

산출물:

- YOLO ROI 결과: per-class metric, latency, failure examples
- OCR improvement report: full image OCR vs ROI crop OCR
- Multimodal fallback report: candidate extraction success/failure, hallucination review
- 금지 표현 검사 결과
- license review note

## 11. 테스트 플랜

1. Unit
   - `tests/unit/vision/test_yolo_detector.py`
   - `tests/unit/vision/test_yolo_preprocessing.py`
   - `tests/unit/llm/test_ollama_vision_assist.py`
2. Service
   - `tests/unit/services/test_supplement_image_analysis.py`
   - fake vision, fake OCR, fake multimodal adapter 조합
3. Integration
   - `tests/integration/api/test_supplement_intake_api.py`
   - 기본 API contract 변화 없음
4. Optional local smoke
   - `RUN_YOLO_TESTS=1`
   - `RUN_OLLAMA_VISION_TESTS=1`
   - 로컬 모델 설치와 테스트 이미지 consent fixture가 있을 때만 실행

필수 검증 명령:

```bash
cd yeong-Lemon-Aid/backend
pytest tests/unit/vision tests/unit/llm tests/unit/services/test_supplement_image_analysis.py --no-cov
pytest tests/integration/api/test_supplement_intake_api.py tests/integration/api/test_supplement_ocr_text_api.py --no-cov
pytest tests/integration/api/test_openapi_examples.py --no-cov
ruff check src/vision src/llm src/services tests/unit/vision tests/unit/llm
mypy src/vision src/llm src/services/supplement_image_analysis.py
```

## 12. 완료 기준

- 기본 flags false에서 기존 API와 테스트 결과가 변하지 않는다.
- YOLO는 ROI bbox/class/confidence만 반환한다.
- YOLO 결과가 제품명/성분명/함량 추출 경로로 직접 연결되지 않는다.
- OCR이 정상일 때 multimodal assist가 호출되지 않는다.
- OCR 실패/저신뢰일 때만 multimodal assist 후보가 생성된다.
- multimodal output은 JSON schema와 Pydantic으로 재검증된다.
- raw image, raw OCR text, raw LLM response가 저장되지 않는다.
- production에서 `enable_multimodal_llm=true`, `enable_vision_classifier=true`는 게이트 통과 전 validation error를 유지한다.
- Ultralytics license와 모델 weight 출처가 기록된다.

## 13. 커밋 단위 제안

```text
test(vision): freeze supplement image analysis fallback behavior

Why:
Multimodal and YOLO experiments must not change the existing OCR text and
intake-only default paths.
```

```text
feat(vision): add gated YOLO ROI runner

Why:
YOLO should only provide bottle, label, and blister ROI metadata for OCR
preprocessing, not product or ingredient extraction.
```

```text
feat(llm): add local Ollama vision assist for OCR fallback

Why:
Multimodal inference is limited to visible text candidate extraction when OCR is
empty or low-confidence, and every output is schema-validated before preview use.
```

```text
docs(ai): record multimodal and YOLO gate evidence

Why:
Production enablement requires measured ROI/OCR impact, license review, and
forbidden-expression checks before feature flags can be changed.
```
