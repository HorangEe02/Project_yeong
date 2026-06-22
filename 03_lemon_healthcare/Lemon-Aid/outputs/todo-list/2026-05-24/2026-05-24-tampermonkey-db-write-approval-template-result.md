# Tampermonkey DB Write Approval Template Result

## Summary

- DB write gate가 요구하는 reviewer approval log를 사람이 만들기 전에, 필요한 증거 파일을 SHA-256으로 묶는 non-importable approval template exporter를 추가했다.
- template은 `template_importable=false`, `approved_for_db_write=false`로 고정되어 DB write runner가 그대로 받지 않는다.
- 기본 실행은 파일 검증과 JSON 출력만 수행하며 DB write, OCR provider 호출, LLM 호출, 외부 전송을 수행하지 않는다.

## Changed Files

- `backend/scripts/export_naver_tampermonkey_db_write_approval_template.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_db_write_approval_template.py`

## Official References

- Python `hashlib`: https://docs.python.org/3/library/hashlib.html
- Python `argparse`: https://docs.python.org/3/library/argparse.html

## Security Review

- DB session, OCR provider, Ollama, 외부 API를 호출하지 않는다.
- raw OCR text, provider payload, request header, image bytes, model raw response, local path literal을 저장하지 않는다.
- template 자체를 import 불가능하게 만들어 operator가 그대로 `--approval-log`로 쓰는 실수를 막는다.
- DB write runner 테스트에서 template 파일을 approval log로 쓰면 실패하는 조건을 직접 검증한다.

## Verification

Result:

```text
40 passed in 0.36s
black: 2 files would be left unchanged
ruff: All checks passed
git diff --check: passed
detect-secrets: no findings
```

## Next Steps

1. Human reviewer가 approved input, dry-run plan, dry-run summary, privacy summary를 확인한다.
2. Approval template의 digest와 계획 수량을 확인한 뒤, 별도 approval log schema로 변환한다.
3. 기존 DB write runner preflight-only 결과 확인 후 `--execute-db-write`로 1회 실행한다.
