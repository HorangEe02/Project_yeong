# 사용자 다음 단계 작업 가이드 (Top 3 P0 완료 이후)

> 작성일: **2026-05-21**
> 짝 문서: [project-status-report.md](./project-status-report.md) (현황 분석), [stage0-labeling-worksheet.md](../../generated/ocr-eval/stage0-labeling-worksheet.md) (라벨링 표준)
> 전제: Top 3 P0 (LLM 메트릭 분리 / 한·영 CER·WER / 라벨링 도구) 모두 구현 완료. 회귀 0, 테스트 702 passed.

---

## 한 페이지 요약

| 단계 | 누구 | 예상 시간 | 산출물 |
|---|---|---|---|
| **STEP 1**: Ground truth 라벨링 (≥30 fixture) | **사용자** | 3~5일 | `expected/*.snapshot_v{2,3}.json` 30개 human-labeled |
| **STEP 2**: Stage 0 재실행 (LLM + CER/WER 활성화) | 사용자 또는 Claude | 10~15분 | `observations-with-llm/`, `three-tier-with-llm/` 보고서 |
| **STEP 3**: 결과 해석 + 95% 목표 갭 분석 | 사용자 + Claude | 1~2시간 | 의사결정: P1 진행 / 운영 fixture 수집 / 모델 교체 검토 |
| **STEP 4** *(선택)*: 운영 환경 fixture 수집 후 재측정 | 사용자 | 1~2주 | 사용자 촬영 라벨 fixture + 재측정 보고서 |

**핵심 메시지**: STEP 1 ground truth 라벨링이 진행될수록 STEP 2의 메트릭들이 의미 있는 수치로 채워진다. **1개라도 라벨링되면 첫 신호 측정 가능**, 30개 완성 시 Stage 0 게이트 통과.

---

## STEP 1 — Ground Truth 라벨링 (사용자, 3~5일)

### 1.1 라벨링 대상 30개 fixture

전체 인벤토리: [stage0-labeling-worksheet.md §1](../../generated/ocr-eval/stage0-labeling-worksheet.md)

권장 진행 순서:
- **Tier 1 (9개, 우선)**: 멀티영양소·텍스트 풍부 → 가장 빠르게 메트릭에 신호 줌
- **Tier 2 (14개, 다양성)**: 16개 카테고리 균형 확보
- **Tier 3 (7개, 비타민 단일)**: 한·영 분리 CER/WER baseline에 직접 신호

### 1.2 단일 fixture 라벨링 절차

**1) Skeleton 자동 생성**

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

.venv/bin/python scripts/label_ground_truth.py \
  --fixture-id naver-live-0029 \
  --category 멀티비타민 \
  --output ../Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-live-0029.snapshot_v2.json \
  --seed-ingredients "비타민 A, 비타민 C, 비타민 D, 마그네슘"
```

> `--seed-ingredients`는 선택. 미리 알고 있는 ingredient를 미리 채워두면 사람 검수가 빠르다. 없으면 생략.
> 기존 파일이 있으면 skip; `--overwrite` 로 강제 대체 가능.

**2) 이미지 열기**

```bash
open "/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/data/supplement_images/private_workspace/stage0_naver/images/naver-live-0029.jpg"
```

**3) V2 snapshot JSON 편집**

`backend/Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-live-0029.snapshot_v2.json` 을 텍스트 에디터로 열고 다음을 채운다.

| 필드 | 채울 내용 |
|---|---|
| `product.product_name` | 라벨에 표시된 제품명 (현재 `"TBD"`) |
| `product.manufacturer` | 제조사 (있으면) |
| `product.barcode_text` | 바코드 (있으면, 보통 `null`) |
| `serving.serving_size_text` | "1일 1정", "1회 2정" 등 |
| `serving.serving_amount` | 숫자 (예: 1) |
| `serving.serving_unit` | "정", "캡슐", "g" 등 |
| `serving.daily_servings` | 1일 권장 횟수 |
| `ingredient_candidates[]` | 라벨의 영양·기능정보 표를 한 줄씩 옮김 (아래 1.3 참조) |
| `intake_method.text` | 라벨의 섭취 안내 문구 그대로 |
| `intake_method.structured.frequency` | `"daily"` / `"weekly"` / `"as_needed"` |
| `precautions[]` | 임산부/약물 복용 시 주의 등 |
| `functional_claims[]` | 기능성 문구 (의료 표현 금지) |
| `warnings` | **`"ground_truth_pending_human_review"` 토큰을 제거**. `category:...`, `labels:...` 는 유지 |

**4) ingredient_candidates 채우기 (핵심)**

자동 시드된 항목은 모두 `source: "ocr_llm_preview"` + `confidence: 0.0` 상태. 사람 검수 시 다음으로 갱신:

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

**중요 변경 3가지**:
- `source`: `"ocr_llm_preview"` → **`"manual"`** (또는 `"user_confirmed"`)
- `confidence`: `0.0` → `1.0`
- `nutrient_code_candidates[].confidence`: `1.0` (사람 검수)

영양소 코드 참조: [worksheet §2, §3](../../generated/ocr-eval/stage0-labeling-worksheet.md)

**5) V3 파일도 같은 정보로 채우기**

`naver-live-0029.snapshot_v3.json` — V2와 구조가 살짝 다름. 차이는 [worksheet §4](../../generated/ocr-eval/stage0-labeling-worksheet.md) 참조.

핵심 V3 차이:
- `ingredient_candidates` → `ingredients`
- `product.barcode_text/barcode_format` → `product.barcode_candidates[]`
- `precautions[]` 각 항목에 `severity: "unknown"` 추가
- `source` 에 `parser_schema_version: "supplement-parser-output-v2"`, `raw_model_response_stored: false` 필드 추가

**6) 단일 파일 schema 검증**

```bash
.venv/bin/python -c "
import json, sys
sys.path.insert(0, 'Nutrition-backend')
from src.models.schemas.supplement_snapshot import SupplementParsedSnapshotV2, SupplementParsedSnapshotV3
from pathlib import Path
d = Path('Nutrition-backend/tests/fixtures/supplement_labels/expected')
SupplementParsedSnapshotV2.model_validate(json.loads((d/'naver-live-0029.snapshot_v2.json').read_text()))
SupplementParsedSnapshotV3.model_validate(json.loads((d/'naver-live-0029.snapshot_v3.json').read_text()))
print('ok')
"
```

`ok` 가 출력되면 schema 통과.

### 1.3 진행률 확인 (매 5~10개 라벨링 후 권장)

```bash
.venv/bin/python scripts/validate_ground_truth.py \
  --expected-dir Nutrition-backend/tests/fixtures/supplement_labels/expected/ \
  --target-count 30
```

출력 예시:
```
Validation summary:
  V2 files: 15
  V2 schema valid: 15/15
  V2 human-labeled: 3/15
  V3 files: 15
  V3 schema valid: 15/15
  V3 human-labeled: 3/15

