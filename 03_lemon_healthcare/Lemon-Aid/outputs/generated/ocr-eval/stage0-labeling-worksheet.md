# Stage 0 Ground-Truth Labeling Worksheet (45 fixture, 24 카테고리)

> 본 워크시트는 plan §I Stage 0 / status report 2026-05-21 P0-2 / brainstorming 보고서 §5 의 ground-truth 라벨링을 책상 위 참조 자료로 정리한 것이다.
> 50 fixture (stage0_naver) + 16 fixture (Tier 4 만성질환 신규) → 총 라벨링 목표 **45 개**. PaddleOCR auto-seed 결과는 대부분 garbage(`Once Daily`, `SUGGESTED USE:`, `nutricost` 등)이므로 ingredient 정보는 **이미지를 직접 보고** 라벨링한다.
>
> Tier 4 (만성질환 우선) 는 페르소나 B형 (52세 만성질환자) 차별화를 위해 외장 SSD 의 미활용 카테고리에서 신규 수집한다. 매트릭스: `data/nutrition_reference/chronic_disease_supplement_matrix.json`
>
> 도구:
> - 신규 helper: `backend/scripts/label_ground_truth.py` (V2 snapshot skeleton 생성, 자동 시드 ingredient 옵션, `--chronic-disease-targets` 옵션)
> - 신규 validator: `backend/scripts/validate_ground_truth.py` (schema validation + 진행률)
> - manifest 확장: `backend/scripts/prepare_supplement_ocr_live_manifest.py` (`--category-filter`, `--chronic-disease-priority` 옵션)

---

## 1. Fixture 인벤토리 (30 case, 16 카테고리)

이미지 경로 root: `data/supplement_images/private_workspace/stage0_naver/images/`
라벨링 파일 root: `backend/Nutrition-backend/tests/fixtures/supplement_labels/expected/`

### Tier 1 — 우선 라벨링 (text 풍부, 멀티 영양소) — 9개

| # | fixture_id | category | image filename | size (KB) | 비고 |
| --- | --- | --- | --- | ---: | --- |
| 1 | `naver-live-0029` | 멀티비타민 | `naver-live-0029.jpg` | 115 | text 가장 풍부 (PaddleOCR 2764 char) |
| 2 | `naver-live-0045` | 멀티비타민 | `naver-live-0045.jpg` | 204 | 종합영양제 |
| 3 | `naver-live-0013` | 멀티비타민 | `naver-live-0013.jpg` | 102 | 종합영양제 |
| 4 | `naver-live-0024` | 뇌_은행잎 | `naver-live-0024.jpg` | 236 | 가장 큰 이미지 |
| 5 | `naver-live-0022` | 기타 | `naver-live-0022.jpg` | 222 | 기타 카테고리 대표 |
| 6 | `naver-live-0023` | 남성_쏘팔메토 | `naver-live-0023.jpg` | 213 | 큰 이미지 |
| 7 | `naver-live-0035` | 강황_커큐민 | `naver-live-0035.jpg` | 200 | 강황 |
| 8 | `naver-live-0041` | 다이어트_체지방 | `naver-live-0041.jpg` | 192 | 다이어트 |
| 9 | `naver-live-0004` | 관절_MSM_콘드로이친 | `naver-live-0004.jpg` | 185 | 관절 |

### Tier 2 — 카테고리 다양성 확보 — 14개

