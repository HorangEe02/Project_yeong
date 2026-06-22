# Review PII Screening Manifest 결과

## 요약

- review 이미지 외부 전송 전 단계로 local-only PII screening manifest를 생성하는 스크립트를 추가했다.
- 이 단계는 OCR/LLM 호출, DB write, 외부 전송을 하지 않는다.
- review row는 모두 `contains_personal_data=null`, `pii_screening_status=pending_local_screening`, `external_transfer_allowed=false`로 고정된다.
- product directory 원문은 저장하지 않고 `product_dir_hash`만 저장한다.
- 정상 실행 summary는 생성 artifact의 절대 경로를 출력하지 않고 파일명만 남긴다.
- CLI 실패도 Python traceback 대신 redacted JSON summary만 출력/저장한다.

## 구현 파일

- `backend/scripts/build_naver_tampermonkey_review_pii_screening_manifest.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_review_pii_screening_manifest.py`

## 실제 생성 결과

출력은 ignored local artifact로만 유지한다.

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/review-pii-screening-local-only/
```

| 항목 | 값 |
| --- | ---: |
| files_seen | 137,940 |
| candidate_count | 130,303 |
| review_candidate_count | 126,526 |
| manifest_row_count | 126,526 |
| pending_local_screening_rows | 126,526 |
| external_transfer_allowed_rows | 0 |
| category_key_count | 41 |
| product_dir_literals_stored | false |

## 보안 점검

- privacy gate: `file_count=2`, `json_value_count=4,233,882`, `finding_count=0`, `passed=true`
- CLI 실패 summary privacy gate: `file_count=1`, `json_value_count=25`, `finding_count=0`, `passed=true`
- raw OCR text/provider payload/model response/request header/image bytes/secret key 저장 없음
- `/private`, `/Users`, `/Volumes`, `file://` 로컬 절대경로 literal 없음
- `product_dir` 원문 key 없음
- `image_path`는 local-only tool resolution을 위한 `$NAVER_TAMPERMONKEY_SOURCE_ROOT/...` token path만 저장한다.
- `manifest_name` / `summary_name`은 filename만 허용해 output directory escape를 막는다.
- CLI 실패 summary는 `source_root_hash`, `source_root_exists`, safe `error_code`, bounded safe `error_message`만 남기며 traceback과 로컬 경로 literal을 출력하지 않는다.

## 검증

- review PII manifest + OCR manifest + privacy unit tests: `19 passed`
- black check: pass
- ruff check: pass
- `git diff --check`: pass

## 다음 단계

사람 검수 도구가 이 manifest를 읽어 PII screening decision을 별도 JSONL로 만들고, 통과된 review 이미지만 후속 OCR/DB review workflow에 연결한다.