Stage 0 gate progress (V2): 3/30 (10.0%)
```

`V2 human-labeled` 가 1 이상으로 올라가야 STEP 2에서 진짜 메트릭이 채워진다. ≥30 이 되면 Stage 0 게이트 통과.

### 1.4 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| schema validation 실패 | source 가 `"ocr_llm_preview"` / `"manual"` / `"user_confirmed"` 외의 값 | schema literal 만 허용 — 위 3 가지 중 하나로 |
| `human-labeled: 0` 인데 다 채웠다고 생각 | `warnings` 에 `ground_truth_pending_human_review` 남아있음 | 그 토큰을 list 에서 제거 |
| `nutrient_code` 를 모르겠다 | 라벨에 표기된 영양소가 표에 없거나 한국어 별칭 다름 | `nutrient_code_candidates: []` 로 두고 `warnings` 에 `nutrient_code_unmatched:<display_name>` 추가 |
| 라벨에 정보가 부족함 (예: naver-live-0016) | 광고 이미지라서 영양정보 누락 | `warnings` 에 `image_label_insufficient` 추가 후 skip |
| `μg` vs `ug` 표기 차이 | OCR 가 한 가지로 읽음 | 라벨링 시 `ug` 로 통일 |

---

## STEP 2 — Stage 0 재실행 (라벨링 ≥1개 완료 후, 10~15분)

### 2.1 사전 점검

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

# PaddleOCR 준비 상태 확인
.venv/bin/python scripts/probe_paddleocr_runtime.py

# Ollama 로컬 서버 가동 확인 (필요 모델: qwen3.5:9b)
ollama list | grep qwen3.5
# 없으면: ollama pull qwen3.5:9b
```

### 2.2 OCR 관찰 수집 (`--llm-parse` 활성화)

```bash
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=true \
LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-with-llm \
  --providers paddleocr_local \
  --llm-parse
```

> 50 fixture × 약 9초 = **8~10분** 소요 (macOS CPU 기준).
> `--llm-parse` 가 핵심: 이게 있어야 LLM 메트릭이 채워진다.
> textline_orientation은 4-way isolation 결과(`stage1-l1h-isolation.md`)에 따라 **False** 유지가 sweet spot.

### 2.3 Three-tier manifest 빌드

```bash
.venv/bin/python scripts/build_three_tier_manifest.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest-with-observations.json \
  --observations ../outputs/generated/ocr-eval/observations-with-llm/supplement-ocr-observations.jsonl \
  --output ../data/supplement_images/private_workspace/stage0_naver/manifest-three-tier-llm.jsonl
```

### 2.4 평가 보고서 생성

```bash
.venv/bin/python scripts/evaluate_ocr_three_tier.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest-three-tier-llm.jsonl \
  --output-dir ../outputs/generated/ocr-eval/three-tier-with-llm
```

생성되는 파일:
- `three-tier-with-llm/ocr-three-tier-evaluation.json` — 모든 메트릭 (JSON)
- `three-tier-with-llm/ocr-three-tier-evaluation.md` — 마크다운 보고서

### 2.5 결과 확인 — 신규 7개 필드

```bash
.venv/bin/python -c "
import json
data = json.load(open('../outputs/generated/ocr-eval/three-tier-with-llm/ocr-three-tier-evaluation.json'))
metrics = data['providers']['paddleocr_local']
print('--- 기존 메트릭 ---')
print(f\"  text_non_empty_rate         : {metrics.get('text_non_empty_rate')}\")
print(f\"  ingredient_name_exact_rate  : {metrics.get('ingredient_name_exact_rate')}\")
print('--- 신규 LLM 메트릭 (P0-1) ---')
print(f\"  llm_parse_attempt_count       : {metrics.get('llm_parse_attempt_count')}\")
print(f\"  llm_parse_success_rate        : {metrics.get('llm_parse_success_rate')}\")
print(f\"  llm_ingredient_name_exact_rate: {metrics.get('llm_ingredient_name_exact_rate')}\")
print('--- 신규 한/영 CER/WER (P0-3) ---')
print(f\"  cer_ko_avg : {metrics.get('cer_ko_avg')}\")
print(f\"  cer_en_avg : {metrics.get('cer_en_avg')}\")
print(f\"  wer_ko_avg : {metrics.get('wer_ko_avg')}\")
print(f\"  wer_en_avg : {metrics.get('wer_en_avg')}\")
"
```

### 2.6 Redaction 회귀 확인 (필수)

```bash
grep -rn '"raw_artifacts_stored": *true\|"raw_ocr_text_stored": *true\|"raw_provider_payload_stored": *true' \
  ../outputs/generated/ocr-eval/ && echo "REDACTION FAILED" || echo "redaction OK"
```