| # | fixture_id | category | image filename | size (KB) | 비고 |
| --- | --- | --- | --- | ---: | --- |
| 10 | `naver-live-0027` | 루테인_눈 | `naver-live-0027.jpg` | 181 | 루테인 |
| 11 | `naver-live-0018` | HMB_타우린 | `naver-live-0018.jpg` | 95 | HMB |
| 12 | `naver-live-0001` | BCAA_EAA | `naver-live-0001.jpg` | 160 | BCAA |
| 13 | `naver-live-0019` | 강황_커큐민 | `naver-live-0019.jpg` | 185 | 강황 보조 |
| 14 | `naver-live-0005` | 글루코사민 | `naver-live-0005.jpg` | 171 | 글루코사민 |
| 15 | `naver-live-0011` | 루테인_눈 | `naver-live-0011.jpg` | 154 | 루테인 보조 |
| 16 | `naver-live-0012` | 마그네슘 | `naver-live-0012.jpg` | 138 | 미네랄 |
| 17 | `naver-live-0042` | 단백질_프로틴 | `naver-live-0042.jpg` | 85 | 단백질 |
| 18 | `naver-live-0014` | 밀크씨슬_간 | `naver-live-0014.jpg` | 84 | 간 |
| 19 | `naver-live-0034` | HMB_타우린 | `naver-live-0034.jpg` | 64 | HMB 보조 |
| 20 | `naver-live-0017` | BCAA_EAA | `naver-live-0017.jpg` | 130 | BCAA 보조 |
| 21 | `naver-live-0046` | 밀크씨슬_간 | `naver-live-0046.jpg` | 63 | 간 보조 |
| 22 | `naver-live-0007` | 남성_쏘팔메토 | `naver-live-0007.jpg` | 184 | 쏘팔메토 보조 |
| 23 | `naver-live-0009` | 다이어트_체지방 | `naver-live-0009.jpg` | 133 | 다이어트 보조 |

### Tier 3 — 비타민 단일 영양소 (한/영 분리 메트릭에 핵심) — 7개

| # | fixture_id | category | image filename | size (KB) | 비고 |
| --- | --- | --- | --- | ---: | --- |
| 24 | `naver-live-0015` | 비타민A | `naver-live-0015.jpg` | 83 | 비타민 A |
| 25 | `naver-live-0031` | 비타민A | `naver-live-0031.jpg` | 101 | 비타민 A 보조 |
| 26 | `naver-live-0047` | 비타민A | `naver-live-0047.webp` | 19 | webp (작은 파일) |
| 27 | `naver-live-0032` | 비타민B | `naver-live-0032.jpg` | 320 | 비타민 B (가장 큼) |
| 28 | `naver-live-0048` | 비타민B | `naver-live-0048.jpg` | 66 | 비타민 B 보조 |
| 29 | `naver-live-0016` | 비타민B | `naver-live-0016.jpg` | 113 | OCR error → 이미지 품질 확인 후 라벨링 가능 시 진행 |
| 30 | `naver-live-0020` | 관절_MSM_콘드로이친 | `naver-live-0020.jpg` | 118 | 관절 보조 |

### Tier 4 — 만성질환 우선 카테고리 (B형 페르소나 차별화) — 16개

> ⚠️ Tier 4 fixture 는 **외장 SSD** (`/Volumes/Corsair EX300U Media/.../tampermonkey/naver/`) 의 미활용 카테고리에서 신규 수집한다. fixture_id 는 `naver-chronic-NNNN` 형식으로 새로 할당. 수집 명령은 §5.4 참조.

| # | fixture_id (예) | category | 만성질환 타겟 | 매트릭스 권장 |
| --- | --- | --- | --- | --- |
| 31 | `naver-chronic-0001` | 오메가3 | cardiovascular / dyslipidemia / diabetes / cognitive_decline | prioritize_for_chronic |
| 32 | `naver-chronic-0002` | 오메가3 | (동일) | prioritize_for_chronic |
| 33 | `naver-chronic-0003` | 코엔자임Q10 | cardiovascular / hypertension / diabetes | prioritize_for_chronic |
| 34 | `naver-chronic-0004` | 코엔자임Q10 | (동일) | prioritize_for_chronic |
| 35 | `naver-chronic-0005` | 혈관_낫토_폴리코사놀 | cardiovascular / dyslipidemia | prioritize_for_chronic |
| 36 | `naver-chronic-0006` | 혈관_낫토_폴리코사놀 | (동일) | prioritize_for_chronic |
| 37 | `naver-chronic-0007` | 식이섬유 | dyslipidemia / diabetes | prioritize_for_chronic |
| 38 | `naver-chronic-0008` | 식이섬유 | (동일) | prioritize_for_chronic |
| 39 | `naver-chronic-0009` | 비타민D | osteoporosis (50+) | prioritize_for_chronic |
| 40 | `naver-chronic-0010` | 비타민D | (동일) | prioritize_for_chronic |
| 41 | `naver-chronic-0011` | 비타민K | osteoporosis (K2) | prioritize_for_chronic |
| 42 | `naver-chronic-0012` | 비타민K | (동일) | prioritize_for_chronic |
| 43 | `naver-chronic-0013` | 스트레스_아쉬와간다 | (만성 스트레스 동반) | caution_for_chronic ⚠️ SSRI 상호작용 |
| 44 | `naver-chronic-0014` | 스트레스_아쉬와간다 | (동일) | caution_for_chronic |
| 45 | `naver-chronic-0015` | 수면_멜라토닌 | (만성 수면 장애 동반) | moderate_for_chronic |
| 46 | `naver-chronic-0016` | 수면_멜라토닌 | (동일) | moderate_for_chronic |

> 권장 진행 순서: Tier 1 (9 case) → Tier 2 (14 case) → Tier 3 (7 case) → Tier 4 (16 case).
> Tier 1~3 은 기존 50 fixture (`stage0_naver/manifest.json`) 활용. Tier 4 만 신규 manifest 수집 필요.
> Tier 3 의 비타민 단일 영양소들은 P0-3 한/영 분리 CER/WER 메트릭의 baseline 측정에 가장 직접적인 신호를 준다.
> Tier 4 의 만성질환 우선 카테고리는 페르소나 B형 시나리오의 정확도 차별화에 직접 신호를 준다.

---

## 2. 비타민 표준 영양소 코드 (`data/nutrition_reference/nutrient/nutrient_codes.json` 기준)

| 영양소 (한글) | 영양소 (영문) | nutrient_code | 기본 단위 | 일반적 라벨 표기 |
| --- | --- | --- | --- | --- |
| 비타민 A | Vitamin A | `vitamin_a_ug` | ug RAE | `ug`, `mcg`, `μg`, 또는 `IU`(구단위) |
| 비타민 B1 (티아민) | Thiamin | `vitamin_b1_mg` | mg | `mg` |
| 비타민 B2 (리보플라빈) | Riboflavin | `vitamin_b2_mg` | mg | `mg` |
| 비타민 B3 (니아신) | Niacin | `vitamin_b3_mg` | mg | `mg NE`, `mg` |
| 비타민 B5 (판토텐산) | Pantothenic Acid | `vitamin_b5_mg` | mg | `mg` |
| 비타민 B6 (피리독신) | Pyridoxine | `vitamin_b6_mg` | mg | `mg` |
| 비타민 B7 (비오틴) | Biotin | `vitamin_b7_ug` | ug | `ug`, `mcg` |
| 비타민 B9 (엽산) | Folate | `vitamin_b9_ug` | ug DFE | `ug`, `mcg` |
| 비타민 B12 (코발라민) | Cobalamin | `vitamin_b12_ug` | ug | `ug`, `mcg` |
| 비타민 C | Vitamin C | `vitamin_c_mg` | mg | `mg` |
| 비타민 D | Vitamin D | `vitamin_d_ug` | ug | `ug`, `mcg`, `IU` |
| 비타민 E | Vitamin E | `vitamin_e_mg` | mg α-TE | `mg`, `IU` |
| 비타민 K | Vitamin K | `vitamin_k_ug` | ug | `ug`, `mcg` |

> 단위 환산 (라벨이 IU로 표기된 경우):
> - 비타민 A: 1 IU ≈ 0.3 μg RAE
> - 비타민 D: 1 IU = 0.025 μg (40 IU = 1 μg)
> - 비타민 E: 1 IU ≈ 0.67 mg α-TE (천연), 0.45 mg (합성)

---

## 3. 멀티비타민 / 미네랄 / 기타 영양소 코드 (참고)

| 영양소 (한글) | nutrient_code (예) | 기본 단위 |
| --- | --- | --- |
| 칼슘 | `calcium_mg` | mg |
| 마그네슘 | `magnesium_mg` | mg |
| 철분 | `iron_mg` | mg |
| 아연 | `zinc_mg` | mg |
| 셀레늄 | `selenium_ug` | ug |
| 망간 | `manganese_mg` | mg |
| 구리 | `copper_mg` 또는 `copper_ug` | mg 또는 ug |
| 크롬 | `chromium_ug` | ug |
| 몰리브덴 | `molybdenum_ug` | ug |
| 요오드 | `iodine_ug` | ug |
| 오메가-3 (EPA+DHA) | `omega3_mg` | mg |
| 루테인 | `lutein_mg` | mg |
| 지아잔틴 | `zeaxanthin_mg` | mg |
| 글루코사민 | `glucosamine_mg` | mg |
| 콘드로이친 | `chondroitin_mg` | mg |
| MSM | `msm_mg` | mg |
| 강황 / 커큐민 | `curcumin_mg` | mg |
| 쏘팔메토 | `saw_palmetto_mg` | mg |
| 은행잎 (Ginkgo) | `ginkgo_mg` | mg |
| 밀크씨슬 (실리마린) | `silymarin_mg` | mg |

> 실제 코드는 `data/nutrition_reference/nutrient/nutrient_codes.json`에서 확인. `nutrient_code_candidates` 에 적을 때 `match_method: "alias_exact"`(라벨에 한글/영어로 정확히 일치) 또는 `"alias_fuzzy"`(부분 일치), `confidence: 1.0`(사람 검수)로 기록한다.

---

## 4. 라벨링 표준 (V2 vs V3 차이 요약)

### V2 (`SupplementParsedSnapshotV2`)
- `product`: `{product_name, manufacturer, barcode_text, barcode_format}`
- `ingredient_candidates[]` 각 항목:
  ```json
  {
    "display_name": "비타민 A",
    "normalized_name": "비타민 a",
    "nutrient_code_candidates": [
      {"nutrient_code": "vitamin_a_ug", "match_method": "alias_exact", "confidence": 1.0}
    ],
    "amount": 750.0,
    "unit": "ug",
    "daily_amount": 750.0,
    "confidence": 1.0,
    "source": "manual",
    "evidence_refs": []
  }
  ```

> 핵심: `source` 는 schema literal — 사람 검수 완료 시 **`"manual"`** (또는 `"user_confirmed"`) 로 설정. 자동 시드 상태로 남아 있는 항목은 `"ocr_llm_preview"`.

### V3 (`SupplementParsedSnapshotV3`)
- `source` 에 `parser_schema_version: "supplement-parser-output-v2"`, `raw_model_response_stored: false` 추가
- `product`: `{product_name, manufacturer, barcode_candidates: [], evidence_refs: []}` (V2의 barcode_text/format 대체)
- `ingredients[]` (V2 `ingredient_candidates`와 동일 구조 + `daily_unit`)
- `precautions[]` 항목에 `severity: "unknown"` 추가
- `evidence_spans[]` 별도 (라벨링 시 비워두면 됨)

### V2/V3 공통 작성 필드
- `requires_user_confirmation: true` (그대로)
- `source.raw_image_stored / raw_ocr_text_stored / raw_provider_payload_stored`: 모두 `false` (필수)
- `serving`: `serving_size_text` (예: "1일 1정"), `serving_amount: 1`, `serving_unit: "정"`, `daily_servings: 1`
- `intake_method.text`: 라벨에 적힌 섭취 안내 그대로
- `intake_method.structured.frequency`: `"daily"` / `"weekly"` / `"as_needed"` / `"unknown"`
- `precautions[]`: 임산부/약물 복용자 주의 등
- `functional_claims[]`: 라벨에 적힌 기능성 문구. **의료 표현 금지** (`치료`, `진단`, `처방` 등)
- `low_confidence_fields: []` (사람 라벨이므로 비움)
- `warnings`: 라벨링 완료 시 **`ground_truth_pending_human_review` 토큰을 반드시 제거**. `category:...`, `labels:...` 는 유지.

---

## 5. 라벨링 워크플로 (1 fixture 기준)

