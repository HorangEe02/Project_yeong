# Tampermonkey DB Labeling Staging 보안 보강 결과 - 2026-05-24

## 범위

- `2026-05-24-tampermonkey-folder-category-labeling-result.md`의 다음 작업 2번인 DB import staging 연결을 진행했다.
- Stage14 manifest 86 rows를 DB 라벨링 staging JSONL로 변환하는 스크립트를 추가했다.
- 코드 점검 중 tokenized image path가 symlink를 통해 source root 밖으로 resolve될 수 있는 경로 이탈 가능성을 확인하고 차단했다.

## 변경 파일

- `backend/scripts/build_naver_tampermonkey_db_labeling_staging.py`
  - folder-labeled manifest를 `naver-tampermonkey-db-labeling-staging-v1` JSONL로 변환한다.
  - `category_key`, `display_name_ko`, `display_name_en`, `language_targets=["en","ko"]`, chronic/caution tags를 DB import 후보로 유지한다.
  - `product_dir` 원문과 image path 원문은 저장하지 않고 `product_dir_hash`, `image_ref_hash`, `image_root_token`만 저장한다.
  - raw OCR text, provider payload, request headers, image bytes, raw model response, secret key 계열 필드를 reject한다.
- `backend/scripts/collect_supplement_ocr_observations.py`
  - `$NAVER_TAMPERMONKEY_SOURCE_ROOT/...` 같은 allowlisted env-token image path가 symlink를 통해 root 밖으로 나가면 실패하도록 보강했다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_db_labeling_staging.py`
  - bilingual DB label, raw field reject, local absolute path reject, review external PII clearance reject, safe summary 테스트를 추가했다.
- `backend/Nutrition-backend/tests/unit/scripts/test_collect_supplement_ocr_observations.py`
  - env-token image path의 symlink escape 차단 회귀 테스트를 추가했다.

## 생성 산출물

생성 위치:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/
```

추가 생성 파일:

- `db-labeling-staging.jsonl`
- `db-labeling-staging.summary.json`

핵심 결과:

| 항목 | 값 |
| --- | ---: |
| staging_rows | 86 |
| section | detail only |
| category_key count | 41 |
| review_rows | 0 |
| external_allowed_rows | 86 |
| product_dir_literals_stored | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |
| raw_model_response_stored | false |

## 보안/유출 점검

- DB staging에는 외장 디스크 절대경로(`/Volumes/...`)를 저장하지 않는다.
- DB staging에는 product directory 원문 또는 image path 원문을 저장하지 않는다.
- raw OCR text, provider raw payload, request headers, image bytes, Ollama raw response, `.env`, secret 값은 저장하지 않는다.
- review row가 `contains_personal_data=false`로 명시 검수되지 않은 상태에서 external transfer로 staging되면 실패한다.
- env-token image path는 allowlist env var만 허용하고, symlink resolve 결과가 image root 밖이면 실패한다.

검증:

```text
focused script tests: 47 passed
black --check: pass
ruff --ignore RUF001: pass
generated artifact privacy scan: ocr_artifact_privacy_ok files=5
git diff --check: pass
```

## 남은 작업

1. `db-labeling-staging.jsonl`을 실제 DB import job 또는 review UI ingest contract에 연결한다.
2. PaddleOCR + local Ollama Gemma4 실행 결과의 `llm_parsed_ingredients`를 DB staging에 병합할 별도 opt-in 스크립트를 추가한다.
3. review 이미지 126,526개는 local-only PII screening staging을 먼저 만들고, 사람 검수 전 외부 OCR 전송은 계속 금지한다.