`redaction OK` 가 나와야 함. raw 데이터 누출 시 즉시 멈추고 수정 필요.

### 2.7 라벨링 진행률에 따라 예상되는 메트릭 상태

| 라벨링 fixture 수 | `ingredient_name_exact_rate` | `llm_ingredient_name_exact_rate` | `cer_ko_avg` | `wer_en_avg` |
|---|---|---|---|---|
| **0** | `null` (분모 0) | `null` | `null` | `null` |
| **1~5** | 약간의 신호 | LLM 파서 동작 시 채워짐 | 측정 시작 | 측정 시작 |
| **≥10** | 안정적 수치 | 안정적 수치 | 카테고리 평균에 수렴 | 카테고리 평균에 수렴 |
| **≥30** | **Stage 0 게이트 통과**, 신뢰성 있는 baseline | 동일 | 동일 | 동일 |

---

## STEP 3 — 결과 해석 + 95% 목표 갭 분석 (1~2시간)

### 3.1 메트릭별 해석 가이드

#### 3.1.1 `ingredient_name_exact_rate` (OCR regex 기반)

- **0.95 이상**: OCR 텍스트에 모든 expected ingredient 명이 그대로 등장한다는 의미. PaddleOCR 자체 인식이 충분히 좋다는 신호.
- **0.85~0.94**: 일부 ingredient는 정자체로 인식되지 못함. domain correction(P1-3) 또는 alias 사전 보강이 필요.
- **0.85 미만**: OCR 엔진 자체 정확도 부족. L1 escalation (Google Vision) 검토 필요.

#### 3.1.2 `llm_ingredient_name_exact_rate` (Ollama LLM 파서 기반)

- **OCR보다 높음 (예: OCR 0.86, LLM 0.92)**: LLM이 OCR 오인식을 의미 추정으로 보정 중. 정상 패턴.
- **OCR과 비슷함 (예: 둘 다 0.86)**: LLM이 추가 가치를 못 내고 있음. 프롬프트 튜닝 또는 모델 변경 검토.
- **OCR보다 낮음**: LLM이 hallucinate 중. 즉시 조사 필요.

#### 3.1.3 `cer_ko_avg` / `cer_en_avg` (한·영 분리 CER)

CER = 편집 거리 / 기준 길이. **낮을수록 좋음**.

- **CER ≤ 0.05 (5%)**: 우수
- **CER 0.05~0.10**: 양호 (목표 영역)
- **CER 0.10~0.20**: 개선 여지
- **CER > 0.20**: 모델/전처리 변경 검토

**한·영 비교 패턴**:
- `cer_ko > cer_en`: 한국어 인식이 약함. korean_PP-OCRv5_mobile_rec 모델 한계 가능성.
- `cer_en > cer_ko`: 영문 약함. PaddleOCR 영문 모델 추가 또는 도메인 정렬.
- 두 값 비슷 + 모두 낮음: 균형 잡힌 성능.

#### 3.1.4 `wer_ko_avg` / `wer_en_avg` (한·영 분리 WER)

WER = 단어 수준 편집 거리. CER보다 보통 약간 높음 (한 단어 안의 모든 오류가 1로 카운트되기 때문).

- WER 가 CER 의 2배 이상이면 → 단어 경계 오인식이 많음 (공백 처리 문제 가능성).

### 3.2 95% 목표 대비 갭 분석 매트릭스

라벨링 30개 완료 후 첫 측정에서:

| 시나리오 | 의사결정 |
|---|---|
| **모든 정확도 ≥ 0.95** | 🎉 목표 달성. 운영 환경 fixture로 generalization 검증 (STEP 4) |
| **CER ≤ 0.05 + ingredient_name_exact ≥ 0.90 but LLM_exact < OCR_exact** | LLM 프롬프트 튜닝 우선 (P1-3) |
| **CER 0.05~0.15 + 정확도 0.85~0.92** | L1-G domain correction + 운영 fixture 수집 (P1-1, P1-3) |
| **CER > 0.15 또는 정확도 < 0.85** | PaddleOCR 모델 변경 검토 또는 L1 Google Vision 승격 |
| **`cer_ko_avg`만 높음 (한국어 약함)** | korean_PP-OCRv5_mobile_rec 한계 → korean_PP-OCRv5_server_rec 또는 CLOVA 백업 |
| **`cer_en_avg`만 높음 (영문 약함)** | 영문 dense table fixture 추가 + PaddleOCR 영문 모델 결합 |

### 3.3 결과 보고서 작성

측정 후 다음 형식으로 짧은 보고서를 `outputs/generated/ocr-eval/` 에 추가:

```
파일명: stage0-first-real-metrics-YYYY-MM-DD.md

# Stage 0 첫 실측 메트릭 보고서

## 측정 환경
- 날짜: YYYY-MM-DD
- 라벨링 완료 fixture: N/30
- 옵션: --llm-parse, ori on / txt off

## 핵심 수치
[복사]

## 95% 목표 대비 갭
[표]

## 다음 액션
[3.2 매트릭스에서 선택]
```

---

## STEP 4 (선택) — 운영 환경 Fixture 수집 후 재측정 (1~2주)

### 왜 필요한가
현재 fixture(`stage0_naver`)는 네이버 광고 사진 90%+ 편중 → 운영 환경(사용자가 라벨을 정면 촬영) 대표성 부족. status report §1 에서 fixture 편중 경고 명시.

### 수집 절차

1. **사용자 촬영 라벨 사진 모으기**: 10~20장 (영양·기능정보 dense table 위주, 한국 시판 영양제)
2. **manifest 생성**:
   ```bash
   .venv/bin/python scripts/prepare_supplement_ocr_live_manifest.py \
     --source-root <촬영 이미지 폴더> \
     --work-dir ../data/supplement_images/private_workspace/operational_fixtures \
     --sample-size 20 \
     --min-label-score 3 \
     --manifest-name manifest.json
   ```
3. **ground truth 라벨링**: 각 fixture에 대해 STEP 1 절차 반복
4. **Stage 0 재실행**: STEP 2 명령에서 `--manifest` 만 operational_fixtures로 변경
5. **광고 fixture vs 운영 fixture 비교**:
   - `cer_ko_avg`, `wer_ko_avg`, `ingredient_name_exact_rate` 가 운영 환경에서 더 좋아져야 함
   - 양 fixture 간 차이가 크면 → 광고 fixture 의 측정값은 "fixture-specific signal"로 해석
   - 운영 fixture 결과가 95% 도달하면 → **목표 달성** 선언

---

## 부록 A — 도구 사용법 치트시트

### `label_ground_truth.py` (skeleton 생성)

```bash
.venv/bin/python scripts/label_ground_truth.py \
  --fixture-id <ID> \
  --category <카테고리> \
  --output <경로/ID.snapshot_v2.json> \
  [--seed-ingredients "ingredient 1, ingredient 2, ..."] \
  [--overwrite]
```

옵션:
- `--seed-ingredients`: 미리 알고 있는 ingredient 자동 시드. 사람 검수 시 source를 `manual`로 바꿔주면 됨.
- `--overwrite`: 기존 파일 강제 대체.

### `validate_ground_truth.py` (진행률 확인)

```bash
.venv/bin/python scripts/validate_ground_truth.py \
  --expected-dir Nutrition-backend/tests/fixtures/supplement_labels/expected/ \
  --target-count 30
```

옵션:
- `--target-count`: Stage 0 게이트 목표 (기본 30).

### `collect_supplement_ocr_observations.py` (OCR 수집)

```bash
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=true \
LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest <manifest.json> \
  --output-dir <observations dir> \
  --providers paddleocr_local \
  --llm-parse
```

핵심 옵션:
- `--llm-parse`: Ollama LLM 파서 활성화 (LLM 메트릭 측정 필수)
- env `LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false`: 4-way isolation 결과에 따라 false 권장

