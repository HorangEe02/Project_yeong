# OCR 3-Tier Fixture Evaluation Report

> 이 템플릿은 `backend/scripts/evaluate_ocr_three_tier.py`가 생성하는 redacted report의 검토 기준입니다. raw image와 raw OCR text는 이 문서나 산출물에 포함하지 않습니다.

## 실행 정보

- 실행일:
- manifest:
- fixture 수:
- provider observation 수:
- raw image 저장 여부: `false`
- raw OCR text 저장 여부: `false`

## Provider Metrics

| Provider | Calls | Text non-empty | Parser success | Avg latency ms | Ingredient name exact | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| google_vision_document |  |  |  |  |  |  |
| ollama_vision_assist |  |  |  |  |  |  |
| paddleocr_local |  |  |  |  |  |  |
| clova_ocr |  |  |  |  |  |  |

## Review Notes

- YOLO ROI crop이 primary OCR 결과를 개선했는지:
- Ollama fallback이 hallucination 없이 visible text만 반환했는지:
- PaddleOCR local fallback을 CLOVA보다 먼저 둘 근거가 생겼는지:
- CLOVA external fallback을 켜기 전에 남은 vendor/security/consent 항목:
- 사용자 확인 단계로 보내야 하는 대표 mismatch 사례:
