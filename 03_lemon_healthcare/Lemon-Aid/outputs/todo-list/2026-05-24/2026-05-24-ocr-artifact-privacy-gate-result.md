# OCR Artifact Privacy Gate 결과

## 요약

- generated OCR/LLM JSON artifact를 재귀 검사하는 `check_ocr_artifact_privacy.py`를 추가했다.
- 기본 모드는 raw payload key와 실제 로컬 절대경로 값을 차단한다.
- `--strict-literal-keys` 모드는 review/import 계열 산출물처럼 `image_path`, `product_dir` key 자체도 없어야 하는 경우에 사용한다.
- 2026-05-24 추가 보강으로 privacy checker summary도 입력 절대경로 대신 `path_names`/`path_hashes`만 출력한다.
- macOS 임시 경로인 `/private/`도 로컬 경로 literal로 차단한다.
- 로컬 Ollama 모델 저장소는 현재 EX400U 경로를 사용하며, `backend/.env.example`에는 `OLLAMA_MODELS` shell override 키만 일반화해 추가했다.
- DB write, OCR/LLM 호출, 외부 전송은 없다.

## 구현 파일

- `backend/scripts/check_ocr_artifact_privacy.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_check_ocr_artifact_privacy.py`

## 실제 스캔 결과

Stage14 전체 generated JSON/JSONL:

| 항목 | 값 |
| --- | ---: |
| file_count | 34 |
| json_value_count | 50,501 |
| finding_count | 0 |
| passed | true |

review/import 계열 strict scan:

| 항목 | 값 |
| --- | ---: |
| file_count | 10 |
| json_value_count | 17,737 |
| finding_count | 0 |
| strict_literal_keys | true |

## 발견 및 처리

초기 strict 전체 스캔에서 source manifest의 `image_path`, `product_dir` key가 감지됐다. `image_path`는 OCR collector 입력 계약이며 값은 `$NAVER_TAMPERMONKEY_SOURCE_ROOT/...` token path라 기본 privacy leak은 아니다. 따라서 source manifest는 기본 모드로 검사하고, review/import 산출물은 strict mode로 검사하도록 gate를 분리했다.

추가 검토에서 CLI 실패 시 traceback 또는 path 기반 예외 메시지가 출력될 수 있는 review/import 보조 스크립트들을 확인했다. 다음 스크립트는 실패 시 filename, path hash, bounded error code/message만 출력하도록 보강했고, 생성된 failure summary를 privacy checker `--strict-literal-keys`로 재검사했다.

- `backend/scripts/build_naver_tampermonkey_db_labeling_staging.py`
- `backend/scripts/merge_naver_tampermonkey_ocr_observations_into_db_staging.py`
- `backend/scripts/apply_naver_tampermonkey_review_decisions.py`
- `backend/scripts/export_naver_tampermonkey_review_decision_template.py`
- `backend/scripts/run_naver_tampermonkey_review_import_gate.py`

직접 함수 호출 경로에서도 JSONL row가 object가 아닐 때 입력 JSONL 절대경로가 `ValueError` 메시지에 섞이지 않도록 다음 스크립트의 오류 메시지를 일반화했다.

- `backend/scripts/validate_naver_tampermonkey_review_decisions.py`
- `backend/scripts/dry_run_naver_tampermonkey_approved_db_import.py`
- `backend/scripts/export_naver_tampermonkey_review_pii_screening_suggestions.py`
- `backend/scripts/run_naver_tampermonkey_review_pii_screening_suggestions.py`
- `backend/scripts/apply_naver_tampermonkey_review_pii_screening_decisions.py`

Ground-truth snapshot validator도 오류 report에 입력 절대경로와 raw validation input이 섞이지 않도록 보강했다. `validate_ground_truth.py`는 이제 파일명과 `path_hash`만 출력하고, read/parse/schema 오류는 bounded error type과 validation location 중심으로 보고한다.

- `backend/scripts/validate_ground_truth.py`

3-tier OCR evaluator도 generated JSON/Markdown report에 manifest 절대경로를 저장하지 않도록 보강했다. `manifest`는 basename만 유지하고, 추적용 값은 `manifest_path_hash`로 분리한다. 입력 observation 에 `provider_payload`, `raw_provider_payload`, `request_headers`, `raw_model_response`, secret 계열 key가 있으면 평가를 중단한다.

- `backend/scripts/evaluate_ocr_three_tier.py`

## 검증

- privacy/import focused unit tests: `42 passed`
- JSONL non-object path redaction focused unit tests: `71 passed`
- ground-truth validator redaction focused unit tests: `17 passed`
- ground-truth + 3-tier evaluator focused unit tests: `27 passed`
- failure summary strict privacy probe: `file_count=4`, `finding_count=0`, `passed=true`
- black check: pass
- ruff check: pass
- detect-secrets changed files: `results={}`
- `git diff --check`: pass
