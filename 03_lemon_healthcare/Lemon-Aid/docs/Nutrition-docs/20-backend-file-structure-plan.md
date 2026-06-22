# 백엔드 파일 구조 확장 계획

> 작성일: 2026-05-13
> 상태: 구현 반영 초안
> 범위: 기존 layer 구조를 유지하면서 OCR, local LLM, YOLO, 학습/vector DB 파이프라인을 독립 모듈로 확장

## 1. 기준 원칙

- 기존 `api -> services -> domain adapter/models` 흐름은 유지한다.
- `services/`는 orchestration만 담당하고, OCR/LLM/YOLO/embedding/vector-store 구현은 각각 독립 package에 둔다.
- `enable_multimodal_llm`, `enable_vision_classifier`, `enable_image_learning_pipeline`, `enable_pgvector_storage` 기본값은 OFF다.
- 사용자 이미지의 학습 재사용은 `image_learning_dataset`, `ocr_image_processing`, `data_retention` 동의가 모두 있어야 한다.

## 2. 현재 반영 구조

```text
backend/src/
  api/v1/
    supplements.py                 # 기존 /supplements/analyze 유지, 새 orchestration service 경유

  services/
    supplement_intake.py           # 이미지 검증과 intake-only preview 저장
    supplement_parser.py           # OCR text -> Ollama structured parser 저장
    supplement_image_analysis.py   # intake -> optional OCR -> parser orchestration

  ocr/
    base.py                        # OCRAdapter, OCRImageInput, OCRResult
    preprocessing.py               # OCR용 이미지 정규화
    providers/noop.py              # 기본 OFF 환경용 no-op provider

  llm/
    base.py                        # LLMAdapter 추상 인터페이스
    ollama.py                      # 현재 운영 중인 OllamaSupplementParser

  vision/
    base.py                        # VisionAdapter, BoundingBox
    preprocessing.py               # ROI crop helper
    taxonomy.py                    # 비의료 object label taxonomy
    yolo.py                        # YoloLabelDetector fail-closed scaffold

  learning/
    consent_gate.py                # image learning consent/flag gate
    embeddings.py                  # embedding provider contract
    vector_store.py                # pgvector adapter contract
    retention.py                   # image retention deadline helper

  models/schemas/
    supplement_image.py            # image pipeline metadata
    learning.py                    # learning/vector gate metadata
```

## 3. 구현 게이트

| 기능 | 기본 상태 | 구현 진입 조건 |
|------|-----------|----------------|
| OCR provider | no-op 또는 미주입 | 이미지 처리 동의 + provider별 공식 SDK 검토 |
| Ollama text parser | 운영 중 | local Ollama endpoint + Pydantic schema 검증 |
| Ollama multimodal | OFF | docs/17 게이트 #1 + structured output 검증 |
| YOLO ROI detector | fail-closed scaffold | docs/17 게이트 #2 + `.[vision]` 설치 + 검증된 Ultralytics runner |
| pgvector storage | OFF | docs/17 게이트 #3 + 세 동의 통과 + retention 설정 |

## 4. 공식 문서 기준

- FastAPI multi-file/APIRouter 구조: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Ollama Chat API: https://docs.ollama.com/api
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- pgvector: https://github.com/pgvector/pgvector
- Ultralytics YOLOv8: https://docs.ultralytics.com/models/yolov8/
- GitHub `actions/setup-python`: https://github.com/actions/setup-python
- Python 3.13 공식 문서: https://docs.python.org/3.13/
