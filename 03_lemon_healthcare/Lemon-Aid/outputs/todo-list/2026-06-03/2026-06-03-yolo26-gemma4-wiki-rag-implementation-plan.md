# 2026-06-03 YOLO26 + Gemma 4 + LLM-WIKI RAG 구현 계획

## 현재 확인 결과

- `data/nutrition_reference/crawling-image` 실제 구조는 `카테고리 폴더 / 상품 폴더 / 리뷰 또는 상세페이지`입니다.
- 브랜드 전용 폴더 계층은 없습니다. 상품 폴더명 앞부분에서 브랜드 후보를 추정할 수는 있지만, DB에 제조사로 확정 저장하기 전 human review가 필요합니다.
- 감사 스크립트 실행 결과: 카테고리 43개, 상품 폴더 388개, 이미지 137,809개, 상세페이지 이미지 5,289개, 리뷰 이미지 132,520개입니다.
- 구조 이슈: 브랜드 전용 폴더 부재, 일부 상품의 리뷰 폴더 누락 21건, 상세페이지 폴더 누락 1건, 비이미지 파일 179건입니다.

## 1차 구현 완료

- `backend/scripts/audit_supplement_crawling_image_taxonomy.py`
  - `crawling-image`를 읽기 전용으로 감사합니다.
  - 카테고리, 상품 수, 이미지 수, 리뷰/상세페이지 분포, 브랜드 후보, 구조 이슈를 요약합니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR, provider payload는 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_audit_supplement_crawling_image_taxonomy.py`
  - 카테고리/상품/source kind 집계 검증
  - 브랜드 후보가 `requires_human_review`로 표시되는지 검증
  - 절대경로와 상품 폴더명이 출력되지 않는지 검증
  - 실패 응답도 경로를 노출하지 않는지 검증

## 2차 구현 완료

- `backend/scripts/build_supplement_taxonomy_db_staging.py`
  - 감사 결과를 DB 반영 전 staging JSONL로 변환합니다.
  - `category_seed` row는 `supplement_categories` seed 후보로 표시합니다.
  - `product_brand_candidate` row는 `supplement_products.manufacturer` 후보로만 표시하고 `approved_for_db_write=false`, `requires_human_review=true`로 고정합니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR, provider payload는 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py`
  - 카테고리 seed row와 브랜드 후보 row 분리 검증
  - 브랜드 후보가 검수 전 DB write 불가 상태인지 검증
  - 상품명 literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증
- 실제 실행 결과:
  - `row_count`: 431
  - `category_seed_row_count`: 43
  - `brand_candidate_row_count`: 388
  - `review_required_row_count`: 388
  - `approved_for_db_write_row_count`: 43
  - `source_kind_counts`: 상세페이지 5,289개, 리뷰 132,520개

## 3차 구현 완료

- `backend/scripts/build_supplement_learning_candidate_manifests.py`
  - 리뷰 이미지를 OCR ground-truth 후보 manifest로 분리합니다.
  - 상세페이지 이미지를 YOLO supplement-section bbox annotation 후보 manifest로 분리합니다.
  - 후보 선택 전 전체 이미지 해시를 계산하지 않고, 선택된 샘플만 content SHA-256을 계산합니다.
  - 리뷰 이미지는 기본적으로 `pending_pii_screening`, `external_transfer_allowed=false`, `teacher_ocr_allowed=false`로 고정합니다.
  - `--review-personal-data-cleared`가 있을 때만 teacher OCR 후보로 승격합니다.
  - 상세페이지 YOLO 후보는 `coco_pretrained_allowed_for_final_labels=false`, `custom_section_model_required=true`로 고정합니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR, provider payload는 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_candidate_manifests.py`
  - 리뷰 OCR 후보와 상세페이지 YOLO 후보 분리 검증
  - PII clearance 전/후 teacher OCR gate 검증
  - 카테고리별 샘플링 cap 검증
  - 상품명 literal, local path, raw OCR/provider field 미노출 검증
  - CLI OCR/YOLO JSONL/summary 출력 검증
- 실제 샘플 manifest 실행 결과:
  - `ocr_candidate_count`: 215
  - `yolo_candidate_count`: 205
  - `manual_ground_truth_required_count`: 215
  - `bbox_human_annotation_required_count`: 205
  - `ocr_external_transfer_allowed_count`: 0
  - `yolo_external_transfer_allowed_count`: 0
  - 출력 파일 검사: `"raw_ocr_text"`, `"provider_payload"`, `/Volumes/`, `/private/`, `file://` 미검출

## 4차 구현 완료

- `backend/scripts/build_supplement_ocr_benchmark_manifest.py`
  - 리뷰 OCR 후보 manifest와 수동 ground-truth JSONL을 join합니다.
  - `contains_personal_data=false`, `pii_screening_status=operator_cleared_no_personal_data`, `teacher_ocr_allowed=true` 후보만 benchmark로 승격합니다.
  - ground truth는 `ground_truth_status=human_reviewed` 또는 승인 상태인 경우만 사용합니다.
  - expected 필드는 제품명, 제조사, 성분/함량/단위, 섭취 방법, 주의사항, 기능 문구, label section으로 재구성합니다.
  - raw OCR text, provider payload, request header, local path, image bytes는 입력과 출력 모두에서 차단합니다.
  - 선택 옵션으로 PII-cleared 원본 이미지를 private hashed fixture 디렉터리로 복사하고, manifest에는 `images/<fixture_id>.<ext>` 상대 경로만 기록합니다.
  - provider plan은 teacher `clova_ocr`, `google_vision_document`, target `paddleocr_local`로 고정합니다.
  - 이 단계는 provider 호출, DB write, PaddleOCR 학습을 수행하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py`
  - PII-cleared + human-reviewed GT만 scoreable fixture가 되는지 검증
  - PII 미통과 후보와 미검수 GT가 제외되는지 검증
  - private hashed image materialization의 상대 경로와 파일 복사 검증
  - 상품명 literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증

## 5차 구현 완료

- `backend/scripts/export_supplement_ocr_ground_truth_template.py`
  - PII-cleared 리뷰 OCR 후보를 사람이 채울 수 있는 수동 정답지 JSONL 템플릿으로 변환합니다.
  - `candidate_pii_or_teacher_gate_not_cleared` 후보는 템플릿에서 제외합니다.
  - 템플릿의 `expected`는 제품명, 제조사, 성분명, 함량, 단위, 섭취 방법, 주의사항, 기능 문구, label section의 빈 구조를 제공합니다.
  - 선택 옵션으로 PII-cleared 원본 이미지를 private hashed fixture 디렉터리로 복사하고, 템플릿에는 상대 경로만 기록합니다.
  - 이 단계는 정답을 추론하지 않고, OCR provider 호출, DB write, PaddleOCR 학습을 수행하지 않습니다.
  - 실제 데이터에는 아직 사람이 PII clearance를 확정하지 않았으므로 `--review-personal-data-cleared`를 임의 적용하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_supplement_ocr_ground_truth_template.py`
  - PII-cleared 후보만 템플릿으로 export되는지 검증
  - PII 미통과 후보가 제외되는지 검증
  - private hashed image materialization 검증
  - 상품명 literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증

## 6차 구현 완료

- `backend/scripts/export_supplement_yolo_annotation_template.py`
  - 상세페이지 YOLO 후보 manifest를 사람이 bbox 작업할 수 있는 annotation template JSONL로 변환합니다.
  - 후보 row는 `detail_page`, `supplement_section_bbox_annotation`, `contains_personal_data=false`, `local_processing_allowed=true`, `custom_section_model_required=true`, `coco_pretrained_allowed_for_final_labels=false` gate를 모두 통과해야 합니다.
  - label snapshot은 `coordinate_space=source_image`, `training_export_allowed=false`, `human_review_required=true`, `boxes=[]`로 시작합니다.
  - 선택 옵션으로 원본 상세페이지 이미지를 private hashed fixture 디렉터리에 복사하고, 템플릿에는 `images/detail-yolo-*.ext` 상대 경로만 기록합니다.
  - 이 단계는 DB write, 최종 YOLO label 생성, training export를 수행하지 않습니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR text, provider payload, image bytes는 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py`
  - 상세페이지 후보가 annotation template로 변환되는지 검증
  - 리뷰 OCR 후보가 bbox template로 승격되지 않는지 검증
  - private hashed image materialization 검증
  - 상품명 literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증

## 8차 구현 완료

- `backend/scripts/promote_supplement_yolo_annotation_template.py`
  - 사람이 bbox를 작성하고 승인한 `supplement-yolo-annotation-template-row-v1` JSONL을 `supplement-section-yolo-detect-export-v1` artifact로 변환합니다.
  - `materialize_supplement_section_yolo_dataset.py`가 사용할 operator-private source map을 함께 생성합니다.
  - `annotation_status`가 accepted 계열이고, `training_export_allowed=true`, `human_review_required=false`인 row만 승격합니다.
  - pending row는 학습 export에서 제외합니다.
  - `image_path`는 template/source-map과 같은 private fixture 디렉터리 아래의 상대 경로만 허용합니다.
  - raw OCR, provider payload, absolute path, product literal, source ref, label 내용은 stdout summary에 노출하지 않습니다.
  - 생성된 export/source-map이 실제 YOLO train/val image/label 파일로 materialize되는지 검증합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_promote_supplement_yolo_annotation_template.py`
  - reviewed template가 YOLO export/source-map으로 변환되는지 검증
  - pending template가 export에서 제외되는지 검증
  - raw OCR text와 absolute image path 차단 검증
  - CLI summary가 source ref, image path, label을 출력하지 않는지 검증
  - materializer와 연결되는 end-to-end 파일 생성 검증

## 9차 구현 완료

- `backend/scripts/export_supplement_review_pii_screening_template.py`
  - 리뷰 OCR 후보 manifest에서 `pending_local_screening` 상태인 row만 운영자 PII screening template로 export합니다.
  - 선택 옵션으로 원본 리뷰 이미지를 private hashed fixture 디렉터리에 복사하고, 템플릿에는 `images/review-ocr-gt-*.ext` 상대 경로만 기록합니다.
  - decision stub은 `supplement-review-pii-screening-decision-v1` 형태로 생성하되, 사람이 직접 채우기 전까지 모든 attestation은 false입니다.
  - 이미 PII-cleared 상태인 후보는 재검수 템플릿에서 제외합니다.
  - raw OCR text, provider payload, local path, product directory literal은 출력하지 않습니다.
  - 이 단계는 OCR provider 호출, DB write, PaddleOCR 학습을 수행하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_supplement_review_pii_screening_template.py`
  - pending 후보만 PII screening template로 export되는지 검증
  - private hashed image materialization이 상대 경로만 기록하는지 검증
  - 이미 cleared된 후보가 제외되는지 검증
  - 상품명 literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증

## 10차 구현 완료

- `backend/scripts/apply_supplement_review_pii_screening_decisions.py`
  - 리뷰 OCR 후보 manifest에 운영자 PII screening decision JSONL을 적용합니다.
  - `cleared_no_personal_data` + 필수 attestation이 있는 row만 `contains_personal_data=false`, `pii_screening_status=operator_cleared_no_personal_data`, `external_transfer_allowed=true`, `teacher_ocr_allowed=true`로 승격합니다.
  - 필수 attestation은 `attest_local_screening_completed`, `attest_no_personal_data_visible`, `attest_no_raw_text_copied`, `attest_teacher_ocr_transfer_allowed`입니다.
  - `contains_personal_data`, `needs_rescreen`, `reject` decision은 teacher OCR flow에서 제외합니다.
  - decision 누락 row는 기본적으로 pending/local-only 상태로 유지하고, `--require-all-reviewed` 사용 시 하나라도 누락되면 실패합니다.
  - stale decision을 막기 위해 unmatched fixture id와 duplicate decision을 기본 실패 처리합니다.
  - raw OCR text, provider payload, image path, local path, URL, free-text note, product directory literal은 입력과 출력 모두에서 차단합니다.
  - 이 단계는 이미지 bytes 읽기, OCR provider 호출, DB write, PaddleOCR 학습을 수행하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_apply_supplement_review_pii_screening_decisions.py`
  - attested no-PII 후보만 teacher OCR eligible 상태가 되는지 검증
  - pending row가 local-only/transfer-blocked 상태로 남는지 검증
  - personal data decision이 teacher OCR flow에서 제외되는지 검증
  - duplicate/unmatched decision, 누락 attestation, unsafe payload 차단 검증
  - CLI 출력 summary가 local path와 raw payload를 노출하지 않는지 검증

## 11차 구현 완료

- `backend/scripts/export_supplement_brand_review_template.py`
  - `build_supplement_taxonomy_db_staging.py`가 만든 `product_brand_candidate` row만 operator review template로 export합니다.
  - `category_seed` row는 review template에서 제외합니다.
  - `brand_candidate`는 `brand_key`, `display_name`, `verification_status=requires_human_review` 상태로만 보존합니다.
  - decision stub은 `supplement-brand-review-decision-v1` 형태이며, 사람이 `reviewed_manufacturer`, `reviewed_product_name`, 필수 attestation을 채우기 전까지 `approved_for_db_write=false`입니다.
  - raw OCR text, provider payload, local path, product directory literal은 출력하지 않습니다.
  - 이 단계는 DB write를 수행하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_supplement_brand_review_template.py`
  - brand candidate row만 template로 export되는지 검증
  - category seed row는 skip되는지 검증
  - product folder literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증

## 12차 구현 완료

- `backend/scripts/apply_supplement_brand_review_decisions.py`
  - taxonomy staging JSONL과 operator brand review decision JSONL을 join해 승인된 `supplement_product_import` manifest row를 생성합니다.
  - `decision=approve`와 필수 attestation이 모두 있는 row만 `approved_for_db_write=true`로 승격합니다.
  - 필수 attestation은 `attest_brand_product_review_completed`, `attest_not_using_product_folder_literal_as_manufacturer`, `attest_product_name_reviewed_from_label_or_safe_catalog`, `attest_no_raw_ocr_or_provider_payload_copied`, `attest_db_import_allowed`입니다.
  - 출력 row는 `supplement_products` import 후보와 `supplement_product_categories` category mapping 후보를 함께 담습니다.
  - `reviewed_by_hash`, `product_dir_hash`, `source_folder_hash`, count metadata만 source payload에 남기고 reviewer id 원문, local path, product folder literal, raw OCR/provider payload는 저장하지 않습니다.
  - duplicate/unmatched decision은 기본 실패 처리합니다.
  - 이 단계도 DB writer가 아니라 import manifest 생성까지만 수행합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_apply_supplement_brand_review_decisions.py`
  - 승인 decision이 safe product import row로 변환되는지 검증
  - `needs_review` 등 미승인 decision이 import에서 제외되는지 검증
  - 누락 attestation, duplicate/unmatched decision, unsafe URL/path text 차단 검증
  - product folder literal, local path, raw OCR/provider field 미노출 검증
  - CLI JSONL/summary 출력 검증

## 13차 구현 완료

- `backend/scripts/import_supplement_taxonomy_approved_manifest.py`
  - `category_seed` staging row와 승인된 `supplement_product_import` manifest를 실제 DB upsert 경계로 연결합니다.
  - 기본 실행은 dry-run preflight입니다. `--apply`를 명시한 경우에만 DB session을 열고 write를 수행합니다.
  - `SupplementCategory`는 `category_key` 기준으로 upsert합니다.
  - `SupplementProduct`는 `source_provider`, `source_product_id` 기준으로 upsert합니다.
  - `SupplementProductCategory`는 `product_id`, `category_id` 기준으로 upsert합니다.
  - approved product manifest가 없는 경우 카테고리 upsert 계획만 생성하고, 브랜드/상품 저장은 계속 human review gate 뒤에 둡니다.
  - `manufacturer`는 승인 manifest에서도 필수로 검증해, 브랜드 상세 저장 목적과 맞지 않는 변조 manifest를 차단합니다.
  - category/product mapping source payload에는 해시와 검수 메타데이터만 남기고, local path, product folder literal, raw OCR/provider payload는 저장하지 않습니다.
  - operator-facing summary는 count 중심으로만 출력합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py`
  - dry-run이 DB session을 열지 않는지 검증
  - apply mode에서 category/product/mapping upsert가 각각 수행되는지 검증
  - 기존 row update summary가 정확한지 검증
  - repository failure 시 rollback되는지 검증
  - unknown category, empty required product manifest, duplicate product key, raw OCR payload 차단 검증
  - CLI summary가 local path와 product folder literal을 출력하지 않는지 검증

## DB 설계 판단

### 현 구조 유지

- `SupplementCategory`
  - top-level category folder를 `category_key`, `display_name`, `source_folder_name`으로 매핑합니다.
- `SupplementProduct`
  - 현재 `manufacturer` 필드가 있으므로, 브랜드 후보는 검수 전까지 확정 manufacturer로 저장하지 않습니다.
- `SupplementProductCategory`
  - 상품과 카테고리의 다대다 매핑을 유지합니다.

### 후속 확장

- 브랜드가 UX 필터나 데이터 품질 검증에서 1급 엔티티가 되면 `supplement_brands`, `supplement_product_brands`를 추가합니다.
- 지금 단계에서는 상품 폴더명 기반 브랜드 추정치가 오탐 가능성이 높아 별도 테이블을 즉시 만들지 않습니다.

### DB write gate

- 카테고리는 folder taxonomy로 seed 가능합니다.
- 브랜드 후보는 제조사로 확정하지 않습니다.
- 브랜드 후보를 DB에 반영하려면 별도 approved brand review manifest가 필요합니다.
- 승인 전 `SupplementProduct.manufacturer`와 `SupplementProductCategory`를 자동 생성하지 않습니다.
- 검수 완료 row는 `supplement_product_import` manifest로 만들고, 실제 DB 반영은 `import_supplement_taxonomy_approved_manifest.py --apply`에서만 수행합니다.
- DB insert/upsert writer는 `supplement_products(source_provider, source_product_id)`, `supplement_categories(category_key)`, `supplement_product_categories(product_id, category_id)` unique constraint를 기준으로 동작합니다.

## YOLO26 섹션 탐지 계획

- 영양제 bbox class:
  - `product_identity`
  - `supplement_facts`
  - `ingredient_amounts`
  - `intake_method`
  - `precautions`
  - `other_ingredients`
  - `functional_claims`
- 음식 bbox class:
  - `meal_region`
  - `food_item`
  - `menu_text`
  - `nutrition_label`
- COCO pretrained `yolo26n.pt`는 섹션 탐지 모델로 신뢰하지 않습니다.
- 상세페이지 이미지는 섹션 bbox annotation 후보로 사용합니다.
- 리뷰 이미지는 PII screening 이후 OCR ground-truth 후보로만 사용합니다.
- train/val/test split은 상품 또는 브랜드 후보 단위로 분리해 data leakage를 막습니다.

## OCR 개선 계획

1. CLOVA OCR, Google Vision을 teacher provider로 실행합니다.
2. PaddleOCR 결과와 teacher 결과를 같은 이미지/섹션 단위로 비교합니다.
3. ground truth 확정 전에는 teacher 결과도 provisional로만 유지합니다.
4. 평가 지표:
   - text: CER, WER
   - field: 제품명, 성분명, 함량, 단위, 섭취방법, 주의사항 precision/recall/F1
   - section detection: IoU, mAP
5. PaddleOCR 개선은 데이터셋 확정 후 fine-tuning 또는 post-processing rule 개선으로 분리합니다.

## Gemma 4 + LLM-WIKI RAG 계획

- 기본 모델:
  - `OLLAMA_MODEL=gemma4:e4b`
  - `OLLAMA_VISION_MODEL=gemma4:e4b`
- readiness smoke:
  - `/api/chat` text smoke 통과 전에는 설명 기능 비활성화
  - vision image payload smoke 통과 전에는 Vision 검증 비활성화
- Gemma 4 Vision 역할:
  - crop 이미지와 OCR 후보 텍스트의 일치 여부만 검증합니다.
  - 보이지 않는 성분, 함량, 주의사항을 새로 생성하지 않습니다.
  - 불확실하면 `needs_retake` 또는 `needs_manual_confirmation`으로 반환합니다.
- Gemma 4 Text 역할:
  - 구조화된 제품명, 성분/함량, 섭취방법, 주의사항, 사용자 profile bucket만 사용합니다.
  - raw OCR, provider payload, 이미지 경로, owner hash, 복약 원문은 프롬프트와 응답에서 제외합니다.
- LLM-WIKI RAG:
  - `LLM_WIKI_PATH=/Volumes/Corsair EX400U Media/LLM-WIKI`
  - md 파일만 읽고, 상대 경로/제목/heading/excerpt 단위로 출처를 표시합니다.
  - 출처 없는 내용은 단정하지 않고 `확인 필요`로 표시합니다.

## 사용자 안전 문구

- 출력 범주: `권장`, `주의`, `상담 권고`, `확인 필요`
- 금지: 진단, 치료, 처방, 복용량 변경 지시, 약 중단 지시, 질병 개선 단정
- 고정 고지:
  - `의료적 진단·처방이 아닌 건강관리 참고 정보입니다. 복용 중인 약이나 질환이 있으면 의사·약사와 확인하세요.`

## 구현 순서

1. 감사 스크립트 결과를 seed/review staging 입력으로 고정합니다.
2. category seed manifest를 생성합니다. 완료.
3. 브랜드 후보 review manifest를 생성하되, DB 확정 저장은 막습니다. 완료.
4. operator가 브랜드/제품명을 검수한 decision을 적용해 approved product import manifest를 생성합니다. 완료.
5. 승인된 category/product manifest를 DB upsert 경계로 연결합니다. 기본 dry-run, `--apply` 명시 시에만 DB write. 완료.
6. 리뷰 이미지 PII screening gate를 통과한 샘플만 OCR GT 후보로 승격합니다. PII screening template와 운영자 decision apply 완료.
7. PII-cleared 리뷰 후보를 수동 정답지 작성 템플릿으로 export합니다. 완료.
8. 수동 정답지 작성 후 human-reviewed 상태만 benchmark fixture로 승격합니다. 완료.
9. 상세페이지 이미지를 YOLO section annotation task 후보로 승격합니다. 후보 manifest 완료.
10. 상세페이지 YOLO 후보를 사람이 bbox를 그릴 annotation template로 export합니다. 완료.
11. CLOVA/Google Vision teacher 결과와 PaddleOCR 결과를 비교하는 eval manifest를 생성합니다. 수동 GT benchmark manifest 완료.
12. Gemma 4 Vision smoke와 structured JSON schema 검증을 추가합니다.
13. LLM-WIKI md retriever를 설명 service와 챗 초안에 연결합니다.
14. 모바일은 4개 정보 카드, LED 상태, 출처 목록, 재촬영/수동 편집 안내를 표시합니다.

## DB category/brand 운영 순서

1. `audit_supplement_crawling_image_taxonomy.py`로 실제 폴더 구조를 확인합니다.
2. `build_supplement_taxonomy_db_staging.py`로 `category_seed`와 `product_brand_candidate`를 분리합니다.
3. `category_seed` row는 `supplement_categories` seed 후보로 사용합니다.
4. `export_supplement_brand_review_template.py`로 brand/product review template를 만듭니다.
5. operator가 `reviewed_manufacturer`, `reviewed_product_name`과 attestation을 채웁니다.
6. `apply_supplement_brand_review_decisions.py`로 승인 decision만 `supplement_product_import` manifest로 승격합니다.
7. `import_supplement_taxonomy_approved_manifest.py`를 dry-run으로 실행해 category/product/category-map upsert 계획을 검증합니다.
8. 실제 반영은 검수된 artifact만 대상으로 `--apply`를 명시했을 때 수행합니다.
9. DB writer는 import manifest만 읽고 `supplement_categories`, `supplement_products`, `supplement_product_categories`를 upsert합니다.
10. 미승인/미검수 row는 DB product/manufacturer 값으로 저장하지 않습니다.

## OCR 운영 순서

1. `build_supplement_learning_candidate_manifests.py`로 리뷰 OCR 후보를 생성합니다.
2. operator가 리뷰 이미지 PII screening을 수행합니다.
3. `export_supplement_review_pii_screening_template.py`로 private hashed fixture와 operator decision stub을 생성합니다.
4. operator가 PII screening template의 decision stub을 채웁니다.
5. `apply_supplement_review_pii_screening_decisions.py`로 operator decision을 적용해 no-PII attested row만 teacher OCR 후보로 승격합니다.
6. PII-cleared 후보에 대해서만 `export_supplement_ocr_ground_truth_template.py`를 실행합니다.
7. 사람이 템플릿의 `expected`를 채우고 `ground_truth_status=human_reviewed`, `contains_personal_data=false`로 확정합니다.
8. `build_supplement_ocr_benchmark_manifest.py`로 CLOVA/Google Vision/PaddleOCR benchmark fixture를 생성합니다.
9. opt-in 환경 변수로 provider observation을 수집합니다.
10. `evaluate_ocr_three_tier.py`로 CER/WER, 성분명 정확도, 함량/단위 정확도, 섭취 방법/주의사항 추출률을 평가합니다.
11. `build_paddleocr_improvement_candidates.py`로 PaddleOCR 오류를 detection/recognition/post-processing/manual triage 후보로 분리합니다.
12. 개선 후보는 사람이 private fixture를 보며 `ocr_textline_label` annotation task로 확정합니다.
13. `promote_paddleocr_annotation_tasks_to_dataset.py`로 accepted OCR annotation task를 `paddleocr_detection` 또는 `paddleocr_recognition` dataset item으로 승격합니다.
14. `export_training_manifest.py --export-kind paddleocr_detection|paddleocr_recognition`으로 privacy-approved/frozen dataset만 학습 manifest로 내보냅니다.
15. 실제 PaddleOCR fine-tuning은 export manifest 이후 별도 training run으로 수행합니다.

## YOLO annotation 운영 순서

1. `build_supplement_learning_candidate_manifests.py`로 상세페이지 YOLO 후보를 생성합니다.
2. `export_supplement_yolo_annotation_template.py`로 private hashed image fixture와 annotation template JSONL을 생성합니다.
3. 사람이 `allowed_labels` 기준으로 `product_identity`, `supplement_facts`, `ingredient_amounts`, `intake_method`, `precautions`, `other_ingredients`, `functional_claims` bbox를 작성합니다.
4. accepted row는 `training_export_allowed=true`, `human_review_required=false`, `coordinate_space=source_image` 상태로 검수합니다.
5. 파일 기반 검수 흐름에서는 `promote_supplement_yolo_annotation_template.py`로 reviewed template를 YOLO export/source-map으로 승격합니다.
6. DB annotation task를 사용하는 경우 `import_annotation_review.py`와 `promote_annotation_tasks_to_dataset.py` 흐름으로 dataset item에 승격합니다.
7. export artifact를 만든 뒤 `materialize_supplement_section_yolo_dataset.py`로 Ultralytics YOLO dataset을 생성합니다.
8. COCO pretrained `yolo26n.pt`는 bootstrap/architecture transfer 이상으로 사용하지 않고, 최종 라벨 신뢰는 human-reviewed section dataset에 둡니다.

## 7차 검증 완료

- 최신 실제 데이터 기준 audit/staging을 다시 실행했습니다.
- 구조 판단은 기존과 동일합니다.
  - category: 43개
  - product folder: 388개
  - image: 137,809개
  - review image: 132,520개
  - detail-page image: 5,289개
  - 구조 이슈: category non-image file 27건, missing review dir 21건, missing detail-page dir 1건
- DB staging 결과:
  - total row: 431개
  - category seed row: 43개
  - brand candidate row: 388개
  - review required row: 388개
  - approved DB write row: 43개
- brand review template 결과:
  - staging row: 431개
  - template row: 388개
  - operator decision required row: 388개
  - skipped category seed row: 43개
  - approved DB write row: 0개
- 결론:
  - 카테고리는 DB seed 가능.
  - 브랜드 후보는 제품 폴더 prefix 기반이므로 사람 검수 전 DB 확정 저장 금지.
  - 리뷰 이미지는 PII screening 전 teacher OCR provider 전송 금지.
  - 상세페이지 이미지는 YOLO section bbox annotation template로만 승격 가능.
- 관련 unit test 묶음은 33개 모두 통과했습니다.
- CLOVA/Google Vision/PaddleOCR 비교용 `evaluate_ocr_three_tier.py`도 ruff와 unit test 17개를 통과했습니다.
- reviewed YOLO template promotion도 ruff와 unit test 6개를 통과했습니다.
- 최종 좁은 범위 회귀 묶음은 ruff 통과, pytest 82개 통과 상태입니다.
- brand review template/apply 스크립트 추가 후 새 단위 테스트 12개도 포함했습니다.
- approved taxonomy importer 추가 후 실제 데이터 dry-run 결과:
  - `category_seed_row_count`: 43개
  - `approved_product_import_row_count`: 0개
  - `planned_category_upsert_count`: 43개
  - `planned_product_upsert_count`: 0개
  - `planned_product_category_upsert_count`: 0개
  - `db_write_performed`: false
  - `ready_for_db_write`: true
- importer 포함 최신 script 회귀 묶음은 ruff 통과, pytest 74개 통과 상태입니다.

## 14차 구현 완료

- `backend/scripts/build_paddleocr_improvement_candidates.py`
  - human-reviewed OCR benchmark manifest와 provider observations를 입력으로 사용합니다.
  - PaddleOCR observation에서 `ingredient_name_miss`, `ingredient_amount_unit_miss`, `intake_method_miss`, `precaution_miss`, `section_type_miss`, `paddleocr_empty_text`, `paddleocr_runtime_error`를 분류합니다.
  - candidate row에는 수동 검수에 필요한 `expected` snapshot을 포함하지만, stdout/summary에는 정답 텍스트, source ref, image path를 출력하지 않습니다.
  - recommended next step은 `paddleocr_detection_manual_review`, `paddleocr_recognition_manual_review`, `postprocessing_rule_review`, `provider_runtime_triage`로 제한합니다.
  - 이 단계는 OCR provider 호출, DB write, PaddleOCR 학습 실행을 하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py`
  - teacher provider는 맞고 PaddleOCR가 일부 성분/섹션을 놓친 경우 개선 후보가 생성되는지 검증했습니다.
  - PaddleOCR 결과가 완전 매칭이면 skip되는지 검증했습니다.
  - empty text/runtime error가 detection/manual review 후보로 분류되는지 검증했습니다.
  - `raw_ocr_text`, provider payload, 절대 image path가 들어오면 fail-closed로 거부하는지 검증했습니다.
  - CLI 출력 summary에 정답 텍스트와 private source ref가 노출되지 않는지 검증했습니다.
- 검증 결과:
  - 새 스크립트/테스트 ruff 통과
  - 새 단위 테스트 6개 통과

## 15차 구현 완료

- `backend/scripts/promote_paddleocr_annotation_tasks_to_dataset.py`
  - accepted `ocr_textline_label` annotation task를 `LearningDatasetItem`으로 승격합니다.
  - target task는 `paddleocr_detection`, `paddleocr_recognition` 중 하나로 명시합니다.
  - dataset version key는 각각 `supplement_ocr_detection`, `supplement_ocr_recognition`과 일치해야 합니다.
  - label 검증은 기존 `build_paddleocr_detection_export`, `build_paddleocr_recognition_export`를 재사용해 실제 training export와 동일한 shape를 강제합니다.
  - source는 `media:<uuid>` 또는 `learning_image:<uuid>` private ref로만 검증하고, summary에는 source ref, owner hash, label text를 출력하지 않습니다.
  - retention/deleted source는 dataset item으로 승격하지 않습니다.
  - 이 단계도 OCR provider 호출, DB 외부 artifact export, PaddleOCR 학습 실행을 하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py`
  - recognition label이 `supplement_ocr_recognition` dataset item으로 승격되는지 검증했습니다.
  - detection textline box가 `supplement_ocr_detection` dataset item으로 승격되는지 검증했습니다.
  - dataset key/task mismatch, malformed label, duplicate item을 fail-closed/skip 처리하는지 검증했습니다.
  - CLI failure summary가 label/source/owner 값을 출력하지 않는지 검증했습니다.
- 검증 결과:
  - 새 스크립트/테스트 ruff 통과
  - 새 단위 테스트 6개 통과

## 16차 구현 완료

- `backend/scripts/create_paddleocr_annotation_tasks_from_improvement_candidates.py`
  - `build_paddleocr_improvement_candidates.py`가 만든 개선 후보 manifest를 pending `ocr_textline_label` annotation task로 전환합니다.
  - `media:<uuid>` 또는 `learning_image:<uuid>` private source가 있는 후보만 DB task 생성 대상입니다.
  - 현재 `crawling-image:<hash>`처럼 파일 기반 후보는 DB source row가 없으므로 `unsupported_source_ref`로 skip합니다.
  - `owner_subject_hash`는 CLI 인자로 받되, summary/stdout에는 출력하지 않고 DB source row의 owner hash와 일치할 때만 task를 생성합니다.
  - active task가 이미 있는 source는 duplicate 생성을 막기 위해 `existing_active_task`로 skip합니다.
  - seed `label_snapshot`에는 검수 라우팅에 필요한 실패 코드, target dataset task type, human-reviewed expected snapshot만 넣고 source ref/object ref/provider payload/raw OCR/local path는 넣지 않습니다.
  - 이 seed는 바로 training export shape가 아니며, reviewer가 `text_label` 또는 `textline_boxes` 형태로 accepted label을 확정한 뒤 15차 promotion 스크립트가 dataset item으로 승격합니다.
  - 이 단계도 OCR provider 호출, PaddleOCR 학습 실행을 하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py`
  - learning image source와 media source 기반 후보가 pending annotation task로 생성되는지 검증했습니다.
  - `crawling-image:<hash>` file-only source가 skip되는지 검증했습니다.
  - 기존 active task가 있을 때 duplicate를 만들지 않는지 검증했습니다.
  - `raw_ocr_text` 같은 raw key가 들어오면 task 생성 전에 skip되는지 검증했습니다.
  - CLI failure summary가 정답 텍스트, source ref, owner hash를 출력하지 않는지 검증했습니다.
- 검증 결과:
  - 새 스크립트/테스트 ruff 통과
  - 새 단위 테스트 6개 통과

## 17차 구현 완료

- `backend/scripts/import_supplement_benchmark_fixtures_as_media_objects.py`
  - materialized OCR benchmark fixture manifest의 file-only `crawling-image:<hash>` source를 DB-backed `media:<uuid>` source로 전환하는 bridge입니다.
  - 기본은 dry-run이며 `--apply`를 명시해야만 `MediaObject` row 생성, private local media copy, rewritten benchmark manifest 생성을 수행합니다.
  - `image_path`는 manifest 기준 상대 경로만 허용하고, URL/절대경로/상위 경로 이탈은 `unsafe_image_path`로 skip합니다.
  - fixture 파일의 SHA-256과 `image_size_bytes`를 manifest와 대조해 hash/size mismatch가 있으면 fail-closed로 제외합니다.
  - `MediaObject`는 `domain=supplement_label`, `object_storage_provider=local`, `status=retained`로 생성하며, 같은 owner/image hash의 live row가 있으면 재사용합니다.
  - private object ref는 deterministic relative key로만 만들고, summary/stdout에는 owner hash, source ref, object ref, local path, expected text, raw provider payload를 출력하지 않습니다.
  - output manifest에는 downstream annotation task 생성에 필요한 `source_ref=media:<uuid>`만 반영하고 object ref/local absolute path는 넣지 않습니다.
  - 이 단계도 OCR provider 호출, PaddleOCR 학습 실행은 하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py`
  - dry-run이 DB/file/output write 없이 fixture validation만 수행하는지 검증했습니다.
  - `--apply`가 media row를 만들고 private local object copy와 rewritten manifest를 생성하는지 검증했습니다.
  - 기존 retained `MediaObject`가 있으면 중복 생성 없이 재사용하는지 검증했습니다.
  - hash mismatch와 unsafe absolute image path를 fail-closed skip하는지 검증했습니다.
  - CLI failure summary가 절대경로, owner hash, source ref, 정답 텍스트를 출력하지 않는지 검증했습니다.
- 사용 순서:
  1. `build_supplement_ocr_benchmark_manifest.py`에서 `--materialized-image-dir`를 사용해 private hashed fixture와 benchmark manifest를 생성합니다.
  2. 새 bridge를 dry-run으로 실행해 검증합니다.
  3. 운영자가 owner hash와 local private media root를 확인한 뒤 `--apply`로 rewritten benchmark manifest를 생성합니다.
  4. rewritten manifest를 `evaluate_ocr_three_tier.py`와 `build_paddleocr_improvement_candidates.py`에 넘깁니다.
  5. `create_paddleocr_annotation_tasks_from_improvement_candidates.py`가 `media:<uuid>` source를 검증하고 pending annotation task를 생성합니다.
- 검증 결과:
  - 새 스크립트/테스트 ruff 통과
  - 새 단위 테스트 6개 통과

## 18차 구현 완료

- `backend/scripts/materialize_paddleocr_dataset.py`
  - `export_training_manifest.py --export-kind paddleocr_detection|paddleocr_recognition`이 만든 sanitized export contract를 실제 PaddleOCR 학습 파일로 materialize합니다.
  - 입력은 operator-only `source_map`을 통해 private `source_ref`를 로컬 image path로 해석합니다. stdout summary에는 source ref, source path, label text를 출력하지 않습니다.
  - Detection export:
    - `learning-paddleocr-det-export-v1`의 normalized `textline_boxes`를 source image pixel 크기 기준 4점 polygon으로 변환합니다.
    - 출력 라벨은 PaddleOCR text detection format인 `image/path<TAB>json.dumps([...])` 형식입니다.
    - label file은 `det/det_gt_train.txt`, `det/det_gt_val.txt`, `det/det_gt_test.txt`로 split별 생성합니다.
  - Recognition export:
    - `learning-paddleocr-rec-export-v1`의 `text_label`을 `image/path<TAB>label` 형식으로 씁니다.
    - label file은 `rec/rec_gt_train.txt`, `rec/rec_gt_val.txt`, `rec/rec_gt_test.txt`로 split별 생성합니다.
    - recognition source image는 이미 text-line/word crop이어야 합니다. 이 materializer는 전체 라벨 이미지에서 crop을 새로 만들지 않습니다.
  - source image copy는 deterministic private source ref hash filename을 사용해 product/owner/source path literal을 숨깁니다.
  - 이 단계도 PaddleOCR 학습 실행 자체는 하지 않고, 학습 입력 dataset 파일만 생성합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py`
  - detection export가 PaddleOCR detection tab-separated JSON label로 materialize되는지 검증했습니다.
  - recognition export가 PaddleOCR recognition tab-separated text label로 materialize되는지 검증했습니다.
  - CLI stdout이 source ref, local path, label text를 출력하지 않는지 검증했습니다.
  - source map 누락, tab/newline이 포함된 recognition label을 fail-closed 처리하는지 검증했습니다.
- 사용 순서:
  1. `promote_paddleocr_annotation_tasks_to_dataset.py`로 accepted annotation task를 `LearningDatasetItem`으로 승격합니다.
  2. `export_training_manifest.py --export-kind paddleocr_detection|paddleocr_recognition`으로 sanitized export artifact를 만듭니다.
  3. 운영자 전용 source map으로 private source ref와 실제 training image/crop path를 연결합니다.
  4. `materialize_paddleocr_dataset.py`로 PaddleOCR label txt와 image copy를 생성합니다.
  5. 별도 training runner가 PaddleOCR fine-tuning command를 실행하고 `register_model_training_run.py`/model registry gate로 결과를 추적합니다.
- 검증 결과:
  - 새 스크립트/테스트 ruff 통과
  - 새 단위 테스트 5개 통과

## 19차 구현 완료

- PaddleOCR recognition crop 계약 확장
  - `src/learning/retraining.py`의 `build_paddleocr_recognition_export()`가 `label_snapshot.crop_box`를 optional로 보존합니다.
  - `crop_box`가 있으면 export row에 `recognition_source=source_image_crop`을 표시하고, 없으면 `recognition_source=pre_cropped_image`로 표시합니다.
  - `crop_box`는 source image 기준 normalized `x_center`, `y_center`, `width`, `height`만 허용하며, 0 이하 width/height는 거부합니다.
  - raw OCR, provider payload, path/url-like string guard는 기존 `validate_sanitized_label_snapshot()` 경로를 그대로 통과합니다.
- `backend/scripts/materialize_paddleocr_dataset.py`
  - recognition export item에 `crop_box`가 있으면 source image에서 해당 영역을 crop하여 recognition training image로 저장합니다.
  - `crop_box`가 없으면 기존처럼 source map이 이미 text-line/word crop 이미지를 가리키는 것으로 처리합니다.
  - crop output filename은 source ref hash 기반이라 source path/product/owner literal이 드러나지 않습니다.
  - stdout summary에는 source ref, local path, label text, crop coordinates를 출력하지 않습니다.
- 테스트 보강
  - `test_export_training_manifest.py`: recognition export가 `crop_box`와 `recognition_source`를 보존하는지 검증했습니다.
  - `test_promote_paddleocr_annotation_tasks_to_dataset.py`: accepted annotation task의 `crop_box`가 `LearningDatasetItem.label_snapshot`에 보존되는지 검증했습니다.
  - `test_materialize_paddleocr_dataset.py`: `crop_box`가 실제 cropped image를 생성하는지 검증했습니다.
- 검증 결과:
  - 관련 파일 ruff 통과
  - 관련 단위 테스트 17개 통과
  - OCR benchmark -> private media bridge -> PaddleOCR improvement candidate -> annotation task -> accepted dataset item -> PaddleOCR materializer 연결 회귀 테스트 42개 통과
  - `git diff --check` 통과

## 20차 구현 완료

- PaddleOCR fine-tuning run plan builder 추가
  - `backend/scripts/build_paddleocr_finetune_run_plan.py`가 materialized PaddleOCR dataset directory를 검증하고 `paddleocr-finetune-run-plan-v1` artifact를 생성합니다.
  - detection은 `det/det_gt_train.txt`, recognition은 `rec/rec_gt_train.txt`의 train row가 최소 1개 이상 있어야 합니다.
  - label file의 image ref는 dataset root 내부 relative path만 허용하며 absolute path, traversal, URL-like ref를 차단합니다.
  - detection label은 PaddleOCR detection JSON box list 형태인지 검사합니다.
  - fine-tuning plan은 `model_family=paddleocr_det|paddleocr_rec`, `dataset_version_id`, base model, config/pretrained/save model private relative refs, bounded hyperparameters, official-style command token list를 담습니다.
  - 이 단계는 PaddleOCR 학습을 실행하지 않고 `training_execution_performed=false`로 고정합니다.
  - stdout summary에는 dataset root, image path, label text, source ref, raw OCR, provider payload, model artifact ref를 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py`
  - recognition plan이 label text와 local path를 노출하지 않는지 검증했습니다.
  - detection plan이 PaddleOCR detection JSON label을 검증하는지 확인했습니다.
  - train row 누락, absolute image ref, secret-like save model ref를 fail-closed 처리하는지 검증했습니다.
  - CLI가 plan/summary를 쓰면서 stdout은 aggregate-only로 유지하는지 검증했습니다.
- 검증 결과:
  - 새 script/test ruff 통과
  - 새 단위 테스트 6개와 materializer 테스트 6개, 총 12개 통과
  - OCR/PaddleOCR 전체 연결 회귀에 fine-tune plan builder를 포함해 ruff 통과 및 pytest 48개 통과

## 21차 구현 완료

- PaddleOCR fine-tune run plan -> `model_training_runs` 등록 bridge 추가
  - `backend/scripts/register_paddleocr_finetune_run_from_plan.py`가 `paddleocr-finetune-run-plan-v1` artifact와 verified metrics JSON을 읽어 기존 `register_model_training_run.py` 경계로 등록합니다.
  - 사람이 plan의 `model_family`, `base_model`, `dataset_version_id`, `artifact_ref`, hyperparameter를 CLI 인자로 옮겨 적는 과정에서 생길 수 있는 drift를 줄입니다.
  - `task=recognition`은 `model_family=paddleocr_rec`, `task=detection`은 `model_family=paddleocr_det`로 다시 검증합니다.
  - plan top-level, `paddleocr.save_model_ref`, `register_model_training_run.artifact_ref`가 서로 다르면 fail-closed 처리합니다.
  - `status=succeeded`는 verified metric이 최소 1개 필요합니다.
  - `status=failed`는 artifact ref를 저장하지 않고 실패 run만 추적합니다.
  - bridge 자체는 PaddleOCR 학습을 실행하지 않고 `training_execution_performed_by_script=false`로 고정합니다.
  - stdout summary는 metric name/value, config ref, artifact ref, local path, label text, raw OCR, provider payload를 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_register_paddleocr_finetune_run_from_plan.py`
  - succeeded plan registration이 `ModelTrainingRun` row에 model family, base model, artifact ref, metrics, hyperparams를 보존하는지 검증했습니다.
  - failed registration은 artifact ref 없이 실패 상태만 저장하는지 검증했습니다.
  - succeeded run의 metric 누락, plan registration block drift를 fail-closed 처리하는지 검증했습니다.
  - CLI stdout이 metric name/value, artifact ref, local path를 숨기는지 검증했습니다.
- 검증 결과:
  - 새 bridge + plan builder + model training registration 범위 ruff 통과
  - 새 bridge 5개 포함 관련 단위 테스트 16개 통과
  - OCR benchmark -> private media bridge -> PaddleOCR improvement candidate -> annotation task -> accepted dataset item -> PaddleOCR materializer -> fine-tune plan -> model training run registration 연결 회귀 ruff 통과 및 pytest 58개 통과

## 22차 구현 완료

- PaddleOCR fine-tune plan trusted-worker 실행 경계 추가
  - `backend/scripts/run_paddleocr_finetune_plan.py`가 `paddleocr-finetune-run-plan-v1` artifact를 읽고, local PaddleOCR checkout의 `tools/train.py` 존재를 검증합니다.
  - 기본 실행은 dry-run입니다. `--execute`를 명시한 경우에만 plan의 `suggested_command_tokens`를 `subprocess.run(..., shell=False)`로 실행합니다.
  - command token은 empty/control character/shell syntax/absolute path/traversal/URL/secret-like marker를 차단하고, `tools/train.py` 포함을 요구합니다.
  - 실행 결과는 `paddleocr-finetune-execution-result-v1` artifact로 저장합니다.
  - 저장 필드는 process status, return code, elapsed seconds, stdout/stderr SHA-256 digest, stdout/stderr line count, timeout 여부 같은 실행 메타데이터로 제한합니다.
  - raw stdout/stderr, command token, PaddleOCR root path, config ref, artifact ref, label text, raw OCR text, provider payload는 stdout summary에 출력하지 않습니다.
  - 성공한 실행도 metric을 자동으로 신뢰하지 않습니다. `metrics_json_required_for_registration=true`로 표시해 별도 verified eval metric JSON을 만든 뒤 `register_paddleocr_finetune_run_from_plan.py`로 등록하도록 분리했습니다.
  - timeout은 실패로 덮어쓰지 않고 `process_status=timeout`으로 기록하며 partial stdout/stderr도 digest/line count만 저장합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_run_paddleocr_finetune_plan.py`
  - dry-run이 PaddleOCR root와 plan을 검증하되 학습 실행을 하지 않는지 검증했습니다.
  - fake subprocess 실행으로 command/cwd 전달은 확인하면서 raw stdout/stderr와 local path가 저장되지 않는지 검증했습니다.
  - timeout partial log도 digest/line count만 남기는지 검증했습니다.
  - unsafe command token과 `tools/train.py` 누락 root를 fail-closed 처리하는지 검증했습니다.
  - CLI error summary가 local path, command ref, model artifact ref를 출력하지 않는지 검증했습니다.
- 검증 결과:
  - 새 runner script/test ruff 통과
  - 새 runner 단위 테스트 6개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> PaddleOCR materializer -> fine-tune plan -> trusted execution -> training run registration 연결 회귀 pytest 147개 통과

## 23차 구현 완료

- PaddleOCR fine-tune eval metric trusted-worker 추가
  - `backend/scripts/run_paddleocr_eval_from_finetune_plan.py`가 `paddleocr-finetune-run-plan-v1`과 성공한 `paddleocr-finetune-execution-result-v1`을 함께 검증합니다.
  - official-style PaddleOCR 평가 명령을 `tools/eval.py -c ... -o Global.checkpoints=...` 기준으로 구성합니다.
  - recognition은 공식 문서 흐름에 맞춰 `python3 -m paddle.distributed.launch --gpus ... tools/eval.py ...` 형태를 사용합니다.
  - detection은 `python3 tools/eval.py ... PostProcess.box_thresh=0.6 PostProcess.unclip_ratio=1.5` 형태로 구성합니다.
  - 기본 실행은 dry-run이고, `--execute`가 있을 때만 `subprocess.run(..., shell=False)`로 실행합니다.
  - eval command token은 empty/control character/shell syntax/absolute path/traversal/URL/secret-like marker를 차단하고, `tools/eval.py` 포함을 요구합니다.
  - 성공한 fine-tune execution result가 없으면 실제 eval 실행을 차단합니다.
  - eval stdout/stderr는 raw 저장하지 않고 SHA-256 digest와 line count만 `paddleocr-finetune-eval-result-v1`에 남깁니다.
  - recognition metric은 `acc`, `norm_edit_dis`, detection metric은 `precision`, `recall`, `hmean`이 모두 있을 때만 registration-ready metric JSON으로 승격합니다.
  - `--metrics-output`에는 `register_paddleocr_finetune_run_from_plan.py --metrics-json`에 바로 전달 가능한 flat numeric metric JSON만 씁니다.
  - stdout summary는 metric name/value, command token, PaddleOCR root path, config ref, checkpoint ref, label text, raw OCR text, provider payload를 출력하지 않습니다.
  - return code 0이어도 필수 metric이 없으면 `process_status=metrics_missing`, `metrics_json_ready_for_registration=false`로 fail-closed 처리합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_run_paddleocr_eval_from_finetune_plan.py`
  - dry-run이 eval command/root를 검증하되 실행하지 않는지 검증했습니다.
  - recognition eval에서 `acc`, `norm_edit_dis`만 flat metrics JSON으로 쓰는지 검증했습니다.
  - detection eval에서 `precision`, `recall`, `hmean`을 필수 metric으로 추출하는지 검증했습니다.
  - return code 0이지만 필수 metric이 없으면 registration-ready가 되지 않는지 검증했습니다.
  - timeout partial log가 raw 저장되지 않는지 검증했습니다.
  - 실패한 fine-tune execution result와 unsafe plan ref를 fail-closed 처리하는지 검증했습니다.
- 검증 결과:
  - 새 eval worker script/test ruff 통과
  - 새 eval worker 단위 테스트 7개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> PaddleOCR materializer -> fine-tune plan -> trusted training execution -> trusted eval metric extraction -> training run registration 연결 회귀 pytest 154개 통과

## 24차 구현 완료