### 5.1 신규 fixture 의 skeleton 생성 (자동)

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

.venv/bin/python scripts/label_ground_truth.py \
  --fixture-id naver-live-0024 \
  --category 뇌_은행잎 \
  --output ../Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-live-0024.snapshot_v2.json \
  --seed-ingredients "은행잎 추출물, 비타민 E"
```

> 기존 파일이 있으면 skip 한다. `--overwrite` 로 강제 대체 가능.

### 5.2 사람 검수 (이미지 보면서)

1. 이미지 열기:
   ```bash
   open "/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/data/supplement_images/private_workspace/stage0_naver/images/naver-live-0024.jpg"
   ```
2. V2 파일 열기:
   ```
   backend/Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-live-0024.snapshot_v2.json
   ```
3. `product.product_name`, `product.manufacturer` 채우기. 바코드가 라벨에 있으면 `barcode_text`도.
4. `serving` 4개 필드 채우기.
5. `ingredient_candidates[]` 각 항목을 라벨의 영양·기능정보 표 한 줄씩 옮긴다.
   - `display_name`: 한글/영문 그대로
   - `normalized_name`: 소문자 + 공백 정리 (예: "비타민 A" → "비타민 a")
   - `amount`, `unit`: 라벨 그대로
   - `daily_amount`: `amount × daily_servings`
   - `nutrient_code_candidates`: §2 / §3 표 참조
   - `confidence: 1.0`
   - **`source: "manual"`** (사람 검수 완료 표시)
6. `intake_method.text`, `precautions`, `functional_claims` 채우기.
7. **`warnings` 에서 `ground_truth_pending_human_review` 제거.**
8. V3 파일도 같은 정보로 채우기 (구조 차이만 주의).

### 5.3 검증

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

# 단일 fixture schema 검증
.venv/bin/python -c "
import json; from pathlib import Path; import sys
sys.path.insert(0, 'Nutrition-backend')
from src.models.schemas.supplement_snapshot import SupplementParsedSnapshotV2, SupplementParsedSnapshotV3
d = Path('Nutrition-backend/tests/fixtures/supplement_labels/expected')
SupplementParsedSnapshotV2.model_validate(json.loads((d/'naver-live-0024.snapshot_v2.json').read_text()))
SupplementParsedSnapshotV3.model_validate(json.loads((d/'naver-live-0024.snapshot_v3.json').read_text()))
print('ok')
"

# 전체 진행률 확인
.venv/bin/python scripts/validate_ground_truth.py \
  --expected-dir Nutrition-backend/tests/fixtures/supplement_labels/expected/ \
  --target-count 45
```

### 5.4 Tier 4 (만성질환 우선) fixture 수집

Tier 4 는 외장 SSD 의 새 카테고리에서 16 fixture 를 신규 수집해야 한다. 두 가지 방법:

**방법 A — 카테고리 필터 (만성질환 카테고리만 추출)**:

```bash
.venv/bin/python scripts/prepare_supplement_ocr_live_manifest.py \
  --source-root "/Volumes/Corsair EX300U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver" \
  --work-dir ../data/supplement_images/private_workspace/stage0_naver_chronic \
  --sample-size 16 \
  --category-filter "오메가3,코엔자임Q10,혈관_낫토_폴리코사놀,식이섬유,비타민D,비타민K,스트레스_아쉬와간다,수면_멜라토닌" \
  --scan-limit 60000 \
  --min-width 320 --min-height 240 \
  --max-bytes 20000000 \
  --min-label-score 2 \
  --manifest-name manifest.json
```

**방법 B — 만성질환 가중 샘플링 (전체 카테고리에서 만성질환 가중치 적용)**:

```bash
.venv/bin/python scripts/prepare_supplement_ocr_live_manifest.py \
  --source-root "/Volumes/Corsair EX300U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver" \
  --work-dir ../data/supplement_images/private_workspace/stage0_naver_chronic \
  --sample-size 16 \
  --chronic-disease-priority \
  --scan-limit 60000 \
  --min-label-score 2 \
  --manifest-name manifest.json
```