### `evaluate_ocr_three_tier.py` (평가)

```bash
.venv/bin/python scripts/evaluate_ocr_three_tier.py \
  --manifest <three-tier manifest.jsonl> \
  --output-dir <report dir>
```

생성:
- `<report dir>/ocr-three-tier-evaluation.json` (모든 메트릭)
- `<report dir>/ocr-three-tier-evaluation.md` (사람용 보고서)

---

## 부록 B — 트러블슈팅

### Q. `--llm-parse` 가 정상 동작 안 함

체크리스트:
1. Ollama 서버 가동: `curl http://127.0.0.1:11434/api/tags` 가 응답하는지
2. 모델 존재: `ollama list | grep qwen3.5`
3. `.env` 에 `OLLAMA_BASE_URL`, `OLLAMA_MODEL_TEXT` 설정 확인

실패 시 observation row에 `llm_parse_status: "error"` + `llm_parse_error_code` 가 기록되니 그걸 보고 진단.

### Q. PaddleOCR 가 모든 fixture에서 ocrerror

체크리스트:
1. `RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true` 환경변수
2. 모델 다운로드: 첫 실행 시 약 1GB 다운로드 (cache: `~/.paddleocr/`)
3. macOS arm64 GPU wheel 부재 → CPU only 가 정상

### Q. schema validation 실패하는데 어느 필드인지 모르겠음

```bash
.venv/bin/python scripts/validate_ground_truth.py \
  --expected-dir Nutrition-backend/tests/fixtures/supplement_labels/expected/ \
  --target-count 30
```

오류가 있으면 출력 끝의 `Errors:` 섹션에 파일별 첫 3개 schema 오류 표시.

### Q. ground truth 라벨링이 부담스럽다

권장 분할 작업:
- 1일차: Tier 1 9개 (멀티영양소, 텍스트 풍부)
- 2~3일차: Tier 2 14개 (카테고리 다양성)
- 4~5일차: Tier 3 7개 (비타민 단일)

1개당 약 15~30분 소요 예상 (라벨이 dense table 인 경우). Tier 1 9개만 끝내도 STEP 2에서 첫 신호 측정 가능 — 부분 완성으로도 의미 있음.

---

## 부록 C — 완료 기준 체크리스트

STEP 1 (사용자 라벨링):
- [ ] `validate_ground_truth.py` 가 `V2 human-labeled: ≥30/30` 출력
- [ ] 모든 V2/V3 파일 schema valid
- [ ] V2 만큼 V3도 채워짐 (`V3 human-labeled` 동일)

STEP 2 (Stage 0 재실행):
- [ ] `observations-with-llm/supplement-ocr-observations.jsonl` 생성됨
- [ ] `three-tier-with-llm/ocr-three-tier-evaluation.json` 에 7개 신규 필드 모두 non-null
- [ ] `redaction OK` 확인

STEP 3 (결과 해석):
- [ ] 짧은 보고서 `stage0-first-real-metrics-YYYY-MM-DD.md` 작성
- [ ] 95% 목표 대비 갭 분석 매트릭스(§3.2)에서 다음 액션 결정
- [ ] (해당 시) status report 갱신: 신호등 평가에서 🔴 → 🟡 or 🟢 로 변경

---

**참고 문서**:
- [project-status-report.md](./project-status-report.md) — 2026-05-21 현황 종합 평가
- [stage0-labeling-worksheet.md](../../generated/ocr-eval/stage0-labeling-worksheet.md) — 라벨링 표준 + 30개 fixture 인벤토리
- [stage0-summary.md](../../generated/ocr-eval/stage0-summary.md) — Stage 0 baseline 측정 보고서
- [stage1-l1h-isolation.md](../../generated/ocr-eval/stage1-l1h-isolation.md) — 4-way isolation 결과 (textline_orientation revert 근거)