- PaddleOCR fine-tune baseline comparison gate 추가
  - `backend/scripts/gate_paddleocr_finetune_against_baseline.py`가 verified fine-tuned metric JSON과 baseline metric JSON을 비교합니다.
  - 이 단계는 DB를 수정하지 않고, `promote_model_candidate.py`가 사용할 수 있는 `paddleocr-promotion-metric-rules-v1` artifact만 생성합니다.
  - recognition 필수 metric은 `acc`, `norm_edit_dis`로 고정했습니다.
  - detection 필수 metric은 `precision`, `recall`, `hmean`으로 고정했습니다.
  - 모든 필수 metric에는 명시적 absolute minimum threshold가 필요합니다.
  - promotion threshold는 `max(absolute_threshold, baseline_value + min_improvement)`로 계산합니다.
  - 현재 지원 metric은 모두 higher-is-better 방향으로만 허용합니다.
  - fine-tuned metric이 absolute threshold를 넘더라도 baseline 대비 개선 조건을 만족하지 못하면 `metric_gate_failed`로 차단합니다.
  - metric JSON은 flat numeric object만 허용하고, path-like key, URL-like key, raw OCR/provider marker는 fail-closed 처리합니다.
  - stdout summary는 metric name/value, local path, artifact ref, raw OCR text, provider payload를 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_gate_paddleocr_finetune_against_baseline.py`
  - recognition metric이 baseline delta와 absolute threshold를 모두 만족할 때 promotion rule artifact를 생성하는지 검증했습니다.
  - detection metric이 absolute threshold를 넘더라도 baseline 대비 regression이면 차단되는지 검증했습니다.
  - task 필수 metric threshold 누락과 metric JSON 필수 metric 누락을 fail-closed로 검증했습니다.
  - unsafe metric name을 거부하는지 검증했습니다.
  - CLI success/error summary가 metric name/value와 local path를 출력하지 않는지 검증했습니다.
- 검증 결과:
  - 새 baseline gate script/test ruff 통과
  - 새 baseline gate 단위 테스트 7개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> PaddleOCR materializer -> fine-tune plan -> trusted training execution -> trusted eval metric extraction -> training run registration -> baseline comparison gate 연결 회귀 pytest 133개 통과
  - backend `scripts`, `src`, 신규 test 기준 broader ruff 통과
  - `git diff --check` 통과

## 25차 구현 완료

- baseline gate artifact와 기존 model promotion CLI 연결
  - `backend/scripts/promote_model_candidate.py`에 `--metric-rules-json` 옵션을 추가했습니다.
  - 입력 schema는 `paddleocr-promotion-metric-rules-v1`만 허용합니다.
  - `allowed_by_baseline_gate=true`인 artifact만 promotion metric rule로 변환합니다.
  - 기존 수동 `--metric-rule`과 새 `--metric-rules-json`을 함께 넘기면 fail-closed 처리합니다.
  - JSON artifact의 metric rule도 기존 `MetricGateRule`로 변환해 `evaluate_model_promotion_gate()` 흐름을 그대로 사용합니다.
  - metric name은 safe character, path/URL/traversal/secret-like marker 검사를 통과해야 합니다.
  - CLI error summary는 metric name/value, local path, artifact ref, operator hash를 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_promote_model_candidate.py`
  - baseline gate가 허용한 JSON artifact가 기존 promotion CLI에서 rule 2개로 평가되는지 검증했습니다.
  - baseline gate가 차단한 artifact는 `--apply`가 있어도 DB commit 없이 거부되는지 검증했습니다.
  - 수동 rule과 JSON rule source를 혼합하면 거부되는지 검증했습니다.
  - path-like metric key가 JSON artifact에 들어오면 summary 유출 없이 거부되는지 검증했습니다.
- 검증 결과:
  - promotion CLI script/test ruff 통과
  - promotion CLI 단위 테스트 8개 통과
  - model training run registration -> candidate registration -> eval result registration -> promotion CLI -> PaddleOCR fine-tune registration -> baseline comparison gate 연결 회귀 pytest 37개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> PaddleOCR materializer -> fine-tune plan -> trusted training execution -> trusted eval metric extraction -> training run registration -> model candidate/eval registration -> promotion CLI -> baseline comparison gate 연결 회귀 pytest 158개 통과
  - backend `scripts`, `src`, 관련 신규 test 기준 broader ruff 통과
  - `git diff --check` 통과

## 26차 구현 완료

- PaddleOCR baseline eval trusted-worker 추가
  - `backend/scripts/run_paddleocr_baseline_eval.py`가 `paddleocr-finetune-run-plan-v1`의 task/config/eval dataset 계약을 재사용해 기존 PaddleOCR baseline checkpoint를 평가합니다.
  - fine-tune 실행 결과는 요구하지 않습니다. baseline은 학습 산출물이 아니라 비교 기준 checkpoint이므로 `--baseline-checkpoint-ref`를 별도로 받습니다.
  - command 구성, command token 검증, PaddleOCR root 검증, metric parsing, stdout/stderr digest 처리는 `run_paddleocr_eval_from_finetune_plan.py`와 같은 helper를 재사용합니다.
  - baseline checkpoint ref는 private relative ref만 허용하고 absolute path, traversal, URL, secret-like marker를 차단합니다.
  - dry-run은 `process_status=validated_not_executed`로 command/root/checkpoint 계약만 검증합니다.
  - `--execute`에는 `--metrics-output`을 필수로 요구해 baseline comparison에 쓸 flat metric JSON 생성을 강제합니다.
  - recognition baseline metric은 `acc`, `norm_edit_dis`, detection baseline metric은 `precision`, `recall`, `hmean`이 모두 있을 때만 `metrics_json_ready_for_comparison=true`가 됩니다.
  - return code 0이어도 필수 metric이 없으면 `process_status=metrics_missing`으로 fail-closed 처리합니다.
  - raw stdout/stderr, command token, PaddleOCR root path, config ref, checkpoint ref, metric name/value, label text, raw OCR text, provider payload는 stdout summary에 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_run_paddleocr_baseline_eval.py`
  - dry-run이 baseline checkpoint/root/config 계약을 검증하되 실행하지 않는지 검증했습니다.
  - recognition baseline eval에서 flat `acc`, `norm_edit_dis` metric JSON을 쓰는지 검증했습니다.
  - detection baseline eval에서 `precision`, `recall`, `hmean`을 필수 metric으로 쓰는지 검증했습니다.
  - execute 모드에서 metrics output이 없으면 fail-closed 처리하는지 검증했습니다.
  - return code 0이지만 필수 metric이 없으면 comparison-ready가 되지 않는지 검증했습니다.
  - unsafe baseline checkpoint ref를 summary 유출 없이 거부하는지 검증했습니다.
- 검증 결과:
  - baseline eval worker script/test ruff 통과
  - baseline eval worker 단위 테스트 6개 통과
  - fine-tune eval -> baseline eval -> baseline comparison gate -> promotion CLI 연결 회귀 pytest 28개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> PaddleOCR materializer -> fine-tune plan -> trusted training execution -> trusted eval metric extraction -> trusted baseline metric extraction -> training run registration -> model candidate/eval registration -> promotion CLI -> baseline comparison gate 연결 회귀 pytest 164개 통과
  - backend `scripts`, `src`, 관련 신규 test 기준 broader ruff 통과
  - `git diff --check` 통과

## 27차 구현 완료

- PaddleOCR promotion readiness preflight 추가
  - `backend/scripts/validate_paddleocr_promotion_artifacts.py`가 promotion 직전 필요한 artifact 체인을 검증합니다.
  - 입력 artifact는 plan, fine-tuned eval result, baseline eval result, baseline comparison gate, promotion rules입니다.
  - 모든 artifact가 같은 `task`를 가리켜야 합니다.
  - fine-tuned eval은 `process_status=metrics_verified`, `metrics_json_ready_for_registration=true`여야 합니다.
  - baseline eval은 `process_status=metrics_verified`, `metrics_json_ready_for_comparison=true`여야 합니다.
  - baseline gate는 `allowed=true`이고 모든 rule이 passed여야 합니다.
  - promotion rules는 `paddleocr-promotion-metric-rules-v1`, `allowed_by_baseline_gate=true`이고 rule count가 baseline gate와 일치해야 합니다.
  - eval artifact가 raw stdout/stderr, raw OCR text, raw provider payload를 보관했다고 표시하면 fail-closed 처리합니다.
  - preflight는 DB를 수정하지 않고 `paddleocr-promotion-readiness-v1` artifact와 redacted summary만 생성합니다.
  - stdout summary는 local path, metric name/value, checkpoint ref, artifact ref, raw OCR/provider payload를 출력하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_validate_paddleocr_promotion_artifacts.py`
  - 일관된 artifact set이 readiness artifact를 생성하는지 검증했습니다.
  - baseline eval이 comparison-ready가 아니면 차단되는지 검증했습니다.
  - artifact task mismatch를 차단하는지 검증했습니다.
  - denied baseline gate를 차단하는지 검증했습니다.
  - baseline gate와 promotion rules의 rule count 불일치를 차단하는지 검증했습니다.
  - eval artifact raw log flag가 true이면 차단되는지 검증했습니다.
- 검증 결과:
  - promotion preflight script/test ruff 통과
  - promotion preflight 단위 테스트 6개 통과
  - fine-tune eval -> baseline eval -> baseline comparison gate -> promotion CLI -> promotion preflight 연결 회귀 pytest 34개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> PaddleOCR materializer -> fine-tune plan -> trusted training execution -> trusted eval metric extraction -> trusted baseline metric extraction -> training run registration -> model candidate/eval registration -> promotion CLI -> baseline comparison gate -> promotion preflight 연결 회귀 pytest 170개 통과
  - backend `scripts`, `src`, 관련 신규 test 기준 broader ruff 통과
  - `git diff --check` 통과

## 28차 구현 완료

- PaddleOCR promotion operator runbook 추가
  - `backend/scripts/build_paddleocr_promotion_runbook.py`가 plan, fine-tuned eval, baseline eval, baseline gate, promotion rules, readiness artifact를 다시 검증합니다.
  - 내부적으로 `validate_paddleocr_promotion_artifacts.py` preflight를 재사용해 artifact chain이 같은 `task`와 통과 상태를 유지하는지 확인합니다.
  - stored readiness artifact도 별도로 검증해 operator가 실제로 검토할 artifact가 `ready_for_promotion=true`, `artifact_count=5`, redaction flag safe 상태인지 확인합니다.
  - output은 `paddleocr-promotion-operator-runbook-v1` artifact이며, promotion 전 확인해야 하는 7개 stage를 순서대로 고정합니다.
  - stage는 plan 확인, fine-tuned eval 확인, baseline eval 확인, baseline gate 확인, promotion rules 확인, readiness preflight 확인, operator approval boundary로 구성됩니다.
  - artifact input은 file name, content hash, path hash만 남기고 local absolute path, metric name/value, checkpoint ref, model artifact ref는 출력하지 않습니다.
  - 이 단계는 DB write, provider call, PaddleOCR training/eval 실행을 하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_paddleocr_promotion_runbook.py`
  - 일관된 artifact chain이 redacted runbook을 생성하는지 검증했습니다.
  - readiness가 promotion-ready가 아니면 차단되는지 검증했습니다.
  - artifact task mismatch를 차단하는지 검증했습니다.
  - unsafe readiness redaction flag를 차단하는지 검증했습니다.
  - CLI error summary가 artifact path, metric name/value를 출력하지 않는지 검증했습니다.
- 검증 결과:
  - promotion runbook script/test ruff 통과
  - promotion runbook 단위 테스트 5개 통과
  - fine-tune eval -> baseline eval -> baseline comparison gate -> promotion CLI -> promotion preflight -> promotion runbook 연결 회귀 pytest 39개 통과
  - taxonomy -> OCR benchmark -> private media -> PaddleOCR improvement -> annotation task -> dataset item -> YOLO/PaddleOCR materializer -> fine-tune/eval/baseline/gate/promotion/runbook 관련 script 회귀 pytest 262개 통과
  - `git diff --check` 통과

## 29차 구현 완료

- Supplement taxonomy DB import read-only verifier 추가
  - `backend/scripts/verify_supplement_taxonomy_db_import.py`가 taxonomy staging manifest와 approved product import manifest를 읽고 실제 DB row 반영 상태를 확인합니다.
  - importer와 같은 manifest validation을 재사용해 `category_seed`, `supplement_product_import`, product-category mapping 계약 drift를 줄였습니다.
  - DB query는 read-only이며 `supplement_categories`, `supplement_products`, `supplement_product_categories` 존재 여부만 확인합니다.
  - 카테고리만 seed된 상태도 검증할 수 있고, `--require-approved-products`로 승인 제품 manifest가 없는 상태를 fail-closed 처리할 수 있습니다.
  - `--fail-on-missing`을 사용하면 expected row 중 하나라도 DB에서 확인되지 않을 때 CLI가 non-zero로 종료합니다.
  - summary는 expected/matched/missing count와 missing key hash만 기록하고, 제품명, 제조사명, source product id 원문, local path, raw OCR/provider payload는 출력하지 않습니다.
  - 이 단계는 DB write, OCR provider call, PaddleOCR 학습/평가 실행을 하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_verify_supplement_taxonomy_db_import.py`
  - 카테고리/제품/매핑이 모두 존재하면 `db_import_verified=true`가 되는지 검증했습니다.
  - product-category mapping 누락을 count/hash 중심으로 보고하는지 검증했습니다.
  - category-only import 상태를 제품 row 없이 검증할 수 있는지 검증했습니다.
  - 승인 제품을 필수로 요구한 경우 product row 부재를 차단하는지 검증했습니다.
  - CLI `--fail-on-missing`과 error summary가 artifact path, 제품명, 제조사명을 출력하지 않는지 검증했습니다.
- 검증 결과:
  - taxonomy verifier script/test ruff 통과
  - taxonomy verifier 단위 테스트 6개 통과
  - taxonomy audit -> staging -> brand review template -> approved import manifest -> DB importer -> read-only DB verifier 회귀 pytest 36개 통과
  - `git diff --check` 통과

## 30차 구현 완료