수집 후 라벨링 시 `--chronic-disease-targets` 옵션으로 V3 schema `chronic_disease_indications` 필드 초기값 세팅:

```bash
.venv/bin/python scripts/label_ground_truth.py \
  --fixture-id naver-chronic-0001 \
  --category 오메가3 \
  --output ../Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-chronic-0001.snapshot_v3.json \
  --chronic-disease-targets "cardiovascular,dyslipidemia" \
  --seed-ingredients "EPA, DHA, 비타민E"
```

---

## 6. 진행 추적 체크리스트

라벨링 완료한 fixture 에 ✅ 마크. 30 개 모두 마치면 Stage 0 게이트 통과 → P0-3 메트릭이 실측 수치로 채워진다.

### Tier 1 (우선) — 0/9 완료

- [ ] `naver-live-0029` — 멀티비타민, V2 / V3
- [ ] `naver-live-0045` — 멀티비타민, V2 / V3
- [ ] `naver-live-0013` — 멀티비타민, V2 / V3
- [ ] `naver-live-0024` — 뇌_은행잎, V2 / V3
- [ ] `naver-live-0022` — 기타, V2 / V3
- [ ] `naver-live-0023` — 남성_쏘팔메토, V2 / V3
- [ ] `naver-live-0035` — 강황_커큐민, V2 / V3
- [ ] `naver-live-0041` — 다이어트_체지방, V2 / V3
- [ ] `naver-live-0004` — 관절_MSM_콘드로이친, V2 / V3

### Tier 2 (카테고리 다양성) — 0/14 완료

- [ ] `naver-live-0027` — 루테인_눈, V2 / V3
- [ ] `naver-live-0018` — HMB_타우린, V2 / V3
- [ ] `naver-live-0001` — BCAA_EAA, V2 / V3
- [ ] `naver-live-0019` — 강황_커큐민, V2 / V3
- [ ] `naver-live-0005` — 글루코사민, V2 / V3
- [ ] `naver-live-0011` — 루테인_눈, V2 / V3
- [ ] `naver-live-0012` — 마그네슘, V2 / V3
- [ ] `naver-live-0042` — 단백질_프로틴, V2 / V3
- [ ] `naver-live-0014` — 밀크씨슬_간, V2 / V3
- [ ] `naver-live-0034` — HMB_타우린, V2 / V3
- [ ] `naver-live-0017` — BCAA_EAA, V2 / V3
- [ ] `naver-live-0046` — 밀크씨슬_간, V2 / V3
- [ ] `naver-live-0007` — 남성_쏘팔메토, V2 / V3
- [ ] `naver-live-0009` — 다이어트_체지방, V2 / V3

### Tier 3 (비타민 단일) — 0/7 완료

- [ ] `naver-live-0015` — 비타민A, V2 / V3
- [ ] `naver-live-0031` — 비타민A, V2 / V3
- [ ] `naver-live-0047` — 비타민A (webp), V2 / V3
- [ ] `naver-live-0032` — 비타민B, V2 / V3
- [ ] `naver-live-0048` — 비타민B, V2 / V3
- [ ] `naver-live-0016` — 비타민B (ocrerror, 이미지 품질 확인 후 진행), V2 / V3
- [ ] `naver-live-0020` — 관절_MSM_콘드로이친, V2 / V3

### Tier 4 (만성질환 우선) — 0/16 완료

