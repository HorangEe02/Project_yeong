# Plan D. Parser/domain correction 학습 상세 설계 및 구현 플랜

## Summary

Plan D는 OCR/LLM parser를 재학습하기 전에, 사용자가 명시적으로 확인한 수정 결과를 deterministic parser/domain correction rule로 축적해 구조화 정확도를 높이는 작업이다. v1은 모델 학습이 아니라 `ParserCorrectionEvent -> DomainCorrectionCandidate -> reviewed artifact -> parser post-processing` 흐름을 구현한다.

현재 backend에는 `SupplementStructuredParseResultV2`, `SupplementParsedSnapshotV3`, `UserSupplementCreate.user_confirmed=True`, `ocr_text_hash`, `nutrient_code_matcher`가 이미 있으므로 기존 preview-confirmation 계약을 유지한다. 자동 보정은 `rule_status=approved` artifact만 적용하고, raw OCR full text/provider payload/raw image/user id는 correction artifact에 저장하지 않는다.

공식 기준:

- Pydantic validator/model validator: https://docs.pydantic.dev/latest/concepts/validators/
- Python Unicode normalization: https://docs.python.org/3/library/unicodedata.html
- Python `difflib.SequenceMatcher` / `get_close_matches`: https://docs.python.org/3/library/difflib.html

명시적 한계:

- I cannot find the official documentation for this specific query: supplement-label-specific parser/domain correction thresholds.
- 따라서 `min_support`, fuzzy cutoff, promotion gate는 공식 권장값이 아니라 frozen fixture와 팀 리뷰로 보정할 내부 정책값이다.

## Implemented Design

- `ParserCorrectionEvent`
  - 사용자 확정 저장 흐름 이후 preview snapshot과 confirmed payload를 비교해 field-level diff를 만든다.
  - `analysis_id`, `ocr_text_hash`, `parser_algorithm_version`, `field_path`, `correction_type`, `before_value_hash`, `confirmed_value`, `evidence_refs`, `consent_scope`, `created_at`만 저장한다.
  - raw OCR text, raw provider payload, raw image, EXIF/GPS, filename, user id는 schema/service validator에서 차단한다.

- `DomainCorrectionCandidate` / `DomainCorrectionArtifactManifest`
  - event를 집계해 review queue 후보를 만들고, conflict가 있으면 `needs_review`로 유지한다.
  - reviewed artifact는 `domain_dictionary_version`, `confusion_map_version`, `created_from_manifest_checksum`, `checksum`, `rules`를 가진다.
  - artifact checksum은 `checksum` field를 제외한 JSON 정규화 결과로 계산한다.

- Runtime correction layer
  - `ENABLE_PARSER_DOMAIN_CORRECTION=false`가 기본값이다.
  - `PARSER_DOMAIN_CORRECTION_MODE=report_only`에서는 core snapshot 값과 candidate를 바꾸지 않고 audit/warning만 남긴다.
  - `apply_reviewed`에서는 approved `ingredient_alias` rule을 nutrient candidate matching의 extra catalog로 전달하고, approved `unit_normalization` rule만 unit을 교체한다.
  - `display_name`, `amount_text`, `evidence_refs`는 보존한다. amount가 없으면 새 amount를 만들지 않는다.

- User confirmation capture
  - `create_user_supplement_from_confirmation()`에 optional `Settings`를 연결했다.
  - feature flag가 켜진 경우에만 correction events를 `preview.match_snapshot["parser_domain_correction_events"]`에 저장한다.
  - preview에 `ocr_text_hash`가 없으면 learning source로 취급하지 않는다.

## Implementation Phases

1. **D0: Correction Schema**
   - `src/models/schemas/parser_domain_correction.py`
   - schema, forbidden raw field validation, control character validation 구현.

2. **D1: User Confirmation Capture**
   - `src/services/parser_domain_correction.py`
   - `src/services/supplement_registration.py`
   - confirmed payload와 preview snapshot diff 기반 event 생성.

3. **D2: Candidate Mining**
   - `mine_domain_correction_candidates()` 구현.
   - conflict가 있는 후보는 `needs_review`로 승격 보류.

4. **D3: Review and Promotion**
   - `DomainCorrectionRule`, `DomainCorrectionArtifactManifest`, checksum helper 구현.
   - approved rule만 runtime에서 사용할 수 있게 필터링.

5. **D4: Runtime Correction Application**
   - `src/services/supplement_parser.py`에서 parser validation 이후 snapshot 생성 전에 correction application 호출.
   - `src/services/nutrient_code_matcher.py`에 reviewed extra alias catalog를 exact-only로 연결.

6. **D5: Evaluation Harness**
   - `backend/scripts/evaluate_domain_correction_rules.py`
   - baseline/candidate aggregate metric, safety metric, promotion decision 출력.

7. **D6: Verification**
   - schema, service, registration capture, parser runtime integration, script tests 추가.
   - threshold는 fixture calibration 전까지 공식값으로 주장하지 않는다.

## Test Plan

- Unit tests:
  - raw OCR/provider/image/user id/filename/EXIF/GPS field 차단
  - tab/newline/control character가 포함된 correction value 거부
  - `amount_parse`가 non-amount field에 붙는 경우 거부
  - preview-only 또는 `ocr_text_hash` 없는 row는 event 생성 차단
  - conflict candidate는 `needs_review`
  - report-only는 audit만 생성하고 값 변경 없음
  - approved rule만 apply 가능
  - disabled/rejected rule은 무시

- Integration-oriented tests:
  - user confirmation 저장 후 redacted correction event 생성
  - parser snapshot 생성 시 approved alias/unit rule 적용
  - `display_name`은 보존되고 `unit`/nutrient candidate만 reviewed rule로 개선
  - raw OCR text는 snapshot/report artifact에 저장되지 않음

- Evaluation tests:
  - baseline과 candidate는 같은 frozen fixture metric만 비교
  - `fabricated_field_count`, `false_correction_count`, `raw_text_leak_count` 중 하나라도 0보다 크면 promotion 실패
  - primary metric 중 하나 이상 개선되고 나머지가 악화되지 않아야 promotion candidate

## Assumptions

- Plan D v1은 OCR/PaddleOCR/LLM fine-tuning이 아니라 deterministic parser/domain correction 학습이다.
- 사용자 확정값은 서비스 데이터 및 correction diff로 저장 가능하지만, raw OCR full text와 provider raw payload는 계속 저장하지 않는다.
- `nutrient_code_matcher`의 기존 계약은 유지하고, approved dictionary artifact만 optional extra catalog로 연결한다.
- correction은 의료 판단이나 복용량 변경 안내가 아니라 라벨 구조화 정확도 개선에만 사용한다.
- 모든 신규 class/function에는 Google Style docstring을 작성한다.
