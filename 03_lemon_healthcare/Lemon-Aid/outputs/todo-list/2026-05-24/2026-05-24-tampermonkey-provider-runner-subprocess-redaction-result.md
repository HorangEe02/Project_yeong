# Tampermonkey Provider Runner Subprocess Redaction Result

## Summary

- OCR provider wrapper가 collector/evaluator subprocess stdout/stderr를 직접 스트리밍하지 않도록 `capture_output=True`를 적용했다.
- 하위 프로세스가 traceback, local path, provider warning, secret-like stderr를 출력해도 wrapper의 public output에는 redacted failure summary만 남는다.
- DB write, OCR provider 호출, Ollama 호출, 외부 전송은 이번 코드 변경/테스트에서 수행하지 않았다.

## Changed Files

- `backend/scripts/run_naver_tampermonkey_ocr_eval.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_ocr_eval.py`

## Official Reference

- Python `subprocess.run(capture_output=...)`: https://docs.python.org/3/library/subprocess.html

## Security Review

- child stdout/stderr가 터미널로 직접 흘러나가는 로그 유출 경로를 차단했다.
- wrapper summary는 기존대로 manifest/output 경로를 name/hash만 저장한다.
- raw OCR text, provider payload, request header, image bytes, raw model response 저장은 없다.

## Verification

```text
pytest focused: 15 passed in 0.06s
black: 2 files would be left unchanged
ruff: All checks passed
git diff --check: passed
detect-secrets: no findings
```