- [ ] `naver-chronic-0001` — 오메가3, V2 / V3 / `chronic_disease_indications: ["cardiovascular","dyslipidemia"]`
- [ ] `naver-chronic-0002` — 오메가3, V2 / V3
- [ ] `naver-chronic-0003` — 코엔자임Q10, V2 / V3 / `chronic_disease_indications: ["cardiovascular","hypertension"]`
- [ ] `naver-chronic-0004` — 코엔자임Q10, V2 / V3
- [ ] `naver-chronic-0005` — 혈관_낫토_폴리코사놀, V2 / V3 / `chronic_disease_indications: ["cardiovascular","dyslipidemia"]`
- [ ] `naver-chronic-0006` — 혈관_낫토_폴리코사놀, V2 / V3
- [ ] `naver-chronic-0007` — 식이섬유, V2 / V3 / `chronic_disease_indications: ["dyslipidemia","diabetes"]`
- [ ] `naver-chronic-0008` — 식이섬유, V2 / V3
- [ ] `naver-chronic-0009` — 비타민D, V2 / V3 / `chronic_disease_indications: ["osteoporosis"]`
- [ ] `naver-chronic-0010` — 비타민D, V2 / V3
- [ ] `naver-chronic-0011` — 비타민K, V2 / V3 / `chronic_disease_indications: ["osteoporosis"]`
- [ ] `naver-chronic-0012` — 비타민K, V2 / V3
- [ ] `naver-chronic-0013` — 스트레스_아쉬와간다, V2 / V3 / precautions 에 SSRI 상호작용 명시 ⚠️
- [ ] `naver-chronic-0014` — 스트레스_아쉬와간다, V2 / V3
- [ ] `naver-chronic-0015` — 수면_멜라토닌, V2 / V3
- [ ] `naver-chronic-0016` — 수면_멜라토닌, V2 / V3

> Tier 1 9 개만 완성해도 `ingredient_name_exact_rate` + 한/영 CER/WER 의 첫 신호가 잡힌다.
> Tier 1~3 30 개 완성 시 Stage 0 게이트 통과 + 카테고리별 신뢰성 있는 비교 가능.
> Tier 4 16 개 완성 시 `accuracy_by_condition` (B형 페르소나 시나리오) 메트릭에 만성질환별 분리 정확도 측정 가능.

---

## 7. 자주 발생하는 문제

- **단위 표기**: PaddleOCR 가 `μg` 를 `ug` 로 읽거나 `IU` 를 `IU` 로 잘 읽지만, `ug` ↔ `μg` 같은 표기는 라벨링 시 한 가지로 통일한다 (예: `ug`).
- **여러 nutrient_code 후보**: 한 영양소가 여러 형태(예: 비타민 D2 vs D3)인 경우 가장 가까운 단일 코드를 first, 나머지를 list 후속 항목으로.
- **nutrient_code 모름**: `nutrient_code_candidates: []` 로 두고 `warnings` 에 `nutrient_code_unmatched:<display_name>` 추가.
- **라벨이 사진에 안 나오는 부분**: `null` 또는 빈 list 로 두고 `warnings` 에 `field_not_visible:<field>` 추가.
- **bracket/괄호**: `display_name` 에 `(50% NE)` 같은 보조 표기는 그대로 유지. `normalized_name` 에서는 제거.
- **OCR error fixture (`naver-live-0016`)**: 이미지 자체가 영양정보 부족 또는 가독성 불량일 수 있음. 라벨링 불가능 판단 시 `warnings` 에 `image_label_insufficient` 추가 후 skip.

---

## 8. 라벨링 완료 후 다음 단계

1. ≥ 30 개 라벨링 완료 (또는 부분 완성 시점)
2. `validate_ground_truth.py` 로 schema + human-labeled 진행률 확인
3. P0-1 / P0-3 메트릭 인프라는 이미 통합 완료 → Stage 0 재실행하면 다음 신규 메트릭이 채워짐:
   - `ingredient_name_exact_rate` (OCR regex 기반, 기존)
   - `llm_ingredient_name_exact_rate` (Ollama LLM 파서 기반, **신규**)
   - `llm_parse_success_rate` (**신규**)
   - `cer_ko_avg`, `cer_en_avg`, `wer_ko_avg`, `wer_en_avg` (한/영 분리 CER/WER, **신규**)
4. 재현 명령:
   ```bash
   cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
   RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
   LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=true \
   LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false \
     .venv/bin/python scripts/collect_supplement_ocr_observations.py \
     --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
     --output-dir ../outputs/generated/ocr-eval/observations-with-llm \
     --providers paddleocr_local \
     --llm-parse
   ```

이 워크시트는 `outputs/generated/ocr-eval/stage0-labeling-worksheet.md` 에 commit 한다 (재현성 + 사용자 reference).
