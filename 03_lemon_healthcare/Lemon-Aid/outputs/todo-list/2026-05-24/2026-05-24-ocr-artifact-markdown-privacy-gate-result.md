# OCR Artifact Markdown Privacy Gate Result

## Summary

- OCR artifact privacy checker가 JSON/JSONL뿐 아니라 Markdown report도 기본 검사하도록 확장했다.
- Markdown report에서 local path literal과 raw payload field token이 발견되면 privacy gate가 실패한다.
- `raw_ocr_text_stored=false`처럼 안전 상태를 표현하는 derived flag는 허용하고, `raw_ocr_text` 같은 raw field token만 차단한다.
- DB write, OCR provider 호출, Ollama 호출, 외부 전송은 수행하지 않았다.

## Changed Files

- `backend/scripts/check_ocr_artifact_privacy.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_check_ocr_artifact_privacy.py`

## Official Reference

- Python `re`: https://docs.python.org/3/library/re.html

## Security Review

- provider comparison Markdown report가 raw key나 local absolute path를 포함해도 기존 JSON-only gate가 놓치는 경로를 차단했다.
- `.md`는 구조화 JSON으로 파싱하지 않고 line 단위로 local path marker와 forbidden raw token을 검사한다.
- `secret` 일반 단어는 Markdown 설명에서 과탐지 위험이 커서 raw token 검사에서는 제외하고, 구조화 JSON key에서는 계속 차단한다.

## Verification

```text
pytest focused: 25 passed in 0.06s
black: 2 files would be left unchanged
ruff: All checks passed
artifact privacy scan on generated Markdown: 4 files, finding_count=0
git diff --check: passed
detect-secrets: no findings
```
