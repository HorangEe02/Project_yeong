# Supplement Taxonomy, OCR, YOLO, PaddleOCR Implementation Plan

## Summary

현재 `data/nutrition_reference/crawling-image`의 실제 구조는 초기 가정과 다릅니다.

- 실제 구조: `카테고리 폴더 -> 제품 후보 폴더 -> 리뷰 / 상세페이지`
- 부재한 구조: `카테고리 폴더 -> 브랜드 폴더 -> 리뷰 / 상세페이지`
- 따라서 브랜드는 별도 폴더 계층이 아니라 제품 후보 폴더명 앞부분에서 추정되는 `brand_candidate`입니다.
- 이 값은 잘못 추정될 수 있으므로 DB의 `SupplementProduct.manufacturer`로 바로 저장하면 안 되고, operator review를 통과한 승인 manifest만 사용해야 합니다.

이번 구현의 목표는 네 가지입니다.

1. 실제 폴더 구조를 DB taxonomy staging 구조로 안전하게 고정한다.
2. 리뷰 이미지를 OCR 정답지 후보로 쓰되, PII 검토와 수동 ground truth를 먼저 통과시킨다.
3. 상세페이지 이미지는 YOLO26 섹션 bbox annotation 데이터로 사용해 성분표, 함량, 섭취 방법, 주의사항 영역을 분리한다.
4. CLOVA OCR / Google Vision은 teacher OCR로만 비교하고, PaddleOCR은 수동 정답지 기준으로 baseline, fine-tune, promotion gate를 통과할 때만 개선 모델로 승격한다.

## Verified Current State

새로 생성한 sanitized audit 산출물:

- `outputs/todo-list/2026-06-04/2026-06-04-crawling-image-taxonomy-audit.json`
- `outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl`
- `outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.summary.json`

핵심 수치:

| Item | Count / Status |
| --- | --- |
| Category folders | 43 |
| Product candidate folders | 388 |
| Total images | 137,809 |
| Review images | 132,520 |
| Detail page images | 5,289 |
| Staging rows | 431 |
| Category seed rows | 43 |
| Brand candidate rows | 388 |
| Product/brand rows ready for DB write | 0 |

현재 gate 상태:

| Pipeline | Status | Blocking Review |
| --- | --- | --- |
| Category seed DB apply | local DB verified |
| Product/brand DB apply | blocked | `brand_product_review:001` |
| OCR benchmark / teacher OCR | blocked | `review_pii_screening:001` |
| PaddleOCR training | blocked | PII + manual GT + benchmark + baseline promotion |
| YOLO section dataset | blocked | `yolo_section_annotation:001` |

현재 구조 이슈:

- `missing_review_dir`: 21개 제품 후보
- `missing_detail_page_dir`: 1개 제품 후보
- `category_contains_non_image_files`: 27개 카테고리
- `non_image_file_count`: 179개

이 이슈는 source data 품질 이슈이며, 바로 삭제하거나 이동하지 않습니다. 감사 결과에 남기고 operator review 또는 ingestion policy로 처리합니다.

## DB Taxonomy Redesign

### Decision

폴더를 재배치하지 않고, 현재 구조를 다음 계약으로 해석합니다.

| Source | DB / Staging Meaning |
| --- | --- |
| Top-level folder, e.g. `[오메가3]` | `supplement_categories.category_key`, `display_name` |
| Product candidate folder | product candidate source row |
| Product folder trailing numeric suffix | `source_product_id` |
| Product folder prefix | `brand_candidate`, human review required |
| `리뷰` images | OCR ground-truth candidates after PII screening |
| `상세페이지` images | YOLO section bbox annotation candidates |

### DB Write Rules

- Category seed rows can be stored after local target preflight and dry-run gate.
- Product, brand, and product-category rows cannot be stored until the approved product manifest exists.
- Brand candidates are never trusted directly as DB manufacturer values.
- Absolute source paths, product directory literals, raw OCR text, provider payloads, and image bytes must not be written into API responses or operator markdown.
- Source linkage should use source ids, hashes, and approved manifest ids.

## OCR Ground-Truth and PaddleOCR Improvement Loop

### Step 1. Review Image PII Screening

Use review images only after strict PII screening.

- Input: review image candidate manifest.
- Output: PII decision manifest.
- Allowed decisions: approved no-personal-data, reject, needs manual review.
- Current blocker: 215 candidate rows have blank PII decisions.

No CLOVA OCR, Google Vision, or PaddleOCR training job runs before this gate clears.

### Step 2. Manual Ground Truth

After PII clearance, build a ground-truth template for human annotation.

Required fields:

- product identity
- ingredient names
- amounts
- units
- intake method
- precautions
- low-confidence or unreadable flags

Teacher OCR output is not ground truth. Manual review remains authoritative.

### Step 3. Teacher OCR Benchmark

Run CLOVA OCR and Google Vision only on PII-cleared and benchmark-approved images.

Compare providers using:

- character error rate
- word error rate
- ingredient exact match
- ingredient normalized match
- amount and unit precision
- section recall
- false-positive ingredient rate

### Step 4. PaddleOCR Baseline and Improvement Candidates

Run PaddleOCR against the same benchmark fixture.

Failure buckets:

- missed ingredient
- wrong amount
- wrong unit
- section boundary confusion
- Korean/English normalization error
- false ingredient hallucination
- low text confidence

Only these audited failures become improvement candidates.

### Step 5. PaddleOCR Training Dataset and Promotion

Training is allowed only after:

- PII gate passed
- manual GT exists
- annotation tasks are promoted to dataset
- baseline metrics exist
- fine-tune run plan is reviewed
- promotion gate beats baseline on predefined metrics without regression

No model promotion happens from teacher OCR alone.

## YOLO26 Section Detection Loop

### Section Classes

The supplement section detector should use custom labels:

- `product_identity`
- `supplement_facts`
- `ingredient_amounts`
- `intake_method`
- `precautions`
- `other_ingredients`
- `functional_claims`

### Dataset Rule

COCO-pretrained YOLO26 weights are not trusted for supplement label sections. They can be used only as a base model after a custom labeled section dataset exists.

### Annotation Flow

1. Build detail-page image candidates.
2. Export bbox annotation template.
3. Human annotator fills accepted bbox rows.
4. Preflight validates coordinates, labels, source hashes, and blank rows.
5. Promote accepted annotations.
6. Materialize Ultralytics detection dataset.
7. Validate train/val split and label files.
8. Train/evaluate custom section detector.
9. Gate model promotion.

Current blocker: 205 YOLO annotation template rows are blank, so section training is not allowed.

### Runtime Use

When the section detector is approved:

1. Run YOLO section detection on the image.
2. Crop bbox regions by class.
3. OCR each crop.
4. If a required section is empty, run whole-image OCR fallback.
5. Send structured section candidates to Gemma/Ollama validation.
6. Mark missing sections as `needs_retake` or `needs_manual_confirmation`.

## Security and Quality Self-Review

### Privacy

- Do not store raw OCR/provider payloads in API responses, markdown reports, or DB tables.
- Do not store local absolute paths.
- Do not expose source image paths to mobile clients.
- PII-screen review images before any external teacher OCR call.

### Data Leakage

- Split PaddleOCR and YOLO train/val/test by product candidate, not by image, so the same product does not appear in both train and validation.
- Keep review images and detail-page images as separate source roles.
- Do not use teacher OCR output as training labels without manual confirmation.

### Model Reliability

- YOLO26 pretrained object classes do not map to supplement label sections. Custom bbox labels are mandatory.
- PaddleOCR promotion must compare against baseline on a held-out product-level split.
- CLOVA and Google Vision are comparison baselines, not final truth.

### Medical Safety

- The pipeline extracts label facts and supports health-management recommendations.
- It must not present diagnosis, prescription, medication discontinuation, or treatment claims.
- User-facing guidance remains `권장`, `주의`, `상담 권고`, `확인 필요`.

## Implementation Order

1. Keep current category seed DB state as verified and do not reapply product/brand DB writes.
2. Complete `brand_product_review:001` for 388 brand/product candidates.
3. Build approved product import manifest and run product DB dry-run gate.
4. Complete `review_pii_screening:001` for OCR candidate review images.
5. Export OCR ground-truth template only for PII-cleared rows.
6. Build human-reviewed OCR benchmark manifest.
7. Run CLOVA OCR / Google Vision teacher benchmark only after PII and external-transfer gates.
8. Run PaddleOCR baseline eval.
9. Build PaddleOCR improvement candidates and annotation tasks.
10. Materialize PaddleOCR dataset, run fine-tune plan, then promotion gate.
11. Complete `yolo_section_annotation:001` for detail-page section bbox rows.
12. Materialize and validate custom YOLO section dataset.
13. Train/evaluate YOLO26 section detector.
14. Connect approved detector to ROI crop OCR + whole-image fallback.

## Immediate Safe Implementation Started

Completed in this section:

- Refreshed sanitized folder audit JSON without reading image bytes or running OCR.
- Refreshed sanitized DB staging JSONL and summary.
- Confirmed the real source structure requires product-folder based brand review, not direct brand-folder persistence.

Safe next command group:

```bash
cd backend
.venv/bin/python -m ruff check scripts/audit_supplement_crawling_image_taxonomy.py scripts/build_supplement_taxonomy_db_staging.py scripts/gate_supplement_ocr_benchmark.py scripts/gate_supplement_yolo_section_dataset.py
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/scripts/test_audit_supplement_crawling_image_taxonomy.py Nutrition-backend/tests/unit/scripts/test_build_supplement_taxonomy_db_staging.py Nutrition-backend/tests/unit/scripts/test_gate_supplement_ocr_benchmark.py Nutrition-backend/tests/unit/scripts/test_gate_supplement_yolo_section_dataset.py
```

## Official References

- Ultralytics detection task: https://docs.ultralytics.com/tasks/detect/
- Ultralytics detection datasets: https://docs.ultralytics.com/datasets/detect/
- Ultralytics prediction boxes: https://docs.ultralytics.com/modes/predict/
- PaddleOCR OCR pipeline: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- Google Cloud Vision OCR: https://cloud.google.com/vision/docs/ocr
- NAVER Cloud CLOVA OCR API: https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Supabase row-level security: https://supabase.com/docs/guides/database/postgres/row-level-security
- SQLAlchemy ORM select: https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
