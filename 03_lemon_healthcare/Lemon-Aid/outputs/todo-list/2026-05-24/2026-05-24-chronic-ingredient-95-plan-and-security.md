# Chronic Ingredient Exact 95% 복구 계획 및 보안 점검 - 2026-05-24

## 공식 문서 확인

- PaddleOCR General OCR Pipeline Usage Tutorial: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR PP-StructureV3 Pipeline Usage Tutorial: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html
- Ollama API Introduction: https://docs.ollama.com/api/introduction
- Ollama Chat API: https://docs.ollama.com/api/chat
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Pydantic Models / validating data: https://docs.pydantic.dev/latest/concepts/models/
- Pydantic `model_validate_json` API: https://docs.pydantic.dev/latest/api/base_model/#pydantic.main.BaseModel.model_validate_json
- Python subprocess `env` 동작: https://docs.python.org/3/library/subprocess.html#subprocess.run
- OWASP Cross Site Scripting Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- Pillow Image module: https://pillow.readthedocs.io/en/stable/reference/Image.html
- Pillow ImageOps module: https://pillow.readthedocs.io/en/stable/reference/ImageOps.html
- Pillow ImageStat module: https://pillow.readthedocs.io/en/stable/reference/ImageStat.html

문서 기준 판단:

1. PaddleOCR 일반 OCR은 detection, recognition, orientation 계열 모듈로 구성된다. 95% 미달 원인이 인식 누락인지, 표 레이아웃 해석인지, expected 라벨 품질인지 분리해야 한다.
2. PP-StructureV3는 table recognition, layout region detection, reading order 복원에 초점이 있으므로 표 형태 성분표가 주 원인이면 fine-tune보다 먼저 PoC 대상으로 둔다.
3. Ollama는 기본 로컬 API가 `http://localhost:11434/api`이고 Chat API와 structured output schema를 지원한다. OCR 원문은 artifact에 저장하지 않고 메모리 안에서만 `/api/chat` 호출 입력으로 사용한다.
4. Python `subprocess.run(env=...)`는 지정한 mapping이 child process 환경으로 쓰인다. provider runner는 부모 환경 전체를 넘기면 불필요한 secret 전파 위험이 있으므로 allowlist 방식으로 제한한다.
5. Pydantic V2는 JSON 입력을 `model_validate_json()`으로 schema 검증할 수 있다. Ollama 응답은 raw model response로 저장하지 않고 메모리 안에서 허용 필드만 정규화한 뒤 다시 JSON-mode validation을 통과한 구조만 artifact에 기록한다.
6. Pillow `Image`/`ImageOps`/`ImageStat`는 이미지 decode, EXIF 방향 보정, grayscale 통계 산출을 지원한다. 잔여 OCR 저신뢰 fixture는 raw image나 local path를 저장하지 않고 width/height, 밝기, 대비 bucket만 산출해 전처리 후보와 모델 비교 후보를 나눈다.
7. OWASP XSS Prevention Cheat Sheet는 브라우저 출력 context에 맞춘 output encoding을 핵심 방어로 둔다. DB import 전 검수 문자열 gate는 최종 UI escaping을 대체하지 않지만, HTML tag, script protocol, URL-like 값이 reference label로 저장되는 경로를 줄이는 defense-in-depth로 둔다.

## 현재 기준선

재계산 입력:

- `outputs/generated/ocr-eval/2026-05-24-current-ingredient-rate-paddle-rerun/manifest-with-observations.jsonl`

재계산 결과:

| 항목 | 값 |
| --- | ---: |
| fixture_count | 16 |
| observation_count | 16 |
| text_non_empty_rate | 0.875 |
| parser_success_rate | 0.5625 |
| legacy ingredient_name_exact_rate | 0.5 |
| scoreable_ingredient_name_exact_rate | 1.0 |
| scoreable_fixture_count | 3 |
| scoreable ingredient denominator | 5 |
| errors | 2 |
| raw_artifacts_stored | false |
| raw_ocr_text_stored | false |

판단:

- `scoreable_ingredient_name_exact_rate=1.0`은 좋은 신호지만, scoreable 분모가 5개 성분/3개 fixture라서 공식 95% KPI로 쓰기에는 부족하다.
- 16개 fixture 모두 provisional expected를 포함하므로 human verification 없이는 공식 성공 선언을 하지 않는다.
- 현재 학습보다 먼저 verified expected 확정, parser/error 진단, local Gemma4 구조화 파서 연결 안정화가 필요하다.

## 실행 계획

### 1. 16개 fixture human-verified expected 확정

목표:

- `naver-chronic-0001`부터 `naver-chronic-0016`까지 V3 expected snapshot의 `ingredients[].display_name` 또는 `normalized_name`을 사람이 검수한 값으로 확정한다.
- `verification_status`는 `verified` 또는 기존 validator가 human-labeled로 인정하는 값으로 맞춘다.
- `ground_truth_pending_human_review`, `auto_expected_requires_human_verification` 경고는 검수 완료 row에서 제거한다.

보안 기준:

- raw OCR text, provider payload, image bytes, request headers, secret 값은 expected snapshot에 넣지 않는다.
- fixture image local path는 보고서에 평문 저장하지 않고 파일명 또는 hash로만 다룬다.

완료 증거:

- `test_ground_truth_tools.py` 통과
- `validate_ground_truth.py` 또는 동등 validator에서 chronic 16개 V3 human-labeled count가 16으로 출력
- `expected_quality_warnings`에서 human-review pending 계열 warning이 0

구현된 검수 템플릿:

- `backend/scripts/export_chronic_ingredient_review_template.py`
- V3 snapshot 16개를 사람이 검수할 JSONL 템플릿으로 내보낸다.
- 템플릿은 importable decision batch가 아니며 `requires_human_review=true`를 유지한다.
- `naver-chronic-NNNN` expected와 `naver-live-NNNN` observation id를 고정 매핑한다.
- 현재 expected ingredient와 redacted structured observation hints만 포함하고, raw OCR text, provider payload, image bytes, request headers, local path, free-text notes는 포함하지 않는다.
- 현재 실행 결과: 16 rows, pending 16, current expected hint 보유 7 rows, observation hint 보유 5 rows.

구현된 검수 반영 gate:

- `backend/scripts/apply_chronic_ingredient_review_decisions.py`
- `chronic-ingredient-review-decision-v1` JSONL만 입력으로 허용하고, 템플릿 row를 그대로 import하려는 시도는 실패 처리한다.
- 원본 expected directory를 직접 수정하지 않고 별도 output directory에 V3 snapshot copy를 생성한다.
- `verified` decision만 `ingredients[].source=manual`, `confidence=1.0`으로 반영하고 `ground_truth_pending_human_review`, `auto_expected_requires_human_verification` warning을 제거한다.
- `needs_changes`, `not_scoreable` decision은 pending warning을 유지하므로 scoreable KPI denominator에 들어가지 않는다.
- `reviewer_id`는 `operator_*` 형식만 허용하며 `ollama_gemma4` 같은 model-only reviewer id는 거부한다.
- verified decision은 `human_verified_from_local_fixture`, `no_raw_ocr_text_copied`, `no_provider_payload_copied`, `no_secret_or_local_path_copied` attestation이 모두 true여야 한다.
- raw OCR text, provider payload, raw model response, image bytes, request headers, free-text notes, local path literal, secret-like key는 recursive gate에서 거부한다.
- output snapshot은 `SupplementParsedSnapshotV3.model_validate`로 검증한 뒤에만 write 대상이 된다.

### 2. parser_success_rate 0.5625와 errors 2/16 원인 조사

현재 관측:

- status: completed 14, error 2
- parser_success: true 9, false 7
- error_code: `ocr_low_confidence` 1, `ocr_empty_text` 1
- completed row warning: `layout_unavailable`, `review_pii_screening_required`

이번 PR 보강:

- `evaluate_ocr_three_tier.py` provider metric에 bounded diagnostic counters를 추가한다.
- 추가 metric:
  - `status_counts`
  - `error_code_counts`
  - `warning_code_counts`
  - `pii_screening_status_counts`
  - `llm_parse_status_counts`
  - `llm_parse_error_code_counts`
- 모든 diagnostic token은 짧은 identifier 형태만 허용하고, path처럼 보이는 값은 `unsafe_token`으로 치환한다.

완료 증거:

- 재평가 JSON/MD에서 원인별 count를 raw text 없이 확인 가능
- privacy scanner finding 0

### 3. Ollama/Gemma4 parser를 메모리 내에서만 연결

목표:

- PaddleOCR 결과의 raw text는 observation artifact에 저장하지 않는다.
- collector runtime memory 안에서만 `OllamaSupplementParser`에 넘기고, 저장되는 값은 bounded structured fields만 허용한다.
- 사용 모델은 operator-only EX400U Ollama model root로 띄운 local Ollama의 `gemma4:e4b`를 우선 사용한다. 로컬 절대 경로는 repo artifact에 평문 저장하지 않는다.

이번 PR 보강:

- `run_naver_tampermonkey_ocr_eval.py`가 collector subprocess에 `os.environ.copy()`를 넘기지 않도록 수정한다.
- child env allowlist:
  - 실행 필수 기본 키: `PATH`, `HOME`, locale, temp, certificate bundle
  - OCR/LLM operator 키: `ENABLE_LOCAL_OCR`, `RUN_PADDLEOCR_PROBE`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SEC`, CLOVA/Google opt-in 키 등
  - manifest에서 실제 참조한 allowlisted image root 키만 전달
- `UNRELATED_SECRET_TOKEN` 같은 부모 환경 secret은 child로 전달하지 않는다.

완료 증거:

- unit test에서 unrelated secret 미전달 확인
- child output capture 유지
- dry-run/redacted summary에 `.env`, secret, local path 미노출

### 4. verified 16개 기준으로 95% 유지 여부 확인

명령 흐름:

1. verified V3 expected manifest 생성
2. PaddleOCR local + `--llm-parse` 재수집
3. `evaluate_ocr_three_tier.py` 재실행
4. `scoreable_fixture_count=16` 확인
5. `scoreable_ingredient_name_exact_rate >= 0.95` 확인

판단 기준:

- `scoreable_fixture_count < 16`: 라벨링 미완료. 학습 금지.
- `scoreable_fixture_count = 16`이고 `scoreable_ingredient_name_exact_rate >= 0.95`: 학습 불필요. parser/labeling pipeline 안정화로 진행.
- `scoreable_fixture_count = 16`이고 `scoreable_ingredient_name_exact_rate < 0.95`: failure bucket을 나눈 뒤 PP-StructureV3 또는 model fine-tune 검토.

구현된 gate:

```bash
PYTHONPATH=backend:backend/Nutrition-backend python backend/scripts/evaluate_ocr_three_tier.py \
  --manifest <redacted-manifest-with-observations.jsonl> \
  --output-dir <redacted-output-dir> \
  --kpi-provider paddleocr_local \
  --require-scoreable-fixtures 16 \
  --require-no-provisional \
  --min-scoreable-ingredient-rate 0.95
