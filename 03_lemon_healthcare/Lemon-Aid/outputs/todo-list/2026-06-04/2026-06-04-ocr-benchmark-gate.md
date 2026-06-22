# 2026-06-04 OCR Benchmark Gate

## Summary

- `supplement-ocr-benchmark-gate-v1` gate를 추가해 PII review, manual ground-truth review, OCR benchmark fixture 준비 상태를 한 번에 차단/허용 판단하도록 만들었습니다.
- gate는 redacted summary JSON만 읽습니다. 원본 이미지 row, OCR raw text, provider payload, LLM payload, DB row는 읽지 않습니다.
- 현재 실제 preflight 기준 OCR benchmark는 `blocked_by_pii_screening`입니다.

## Current Evidence

- Candidate rows: `215`
- Cleared no personal data: `0`
- Blank PII decisions: `215`
- Pending PII actions: `215`
- Ground-truth template allowed: `false`
- Teacher OCR benchmark allowed: `false`
- External teacher OCR eval allowed: `false`
- PaddleOCR training allowed now: `false`

## Meaning

- 리뷰 이미지에 대해 PII strict review가 끝나기 전에는 CLOVA OCR, Google Vision 같은 teacher OCR 호출을 시작하지 않습니다.
- PaddleOCR 학습은 teacher OCR 비교가 끝나도 바로 허용하지 않고, 별도 baseline/promotion gate를 통과해야 합니다.
- 지금 다음 작업은 PII screening decision을 사람이 채운 뒤 strict preflight와 OCR benchmark gate를 다시 실행하는 것입니다.

## Verification

- `ruff check` passed for the OCR benchmark gate, related OCR preflight/benchmark scripts, and focused tests.
- `pytest --no-cov` passed for focused OCR gate/preflight/benchmark/export tests: `27 passed`.
- Actual gate output: `blocked_by_pii_screening`.

## References

- PaddleOCR OCR pipeline: <https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html>
- Google Cloud Vision OCR: <https://cloud.google.com/vision/docs/ocr>
- NAVER Cloud CLOVA OCR API: <https://api.ncloud-docs.com/docs/en/ai-application-service-ocr>
