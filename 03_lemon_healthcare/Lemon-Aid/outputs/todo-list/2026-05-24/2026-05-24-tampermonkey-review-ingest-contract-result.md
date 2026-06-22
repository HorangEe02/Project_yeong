# Tampermonkey Review Ingest Contract Result

## Summary

- `naver-tampermonkey-db-labeling-with-ocr-v1`을 review UI가 바로 읽을 수 있는 `naver-tampermonkey-review-ingest-v1` JSONL로 축약하는 export 스크립트를 추가했다.
- 이 단계는 production DB import가 아니라 operator review queue 계약이다. 모든 row는 `requires_human_review=true`, `review_task.status=needs_human_review`, `review_task.db_import_ready=false`로 유지한다.
- 기존 EX400U Gemma4 live 결과 artifact를 입력으로 사용했으며, Ollama 재실행은 하지 않았다.

## Changed Files

- `backend/scripts/export_naver_tampermonkey_review_ingest.py`
  - 입력 schema `naver-tampermonkey-db-labeling-with-ocr-v1`만 허용한다.
  - 출력 schema `naver-tampermonkey-review-ingest-v1`을 생성한다.
  - raw OCR text, provider payload, request headers, model raw response, image bytes, secret key, local path literal, product directory literal key를 재귀적으로 차단한다.
  - review 이미지가 local PII screening pending 상태이면 LLM ingredient candidate 노출을 실패 처리한다.
  - UI용 필드는 category label, language targets, chronic/caution tags, hashed image refs, OCR provider summary, bounded ingredient candidates, review/import blocking reasons로 제한한다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_ingest.py`
  - safe contract export, raw field reject, local path literal reject, product_dir literal reject, PII-pending review LLM candidate 차단, PII-pending review queue 허용 테스트를 추가했다.

## Generated Local Artifacts

Ignored local artifact:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-ingest-gemma4-e4b-live.jsonl
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-ingest-gemma4-e4b-live.jsonl.summary.json
```

핵심 summary:

| Metric | Value |
| --- | ---: |
| row_count | 86 |
| review_required_rows | 86 |
| db_import_ready_rows | 0 |
| rows_with_ocr_observations | 86 |
| rows_with_llm_ingredient_candidates | 48 |
| total_ingredient_candidates | 165 |
| pii_pending_review_rows | 0 |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |
| local_path_literals_stored | false |
| clinical_recommendations_stored | false |

## Security Review

- Generated review ingest JSONL에서 forbidden raw keys와 `/private`, `/Users`, `/Volumes`, `file://` literal이 없는지 확인했다.
- `product_dir` literal key는 입력 단계에서 실패 처리한다. output에는 `product_dir_hash`만 남긴다.
- `image_path`와 같은 원본 경로 key도 입력 단계에서 실패 처리한다. output에는 `image.root_token`, `image_ref_hash`, `image_sha256`만 남긴다.
- 성분 후보는 `display_name`, `nutrient_code`, `amount`, `unit`, `confidence`, `source`, `provider`로 제한한다.
- 임상 추천으로 오용되지 않도록 `is_clinical_recommendation=false`, `clinical_recommendation_forbidden=true`를 명시했다.
- CLI 실패 summary는 traceback이나 입력/output 절대경로 대신 `input_name`, `output_name`, hashed path id, bounded `error_code`/`error_message`만 남긴다.

## Verification

```bash
PYTHONPATH=backend /private/tmp/lemon-p1-quality-venv/bin/python -m pytest \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_ingest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_merge_naver_tampermonkey_ocr_observations_into_db_staging.py \
  backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_db_labeling_staging.py \
  -q --no-cov
```

Result:

```text
18 passed in 0.04s
```

```bash
/private/tmp/lemon-p1-quality-venv/bin/python -m black --check \
  backend/scripts/export_naver_tampermonkey_review_ingest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_ingest.py

/private/tmp/lemon-p1-quality-venv/bin/python -m ruff check \
  backend/scripts/export_naver_tampermonkey_review_ingest.py \
  backend/Nutrition-backend/tests/unit/scripts/test_export_naver_tampermonkey_review_ingest.py
```

Result:

```text
black: 2 files would be left unchanged
ruff: All checks passed
CLI failure redaction probe: pass
artifact privacy gate: pass
detect-secrets scan: pass
```

## Next Steps

1. Review UI 또는 DB import job이 `naver-tampermonkey-review-ingest-v1`만 입력으로 받도록 adapter를 추가한다.
2. 사람이 승인한 row만 별도 `review-approved-db-import-v1`으로 승격하는 스크립트를 만든다.
3. review 이미지 126,526개는 local-only PII screening manifest를 먼저 만들고, 사람 검수 전 외부 OCR 전송은 계속 금지한다.
