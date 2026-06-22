# Tampermonkey Review Import Gate 결과

## 요약

- 브랜치: `feat/ocr-tampermonkey-category-labeling-team`
- 범위: review decision 적용 -> decision 검증 -> approved DB import export -> ORM dry-run plan을 한 번에 실행하는 read-only gate 추가
- DB write/OCR/LLM/external transfer: 모두 없음
- raw OCR text/provider payload/request header/secret 저장: 없음

## EX400U 경로

현재 Ollama model store는 `/Volumes/Corsair EX400U Media/.ollama/models` 로 확인했다.
`registry.ollama.ai/library` 하위에 `gemma4/e4b`, `gemma4/latest`, `gemma4/26b`, `gemma4/e2b`, `qwen3.5/9b` manifest가 있다. 이번 gate는 기존 redacted Gemma4 결과만 읽었고 Ollama를 재실행하지 않았다.

## 구현 파일

- `backend/scripts/run_naver_tampermonkey_review_import_gate.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_run_naver_tampermonkey_review_import_gate.py`
- `docs/Nutrition-docs/dev-guides/31-gemma-4-gguf-setup-guide.md`
- `docs/ocr_baseline_reports/README.md`

## 실제 실행

입력은 기존 `review-ingest-gemma4-e4b-live.jsonl`과 empty decision batch이며, 출력은 ignored local artifact로만 유지한다.

| 항목 | 값 |
| --- | ---: |
| review_row_count | 86 |
| pending_count | 86 |
| approved_row_count | 0 |
| planned_product_upsert_count | 0 |
| planned_ingredient_row_count | 0 |
| db_write_performed | false |
| raw/local forbidden scan | pass |

## 검증

- focused script tests: `33 passed`
- black check: pass
- ruff check: pass
- `git diff --check`: pass

## 다음 단계

1. 사람이 review decision JSONL을 만든다.
2. gate runner를 `--require-reviewed`로 실행해 pending row가 남으면 fail-closed 처리한다.
3. 승인 row가 생기면 approved export와 dry-run plan을 검수한다.
4. 실제 DB write는 dry-run artifact와 팀 승인 후 별도 PR로 만든다.