- Supplement learning pipeline readiness report 추가
  - `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`가 taxonomy DB, brand/product review, review PII screening, OCR ground truth, teacher OCR comparison, YOLO section annotation, PaddleOCR improvement/training/promotion artifact를 하나의 redacted operator checkpoint로 집계합니다.
  - 입력은 `--artifact ROLE=PATH` 반복 형태로 받습니다. 각 role은 schema version을 검증하고 JSON/JSONL 모두 지원합니다.
  - stage는 15개로 고정했습니다.
    - `taxonomy_structure_audit`
    - `taxonomy_db_staging`
    - `brand_product_review`
    - `taxonomy_db_import_verification`
    - `learning_candidate_split`
    - `review_pii_screening`
    - `manual_ocr_ground_truth`
    - `teacher_ocr_comparison`
    - `yolo_section_annotation`
    - `yolo_section_dataset`
    - `paddleocr_improvement_triage`
    - `paddleocr_annotation_tasks`
    - `paddleocr_finetune_plan`
    - `paddleocr_metric_gate`
    - `paddleocr_promotion_runbook`
  - stage status는 `verified`, `pending_operator_review`, `blocked_missing_artifact`, `blocked_invalid_artifact`로 구분합니다.
  - brand review template, PII screening template, OCR ground-truth template, YOLO annotation template처럼 사람 검수가 필요한 중간 산출물이 있으면 누락이 아니라 `pending_operator_review`로 표시합니다.
  - DB verifier의 `db_import_verified=false`, PaddleOCR baseline gate의 `allowed=false`, eval artifact의 `process_status != metrics_verified`, promotion runbook의 `ready_for_operator_review != true`는 semantic blocker로 차단합니다.
  - report와 CLI summary에는 content hash, path hash, role, schema version, record count만 남기고 local absolute path, product literal, raw OCR text, provider payload, image bytes, request header, owner hash는 출력하지 않습니다.
  - 이 단계는 source image read, OCR provider call, LLM call, DB write, PaddleOCR training/eval 실행을 수행하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`
  - template만 있는 단계가 operator-review pending으로 표시되는지 검증했습니다.
  - 전체 artifact chain fixture가 promotion-review checkpoint로 집계되는지 검증했습니다.
  - JSONL approved product import row가 schema/record count 중심으로 요약되는지 검증했습니다.
  - downstream artifact 누락 시 blocker code가 출력되지만 path가 누출되지 않는지 검증했습니다.
  - DB import verification과 PaddleOCR metric gate의 semantic blocker를 검증했습니다.
  - unsafe raw OCR/local path payload가 fail-closed 되고 error summary가 redacted 상태인지 검증했습니다.
- 검증 결과:
  - readiness report script/test ruff 통과
  - readiness report 단위 테스트 6개 통과

## 31차 구현 완료

- 실제 artifact 적용 기준 readiness report parser 보정
  - `/private/tmp`에 남아 있는 실제 audit/staging/candidate/template artifact를 `build_supplement_learning_pipeline_readiness_report.py`에 적용하면서 parser 문제가 확인됐습니다.
  - 원인 1: pretty-printed JSON object는 여러 줄이지만 JSONL이 아닙니다.
  - 원인 2: taxonomy staging artifact는 여러 JSON object가 줄 단위로 이어지는 JSONL입니다.
  - 기존 parser는 여러 줄이면 JSONL로 보는 방식이어서 pretty JSON audit artifact를 깨뜨렸고, 첫 글자가 `{`이면 JSON object로 보는 방식에서는 다중 row JSONL을 깨뜨렸습니다.
  - 수정 후에는 전체 payload를 먼저 JSON object로 parse하고, 실패한 경우에만 JSONL row parser로 fallback합니다.
  - `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`에 다중 row JSONL staging fixture와 pretty-printed JSON audit fixture를 모두 추가했습니다.
- 실제 readiness report 실행 결과:
  - 입력 artifact:
    - `taxonomy_audit`
    - `taxonomy_staging`
    - `brand_review_template`
    - `learning_candidate_summary`
    - `yolo_annotation_template`
  - output: `/private/tmp/lemon-supplement-learning-pipeline-readiness.current.json`
  - `stage_count`: 15
  - `verified_stage_count`: 3
  - `pending_operator_review_stage_count`: 2
  - `blocked_stage_count`: 10
  - `overall_status`: `in_progress_blocked_by_missing_or_invalid_artifacts`
  - 현재 verified:
    - `taxonomy_structure_audit`
    - `taxonomy_db_staging`
    - `learning_candidate_split`
  - 현재 operator-review pending:
    - `brand_product_review`
    - `yolo_section_annotation`
  - 현재 blocked/missing:
    - `taxonomy_db_import_verification`
    - `review_pii_screening`
    - `manual_ocr_ground_truth`
    - `teacher_ocr_comparison`
    - `yolo_section_dataset`
    - `paddleocr_improvement_triage`
    - `paddleocr_annotation_tasks`
    - `paddleocr_finetune_plan`
    - `paddleocr_metric_gate`
    - `paddleocr_promotion_runbook`
- 검증 결과:
  - readiness report script/test ruff 통과
  - readiness report 단위 테스트 7개 통과
  - 실제 `/private/tmp` artifact 기반 readiness report 생성 성공

## 32차 실제 artifact 생성 완료

- 실제 review OCR 후보 기반 PII screening template 생성
  - 입력: `/private/tmp/lemon-supplement-review-ocr-candidates.jsonl`
  - output template: `/private/tmp/lemon-supplement-pii-screening/pii-template.jsonl`
  - output summary: `/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json`
  - private image fixture dir: `/private/tmp/lemon-supplement-pii-screening/images`
  - `candidate_count`: 215
  - `template_row_count`: 215
  - `operator_decision_required_count`: 215
  - `image_materialized_count`: 215
  - `external_transfer_allowed_rows`: 0
  - `teacher_ocr_allowed_rows`: 0
  - `ocr_provider_call_performed`: false
  - `db_write_performed`: false
  - `paddleocr_training_performed`: false
  - template row의 `image_path`는 `images/review-ocr-gt-*.jpg` 형태의 상대 private hashed fixture path입니다.
  - 각 row의 decision stub은 `supplement-review-pii-screening-decision-v1` 형태이며, operator가 직접 PII 여부와 attestation을 채우기 전까지 teacher OCR 전송은 허용되지 않습니다.
- readiness report 재실행 결과:
  - output: `/private/tmp/lemon-supplement-learning-pipeline-readiness.after-pii-template.json`
  - `stage_count`: 15
  - `verified_stage_count`: 3
  - `pending_operator_review_stage_count`: 3
  - `blocked_stage_count`: 9
  - `overall_status`: `in_progress_blocked_by_missing_or_invalid_artifacts`
  - 이전 대비 `review_pii_screening` stage가 `blocked_missing_artifact`에서 `pending_operator_review`로 이동했습니다.
  - 현재 operator-review pending stage:
    - `brand_product_review`
    - `review_pii_screening`
    - `yolo_section_annotation`
- 다음 operator action:
  - `brand_product_review`: brand/product review decision 작성 후 approved product import manifest 생성
  - `review_pii_screening`: PII screening decision 작성 후 no-PII attested row만 teacher OCR 후보로 승격
  - `yolo_section_annotation`: supplement section bbox annotation 작성 후 YOLO export/source-map으로 승격

## Self Review

- 강점: 카테고리/브랜드 후보/이미지 소스 종류를 먼저 분리해 DB 오염을 줄입니다.
- 강점: bbox, OCR, Vision 검증, RAG 출처가 단계별로 남아 hallucination 원인 추적이 가능합니다.
- 리스크: 브랜드 후보는 상품명 prefix 기반이라 오탐이 있습니다. human review 없이 manufacturer로 확정 저장하면 안 됩니다.
- 리스크: 리뷰 이미지는 사용자 생성 이미지일 수 있으므로 PII screening 전 외부 OCR provider로 보내면 안 됩니다.
- 리스크: COCO pretrained YOLO26은 영양제 라벨 섹션 탐지용 모델이 아닙니다. section annotation dataset 없이 production confidence로 쓰면 안 됩니다.
- 리스크: Gemma 4 tag가 Vision payload를 실제 처리하지 못할 수 있습니다. readiness smoke 실패 시 fail-closed 해야 합니다.
- 보완: staging manifest는 category row만 seedable로 두고, brand candidate row는 review 승인 전 DB write 불가로 고정했습니다.
- 보완: 승인된 brand/product review decision도 실제 DB write가 아니라 import manifest까지만 생성해, 별도 검증/마이그레이션 단계 전 DB 오염을 막았습니다.
- 보완: DB importer도 기본 dry-run이며 `--apply`를 명시하지 않으면 세션을 열지 않습니다. approved product manifest가 없는 현재 상태에서는 카테고리 upsert 계획까지만 검증했습니다.
- 보완: `verify_supplement_taxonomy_db_import.py`를 추가해 import 이후 실제 DB에 category/product/category mapping이 존재하는지 read-only로 확인할 수 있게 했습니다.
- 보완: `build_supplement_learning_pipeline_readiness_report.py`를 추가해 전체 objective 기준 남은 human review, 정답지, YOLO label, provider comparison, PaddleOCR promotion gate를 한 번에 확인할 수 있게 했습니다.
- 보완: readiness report parser를 실제 pretty JSON audit artifact와 다중 row JSONL staging artifact 모두 처리하도록 보정했습니다.
- 보완: 실제 review OCR 후보 215개를 PII screening template와 private hashed image fixture로 materialize해 OCR ground truth pipeline의 첫 human-review gate를 준비했습니다.
- 보완: PostgreSQL constraint, Supabase RLS, SQLAlchemy ORM 조회 패턴을 기준으로 이후 실제 import API/service는 owner/raw-data 노출 없이 fail-closed로 붙여야 합니다.
- 보완: PaddleOCR 개선은 provider 비교 결과를 곧바로 학습시키지 않고, 개선 후보 manifest에서 detection/recognition/post-processing/manual triage로 먼저 분류하게 했습니다.
- 보완: improvement summary는 정답 텍스트와 private source ref를 출력하지 않아 operator console 유출 면적을 줄였습니다.
- 보완: PaddleOCR dataset item 승격은 accepted annotation task와 dataset key/task type 일치 검증을 통과한 경우에만 수행합니다.
- 보완: label shape는 기존 training export builder로 검증해 promotion 단계와 export 단계의 schema drift를 줄였습니다.
- 보완: PaddleOCR improvement candidate에서 annotation task로 넘어가는 DB write는 private DB source row가 있는 경우로 제한했습니다. 파일 기반 `crawling-image` 후보는 먼저 private storage/DB materialization이 필요합니다.
- 보완: annotation task seed는 reviewer routing용이며 바로 학습 export에 쓰지 않습니다. accepted label로 바뀌기 전까지 PaddleOCR dataset item으로 승격되지 않습니다.
- 보완: file-only `crawling-image` OCR benchmark fixture를 `MediaObject`로 전환하는 bridge를 추가해 실제 crawling review image가 annotation task 생성 경로로 이어질 수 있게 했습니다.
- 리스크: 새 bridge는 EXIF를 재인코딩해 제거하지 않고 private fixture를 복사하므로 `exif_stripped=False`로 저장합니다. 운영 적용 전 별도 EXIF stripping 단계가 필요하면 이 bridge 앞단이나 storage ingestion service에 추가해야 합니다.
- 리스크: bridge는 local media provider 기준입니다. Supabase/S3 object store에 직접 업로드하는 production import는 별도 storage client adapter와 삭제 retry 정책을 붙여 확장해야 합니다.
- 보완: accepted PaddleOCR annotation task가 `LearningDatasetItem`에 멈추지 않고, 공식 PaddleOCR detection/recognition label txt 파일까지 이어지도록 materializer를 추가했습니다.
- 리스크: recognition 학습은 crop image가 전제입니다. 현재 materializer는 source map이 가리키는 이미지를 그대로 복사하므로, 전체 리뷰 이미지를 recognition source로 넣으면 학습 품질이 나빠집니다. detection box 기반 crop 생성 단계는 별도 구현이 필요합니다.
- 리스크: detection materializer는 normalized rectangle을 4점 polygon으로 변환합니다. 회전/곡선 textline annotation을 지원하려면 label snapshot schema를 polygon points 기반으로 확장해야 합니다.
- 보완: recognition export/materializer에 optional `crop_box`를 추가해 전체 source image에서도 reviewer가 승인한 text-line crop을 생성할 수 있게 했습니다.
- 리스크: `crop_box`는 여전히 axis-aligned rectangle입니다. 기울어진 텍스트, 곡면 라벨, 원통형 병 이미지의 왜곡 보정은 polygon crop 또는 perspective transform 단계가 필요합니다.
- 보완: PaddleOCR materialized dataset이 바로 임의 training command로 넘어가지 않도록 `build_paddleocr_finetune_run_plan.py`를 추가했습니다. train split, relative image ref, detection JSON label, hyperparameter bound, private relative model refs를 먼저 검증합니다.
- 리스크: fine-tune run plan은 command token을 생성하지만 실제 PaddleOCR checkout, GPU runtime, pre-trained model 파일 존재, config 내부 dataset 경로 rewrite는 실행하지 않습니다. 실제 학습 runner는 plan 검증 후 별도 trusted-worker 단계로 분리해야 합니다.
- 보완: `register_paddleocr_finetune_run_from_plan.py`를 추가해 verified training metrics가 있는 완료 run만 plan에서 직접 `model_training_runs`로 등록되게 했습니다. 성공 run은 metric 누락을 허용하지 않고, 실패 run은 artifact ref를 저장하지 않습니다.
- 리스크: 이 bridge도 학습 실행/평가를 대신하지 않습니다. 실제 PaddleOCR train/eval command output을 검증하고 metric JSON을 생성하는 trusted-worker가 다음 단계로 필요합니다.
- 보완: `run_paddleocr_finetune_plan.py`를 추가해 plan 검증과 실제 PaddleOCR training subprocess 실행 사이의 trusted-worker 경계를 만들었습니다. 실행 로그는 raw 저장하지 않고 digest/line count만 남깁니다.
- 리스크: runner는 학습 프로세스 실행 여부와 return code만 추적합니다. 모델 품질 검증, eval command 실행, metric JSON 생성은 아직 별도 trusted eval worker가 필요합니다.
- 리스크: runner는 local PaddleOCR root의 `tools/train.py` 존재를 확인하지만, config 내부 dataset path rewrite, pretrained model file 존재, GPU runtime compatibility까지 보장하지 않습니다. 실제 운영 전 PaddleOCR checkout bootstrap 검증 단계를 추가해야 합니다.
- 보완: `run_paddleocr_eval_from_finetune_plan.py`를 추가해 PaddleOCR eval 실행과 metric JSON 생성 경계를 만들었습니다. 성공 training result가 있어야 실행되며, raw eval log는 저장하지 않습니다.
- 보완: registration-ready metric은 task별 필수 metric이 모두 있을 때만 생성합니다. 단순 return code 0을 성공 metric으로 취급하지 않습니다.
- 리스크: eval worker는 PaddleOCR 로그의 metric dict를 파싱합니다. PaddleOCR 버전이나 config에 따라 metric key가 달라지면 `metrics_missing`으로 차단됩니다. 운영 전 사용 모델/config별 sample eval log를 고정 fixture로 추가해야 합니다.
- 보완: `gate_paddleocr_finetune_against_baseline.py`를 추가해 return code나 metric extraction 성공만으로 모델 승격이 진행되지 않게 했습니다. 기존 baseline 대비 개선 조건과 절대 threshold를 함께 만족해야 promotion rule artifact를 만들 수 있습니다.
- 보완: `run_paddleocr_baseline_eval.py`를 추가해 현재 production PaddleOCR 또는 frozen baseline checkpoint를 동일 eval dataset/config에서 평가하고 baseline metric JSON을 생성할 수 있게 했습니다.
- 리스크: baseline gate는 현재 `acc`, `norm_edit_dis`, `precision`, `recall`, `hmean`처럼 higher-is-better metric만 지원합니다. CER/WER 같은 lower-is-better metric을 직접 넣으려면 metric direction 계약을 확장해야 합니다.
- 보완: `promote_model_candidate.py --metric-rules-json`을 추가해 baseline gate가 만든 promotion rule artifact를 기존 DB-backed model promotion CLI가 직접 읽을 수 있게 했습니다.
- 보완: `validate_paddleocr_promotion_artifacts.py`를 추가해 promotion 직전 plan, fine-tuned eval, baseline eval, baseline gate, promotion rules가 서로 같은 task와 통과 상태인지 검증할 수 있게 했습니다.
- 보완: `build_paddleocr_promotion_runbook.py`를 추가해 preflight 이후 operator가 검토할 artifact chain과 promotion boundary를 순서화했습니다.
- 리스크: readiness report는 artifact 상태 집계 도구입니다. 실제 operator review, 실제 DB apply, live provider 비교, PaddleOCR train/eval, 모델 promotion 실행을 대신하지 않습니다.
- 리스크: PII screening template는 operator decision stub만 제공합니다. 아직 어떤 review image도 no-PII로 승인되지 않았으므로 CLOVA/Google Vision teacher OCR 호출은 계속 금지 상태입니다.
- 리스크: runbook은 아직 실제 CI job이 아니며, PaddleOCR checkout/GPU 환경에서 train/eval command를 실행하지 않습니다. 다음 단계에서는 이 runbook을 CI 또는 trusted-worker job template로 연결해야 합니다.

## 33차 구현 완료

- `backend/scripts/build_supplement_pii_screening_review_bundle.py`
  - `export_supplement_review_pii_screening_template.py`가 만든 local-only PII screening template를 운영자 검토용 bundle로 변환합니다.
  - `review-index.html`, `decisions.todo.jsonl`, `README.md`, `summary.json`를 생성합니다.
  - HTML은 `images/...` 상대 경로만 참조하고, bundle 내부로 materialized review image를 복사합니다.
  - decision template는 사람이 채우기 전까지 `decision=""`, attestation false 상태이므로 teacher OCR gate를 자동으로 열지 않습니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR text, provider payload, image bytes는 출력하지 않습니다.
  - 이 단계도 OCR provider 호출, DB write, PaddleOCR 학습을 수행하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `pii_screening_review_bundle` artifact를 추가했습니다.
  - `review_pii_screening` stage는 이제 `pii_screening_template`뿐 아니라 실제 로컬 review bundle도 pending evidence로 표시합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_pii_screening_review_bundle.py`
  - bundle HTML/decision template/README/summary 생성 검증
  - bundle 내부 image copy 검증
  - image path가 상대 `images/...` 경계에 머무는지 검증
  - absolute path, raw OCR/provider field 미노출 검증
- 실제 실행 결과:
  - `reviewable_row_count`: 215
  - `decision_template_row_count`: 215
  - `image_copied_count`: 215
  - `external_transfer_allowed_rows`: 0
  - `teacher_ocr_allowed_rows`: 0
  - readiness report: 3 verified / 3 operator pending / 9 blocked
  - `review_pii_screening` present pending roles: `pii_screening_template`, `pii_screening_review_bundle`

## 34차 구현 완료

- `backend/scripts/build_supplement_yolo_annotation_review_bundle.py`
  - `export_supplement_yolo_annotation_template.py`가 만든 상세페이지 bbox annotation template를 운영자 작업 bundle로 변환합니다.
  - `annotation-index.html`, `annotation.todo.jsonl`, `label-studio-tasks.json`, `README.md`, `summary.json`를 생성합니다.
  - HTML index는 materialized detail-page 이미지를 상대경로로만 참조합니다.
  - `annotation.todo.jsonl`은 사람이 `label_snapshot.boxes`를 normalized `xywh` source-image coordinate로 채울 수 있는 편집본입니다.
  - `label-studio-tasks.json`는 로컬 annotation tool import를 돕는 task 목록이며, 이미지 경로는 bundle 내부 상대경로만 사용합니다.
  - label class는 `product_identity`, `supplement_facts`, `ingredient_amounts`, `intake_method`, `precautions`, `other_ingredients`, `functional_claims`로 제한합니다.
  - 승인 전까지 `training_export_allowed_rows=0`이고, 실제 YOLO label txt 생성은 `promote_supplement_yolo_annotation_template.py`와 materializer 이후로 분리됩니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR text, provider payload, image bytes는 출력하지 않습니다.
  - 이 단계도 OCR provider 호출, LLM 호출, DB write, training export를 수행하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `yolo_annotation_review_bundle` artifact를 추가했습니다.
  - `yolo_section_annotation` stage는 이제 `yolo_annotation_template`뿐 아니라 실제 로컬 bbox review bundle도 pending evidence로 표시합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_yolo_annotation_review_bundle.py`
  - bundle HTML/annotation template/Label Studio task/README/summary 생성 검증
  - bundle 내부 image copy 검증
  - image path가 안전한 상대경로에 머무는지 검증
  - unknown label, absolute path, raw OCR/provider field 차단 검증
- 실제 실행 결과:
  - `candidate_count`: 205
  - `template_row_count`: 205
  - `reviewable_row_count`: 205
  - `annotation_template_row_count`: 205
  - `label_studio_task_count`: 205
  - `image_copied_count`: 205
  - `training_export_allowed_rows`: 0
  - readiness report: 3 verified / 3 operator pending / 9 blocked
  - `yolo_section_annotation` present pending roles: `yolo_annotation_template`, `yolo_annotation_review_bundle`

## 35차 구현 완료

- `backend/scripts/build_supplement_brand_review_bundle.py`
  - `export_supplement_brand_review_template.py`가 만든 brand/product review template를 운영자 작업 bundle로 변환합니다.
  - `review-index.html`, `review.csv`, `decisions.todo.jsonl`, `README.md`, `summary.json`를 생성합니다.
  - `review.csv`는 spreadsheet 보조 자료이고, 실제 apply 입력은 사람이 편집한 `decisions.todo.jsonl`입니다.
  - `decisions.todo.jsonl`은 `supplement-brand-review-decision-v1` row를 그대로 복사하되, 승인 전 attestation은 모두 `false`로 유지합니다.
  - 승인 전까지 `approved_for_db_write_rows=0`이며 실제 DB import manifest 생성은 `apply_supplement_brand_review_decisions.py` 이후로 분리됩니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR text, provider payload, image bytes는 출력하지 않습니다.
  - 이 단계도 OCR provider 호출, LLM 호출, DB write, training export를 수행하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `brand_review_bundle` artifact를 추가했습니다.
  - `brand_product_review` stage는 이제 `brand_review_template`뿐 아니라 실제 로컬 brand/product review bundle도 pending evidence로 표시합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_brand_review_bundle.py`
  - bundle HTML/CSV/decision template/README/summary 생성 검증
  - pre-approved row가 bundle로 들어가지 않는지 검증
  - duplicate fixture id가 operator decision을 모호하게 만들지 않도록 차단하는지 검증
  - local path/URL literal과 raw OCR/provider field 차단 검증
  - CLI summary redaction 검증
- 실제 실행 결과:
  - `template_row_count`: 388
  - `reviewable_row_count`: 388
  - `decision_template_row_count`: 388
  - `operator_decision_required_count`: 388
  - `brand_candidate_count`: 51
  - `approved_for_db_write_rows`: 0
  - `skip_reason_counts`: `{}`
  - readiness report: 3 verified / 3 operator pending / 9 blocked
  - `brand_product_review` present pending roles: `brand_review_template`, `brand_review_bundle`

## 36차 구현 완료

- `backend/scripts/build_supplement_ocr_ground_truth_review_bundle.py`
  - `export_supplement_ocr_ground_truth_template.py`가 만든 PII-cleared review OCR ground-truth template를 운영자 작업 bundle로 변환합니다.
  - `ground-truth-index.html`, `ground-truth.todo.jsonl`, `README.md`, `summary.json`를 생성합니다.
  - HTML index는 materialized review 이미지를 상대경로로만 참조합니다.
  - `ground-truth.todo.jsonl`은 사람이 `expected` 객체에 제품명, 제조사, 성분명, 함량, 단위, 섭취 방법, 주의사항, label section을 채울 수 있는 편집본입니다.
  - operator가 double-check 후 `ground_truth_status=human_reviewed`, `expected.verification_status=human_reviewed`, `ready_for_benchmark_after_review=true`로 바꾼 row만 `build_supplement_ocr_benchmark_manifest.py`의 benchmark fixture 후보가 됩니다.
  - 원본 절대경로, 상품 폴더 literal, raw OCR text, provider payload, image bytes는 출력하지 않습니다.
  - 이 단계도 OCR provider 호출, LLM 호출, DB write, PaddleOCR training을 수행하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `ocr_ground_truth_review_bundle` artifact를 추가했습니다.
  - `manual_ocr_ground_truth` stage는 이제 `ocr_ground_truth_template`뿐 아니라 실제 로컬 ground-truth review bundle도 pending evidence로 표시합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_ground_truth_review_bundle.py`
  - bundle HTML/editable JSONL/README/summary 생성 검증
  - materialized image copy 검증
  - PII-cleared/teacher-OCR eligible gate 검증
  - absolute image path, missing image, duplicate or unsafe row 차단 검증
  - CLI summary redaction 검증
- 실제 `/private/tmp` 상태:
  - `pii_screening_apply` artifact는 아직 존재하지 않습니다.
  - `review_pii_screening` stage는 `pii_screening_template`, `pii_screening_review_bundle` pending evidence를 가진 operator-review pending 상태입니다.
  - `manual_ocr_ground_truth` stage는 아직 `ocr_ground_truth_template`/`ocr_ground_truth_review_bundle` artifact가 없어 blocked 상태입니다.
  - 따라서 실제 215개 review image용 OCR GT bundle 생성은 사람이 PII decisions를 작성하고 `apply_supplement_review_pii_screening_decisions.py`를 실행한 뒤 진행해야 합니다.

## 검증 명령

```bash
cd backend
.venv/bin/python -m ruff check scripts/audit_supplement_crawling_image_taxonomy.py scripts/build_supplement_taxonomy_db_staging.py scripts/build_supplement_learning_candidate_manifests.py Nutrition-backend/tests/unit/scripts/test_audit_supplement_crawling_image_taxonomy.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_candidate_manifests.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_audit_supplement_crawling_image_taxonomy.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_candidate_manifests.py
.venv/bin/python scripts/build_supplement_taxonomy_db_staging.py --root ../data/nutrition_reference/crawling-image --output /private/tmp/lemon-supplement-taxonomy-staging.jsonl --summary /private/tmp/lemon-supplement-taxonomy-staging.summary.json --source-run-id 2026-06-03-taxonomy-staging
.venv/bin/python scripts/build_supplement_learning_candidate_manifests.py --root ../data/nutrition_reference/crawling-image --ocr-output /private/tmp/lemon-supplement-review-ocr-candidates.jsonl --yolo-output /private/tmp/lemon-supplement-detail-yolo-candidates.jsonl --summary /private/tmp/lemon-supplement-learning-candidates.summary.json --source-run-id 2026-06-03-learning-candidates
.venv/bin/python -m ruff check scripts/build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py
.venv/bin/python -m ruff check scripts/export_supplement_ocr_ground_truth_template.py Nutrition-backend/tests/unit/scripts/test_export_supplement_ocr_ground_truth_template.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_supplement_ocr_ground_truth_template.py
.venv/bin/python -m ruff check scripts/export_supplement_yolo_annotation_template.py Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py
.venv/bin/python -m ruff check scripts/export_supplement_review_pii_screening_template.py Nutrition-backend/tests/unit/scripts/test_export_supplement_review_pii_screening_template.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_supplement_review_pii_screening_template.py
.venv/bin/python -m ruff check scripts/apply_supplement_review_pii_screening_decisions.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_review_pii_screening_decisions.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_apply_supplement_review_pii_screening_decisions.py
.venv/bin/python scripts/audit_supplement_crawling_image_taxonomy.py --root ../data/nutrition_reference/crawling-image --output /private/tmp/lemon-supplement-taxonomy-audit.current.json
.venv/bin/python scripts/build_supplement_taxonomy_db_staging.py --root ../data/nutrition_reference/crawling-image --output /private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --summary /private/tmp/lemon-supplement-taxonomy-staging.current.summary.json --source-run-id 2026-06-03-taxonomy-refresh
.venv/bin/python -m ruff check scripts/audit_supplement_crawling_image_taxonomy.py scripts/build_supplement_taxonomy_db_staging.py scripts/build_supplement_learning_candidate_manifests.py scripts/export_supplement_review_pii_screening_template.py scripts/apply_supplement_review_pii_screening_decisions.py scripts/export_supplement_ocr_ground_truth_template.py scripts/build_supplement_ocr_benchmark_manifest.py scripts/export_supplement_yolo_annotation_template.py Nutrition-backend/tests/unit/scripts/test_audit_supplement_crawling_image_taxonomy.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_candidate_manifests.py Nutrition-backend/tests/unit/scripts/test_export_supplement_review_pii_screening_template.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_review_pii_screening_decisions.py Nutrition-backend/tests/unit/scripts/test_export_supplement_ocr_ground_truth_template.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_audit_supplement_crawling_image_taxonomy.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_candidate_manifests.py Nutrition-backend/tests/unit/scripts/test_export_supplement_review_pii_screening_template.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_review_pii_screening_decisions.py Nutrition-backend/tests/unit/scripts/test_export_supplement_ocr_ground_truth_template.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py
.venv/bin/python -m ruff check scripts/evaluate_ocr_three_tier.py Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py
.venv/bin/python -m ruff check scripts/promote_supplement_yolo_annotation_template.py Nutrition-backend/tests/unit/scripts/test_promote_supplement_yolo_annotation_template.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_promote_supplement_yolo_annotation_template.py
.venv/bin/python -m ruff check scripts/export_supplement_brand_review_template.py scripts/apply_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_export_supplement_brand_review_template.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_brand_review_decisions.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_supplement_brand_review_template.py Nutrition-backend/tests/unit/scripts/test_apply_supplement_brand_review_decisions.py
.venv/bin/python -m ruff check scripts/import_supplement_taxonomy_approved_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_import_supplement_taxonomy_approved_manifest.py
.venv/bin/python scripts/import_supplement_taxonomy_approved_manifest.py --taxonomy-staging /private/tmp/lemon-supplement-taxonomy-staging.importer-check.jsonl --summary /private/tmp/lemon-supplement-taxonomy-importer-check.summary.json
.venv/bin/python -m ruff check scripts/build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py
.venv/bin/python -m ruff check scripts/promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py
.venv/bin/python -m ruff check scripts/create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py
.venv/bin/python -m ruff check scripts/import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py
.venv/bin/python -m ruff check scripts/materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m ruff check Nutrition-backend/src/learning/retraining.py scripts/materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m ruff check scripts/build_supplement_ocr_benchmark_manifest.py scripts/import_supplement_benchmark_fixtures_as_media_objects.py scripts/build_paddleocr_improvement_candidates.py scripts/create_paddleocr_annotation_tasks_from_improvement_candidates.py scripts/promote_paddleocr_annotation_tasks_to_dataset.py scripts/export_training_manifest.py scripts/materialize_paddleocr_dataset.py Nutrition-backend/src/learning/retraining.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m ruff check scripts/build_paddleocr_finetune_run_plan.py scripts/materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py
.venv/bin/python -m ruff check scripts/build_supplement_ocr_benchmark_manifest.py scripts/import_supplement_benchmark_fixtures_as_media_objects.py scripts/build_paddleocr_improvement_candidates.py scripts/create_paddleocr_annotation_tasks_from_improvement_candidates.py scripts/promote_paddleocr_annotation_tasks_to_dataset.py scripts/export_training_manifest.py scripts/materialize_paddleocr_dataset.py scripts/build_paddleocr_finetune_run_plan.py Nutrition-backend/src/learning/retraining.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py
.venv/bin/python -m ruff check scripts/register_paddleocr_finetune_run_from_plan.py Nutrition-backend/tests/unit/scripts/test_register_paddleocr_finetune_run_from_plan.py scripts/build_paddleocr_finetune_run_plan.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py scripts/register_model_training_run.py Nutrition-backend/tests/unit/scripts/test_register_model_training_run.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_register_paddleocr_finetune_run_from_plan.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py Nutrition-backend/tests/unit/scripts/test_register_model_training_run.py
.venv/bin/python -m ruff check scripts/build_supplement_ocr_benchmark_manifest.py scripts/import_supplement_benchmark_fixtures_as_media_objects.py scripts/build_paddleocr_improvement_candidates.py scripts/create_paddleocr_annotation_tasks_from_improvement_candidates.py scripts/promote_paddleocr_annotation_tasks_to_dataset.py scripts/export_training_manifest.py scripts/materialize_paddleocr_dataset.py scripts/build_paddleocr_finetune_run_plan.py scripts/register_paddleocr_finetune_run_from_plan.py scripts/register_model_training_run.py Nutrition-backend/src/learning/retraining.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py Nutrition-backend/tests/unit/scripts/test_register_paddleocr_finetune_run_from_plan.py Nutrition-backend/tests/unit/scripts/test_register_model_training_run.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_benchmark_manifest.py Nutrition-backend/tests/unit/scripts/test_import_supplement_benchmark_fixtures_as_media_objects.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_create_paddleocr_annotation_tasks_from_improvement_candidates.py Nutrition-backend/tests/unit/scripts/test_promote_paddleocr_annotation_tasks_to_dataset.py Nutrition-backend/tests/unit/scripts/test_export_training_manifest.py Nutrition-backend/tests/unit/scripts/test_materialize_paddleocr_dataset.py Nutrition-backend/tests/unit/scripts/test_build_paddleocr_finetune_run_plan.py Nutrition-backend/tests/unit/scripts/test_register_paddleocr_finetune_run_from_plan.py Nutrition-backend/tests/unit/scripts/test_register_model_training_run.py
.venv/bin/python -m ruff check scripts/run_paddleocr_finetune_plan.py Nutrition-backend/tests/unit/scripts/test_run_paddleocr_finetune_plan.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_run_paddleocr_finetune_plan.py
.venv/bin/python -m ruff check scripts/run_paddleocr_eval_from_finetune_plan.py Nutrition-backend/tests/unit/scripts/test_run_paddleocr_eval_from_finetune_plan.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_run_paddleocr_eval_from_finetune_plan.py
.venv/bin/python -m ruff check scripts/build_supplement_pii_screening_review_bundle.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_build_supplement_pii_screening_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_pii_screening_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/build_supplement_pii_screening_review_bundle.py --template /private/tmp/lemon-supplement-pii-screening/pii-template.jsonl --output-dir /private/tmp/lemon-supplement-pii-screening/review-bundle --source-run-id 2026-06-03-pii-screening-review-bundle
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template.summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-pii-review-bundle.json
.venv/bin/python -m ruff check scripts/export_supplement_yolo_annotation_template.py scripts/build_supplement_yolo_annotation_review_bundle.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py Nutrition-backend/tests/unit/scripts/test_build_supplement_yolo_annotation_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_supplement_yolo_annotation_template.py Nutrition-backend/tests/unit/scripts/test_build_supplement_yolo_annotation_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/export_supplement_yolo_annotation_template.py --candidate-manifest /private/tmp/lemon-supplement-detail-yolo-candidates.jsonl --output /private/tmp/lemon-supplement-yolo-annotation-template-full.jsonl --summary /private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --source-root ../data/nutrition_reference/crawling-image --materialized-image-dir /private/tmp/lemon-supplement-yolo-annotation-template-full-images --source-run-id 2026-06-03-yolo-annotation-template-full --limit 500
.venv/bin/python scripts/build_supplement_yolo_annotation_review_bundle.py --template /private/tmp/lemon-supplement-yolo-annotation-template-full.jsonl --output-dir /private/tmp/lemon-supplement-yolo-annotation-review-bundle --source-run-id 2026-06-03-yolo-annotation-review-bundle
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-yolo-review-bundle.json
.venv/bin/python -m ruff check scripts/build_supplement_brand_review_bundle.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_build_supplement_brand_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_brand_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/build_supplement_brand_review_bundle.py --template /private/tmp/lemon-supplement-brand-review-template.jsonl --output-dir /private/tmp/lemon-supplement-brand-review-bundle --source-run-id 2026-06-03-brand-review-bundle
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-brand-review-bundle.json
.venv/bin/python -m ruff check scripts/build_supplement_ocr_ground_truth_review_bundle.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_ground_truth_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_ocr_ground_truth_review_bundle.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-ocr-gt-bundle-implementation.json
git diff --check
```

## 37차 구현 완료 - PII screening decision preflight

### 구현 파일

- `backend/scripts/preflight_supplement_review_pii_screening_decisions.py`
  - 운영자가 수정한 `decisions.todo.jsonl`을 `apply_supplement_review_pii_screening_decisions.py`에 넣기 전 검증하는 redacted preflight를 추가했습니다.
  - blank stub은 자동 승인하지 않고 `blank_decision_count`와 `pending_operator_action_count`로 집계합니다.
  - 유효한 partial decision은 `ready_for_partial_apply`, 전체 review 완료 기준은 `ready_for_strict_apply`로 분리했습니다.
  - DB write, OCR provider call, PaddleOCR training, source image read를 수행하지 않습니다.
  - raw OCR/provider payload, absolute path, product directory literal을 summary에 저장하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `pii_screening_decision_preflight` artifact role을 추가했습니다.
  - `review_pii_screening` stage가 template, review bundle뿐 아니라 preflight evidence도 pending evidence로 인식합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_preflight_supplement_review_pii_screening_decisions.py`
  - blank stub, valid partial apply, strict apply, invalid/unsafe decision, CLI redaction을 검증했습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`
  - preflight artifact가 readiness pending evidence로 표시되는 회귀 테스트를 추가했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json`
  - `/private/tmp/lemon-supplement-learning-pipeline-readiness.after-pii-decision-preflight.json`
- 실제 preflight 결과:
  - `candidate_row_count`: 215
  - `decision_row_count`: 215
  - `blank_decision_count`: 215
  - `valid_decision_count`: 0
  - `ready_for_partial_apply`: false
  - `ready_for_strict_apply`: false
  - `ready_for_requested_apply`: false
  - `next_operator_action`: `complete_operator_pii_review`
- 해석:
  - 현재 decision bundle은 아직 사람이 PII screening 결정을 채우지 않은 상태입니다.
  - 따라서 `pii_screening_apply`는 아직 실행하면 안 됩니다.
  - 사람이 각 row를 검토해 no-PII attestation 또는 차단 decision을 작성한 뒤 preflight를 다시 통과해야 OCR ground truth template 생성 단계로 넘어갈 수 있습니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/preflight_supplement_review_pii_screening_decisions.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_review_pii_screening_decisions.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_preflight_supplement_review_pii_screening_decisions.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/preflight_supplement_review_pii_screening_decisions.py --candidate-manifest /private/tmp/lemon-supplement-review-ocr-candidates.jsonl --decisions /private/tmp/lemon-supplement-pii-screening/review-bundle/decisions.todo.jsonl --output /private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --require-all-reviewed
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact pii_screening_decision_preflight=/private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-pii-decision-preflight.json
```

## 38차 구현 완료 - Brand/product review decision preflight

### 구현 파일

- `backend/scripts/preflight_supplement_brand_review_decisions.py`
  - 운영자가 수정한 brand/product `decisions.todo.jsonl`을 `apply_supplement_brand_review_decisions.py`에 넣기 전 검증하는 redacted preflight를 추가했습니다.
  - blank stub은 자동 승인하지 않고 `blank_decision_count`, `pending_operator_action_count`로 집계합니다.
  - `approve` decision은 제조사, 제품명, DB import attestation을 모두 요구합니다.
  - partial apply와 strict apply를 각각 `ready_for_partial_apply`, `ready_for_strict_apply`로 분리합니다.
  - DB write, OCR provider call, LLM call을 수행하지 않습니다.
  - raw OCR/provider payload, absolute path, product directory literal을 summary에 저장하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `brand_review_decision_preflight` artifact role을 추가했습니다.
  - `brand_product_review` stage가 template, review bundle뿐 아니라 preflight evidence도 pending evidence로 인식합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_preflight_supplement_brand_review_decisions.py`
  - blank stub, valid partial apply, strict apply, invalid/unsafe decision, CLI redaction을 검증했습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`
  - brand preflight artifact가 readiness pending evidence로 표시되는 회귀 테스트를 추가했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json`
  - `/private/tmp/lemon-supplement-learning-pipeline-readiness.after-brand-decision-preflight.json`
- 실제 brand preflight 결과:
  - `brand_candidate_count`: 388
  - `decision_row_count`: 388
  - `blank_decision_count`: 388
  - `valid_decision_count`: 0
  - `approved_decision_count`: 0
  - `ready_for_partial_apply`: false
  - `ready_for_strict_apply`: false
  - `ready_for_requested_apply`: false
  - `next_operator_action`: `complete_operator_brand_review`
- 해석:
  - 현재 brand decision bundle은 아직 사람이 category/brand/product 결정을 채우지 않은 상태입니다.
  - 따라서 `approved_product_import` manifest는 아직 생성하면 안 됩니다.
  - 사람이 각 row에 제조사/제품명/승인 또는 차단 decision을 작성한 뒤 preflight를 다시 통과해야 DB import manifest 생성 및 read-only DB verification으로 넘어갈 수 있습니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/preflight_supplement_brand_review_decisions.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_preflight_supplement_brand_review_decisions.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/preflight_supplement_brand_review_decisions.py --taxonomy-staging /private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --decisions /private/tmp/lemon-supplement-brand-review-bundle/decisions.todo.jsonl --output /private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json --require-all-reviewed
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact brand_review_decision_preflight=/private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact pii_screening_decision_preflight=/private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-brand-decision-preflight.json
```

## 39차 구현 완료 - YOLO section bbox annotation decision preflight

### 구현 파일

- `backend/scripts/preflight_supplement_yolo_annotation_decisions.py`
  - 운영자가 수정한 `annotation.todo.jsonl`을 `promote_supplement_yolo_annotation_template.py`에 넣기 전 검증하는 redacted preflight를 추가했습니다.
  - `annotation_status`, `training_export_allowed`, `human_review_required`, section bbox label, normalized xywh, positive bbox area, fixture image hash를 aggregate로 검증합니다.
  - blank bbox stub은 자동 승인하지 않고 `blank_box_row_count`, `pending_review_row_count`, `pending_operator_action_count`로 집계합니다.
  - partial promotion과 strict promotion을 각각 `ready_for_partial_promotion`, `ready_for_strict_promotion`으로 분리합니다.
  - DB write, OCR provider call, LLM call, training, export artifact/source-map write를 수행하지 않습니다.
  - fixture image read는 `image_sha256` integrity check 용도로만 수행하고, source ref/image path/label/raw OCR/provider payload/product literal은 출력하지 않습니다.
- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `yolo_annotation_decision_preflight` artifact role을 추가했습니다.
  - `yolo_section_annotation` stage가 annotation template, review bundle뿐 아니라 preflight evidence도 pending evidence로 인식합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_preflight_supplement_yolo_annotation_decisions.py`
  - blank/pending stub, accepted row, strict mode, invalid bbox area, unsafe raw OCR text, CLI redaction을 검증했습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`
  - YOLO annotation preflight artifact가 readiness pending evidence로 표시되는 회귀 테스트를 추가했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-yolo-annotation-review-bundle/decision-preflight.current.json`
  - `/private/tmp/lemon-supplement-learning-pipeline-readiness.after-yolo-decision-preflight.json`
- 실제 YOLO annotation preflight 결과:
  - `template_row_count`: 205
  - `pending_review_row_count`: 205
  - `blank_box_row_count`: 205
  - `reviewed_box_row_count`: 0
  - `valid_accepted_row_count`: 0
  - `invalid_row_count`: 0
  - `image_missing_or_unresolved_count`: 0
  - `image_sha256_mismatch_count`: 0
  - `ready_for_partial_promotion`: false
  - `ready_for_strict_promotion`: false
  - `ready_for_requested_promotion`: false
  - `next_operator_action`: `complete_supplement_section_bbox_review`
- readiness 결과:
  - `provided_artifact_count`: 12
  - `verified_stage_count`: 3
  - `pending_operator_review_stage_count`: 3
  - `blocked_stage_count`: 9
  - `yolo_section_annotation`: `pending_operator_review`
  - `present_pending_roles`: `yolo_annotation_template`, `yolo_annotation_review_bundle`, `yolo_annotation_decision_preflight`
- 해석:
  - 현재 detail-page YOLO bundle은 이미지 fixture와 template는 준비됐지만, 사람이 section bbox를 아직 그리지 않은 상태입니다.
  - 따라서 `yolo_template_promotion`과 dataset materialization은 아직 실행하면 안 됩니다.
  - 사람이 `product_identity`, `supplement_facts`, `ingredient_amounts`, `intake_method`, `precautions`, `other_ingredients`, `functional_claims` bbox를 작성하고 accepted flag를 설정한 뒤 preflight를 다시 통과해야 YOLO export/source-map 승격으로 넘어갈 수 있습니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/preflight_supplement_yolo_annotation_decisions.py scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_yolo_annotation_decisions.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_preflight_supplement_yolo_annotation_decisions.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/preflight_supplement_yolo_annotation_decisions.py --template /private/tmp/lemon-supplement-yolo-annotation-review-bundle/annotation.todo.jsonl --source-map /private/tmp/lemon-supplement-yolo-annotation-review-bundle/source-map.json --output /private/tmp/lemon-supplement-yolo-annotation-review-bundle/decision-preflight.current.json --require-all-reviewed
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit-current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging-current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact brand_review_decision_preflight=/private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact pii_screening_decision_preflight=/private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --artifact yolo_annotation_decision_preflight=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/decision-preflight.current.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.after-yolo-decision-preflight.json
git diff --check
```

## 40차 구현 완료 - 통합 operator review queue/runbook

### 구현 파일

- `backend/scripts/build_supplement_operator_review_queue.py`
  - brand/product review, review-image PII screening, YOLO section bbox annotation preflight summary를 하나의 redacted operator queue로 집계하는 스크립트를 추가했습니다.
  - 입력은 preflight/readiness summary JSON만 허용하며, 원본 이미지, OCR 원문, provider payload, DB record, 모델 응답, 로컬 경로 literal은 읽거나 출력하지 않습니다.
  - 각 큐는 `queue_key`, readiness stage status, total/pending/blank/valid count, next action만 노출합니다.
  - 미등록 source documentation URL은 fail-closed로 거부하되, 기존 preflight들이 사용하는 PostgreSQL, Supabase, SQLAlchemy, Ultralytics, PaddleOCR, Google Vision, NAVER Cloud CLOVA OCR 공식 문서 URL은 허용했습니다.
  - Markdown runbook 생성 기능을 함께 추가해 운영자가 다음 수동 작업 순서를 한눈에 확인할 수 있게 했습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_queue.py`
  - 세 큐 pending 집계, 모두 ready 상태, raw OCR 필드 거부, 공식 문서 URL allow-list, 미등록 URL 거부, Markdown redaction, CLI JSON/Markdown write를 검증했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-operator-review-queue.current.json`
  - `/private/tmp/lemon-supplement-operator-review-queue.current.md`
- 실제 operator queue 결과:
  - `queue_count`: 3
  - `pending_queue_count`: 3
  - `total_pending_operator_action_count`: 808
  - `next_queue_key`: `brand_product_review`
  - `brand_product_review`: total 388 / pending 388 / blank 388 / valid 0
  - `review_pii_screening`: total 215 / pending 215 / blank 215 / valid 0
  - `yolo_section_annotation`: total 205 / pending 205 / blank 205 / valid 0
- 해석:
  - 현재 학습 파이프라인은 코드 생성보다 사람 검수 입력이 우선 병목입니다.
  - 다음 순서는 `brand_product_review`를 먼저 채워 category/brand/product import 조건을 만들고, 이후 PII screening과 YOLO bbox annotation을 각각 preflight로 재검증하는 흐름입니다.
  - 세 큐 모두 pending 상태이므로 DB apply, teacher OCR 승격, YOLO export/source-map 승격은 아직 실행하면 안 됩니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/build_supplement_operator_review_queue.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_queue.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_queue.py
.venv/bin/python scripts/build_supplement_operator_review_queue.py --brand-preflight /private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json --pii-preflight /private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --yolo-preflight /private/tmp/lemon-supplement-yolo-annotation-review-bundle/decision-preflight.current.json --readiness /private/tmp/lemon-supplement-learning-pipeline-readiness.after-yolo-decision-preflight.json --output /private/tmp/lemon-supplement-operator-review-queue.current.json --markdown-output /private/tmp/lemon-supplement-operator-review-queue.current.md
```

## 41차 구현 완료 - operator review batch plan/checklist

### 구현 파일

- `backend/scripts/build_supplement_operator_review_batch_plan.py`
  - 40차 통합 operator review queue를 사람이 처리하기 쉬운 row range batch로 분할하는 스크립트를 추가했습니다.
  - 입력은 `supplement-operator-review-queue-summary-v1`과 선택적 bundle summary만 허용합니다.
  - 실제 decision/annotation JSONL row, 원본 이미지, OCR 원문, provider payload, 모델 응답, DB record는 읽지 않습니다.
  - output은 `batch_key`, `queue_key`, editable file name, start/end row, pending row count, queue별 짧은 checklist만 포함합니다.
  - batch size는 1-200 범위로 제한하며 기본값은 50입니다.
  - raw/provider key, 로컬 절대경로, 제품 폴더 literal, 미등록 source documentation URL은 fail-closed로 거부합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_batch_plan.py`
  - pending queue batch 분할, ready queue no-batch, unsafe raw field 거부, wrong bundle schema 거부, Markdown redaction, CLI JSON/Markdown write를 검증했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-operator-review-batch-plan.current.json`
  - `/private/tmp/lemon-supplement-operator-review-batch-plan.current.md`
- 실제 batch plan 결과:
  - `batch_size`: 50
  - `batch_count`: 18
  - `total_pending_operator_action_count`: 808
  - `next_queue_key`: `brand_product_review`
  - `queue_batch_counts`:
    - `brand_product_review`: 8
    - `review_pii_screening`: 5
    - `yolo_section_annotation`: 5
- 해석:
  - 운영자는 먼저 brand/product `decisions.todo.jsonl` 1-50, 51-100 ... 351-388 row를 검수합니다.
  - 이후 PII screening `decisions.todo.jsonl` 1-50 ... 201-215 row를 검수합니다.
  - 이후 YOLO section annotation `annotation.todo.jsonl` 1-50 ... 201-205 row를 검수합니다.
  - 각 큐 검수 후에는 해당 preflight를 다시 실행해 blank/pending/invalid count가 0인지 확인해야 하며, 통과한 큐만 apply 또는 promotion 단계로 넘깁니다.
  - batch plan은 작업 분할 보조 산출물이며 DB write, provider call, LLM call, training/promotion을 수행하지 않습니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/build_supplement_operator_review_batch_plan.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_batch_plan.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_batch_plan.py
.venv/bin/python scripts/build_supplement_operator_review_batch_plan.py --queue-summary /private/tmp/lemon-supplement-operator-review-queue.current.json --brand-bundle-summary /private/tmp/lemon-supplement-brand-review-bundle/summary.json --pii-bundle-summary /private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --yolo-bundle-summary /private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --batch-size 50 --output /private/tmp/lemon-supplement-operator-review-batch-plan.current.json --markdown-output /private/tmp/lemon-supplement-operator-review-batch-plan.current.md
```

## 42차 구현 완료 - operator review batch progress preflight

### 구현 파일

- `backend/scripts/preflight_supplement_operator_review_batch_progress.py`
  - 41차 batch plan과 실제 operator-edited decision/annotation JSONL을 함께 읽어 batch별 진행률을 aggregate로 계산하는 preflight를 추가했습니다.
  - 출력은 `batch_key`, `queue_key`, row range, valid/blank/pending/invalid/missing count, aggregate reason count만 포함합니다.
  - fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, notes, 로컬 절대경로는 출력하지 않습니다.
  - brand/PII row는 기존 apply validator와 blank detector 기준으로 valid/blank/invalid를 분류합니다.
  - YOLO row는 기존 annotation schema, `label_snapshot.boxes`, accepted/training export flag 기준으로 valid/blank/pending/invalid를 분류합니다.
  - 이 도구는 batch 진행률 확인용이며, 최종 apply/promotion 가능 여부는 반드시 큐별 정식 preflight로 다시 확인해야 합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_preflight_supplement_operator_review_batch_progress.py`
  - batch별 count, invalid row redaction, YOLO boxes-not-accepted pending 상태, missing editable file fail-closed, Markdown redaction, CLI JSON/Markdown write를 검증했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-operator-review-batch-progress.current.json`
  - `/private/tmp/lemon-supplement-operator-review-batch-progress.current.md`
- 실제 progress 결과:
  - `batch_count`: 18
  - `complete_batch_count`: 0
  - `pending_batch_count`: 18
  - `invalid_batch_count`: 0
  - `next_incomplete_batch_key`: `brand_product_review:001`
  - `total_valid_row_count`: 0
  - `total_blank_row_count`: 808
  - `total_invalid_row_count`: 0
- 해석:
  - 현재 operator decision/annotation 파일은 모두 template stub 상태입니다.
  - brand/product, PII screening, YOLO section bbox 검수 중 완료된 batch는 아직 없습니다.
  - 다음 실제 수동 작업은 `brand_product_review:001` row 1-50부터 시작하면 됩니다.
  - 모든 batch가 complete가 된 이후에도 `preflight_supplement_brand_review_decisions.py`, `preflight_supplement_review_pii_screening_decisions.py`, `preflight_supplement_yolo_annotation_decisions.py`를 다시 실행해야 합니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/preflight_supplement_operator_review_batch_progress.py Nutrition-backend/tests/unit/scripts/test_preflight_supplement_operator_review_batch_progress.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_preflight_supplement_operator_review_batch_progress.py
.venv/bin/python scripts/preflight_supplement_operator_review_batch_progress.py --batch-plan /private/tmp/lemon-supplement-operator-review-batch-plan.current.json --brand-decisions /private/tmp/lemon-supplement-brand-review-bundle/decisions.todo.jsonl --pii-decisions /private/tmp/lemon-supplement-pii-screening/review-bundle/decisions.todo.jsonl --yolo-annotations /private/tmp/lemon-supplement-yolo-annotation-review-bundle/annotation.todo.jsonl --output /private/tmp/lemon-supplement-operator-review-batch-progress.current.json --markdown-output /private/tmp/lemon-supplement-operator-review-batch-progress.current.md
```

## 43차 구현 완료 - operator review batch file export

### 구현 파일

- `backend/scripts/export_supplement_operator_review_batch_files.py`
  - 41차 batch plan의 1-based row range를 기준으로 brand/product, PII screening, YOLO section annotation editable JSONL을 operator-local batch 파일로 분할하는 스크립트를 추가했습니다.
  - 원본 `decisions.todo.jsonl` 및 `annotation.todo.jsonl`은 수정하지 않고, 지정된 output directory에 batch별 JSONL working copy만 생성합니다.
  - batch JSONL에는 operator가 실제로 편집해야 하는 row payload가 들어가지만, summary/Markdown/CLI 출력에는 fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 절대경로를 포함하지 않습니다.
  - 입력 row에서 raw OCR/provider key 또는 로컬 절대경로 marker가 발견되면 batch copy 자체를 fail-closed로 중단합니다.
  - 이 도구는 수동 검수 작업 분할 보조이며 DB write, provider call, LLM call, OCR 실행, training/promotion 실행을 수행하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_export_supplement_operator_review_batch_files.py`
  - batch row range export, summary redaction, missing editable file fail-closed, unsafe editable row 거부, Markdown redaction, CLI JSON/Markdown write를 검증했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-operator-review-batches.current/`
  - `/private/tmp/lemon-supplement-operator-review-batches.current.summary.json`
  - `/private/tmp/lemon-supplement-operator-review-batches.current.md`
- 실제 export 결과:
  - `batch_file_count`: 18
  - `exported_row_count`: 808
  - `next_batch_key`: `brand_product_review:001`
  - `queue_batch_counts`:
    - `brand_product_review`: 8
    - `review_pii_screening`: 5
    - `yolo_section_annotation`: 5
  - `queue_row_counts`:
    - `brand_product_review`: 388
    - `review_pii_screening`: 215
    - `yolo_section_annotation`: 205
- 생성된 batch 파일:
  - `brand_product_review-001.jsonl` ... `brand_product_review-008.jsonl`
  - `review_pii_screening-001.jsonl` ... `review_pii_screening-005.jsonl`
  - `yolo_section_annotation-001.jsonl` ... `yolo_section_annotation-005.jsonl`
- 해석:
  - 운영자는 `brand_product_review-001.jsonl`부터 작업해도 되고, 작업 완료 row를 반드시 큐별 원본 editable JSONL에 reconcile해야 합니다.
  - batch 파일을 편집 완료했더라도 정식 완료 판정은 기존 큐별 preflight와 42차 batch progress preflight를 다시 실행해 확인합니다.
  - 모든 batch가 complete가 되기 전까지 DB apply, teacher OCR 승격, YOLO dataset promotion은 계속 차단합니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/export_supplement_operator_review_batch_files.py Nutrition-backend/tests/unit/scripts/test_export_supplement_operator_review_batch_files.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_export_supplement_operator_review_batch_files.py
.venv/bin/python scripts/export_supplement_operator_review_batch_files.py --batch-plan /private/tmp/lemon-supplement-operator-review-batch-plan.current.json --brand-decisions /private/tmp/lemon-supplement-brand-review-bundle/decisions.todo.jsonl --pii-decisions /private/tmp/lemon-supplement-pii-screening/review-bundle/decisions.todo.jsonl --yolo-annotations /private/tmp/lemon-supplement-yolo-annotation-review-bundle/annotation.todo.jsonl --output-dir /private/tmp/lemon-supplement-operator-review-batches.current --summary-output /private/tmp/lemon-supplement-operator-review-batches.current.summary.json --markdown-output /private/tmp/lemon-supplement-operator-review-batches.current.md
```

## 44차 구현 완료 - operator review batch reconcile

### 구현 파일

- `backend/scripts/reconcile_supplement_operator_review_batch_files.py`
  - 43차 operator-local batch JSONL을 다시 queue-level reconciled JSONL copy로 합치는 도구를 추가했습니다.
  - 원본 `decisions.todo.jsonl`, `annotation.todo.jsonl`은 덮어쓰지 않고 `*.reconciled.jsonl` copy만 생성합니다.
  - batch plan의 row range와 batch file row count가 맞지 않거나, batch range가 겹치거나, raw OCR/provider key/로컬 절대경로 marker가 있으면 fail-closed로 중단합니다.
  - summary/Markdown은 batch key, queue key, batch file name, row count, changed/unchanged count만 포함합니다.
  - fixture id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 절대경로는 summary/Markdown/CLI 출력에 포함하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_reconcile_supplement_operator_review_batch_files.py`
  - edited batch row merge, redacted summary, missing batch file, row count mismatch, unsafe batch row, Markdown redaction, CLI artifact write를 검증했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-operator-review-reconciled.current/`
  - `/private/tmp/lemon-supplement-operator-review-reconciled.current.summary.json`
  - `/private/tmp/lemon-supplement-operator-review-reconciled.current.md`
  - `/private/tmp/lemon-supplement-operator-review-reconciled-progress.current.json`
  - `/private/tmp/lemon-supplement-operator-review-reconciled-progress.current.md`
- 실제 reconcile 결과:
  - `batch_count`: 18
  - `expected_row_count`: 808
  - `changed_row_count`: 0
  - `human_review_changes_detected`: false
  - `reconciled_copy_count`: 3
  - `queue_changed_counts`:
    - `brand_product_review`: 0
    - `review_pii_screening`: 0
    - `yolo_section_annotation`: 0
- reconciled copy를 42차 batch progress preflight에 넣은 결과:
  - `complete_batch_count`: 0
  - `pending_batch_count`: 18
  - `invalid_batch_count`: 0
  - `total_valid_row_count`: 0
  - `total_blank_row_count`: 808
  - `next_incomplete_batch_key`: `brand_product_review:001`
- 해석:
  - 현재 batch working copy는 아직 사람이 수정하지 않은 template 상태와 동일합니다.
  - reconcile 도구는 검수 후 되돌리기 경로를 준비했지만, 현재 상태에서는 DB apply, teacher OCR transfer, YOLO dataset promotion을 계속 진행하면 안 됩니다.
  - 다음 실제 전진 조건은 operator가 `brand_product_review:001`부터 검수해 changed row를 만들고, reconciled copy와 정식 preflight가 이를 통과하는 것입니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/reconcile_supplement_operator_review_batch_files.py Nutrition-backend/tests/unit/scripts/test_reconcile_supplement_operator_review_batch_files.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_reconcile_supplement_operator_review_batch_files.py
.venv/bin/python scripts/reconcile_supplement_operator_review_batch_files.py --batch-plan /private/tmp/lemon-supplement-operator-review-batch-plan.current.json --brand-decisions /private/tmp/lemon-supplement-brand-review-bundle/decisions.todo.jsonl --pii-decisions /private/tmp/lemon-supplement-pii-screening/review-bundle/decisions.todo.jsonl --yolo-annotations /private/tmp/lemon-supplement-yolo-annotation-review-bundle/annotation.todo.jsonl --batch-dir /private/tmp/lemon-supplement-operator-review-batches.current --output-dir /private/tmp/lemon-supplement-operator-review-reconciled.current --summary-output /private/tmp/lemon-supplement-operator-review-reconciled.current.summary.json --markdown-output /private/tmp/lemon-supplement-operator-review-reconciled.current.md
.venv/bin/python scripts/preflight_supplement_operator_review_batch_progress.py --batch-plan /private/tmp/lemon-supplement-operator-review-batch-plan.current.json --brand-decisions /private/tmp/lemon-supplement-operator-review-reconciled.current/brand_product_review.reconciled.jsonl --pii-decisions /private/tmp/lemon-supplement-operator-review-reconciled.current/review_pii_screening.reconciled.jsonl --yolo-annotations /private/tmp/lemon-supplement-operator-review-reconciled.current/yolo_section_annotation.reconciled.jsonl --output /private/tmp/lemon-supplement-operator-review-reconciled-progress.current.json --markdown-output /private/tmp/lemon-supplement-operator-review-reconciled-progress.current.md
```

## 45차 구현 완료 - operator review workpack

### 구현 파일

- `backend/scripts/build_supplement_operator_review_workpack.py`
  - 41차 batch plan, 43차 batch export summary, brand/PII/YOLO review bundle summary를 연결해 batch별 operator Markdown guide를 생성하는 도구를 추가했습니다.
  - source row, 원본 이미지, OCR 원문, provider payload, 모델 응답, DB record는 읽지 않습니다.
  - batch별 guide는 batch JSONL 파일명, source editable 파일명, row range, source bundle file name, checklist, 완료 규칙만 포함합니다.
  - summary/index/guide에는 row id, 제품명, OCR 원문, provider payload, 이미지 경로, source ref, 로컬 절대경로를 포함하지 않습니다.
  - source bundle summary 누락, duplicate batch export, unsafe raw/provider summary key는 fail-closed로 거부합니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_workpack.py`
  - batch guide/index 생성, missing bundle summary, duplicate export batch, unsafe bundle summary, CLI summary write를 검증했습니다.

### 실제 artifact 상태

- 생성:
  - `/private/tmp/lemon-supplement-operator-review-workpack.current/`
  - `/private/tmp/lemon-supplement-operator-review-workpack.current.summary.json`
- 실제 workpack 결과:
  - `status`: `ok`
  - `batch_count`: 18
  - `workpack_file_count`: 19
  - `next_batch_key`: `brand_product_review:001`
  - `queue_workpack_counts`:
    - `brand_product_review`: 8
    - `review_pii_screening`: 5
    - `yolo_section_annotation`: 5
- 생성된 Markdown:
  - `index.md`
  - `brand_product_review-001.md` ... `brand_product_review-008.md`
  - `review_pii_screening-001.md` ... `review_pii_screening-005.md`
  - `yolo_section_annotation-001.md` ... `yolo_section_annotation-005.md`
- 해석:
  - 운영자는 `index.md`에서 다음 batch를 확인하고, 해당 batch guide를 열어 어떤 batch JSONL과 source bundle 파일을 같이 볼지 확인할 수 있습니다.
  - 첫 작업은 여전히 `brand_product_review:001`입니다.
  - workpack은 작업 안내용이며 DB apply, teacher OCR transfer, YOLO dataset promotion을 수행하지 않습니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/build_supplement_operator_review_workpack.py Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_workpack.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_operator_review_workpack.py
.venv/bin/python scripts/build_supplement_operator_review_workpack.py --batch-plan /private/tmp/lemon-supplement-operator-review-batch-plan.current.json --batch-export-summary /private/tmp/lemon-supplement-operator-review-batches.current.summary.json --brand-bundle-summary /private/tmp/lemon-supplement-brand-review-bundle/summary.json --pii-bundle-summary /private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --yolo-bundle-summary /private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --output-dir /private/tmp/lemon-supplement-operator-review-workpack.current --summary-output /private/tmp/lemon-supplement-operator-review-workpack.current.summary.json
```

## 46차 구현 완료 - readiness report에 operator workpack evidence 연결

### 구현 파일

- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `operator_review_workpack` artifact role을 추가했습니다.
  - expected schema는 `supplement-operator-review-workpack-v1`입니다.
  - 해당 artifact를 다음 3개 stage의 shared pending evidence로 연결했습니다.
    - `brand_product_review`
    - `review_pii_screening`
    - `yolo_section_annotation`
  - artifact summary에는 `status`, `batch_count`, `workpack_file_count`, `next_batch_key`만 safe aggregate로 노출합니다.
  - source row, 이미지, OCR 원문, provider payload, local path는 readiness report에 포함하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`
  - workpack artifact fixture를 추가했습니다.
  - workpack 하나가 brand/PII/YOLO 수동 검수 stage의 pending evidence로 인식되는지 검증했습니다.

### 실제 current readiness 결과

- 재생성:
  - `/private/tmp/lemon-supplement-learning-pipeline-readiness.current.json`
- 실제 입력 artifact:
  - `provided_artifact_count`: 13
  - `operator_review_workpack`: present
- 실제 aggregate:
  - `overall_status`: `in_progress_blocked_by_missing_or_invalid_artifacts`
  - `verified_stage_count`: 3
  - `pending_operator_review_stage_count`: 3
  - `blocked_stage_count`: 9
- workpack artifact summary:
  - `status`: `ok`
  - `batch_count`: 18
  - `workpack_file_count`: 19
  - `next_batch_key`: `brand_product_review:001`
- stage별 반영:
  - `brand_product_review`: `operator_review_workpack` 포함, `approved_product_import` 누락으로 pending
  - `review_pii_screening`: `operator_review_workpack` 포함, `pii_screening_apply` 누락으로 pending
  - `yolo_section_annotation`: `operator_review_workpack` 포함, `yolo_template_promotion` 누락으로 pending

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact brand_review_decision_preflight=/private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact pii_screening_decision_preflight=/private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --artifact yolo_annotation_decision_preflight=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/decision-preflight.current.json --artifact operator_review_workpack=/private/tmp/lemon-supplement-operator-review-workpack.current.summary.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.current.json
```

## 47차 구현 완료 - readiness report에 operator batch progress evidence 연결

### 구현 파일

- `backend/scripts/build_supplement_learning_pipeline_readiness_report.py`
  - `operator_review_batch_progress` artifact role을 추가했습니다.
  - expected schema는 `supplement-operator-review-batch-progress-preflight-v1`입니다.
  - 해당 artifact를 다음 3개 stage의 shared pending evidence로 연결했습니다.
    - `brand_product_review`
    - `review_pii_screening`
    - `yolo_section_annotation`
  - artifact summary에는 다음 aggregate만 노출합니다.
    - `batch_count`
    - `complete_batch_count`
    - `pending_batch_count`
    - `invalid_batch_count`
    - `all_batches_complete`
    - `next_incomplete_batch_key`
    - `total_expected_row_count`
    - `total_valid_row_count`
    - `total_blank_row_count`
    - `total_pending_row_count`
    - `total_invalid_row_count`
    - `total_missing_row_count`
  - row id, 제품명, OCR 원문, provider payload, 이미지 경로, local path는 readiness report에 포함하지 않습니다.
- `backend/Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py`
  - batch progress artifact fixture를 추가했습니다.
  - batch progress 하나가 brand/PII/YOLO 수동 검수 stage의 pending evidence로 인식되는지 검증했습니다.

### 실제 current readiness 결과

- 재생성:
  - `/private/tmp/lemon-supplement-learning-pipeline-readiness.current.json`
- 실제 입력 artifact:
  - `provided_artifact_count`: 14
  - `operator_review_workpack`: present
  - `operator_review_batch_progress`: present
- 실제 aggregate:
  - `overall_status`: `in_progress_blocked_by_missing_or_invalid_artifacts`
  - `verified_stage_count`: 3
  - `pending_operator_review_stage_count`: 3
  - `blocked_stage_count`: 9
- batch progress artifact summary:
  - `batch_count`: 18
  - `complete_batch_count`: 0
  - `pending_batch_count`: 18
  - `invalid_batch_count`: 0
  - `all_batches_complete`: false
  - `next_incomplete_batch_key`: `brand_product_review:001`
  - `total_expected_row_count`: 808
  - `total_valid_row_count`: 0
  - `total_blank_row_count`: 808
  - `total_pending_row_count`: 0
  - `total_invalid_row_count`: 0
  - `total_missing_row_count`: 0
- 해석:
  - 세 수동 검수 stage는 모두 pending 상태입니다.
  - 아직 어떤 batch도 complete가 아니므로 `approved_product_import`, `pii_screening_apply`, `yolo_template_promotion`을 실행하면 안 됩니다.
  - 다음 operator 작업은 `brand_product_review:001`입니다.

### 검증

```bash
cd backend
.venv/bin/python -m ruff check scripts/build_supplement_learning_pipeline_readiness_report.py Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_build_supplement_learning_pipeline_readiness_report.py
.venv/bin/python scripts/build_supplement_learning_pipeline_readiness_report.py --artifact taxonomy_audit=/private/tmp/lemon-supplement-taxonomy-audit.current.json --artifact taxonomy_staging=/private/tmp/lemon-supplement-taxonomy-staging.current.jsonl --artifact brand_review_template=/private/tmp/lemon-supplement-brand-review-template.summary.json --artifact brand_review_bundle=/private/tmp/lemon-supplement-brand-review-bundle/summary.json --artifact brand_review_decision_preflight=/private/tmp/lemon-supplement-brand-review-bundle/decision-preflight.current.json --artifact learning_candidate_summary=/private/tmp/lemon-supplement-learning-candidates.summary.json --artifact pii_screening_template=/private/tmp/lemon-supplement-pii-screening/pii-template.summary.json --artifact pii_screening_review_bundle=/private/tmp/lemon-supplement-pii-screening/review-bundle/summary.json --artifact pii_screening_decision_preflight=/private/tmp/lemon-supplement-pii-screening/decision-preflight.current.json --artifact yolo_annotation_template=/private/tmp/lemon-supplement-yolo-annotation-template-full.summary.json --artifact yolo_annotation_review_bundle=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/summary.json --artifact yolo_annotation_decision_preflight=/private/tmp/lemon-supplement-yolo-annotation-review-bundle/decision-preflight.current.json --artifact operator_review_workpack=/private/tmp/lemon-supplement-operator-review-workpack.current.summary.json --artifact operator_review_batch_progress=/private/tmp/lemon-supplement-operator-review-batch-progress.current.json --output /private/tmp/lemon-supplement-learning-pipeline-readiness.current.json
```

## 공식 참고

- PostgreSQL Constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- SQLAlchemy ORM Select: https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html
- SQLAlchemy AsyncIO: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- Ultralytics Detect: https://docs.ultralytics.com/tasks/detect/
- Ultralytics Predict Boxes: https://docs.ultralytics.com/modes/predict/
- PaddleOCR OCR Pipeline: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR Fine-tuning: https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
- PaddleOCR Text Detection Eval: https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
- PaddleOCR Text Recognition Eval: https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- NAVER Cloud CLOVA OCR: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- Ollama Vision: https://docs.ollama.com/capabilities/vision
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama API: https://docs.ollama.com/api
