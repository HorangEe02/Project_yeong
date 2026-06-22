# Tampermonkey Folder Category Labeling 결과 - 2026-05-24

## 범위

- 외장 Naver Tampermonkey crawl 폴더명을 OCR fixture category label seed로 사용하도록 보강했다.
- 생성된 label은 DB 적재 준비용 seed이며, 만성질환자 섭취 권고나 추천 엔진으로 사용하지 않는다.
- 상세페이지 fixture는 외부 전송 가능 flag를 유지하지만, 이번 작업에서는 OCR provider 호출이나 raw OCR text 저장을 수행하지 않았다.

## 변경 파일

- `data/nutrition_reference/ocr_fixture_chronic_supplement_categories.json`
  - 43개 Tampermonkey 폴더 alias를 DB용 `category_key`로 매핑한다.
  - 각 label에 `display_name_ko`, `display_name_en`, `condition_tags`, `caution_tags`, `source_urls`를 둔다.
  - 모든 row는 `requires_human_review=true`로 유지해 자동 추천으로 오용되지 않게 했다.
- `backend/scripts/build_naver_tampermonkey_ocr_manifest.py`
  - manifest row에 `fixture_labels`와 `db_labeling`을 추가했다.
  - `category-labels.json` inventory를 별도 생성한다.
  - taxonomy가 없는 새 폴더도 `unmapped_tampermonkey_<hash>` key로 DB 라벨링 후보가 되도록 했다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_naver_tampermonkey_ocr_manifest.py`
  - 공식 taxonomy mapping, unmapped fallback, custom taxonomy path 테스트를 추가했다.

## 공식 자료 확인

이번 taxonomy는 label coverage/caution tag 기준만 제공한다. 효능 주장이나 권장량은 넣지 않았다.

- NIH ODS supplement fact sheets: https://ods.od.nih.gov/factsheets/list-all/
- NIH ODS Omega-3 fact sheet: https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/
- NIH ODS Vitamin D fact sheet: https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
- NIH ODS Magnesium fact sheet: https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/
- NIH ODS Vitamin K fact sheet: https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/
- NCCIH Using Dietary Supplements Wisely: https://www.nccih.nih.gov/health/using-dietary-supplements-wisely
- NCCIH safety page: https://www.nccih.nih.gov/health/safety
- NCCIH diabetes and dietary supplements: https://www.nccih.nih.gov/health/diabetes-and-dietary-supplements-what-you-need-to-know
- NCCIH turmeric: https://www.nccih.nih.gov/health/turmeric
- NCCIH probiotics: https://www.nccih.nih.gov/health/probiotics-usefulness-and-safety
- National Kidney Foundation vitamins in CKD: https://www.kidney.org/kidney-topics/vitamins-chronic-kidney-disease
- CDC fiber and diabetes: https://www.cdc.gov/diabetes/healthy-eating/fiber-helps-diabetes.html

## Stage14 산출물

생성 위치:

```text
outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling/
```

생성 파일:

- `manifest-detail-folder-labeled-86.jsonl`
- `inventory-folder-labeled.json`
- `category-labels.json`

핵심 결과:

| 항목 | 값 |
| --- | ---: |
| candidate_count | 130,303 |
| detail_candidates | 3,777 |
| review_candidates | 126,526 |
| category_count | 43 |
| category_label_count | 43 |
| unmapped_category_count | 0 |
| manifest_rows | 86 |
| raw_artifacts_stored | false |
| raw_ocr_text_stored | false |
| raw_provider_payload_stored | false |

## 실행 명령

```bash
/private/tmp/lemon-p1-quality-venv/bin/python backend/scripts/build_naver_tampermonkey_ocr_manifest.py \
  --source-root '/Volumes/Corsair EX400U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver' \
  --output-dir outputs/generated/ocr-eval/2026-05-24-stage14-tampermonkey-folder-category-labeling \
  --manifest-name manifest-detail-folder-labeled-86.jsonl \
  --inventory-name inventory-folder-labeled.json \
  --category-labels-name category-labels.json \
  --section detail \
  --sample-size 86 \
  --scan-limit 200000 \
  --seed 20260524 \
  --min-width 160 \
  --min-height 120 \
  --max-bytes 50000000
```

## 보안/유출 확인

- generated artifact에는 `/Volumes/...` 외장 절대경로를 저장하지 않고 `$NAVER_TAMPERMONKEY_SOURCE_ROOT/...` token path만 저장한다.
- CLI 정상 summary는 `manifest_name`, `inventory_name`, `category_labels_name`만 출력하며 output 절대경로를 출력하지 않는다.
- `manifest_name` / `inventory_name` / `category_labels_name`은 filename만 허용해 output directory escape를 막는다.
- CLI 실패 summary는 safe `error_code`, bounded `error_message`, hashed `source_root_hash`만 남기며 traceback과 로컬 경로 literal을 출력하지 않는다.
- OCR 원문, provider raw payload, model raw response, request header, image bytes, `.env`, secret 값은 생성하지 않았다.
- 리뷰 이미지는 이번 manifest 범위에서 제외했고, 기존 정책대로 review row는 외부 전송 전 local PII screening이 필요하다.

검증:

```text
json taxonomy validation: pass
focused builder tests: 10 passed
CLI failure redaction probe: pass
artifact privacy gate: pass
absolute path / raw-key grep: no external path hit; only *_stored=false flags present
```

## 다음 작업

1. `manifest-detail-folder-labeled-86.jsonl`를 입력으로 PaddleOCR + 로컬 Ollama Gemma4 파서를 실행한다.
2. `db_labeling.category_key`, `language_targets=["ko","en"]`, `chronic_fixture_tags`를 DB import staging schema에 연결한다.
3. review 이미지 126,526개는 local-only PII screening manifest를 따로 만들고, 사람 검수 후에만 외부 OCR 전송 여부를 결정한다.
