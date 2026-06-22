# Naver OCR Markdown Table Escaping Result

## Summary

- Naver Tampermonkey OCR comparison Markdown renderer가 provider/category/product 같은 manifest-derived table cell 값을 escape하도록 보강했다.
- `|`는 `\|`로 변환하고, `<`, `>`, `&`는 HTML-safe sequence로 변환한다.
- 줄바꿈이 포함된 label은 한 줄로 접어 Markdown table 구조가 깨지지 않게 했다.
- DB write, OCR provider 호출, Ollama 호출, 외부 전송은 수행하지 않았다.

## Changed Files

- `backend/scripts/evaluate_naver_tampermonkey_ocr.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_evaluate_naver_tampermonkey_ocr.py`

## Official References

- GitHub Docs table escaping: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-tables
- Python `html.escape`: https://docs.python.org/3/library/html.html

## Security Review

- manifest/observation label이 Markdown table delimiter로 동작하는 출력 주입 경로를 차단했다.
- HTML-like label이 report renderer에서 raw HTML로 렌더링되는 경로를 줄였다.
- raw OCR text, provider payload, request header, image bytes, raw model response 저장은 없다.

## Verification

```text
pytest focused: 16 passed in 0.05s
black: 2 files would be left unchanged
ruff: All checks passed
privacy scan on regenerated report: 2 files, finding_count=0
git diff --check: passed
detect-secrets: no findings
```