```

이 gate는 summary에 `kpi_gate`를 기록하고 실패 시 exit code 1로 종료한다. 현재 provisional 16개 상태에서는 `scoreable_fixture_count_below_required`, `provisional_fixture_count_nonzero`가 나와야 정상이다.

### 5. 95% 미만일 때만 PaddleOCR/레이아웃/모델 fine-tune 검토

분기:

| 실패 원인 | 우선 조치 |
| --- | --- |
| OCR text empty 또는 low confidence | image quality/preprocess, PP-OCRv5 server model 비교 |
| OCR text는 있으나 표 셀 순서/열 해석 실패 | PP-StructureV3 table/layout PoC |
| 텍스트는 있으나 성분 alias/compound name mismatch | alias dictionary, expected compound split, Gemma4 parser prompt/schema 축소 |
| 동일 성분이 반복적으로 recognition 실패 | PaddleOCR recognition fine-tune 후보 |

fine-tune 착수 조건:

- human-verified 16개 또는 확장 fixture set에서 동일 recognition miss가 반복됨
- PP-StructureV3/layout parser 및 alias 보정으로도 95% 미달
- 학습 데이터는 human-verified transcript만 사용

## EX400U Tampermonkey/Naver 확장 fixture 테스트

운영 기준:

- 기존 16개 chronic fixture는 parser/expected 품질을 분리하기 위한 legacy
  diagnostic set으로만 남긴다.
- 현재 OCR/DB-labeling 테스트 기준은 EX400U Tampermonkey/Naver folder-name
  labeled manifest 120개와 공식 source URL 기반 category taxonomy fixture다.
- ingredient exact 95% KPI는 human-verified expected가 있는 별도 fixture에서만
  사용하고, EX400U 120개는 coverage, parser, review/import-readiness KPI로 평가한다.

사용자 요청에 따라 기존 16개 chronic fixture 대신 operator-provided EX400U
Tampermonkey/Naver source root의 folder-name labeled fixture를 사용했다.
웹 근거 taxonomy는 `ocr_fixture_chronic_supplement_categories.json`에 기록된
공식 source URL 기반 category mapping을 사용했다.

검증 결과:

- 120개 detail manifest 생성: candidate 130303, category label 43, unmapped category 0
- generated manifest/inventory/category-label artifact privacy scan: finding 0
- 43개 category-balanced OCR-only 평가: completed 36/43, text non-empty 0.8372, parser success 0.8372, error `ocr_low_confidence` 7
- 43개 DB labeling staging 생성: row 43, review row 0, external allowed row 43, product_dir literal 저장 false
- 43개 staging + OCR observation merge: matched observation 43, completed 36, error 7, unmatched 0
- EX400U Ollama model root에서 `gemma4:e4b` 존재 확인
- 8개 Gemma4 smoke 평가: completed 0.875, LLM parse attempt 7, LLM parse success 1.0, avg structured ingredient count 2.7143, error `ocr_low_confidence` 1
- batch-001 Gemma4 재평가: sandbox 내부 Python `httpx`는 local Ollama 접속이 제한되어 `ollama_client`로 실패했으나, sandbox 밖 재실행에서 completed 0.875, LLM parse attempt 7, LLM parse success 1.0, avg structured ingredient count 2.7143, error `ocr_low_confidence` 1을 확인했다.
- 120개 full batch OCR+Gemma4 평가: batch 15/15 completed, observation 120, completed 107, error 13, text non-empty 0.8917, parser success 0.8917, LLM parse attempt 107, LLM parse success 0.9533, avg structured ingredient count 2.9706, error `ocr_low_confidence` 13, LLM error `ollama_structured_output` 5
- 기존 120개 단일 full OCR+Gemma4 평가는 fixture별 structured output 호출 시간이 길어 중단했으나, batch runner 도입 후 15개 batch 전체 실행을 완료했다.

구현된 batch 실행 보강:

- `backend/scripts/split_naver_tampermonkey_manifest_batches.py`
- redacted Tampermonkey manifest를 작은 JSONL batch로 나눠 기존 OCR runner의 `--resume` 재시도 단위로 사용한다.
- summary에는 batch 파일명, row count, section/category count, path hash만 기록한다.
- raw OCR text, provider payload, raw model response, image bytes, request headers, local path literal은 recursive gate에서 거부한다.
- 이 보강으로 120개 full OCR+Gemma4는 batch 단위로 나누어 실패/timeout fixture만 재개할 수 있다.

구현된 batch orchestration 보강:

- `backend/scripts/run_naver_tampermonkey_batch_ocr_eval.py`
- splitter가 만든 batch JSONL을 읽어 기존 `run_naver_tampermonkey_ocr_eval.py`를 batch별 subprocess로 순차 실행한다.
- batch별 stdout/stderr는 캡처만 하고 저장하지 않으며, summary에는 batch name, path hash, return code, provider run count만 기록한다.
- child env는 allowlist로 제한하고 manifest에서 실제 참조한 image-root env만 전달한다.
- 실패 batch는 `--continue-on-error` 여부에 따라 중단 또는 계속 진행하며, `--resume`으로 완료 batch를 재사용한다.
- 실제 120개 batch directory dry-run 결과: planned batch 15, first `ex400u-detail-batch-001.jsonl`, last `ex400u-detail-batch-015.jsonl`, privacy scan finding 0.

구현된 OCR failure review 보강:

- `backend/scripts/export_naver_tampermonkey_ocr_failure_review_template.py`
- batch manifest와 batch observation을 fixture id로 조인해 실패 검수 큐를 생성한다.
- review row에는 fixture id, batch name, provider, section, category key, failure kind, bounded error code, suggested next action만 기록한다.
- raw OCR text, provider payload, raw model response, image bytes, request headers, local path literal은 recursive gate에서 거부한다.
- 실제 full batch 결과에서 review row 18개 생성: `ocr_error` 13, `llm_parse_error` 5, missing category 0, strict privacy scan finding 0.
- suggested action: `inspect_image_quality_or_preprocess` 13, `retry_structured_parser_or_schema_prompt` 5.

구현된 retry manifest 보강:

- `backend/scripts/export_naver_tampermonkey_ocr_retry_manifest.py`
- failure review queue와 원본 batch manifest를 fixture id로 조인해 collector-compatible retry manifest를 생성한다.
- OCR 재시도와 LLM 구조화 재시도를 `failure_kind`로 분리할 수 있다.
- retry row에는 원본 manifest metadata와 bounded `retry_metadata`만 붙이고, raw OCR text, provider payload, raw model response, image bytes, request headers, local path literal은 recursive gate에서 거부한다.
- 실제 full batch failure queue에서 OCR low confidence retry manifest 13 rows, LLM structured-output retry manifest 5 rows를 생성했다.
- retry manifest는 collector 입력으로 다시 쓰기 위해 `image_path` token key가 필요하므로 strict literal-key scan 대상이 아니다.
- 전체 retry manifest directory는 non-strict privacy scan finding 0으로 raw/local-path value 미저장을 확인했고, 공개 가능한 summary JSON 2개는 strict literal-key scan finding 0으로 확인했다.

판단:

- folder-name category labeling과 웹 근거 taxonomy mapping은 현재 43개 category 전체에서 매핑 누락 없이 동작한다.
- 120개 full batch 기준에서 OCR 실패 13개는 `ocr_low_confidence`로 분리되며, raw OCR text 저장 없이 report와 review queue에서 확인 가능하다.
- Gemma4 parser 연결은 EX400U 모델 경로 기준 smoke와 batch-001 sandbox 밖 재실행에서 정상 동작했다.
- Gemma4 parser는 full batch에서 102/107 성공했으며, 남은 5개는 `ollama_structured_output`으로 분리되어 prompt/schema retry 보강 후보가 되었다.
- retry manifest 기준 다음 실행 단위는 OCR 저신뢰 13건의 image quality/preprocess 또는 Paddle 설정 비교, LLM 구조화 실패 5건의 prompt/schema retry이다.
- 이 확장 fixture set은 human-verified ingredient exact KPI가 아니라 OCR/DB-labeling coverage KPI로 봐야 한다. ingredient exact 95% 판단은 별도 human-verified expected가 붙은 fixture에서만 수행한다.

추가 retry 실행 결과:

- OCR low-confidence 13건 textline orientation ON 재실행: completed 0, error 13, error `ocr_low_confidence` 13.
- OCR low-confidence 13건 textline orientation ON + diagnostic threshold 0.60 재실행: completed 9, error 4, text non-empty 0.6923, parser success 0.6923, LLM parse success 1.0.
- LLM structured-output 5건 기존 schema 재실행: completed 5, OCR parser success 1.0, LLM parse success 0.0, error `ollama_structured_output` 5.
- LLM structured-output 5건 schema-safe normalization 적용 후 재실행: completed 5, LLM parse success 1.0, parsed ingredient counts `[5, 9, 2, 7, 4]`.
- 새 LLM parser normalization은 raw model response를 저장하지 않고, common alias, code-fenced JSON, optional numeric/string bounds, hallucinated `nutrient_code` discard, fixed `source=ollama_structured`, invalid/missing confidence `0.0` sentinel만 적용한다.
- retry 산출물 privacy scan: 전체 retry output non-strict finding 0, report JSON strict literal-key finding 0.
- 판단: LLM 구조화 실패 5건은 parser normalization으로 해소됐다. OCR 13건 중 9건은 threshold 진단상 OCR text는 존재하므로 human review 또는 confidence policy 분기 대상이고, 남은 4건은 image quality/preprocess, PP-OCRv5 server model, PP-StructureV3 후보로 남는다.

구현된 retry observation reconcile 보강:

- `backend/scripts/reconcile_naver_tampermonkey_ocr_observations.py`
- base batch observation과 retry observation을 `fixture_id/provider`별로 1개 대표 row로 병합한다.
- 선택 기준은 `completed` > `error` > `not_run`, LLM completed, parser success, text non-empty, ingredient count, 입력 순서 순이다.
- 이 단계가 없으면 evaluator가 base와 retry를 중복 호출로 합산하므로 120개 기준 coverage를 정확히 볼 수 없다.
- 실제 base 120 + LLM retry 5 + OCR retry 13 reconcile 결과: input observation 138, duplicate group 18, output observation 120, completed 116, error 4, LLM completed 116.
- reconciled 120개 평가 결과: fixture 120, observation 120, completed rate 0.9667, text non-empty rate 0.9667, parser success rate 0.9667, LLM parse success rate 1.0, ingredient count avg 3.0603, remaining error `ocr_low_confidence` 4.
- 120개 DB-labeling staging 생성 및 reconciled observation merge 결과: staging row 120, matched observation 120, rows with OCR observations 120, rows with LLM ingredients 111, unmatched 0.
- reconciled output directory privacy scan finding 0, summary/report strict literal-key scan finding 0.

구현된 image quality diagnostic 보강:

- `backend/scripts/export_naver_tampermonkey_ocr_image_quality_diagnostics.py`
- manifest의 tokenized image path를 런타임 env에서만 해석하고, 출력 artifact에는 `image_path`, `product_dir`, local absolute path를 저장하지 않는다.
- Pillow `ImageOps.exif_transpose`, grayscale 변환, `ImageStat` 기반 brightness/contrast 통계로 bounded bucket을 만든다.
- output row에는 fixture id, provider, category key, image sha256, dimension, megapixel/aspect/brightness/contrast bucket, suggested preprocess action만 기록한다.
- raw OCR text, provider payload, raw model response, image bytes, request headers, local path literal은 input/output recursive gate에서 거부한다.
- 실제 reconciled 120개 결과의 잔여 `ocr_low_confidence` 4건 진단 결과: diagnostic row 4, decode error 0, strict privacy scan finding 0.
- bucket 분리:
  - `naver-tm-detail-000007`: saw_palmetto, brightness normal, contrast high, squareish, small, `try_ppocrv5_server_or_layout_model`
  - `naver-tm-detail-000030`: omega_3, brightness bright, contrast normal, squareish, small, `try_glare_or_overexposure_review`
  - `naver-tm-detail-000050`: saw_palmetto, brightness normal, contrast normal, squareish, small, `try_ppocrv5_server_or_layout_model`
  - `naver-tm-detail-000112`: zinc, brightness bright, contrast low, squareish, small, `try_glare_or_overexposure_review`, `try_contrast_autocontrast`
- 판단: 2건은 이미지 품질 bucket만으로는 설명되지 않아 PP-OCRv5 server 또는 layout model 비교 후보이고, 2건은 glare/contrast 전처리 후보이다.

구현된 local OCR 전처리 opt-in 보강:

- `LOCAL_OCR_PREPROCESS_MODE`를 추가했다. 기본값은 `none`이며 기존 PaddleOCR 입력 바이트를 변경하지 않는다.
- 허용 mode:
  - `none`: 기존 동작 유지
  - `autocontrast`: EXIF 방향 보정 후 RGB autocontrast 적용, temp PNG로만 전달
  - `grayscale_autocontrast`: EXIF 방향 보정 후 grayscale autocontrast 적용, temp PNG로만 전달
- 전처리 이미지는 PaddleOCR adapter의 `TemporaryDirectory` 안에서만 사용하고 artifact로 저장하지 않는다.
- runner/collector child env allowlist에 `LOCAL_OCR_PREPROCESS_MODE`만 추가했으며, unrelated parent secret 미전파 정책은 유지했다.
- 실제 잔여 `ocr_low_confidence` 4건에 대해 `LOCAL_OCR_USE_TEXTLINE_ORIENTATION=true`, `LOCAL_OCR_CONFIDENCE_THRESHOLD=0.60` 조건에서 비교했다.
- 결과:
  - `autocontrast`: call 4, completed 0, error `ocr_low_confidence` 4
  - `grayscale_autocontrast`: call 4, completed 1, error `ocr_low_confidence` 3, 복구 fixture `naver-tm-detail-000030`
- privacy scan:
  - 두 retry output directory non-strict finding 0
  - 공개 가능한 report JSON strict literal-key finding 0
- 판단: 과노출 계열 중 1건은 grayscale autocontrast로 복구 가능하다. 남은 3건(`naver-tm-detail-000007`, `naver-tm-detail-000050`, `naver-tm-detail-000112`)은 동일 전처리로 해결되지 않으므로 PP-OCRv5 server model 또는 layout/region 분리 비교 후보로 남긴다.

구현된 PaddleOCR model profile 비교 보강:

- `LOCAL_OCR_MODEL_PROFILE`을 추가했다. 기본값은 `mobile`이며 기존 PP-OCRv5 mobile detection + language-specific mobile recognition 동작을 유지한다.
- 허용 profile:
  - `mobile`: 기존 `PP-OCRv5_mobile_det` + `korean_PP-OCRv5_mobile_rec`
  - `server_detection`: `PP-OCRv5_server_det` + `korean_PP-OCRv5_mobile_rec`
  - `server`: `PP-OCRv5_server_det` + `PP-OCRv5_server_rec`
- 공식 PaddleOCR 문서상 PP-OCRv5 server detection은 higher accuracy 후보이고, 한국어 recognition은 `korean_PP-OCRv5_mobile_rec`가 별도 모델로 제공되므로 한국어 라벨 비교의 1차 후보는 `server_detection`으로 제한했다.
- predictor cache key에 model profile을 포함해 mobile/server 비교가 같은 predictor를 재사용하지 않게 했다.
- runner/collector child env allowlist에 `LOCAL_OCR_MODEL_PROFILE`만 추가했고, unrelated parent secret 미전파 정책은 유지했다.
- 실제 잔여 `ocr_low_confidence` 4건에 대해 `LOCAL_OCR_MODEL_PROFILE=server_detection`, `LOCAL_OCR_USE_TEXTLINE_ORIENTATION=true`, `LOCAL_OCR_CONFIDENCE_THRESHOLD=0.60`, `OLLAMA_MODEL=gemma4:e4b` 조건으로 sandbox 밖 Python collector 재실행을 수행했다.
- 결과: call 4, completed 2, error 2, text non-empty 0.5, parser success 0.5, LLM parse success 1.0, avg structured ingredient count 3.5.
- 복구 fixture: `naver-tm-detail-000030`, `naver-tm-detail-000050`.
- 잔여 실패 fixture: `naver-tm-detail-000007`, `naver-tm-detail-000112`, error `ocr_low_confidence`.
- retry output directory non-strict privacy scan finding 0, 공개 가능한 report JSON/MD strict literal-key scan finding 0.

최신 120개 EX400U reconciled 평가:

- base batch 120 + LLM sanitized-schema retry 5 + OCR threshold retry 13 + grayscale retry 4 + server-detection retry 4를 fixture/provider 단위로 reconcile했다.
- source label이 긴 retry 경로에서 120자 token 제한에 걸리는 버그를 발견해, local path를 저장하지 않는 hash 기반 source label fallback을 추가했다.
- reconcile 결과: input file 19, input observation 146, duplicate group 18, output observation 120, status completed 118, error 2, LLM completed 118.
- 평가 결과: fixture 120, observation 120, completed rate 0.9833, text non-empty rate 0.9833, parser success rate 0.9833, LLM parse success rate 1.0, ingredient count avg 3.0678, remaining error `ocr_low_confidence` 2.
- 잔여 실패 fixture는 `naver-tm-detail-000007`, `naver-tm-detail-000112`이며, 다음 후보는 PP-StructureV3/layout 분리 또는 human review 대상이다.
- reconciled output directory privacy scan finding 0, 공개 가능한 summary/report strict literal-key scan finding 0.

구현된 reconciled failure retry manifest 보강:

- `backend/scripts/export_naver_tampermonkey_reconciled_failure_retry_manifest.py`
- source manifest와 reconciled observation JSONL을 fixture id로 조인해, 현재 남은 실패만 collector-compatible retry manifest로 내보낸다.
- base failure review queue가 아니라 retry 이후 최종 reconciled output을 기준으로 하므로 재실험 대상이 중복되지 않는다.
- `ocr_error`, `llm_parse_error`, `all` failure kind filter를 지원한다.
- raw OCR text, provider payload, raw model response, image bytes, request headers, local path literal은 input/output recursive gate에서 거부한다.
- 실제 최신 120개 reconciled 결과에서 남은 OCR error 2건만 retry manifest로 추출했다: `saw_palmetto` 1, `zinc` 1, error `ocr_low_confidence` 2, skipped missing fixture 0.

추가 model/preprocess 비교 결과:

- `LOCAL_OCR_MODEL_PROFILE=server`, `LOCAL_OCR_USE_TEXTLINE_ORIENTATION=true`, `LOCAL_OCR_CONFIDENCE_THRESHOLD=0.60`, preprocess `none`: call 2, completed 0, error `ocr_low_confidence` 2.
- 동일 server profile + `LOCAL_OCR_PREPROCESS_MODE=grayscale_autocontrast`: call 2, completed 0, error `ocr_low_confidence` 2.
- 두 retry output directory 및 retry manifest directory privacy scan finding 0.
- 공개 가능한 report JSON/MD 및 retry summary JSON strict literal-key scan finding 0.
- `paddleocr.PPStructureV3` import는 현재 OCR venv에서 가능함을 확인했다. 공식 문서상 PP-StructureV3는 layout region detection, table recognition, reading order recovery를 포함하므로, 남은 2건은 일반 OCR model/preprocess retry가 아니라 PP-StructureV3/layout PoC 또는 human review로 넘기는 것이 맞다.

구현된 PP-StructureV3 redacted layout probe 보강:

- `backend/scripts/run_naver_tampermonkey_ppstructure_probe.py`
- 공식 문서의 `PPStructureV3().predict(...)` 통합 경로를 사용하되, 예제처럼 raw JSON/Markdown/table HTML을 저장하지 않고 layout/table/OCR count만 기록한다.
- probe output row에는 fixture id, category key, image hash, layout box count, layout label count, table/text/figure region count, overall OCR detection/text count, bounded layout score만 저장한다.
- raw OCR text, Markdown, table HTML, provider payload, raw model response, image bytes, request headers, local path literal은 input/output recursive gate에서 거부한다.
- 테스트 fixture는 fake PP-StructureV3 result에 raw text와 table HTML이 들어 있어도 output에 저장되지 않는지 검증한다.
- 실제 잔여 `ocr_low_confidence` 2건에 대해 `--use-textline-orientation`으로 sandbox 밖 probe를 실행했다.
- 결과: probe row 2, status completed 2, category `saw_palmetto` 1, `zinc` 1, layout label `image` 2, table region 0, text region 0, figure region 2.
- 세부 count: `naver-tm-detail-000007`은 overall OCR detection/text count 81, `naver-tm-detail-000112`는 24였지만 layout은 둘 다 `image` 1개로만 분류됐다.
- 해석: PP-StructureV3가 텍스트 후보 자체는 내부 OCR count로 보지만, 영양성분표를 독립 table/text layout region으로 분리하지 못했다. 따라서 남은 2건은 일반 OCR/preprocess/server profile 추가 반복보다 ROI crop, 상세 이미지 영역 분할, human review label 보강 후보로 돌리는 것이 합리적이다.
- privacy scan: probe output directory non-strict finding 0, summary/JSONL strict literal-key finding 0.

구현된 ROI crop retry 보강:

- `backend/scripts/run_naver_tampermonkey_roi_crop_ocr_eval.py`
- 원본 fixture 이미지를 런타임에서만 열고, `TemporaryDirectory` 안에 crop PNG를 만든 뒤 기존 redacted collector에 넘긴다.
- 최종 산출물에는 crop image, temp manifest, raw OCR text, raw model response를 저장하지 않고 `roi_crop_profile`, crop hash, crop dimension, provider status, bounded LLM parsed ingredient count만 남긴다.
- 기본 profile은 `full_x2`, `full_x2_gray`, `top_half_x2_gray`, `middle_half_x2_gray`, `bottom_half_x2_gray`, `center_80_x2_gray` 6개다.
- `server_detection` + 2x crop 조합은 PaddleOCR native runtime이 JSON summary 없이 종료되어, 운영 기본값으로 두지 않고 mobile profile에서 ROI 효과를 확인했다.
- 실제 잔여 `ocr_low_confidence` 2건에 대해 mobile profile + 기본 6개 crop을 실행했다: crop observation 12, completed 5, error 7, source fixture with completed crop 1.
- Gemma4 parse 포함 재실행 결과: LLM parse completed 5, `naver-tm-detail-000007`은 `middle_half_x2_gray`가 최종 reconcile에서 선택됐고 ingredient count 3으로 구조화됐다.
- `naver-tm-detail-000112`는 모든 crop profile에서 계속 `ocr_low_confidence`로 남았다.
- ROI crop 결과를 기존 120개 reconciled observation에 병합한 최신 평가: fixture 120, observation 120, completed 119, error 1, text non-empty rate 0.9917, parser success rate 0.9917, LLM parse success rate 1.0, remaining error `ocr_low_confidence` 1.
- ROI 이후 남은 retry manifest는 1 row이며 category는 `zinc`, suggested action은 `inspect_image_quality_or_layout_model`이다.
- privacy scan: ROI crop output directory non-strict finding 0, ROI summary/JSONL strict literal-key finding 0, ROI reconciled output directory finding 0, 공개 가능한 summary/report strict literal-key finding 0.

최신 DB labeling/review queue 반영:

- ROI crop 병합 후 최신 120개 observation을 DB-labeling staging에 다시 병합했다.
- DB-labeling staging 결과: staging row 120, matched observation 120, status completed 119/error 1, rows with OCR observations 120, rows with LLM ingredients 114, unmatched observation 0.
- review ingest 결과: row 120, review required 120, DB import ready 0, rows with LLM ingredient candidates 114, total ingredient candidates 362.
- review decision template 결과: row 120, rows with candidate hints 114, total candidate hints 334, decision batch importable false.
- candidate hint가 없는 human-review row는 6개다: `naver-tm-detail-000015` vitamin_a, `naver-tm-detail-000064` melatonin_sleep, `naver-tm-detail-000065` ashwagandha_stress, `naver-tm-detail-000076` iron, `naver-tm-detail-000091` joint_msm_chondroitin, `naver-tm-detail-000112` zinc.
- `naver-tm-detail-000112`는 최신 OCR retry에서도 error로 남은 유일한 fixture이므로, 다음 작업은 해당 원본 이미지를 사람이 확인해 manual ingredient entry 또는 fixture 제외 여부를 결정하는 것이다.
- DB staging, merged staging, review ingest, review decision template artifact privacy scan finding 0.
- 공개 가능한 summary JSON 4종 strict literal-key scan finding 0.

구현된 manual-review gap queue 보강:

- `backend/scripts/export_naver_tampermonkey_manual_review_gap_queue.py`
- review ingest 120개 중 ingredient candidate가 없거나 OCR error가 남은 row만 operator triage queue로 분리한다.
- output은 importable decision batch가 아니며 DB write를 수행하지 않는다.
- 실제 결과: input row 120, gap row 6, reason `ingredient_candidate_count_zero` 6, `llm_zero_ingredient_candidates` 5, `ocr_provider_error` 1.
- gap category: vitamin_a 1, melatonin_sleep 1, ashwagandha_stress 1, iron 1, joint_msm_chondroitin 1, zinc 1.
- operator action: 5건은 `review_ocr_summary_and_enter_manual_ingredients`, 1건은 `inspect_source_image_and_enter_manual_ingredients`.
- gap queue privacy scan finding 0, gap queue summary/JSONL strict literal-key scan finding 0.

구현된 manual-review gap decision template 보강:

- `backend/scripts/export_naver_tampermonkey_review_decision_template.py --gap-queue`
- 기존 120개 review decision template exporter에 gap queue filter를 추가해 수동 검수 gap row만 decision template로 내보낸다.
- gap context에는 bounded reason/action/count만 포함하고 raw OCR text, provider payload, model response, image bytes, local path literal은 포함하지 않는다.
- 각 row에는 사람이 decision JSONL을 작성할 때 복사할 수 있는 `decision_entry_template` skeleton을 포함한다.
- skeleton은 `review_decision` 값을 top-level에 두지 않고 null/false placeholder를 사용하므로 그대로 import하면 실패한다.
- approved ingredient skeleton의 `source`는 `human_reviewed`로 고정하고 amount는 null placeholder로 둔다.
- apply gate 테스트에서 template row 자체와 unedited skeleton row가 decision input으로 들어와도 실패하는 것을 고정했다.
- 실제 결과: gap decision template row 6, rows with candidate hints 0, total candidate hints 0, decision batch importable false.
- gap decision template artifact privacy scan finding 0, strict literal-key scan finding 0.

구현된 review decision human-gate 보강:

- `backend/scripts/validate_naver_tampermonkey_review_decisions.py`
- `backend/scripts/export_naver_tampermonkey_approved_db_import.py`
- review decision의 `reviewer_id`는 `operator_` prefix를 요구한다.
- review decision의 `reviewed_at`은 timezone-aware ISO datetime만 허용한다.
- `ollama_gemma4` 같은 model-only reviewer id는 validation 단계와 direct approved export 단계 모두에서 실패한다.
- approved ingredient의 `source`는 `human_reviewed`만 허용한다.
- approved ingredient의 `amount`는 숫자 또는 null만 허용하고 string/bool amount는 실패 처리한다.
- approved ingredient는 normalized display name과 nutrient code 기준으로 product 안에서 중복될 수 없다.
- approved ingredient의 display name은 `g X30포(`, `정x 3개입(`, `1000mg`, `60 capsules` 같은 포장 수량/용량-only 문자열이면 실패 처리한다.
- review decision과 approved import의 검수 문자열은 HTML angle bracket, script/data/vbscript protocol, URL-like 값, control character를 포함하면 실패 처리한다.
- import 가능한 decision row는 top-level `schema_version=naver-tampermonkey-review-decision-v1`을 요구해 template row 또는 임의 JSONL을 decision batch로 쓰는 실수를 차단한다.
- gap decision template contract에도 `reviewer_id_required_prefix=operator_`를 명시했다.
- gap decision template contract에도 `reviewed_at_required_format=timezone_aware_iso8601`과 unique ingredient identity 기준을 명시했다.
- gap decision template contract에도 `approved_ingredient_source_required=human_reviewed`, `approved_ingredient_amount_type=number_or_null`, `approved_ingredient_packaging_quantity_text_allowed=false`를 명시했다.
- gap decision template contract에도 `decision_row_schema_version_required=naver-tampermonkey-review-decision-v1`을 명시하고 skeleton row에 같은 schema version을 넣는다.
- gap decision template contract에도 `reviewed_text_executable_or_url_content_allowed=false`를 명시했다.

구현된 gap-scoped import gate 보강:

- `backend/scripts/run_naver_tampermonkey_review_import_gate.py --gap-queue`
- `--require-gap-reviewed`, `--require-gap-approved`로 120개 전체가 아닌 manual-review gap row만 엄격 검수할 수 있다.
- `--restrict-decisions-to-gap`으로 decision batch에 gap queue 밖 review id가 섞이면 실패시킬 수 있다.
- 114개 일반 review row는 pending으로 남기면서 6개 gap decision batch만 DB import dry-run gate로 검증할 수 있다.
- 실제 empty decision gate 결과: review row 120, gap row 6, gap pending 6, approved row 0, planned product upsert 0, DB write false.
- `--require-gap-reviewed`를 켠 empty decision gate는 `Gap review queue requires every gap row to be reviewed.`로 실패해, 6개 gap decision이 비어 있으면 통과하지 않는다.
- rejected gap decision은 reviewed로는 인정되지만 approved/import candidate로는 넘어가지 않으며, `--require-gap-approved`에서는 실패하도록 테스트로 고정했다.
- `--restrict-decisions-to-gap`을 켠 empty decision gate 결과: non-gap decision 0, gap pending 6, DB write false.
- gap-scoped import gate artifact privacy scan finding 0, strict literal-key scan finding 0.

구현된 review-readiness summary gate 보강:

- `backend/scripts/summarize_naver_tampermonkey_review_readiness.py`
- redacted summary JSON만 읽고 OCR JSONL row, source image, raw OCR text, provider payload, model response, local path, DB record는 읽지 않는다.
- EX400U coverage 지표와 DB import readiness를 분리해 `ready_for_db_import`, `human_review_required`, `blocking_reasons`를 산출한다.
- `--require-db-ready`를 켜면 manual review gap 또는 승인 row 부족 상태에서 exit code 1로 실패한다.
- 실제 최신 EX400U 결과: fixture 120, observation 120, completed 119, error 1, gap pending 6, approved row 0, DB import ready row 0.
- readiness 결과: `ready_for_db_import=false`, blocker `manual_gap_review_pending`, `no_approved_import_rows`, `ocr_provider_errors_present`, `review_rows_not_db_import_ready`.
- readiness artifact privacy scan finding 0, strict literal-key scan finding 0.

## 이번 변경의 보안 점검

- subprocess child env를 allowlist로 제한해 부모 환경 secret 전파 위험을 줄인다.
- OCR retry에 필요한 `LOCAL_OCR_USE_TEXTLINE_ORIENTATION`, `LOCAL_OCR_CONFIDENCE_THRESHOLD`만 runner allowlist에 추가하고 unrelated parent secret 미전파 테스트를 유지한다.
- OCR 전처리 retry에 필요한 `LOCAL_OCR_PREPROCESS_MODE`만 runner/collector allowlist에 추가하고, 전처리 이미지는 temp file로만 사용한다.
- PaddleOCR model profile 비교에 필요한 `LOCAL_OCR_MODEL_PROFILE`만 runner/collector allowlist에 추가하고, 기본값은 기존 mobile profile로 유지한다.
- retry reconcile은 raw OCR text, raw provider payload, raw model response, image bytes, request headers, local path literal을 recursive gate로 거부한다.
- retry reconcile의 source label은 경로 component가 길어도 hash 기반 공개 token으로 축약하고, local absolute path는 summary에 쓰지 않는다.
- reconciled failure retry manifest exporter도 source manifest와 observation을 모두 recursive privacy gate로 검사하고, summary에는 path hash/name만 기록한다.
- image quality diagnostic은 EX400U source root를 런타임 env로만 사용하고, generated artifact에는 path hash/name과 bounded image-quality bucket만 기록한다.
- PP-StructureV3 probe는 PaddleOCR가 반환할 수 있는 raw JSON/Markdown/table HTML을 저장하지 않고, layout/table/OCR count만 저장한다.
- ROI crop retry는 파생 crop image를 temp directory에만 만들고 최종 artifact에는 crop hash/count/profile만 기록한다.
- DB-labeling staging/review ingest/decision template은 모두 human review gate이며 production DB write를 수행하지 않는다.
- manual-review gap queue는 review ingest에서 안전한 hash/count/status만 복사하고 import 가능한 decision payload를 만들지 않는다.
- manual-review gap decision template은 gap queue를 필터로만 사용하고 bounded reason/action/count, non-importable decision skeleton, validator와 같은 reviewed_at/ingredient identity contract만 노출한다.
- review decision apply gate는 decision row의 top-level `fixture_id`가 review ingest row의 `fixture_id`와 일치해야 같은 `review_task_id`에 붙일 수 있다.
- review decision apply/import gate는 decision row schema version을 요구하고, gap queue의 `review_task_id`와 `fixture_id`가 review ingest와 함께 일치해야 gap-scoped strict gate를 진행한다.
- review decision validator와 approved DB import exporter는 `operator_` reviewer id와 timezone-aware ISO `reviewed_at`만 허용해 model-only approval 또는 시간대가 불명확한 review decision 우회를 막는다.
- approved DB import exporter는 human-reviewed source, numeric amount, product 안 unique ingredient identity만 허용해 OCR/LLM provenance, free-form amount, duplicate child row가 DB import 후보에 섞이지 않게 한다.
- review decision validator, approved DB import exporter, dry-run approved DB import gate는 포장 수량/용량-only 문자열이 human-approved ingredient로 들어오면 실패시켜 auto-seed 오염이 DB 라벨로 승격되는 경로를 막는다.
- review decision validator, approved DB import exporter, dry-run approved DB import gate, review decision template exporter는 HTML/URL/script-like/control-character 문자열이 검수명, 제조사명, 성분명, 단위명, candidate hint로 저장되는 것을 차단한다.
- dry-run approved DB import gate는 duplicate source product key와 duplicate ingredient identity를 DB write 전에 차단한다.
- DB write approval log도 `operator_` reviewer id와 UTC ISO-8601 `approved_at`만 허용해 model-only 또는 시간대가 불명확한 approval log가 최종 DB write preflight를 통과하지 못하게 한다.
- gap-scoped import gate는 6개 gap decision 완료 여부를 별도 count로 검증하고 production DB write를 수행하지 않는다.
- gap-scoped import gate의 restricted mode는 비-gap approval이 같은 decision batch에 섞여 import dry-run으로 넘어가는 것을 차단한다.
- review-readiness summary gate는 EX400U OCR coverage와 DB import 가능 상태를 분리하고, summary JSON만 읽어 raw OCR/이미지/모델 응답이 재노출될 통로를 만들지 않는다.
- evaluator diagnostic counters는 token allowlist를 적용해 local path/secret 형태 값을 public artifact에 쓰지 않는다.
- raw OCR text, raw provider payload, raw model response, image bytes 저장 정책은 변경하지 않는다.

## 2026-05-25 EX400U 기준 재테스트

입력:

- manifest: `2026-05-24-stage15-ex400u-folder-fixture-test/manifest-detail-folder-labeled-ex400u.jsonl`
- observation: `2026-05-24-stage15-ex400u-folder-fixture-test/reconciled-gemma4-e4b-live-roi-crop/reconciled-supplement-ocr-observations.jsonl`
- output: `2026-05-25-ex400u-folder-web-fixture-test`

결과:

- category taxonomy: label 43, unmapped 0, official source URL recorded, clinical recommendation false.
- OCR/Ollama coverage: fixture 120, observation 120, completed 119, error 1, parser success 0.9917, LLM parse success 1.0, remaining error `ocr_low_confidence` 1.
- DB-labeling staging/review: staging row 120, matched observation 120, rows with OCR observation 120, rows with LLM ingredient candidates 114, total candidate hints 362.
- review gate: review required 120, DB import ready 0, manual-review gap row 6.
- gap reasons: `ingredient_candidate_count_zero` 6, `llm_zero_ingredient_candidates` 5, `ocr_provider_error` 1.
- gap strict gate: empty decisions with `--restrict-decisions-to-gap` produces approved row 0 and DB write false; adding `--require-gap-reviewed` fails with `Gap review queue requires every gap row to be reviewed.` as expected.
- readiness gate: `ready_for_db_import=false`, `human_review_required=true`, blocker `manual_gap_review_pending`, `no_approved_import_rows`, `ocr_provider_errors_present`, `review_rows_not_db_import_ready`; `--require-db-ready` fails as expected.
- review decision gate: `ollama_gemma4` 같은 model-only reviewer id, naive/invalid `reviewed_at`, duplicate approved ingredient는 validation 및 direct approved export에서 실패하도록 테스트로 고정했다.
- review decision gate: `g X30포(`, `정x 3개입(`, `1000mg`, `60 capsules` 같은 포장 수량/용량-only 성분명은 validation, direct approved export, dry-run import plan에서 실패하도록 테스트로 고정했다.
- review decision gate: HTML tag, script protocol, URL-like value, control character 계열 검수 문자열은 validation, direct approved export, dry-run import plan, decision template candidate export에서 실패하도록 테스트로 고정했다.
- review decision gate: missing decision schema version과 gap queue fixture mismatch는 apply/import gate에서 실패하도록 테스트로 고정했다.
- review decision template gate: timezone-aware `reviewed_at`, unique approved ingredient identity, packaging quantity ingredient 금지, executable/URL-like text 금지 요구사항을 template contract에 노출하도록 테스트로 고정했다.
- review decision apply gate: 같은 `review_task_id`라도 decision row `fixture_id`가 review ingest `fixture_id`와 다르면 실패하도록 테스트로 고정했다.
- dry-run DB import gate: duplicate source product key와 duplicate ingredient identity는 ORM dry-run plan 생성 전에 실패하도록 테스트로 고정했다.
- DB write approval gate: `ollama_gemma4` 같은 model-only reviewer id와 naive/non-UTC `approved_at`은 최종 DB write preflight에서 실패하도록 테스트로 고정했다.
- privacy scan: 2026-05-25 generated output strict literal-key scan finding 0; category-label/inventory strict scan finding 0.
