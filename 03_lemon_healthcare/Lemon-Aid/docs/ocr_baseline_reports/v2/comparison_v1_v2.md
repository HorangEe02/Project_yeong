# OCR 베이스라인 v1 → v2 비교 (빠른 win 3개 적용 후)

> **측정일**: 2026-05-20 (v2)
> **데이터셋**: 합성 60장 (동일, seed=42)
> **적용된 변화**:
> 1. `text_normalizer.py` — 유니코드 단위(`μ`/`α`) + 한·영 경계 공백 자동화
> 2. `preprocessor.enhance_for_ocr` — `autocontrast(cutoff=1)` + `Sharpness(1.5)`
> 3. `metrics.normalize_text` 통합 — GT/OCR 양쪽에 동일 정규화

---

## 1. 어댑터별 전체 결과

| 지표 | paddleocr-ko (v1→v2) | paddleocr-en (v1→v2) | **multi (v1→v2)** |
|------|---------------------|---------------------|-------------------|
| avg_cer | 9.07% → **8.55%** (-0.52%p) | 24.40% → 24.39% (≈0) | 8.47% → **8.03%** (-0.44%p) |
| avg_wer | 46.57% → 44.46% (-2.11%p) | 44.09% → 43.99% (-0.10%p) | 43.81% → 42.14% (-1.67%p) |
| exact_match_ratio | 0.00% → **1.67%** | 10.00% → 10.00% | 10.00% → 10.00% |
| **field_match_ratio** | 60.00% → **64.44%** (+4.44%p) | 50.00% → 50.00% | 65.00% → **68.33%** (+3.33%p) |

## 2. 필드별 분해 (multi 기준)

| 필드 | v1 | v2 | Δ |
|------|------|------|------|
| product_name | 66.67% | 66.67% | +0.00%p |
| **ingredients** | 51.67% | **60.00%** | **+8.33%p** ✅ |
| dosage | 76.67% | 78.33% | +1.67%p |

> **핵심 개선**: `ingredients` 필드 +8.33%p — `text_normalizer` 의 한·영 공백 자동화로 OCR이 `비타민C` 로 붙여 읽은 결과가 GT `비타민 C` 와 매칭됨.

## 3. 언어별 분해 (multi 기준)

| 언어 | v1 CER | v2 CER | Δ |
|------|-------|-------|------|
| ko | 11.10% | **10.32%** | -0.78%p |
| en | 4.53% | 4.53% | (이미 5% 게이트 통과) |
| mixed | 9.78% | 9.24% | -0.54%p |

## 4. 95% 목표 대비 진행률 (multi 기준)

```
       avg_cer (≤ 5%):
       v1 ████████████████████████ 8.47%
       v2 ███████████████████████  8.03%  → 갭 3.03%p

  field_match (≥ 95%):
       v1 █████████████ 65.00%
       v2 ██████████████ 68.33% → 갭 26.67%p
```

## 5. 검증된 효과와 검증되지 않은 효과

### ✅ 검증된 효과
- **text_normalizer**: ingredients 매칭에서 가장 큰 효과 (+8.33%p). 한·영 공백·μ/α 변형이 매칭의 큰 노이즈였음.
- **enhance_for_ocr (autocontrast + sharpness 1.5)**: ko CER 0.78%p ↓ — 한글 자모 혼동(``엽산``→``염산``, ``루테인``→``투테인``) 줄어듦.

### ❓ 미미한 효과
- **product_name**: 0%p 변화 — 헤더 다음 줄 매칭은 글자 한두 개 오류로도 false. 추가 작업 필요.
- **paddleocr-en**: 거의 변화 없음 — 합성 영문 라벨은 이미 OCR 성공률 높고, normalizer 가 손댈 변형이 적음.

## 6. 다음 큰 lever (95% 도달을 위해)

현재 갭 (multi): avg_cer 3.03%p, field_match 26.67%p. 빠른 win 3개로는 부족. 다음 무거운 작업이 필요:

| # | 작업 | 예상 효과 | 비용 |
|---|------|---------|------|
| 1 | **YOLO ROI** — 라벨 영역만 잘라 OCR | CER 5-10%p ↓ (실사에서 큰 효과) | 大 (모델 학습 or 사전훈련) |
| 2 | **Ollama 멀티모달 보조** — VLM 으로 OCR 결과 재해석 | mixed CER 5%p ↓ | 中 |
| 3 | **product_name fuzzy 매칭** — exact 대신 0.9 이상 유사도면 match | field_match 5-10%p ↑ | 小 |
| 4 | **PP-OCRv5 한국어 fine-tuning** (실사 라벨 데이터로) | ko CER 3-5%p ↓ | 大 |
| 5 | **실사 데이터셋 라벨링** (현재 86장 gt 비어 있음) | 합성 vs 실사 갭 노출 | 中 |

## 7. 변경된 파일 (v1 → v2)

| 파일 | 변경 |
|------|------|
| `backend/src/ocr/text_normalizer.py` | 신규 모듈 (~120 LOC) |
| `backend/src/ocr/metrics.py` | normalize_text 에 normalize_ocr_text 통합 (~8 LOC) |
| `backend/src/ocr/preprocessor.py` | enhance_for_ocr 추가 + 호출 (~30 LOC) |
| `backend/tests/unit/ocr/test_text_normalizer.py` | 신규 18 tests |
| `backend/tests/unit/ocr/test_preprocessor.py` | TestEnhanceForOcr 4 tests 추가 |

**총 변경**: ~180 LOC + 22 신규 tests. **백엔드 OCR unit 테스트 118 passed**.

## 8. 원시 보고서 파일

- v1: [`../synthetic_manifest__paddleocr-ko.json`](../synthetic_manifest__paddleocr-ko.json)
       [`../synthetic_manifest__paddleocr-en.json`](../synthetic_manifest__paddleocr-en.json)
       [`../synthetic_manifest__multi.json`](../synthetic_manifest__multi.json)
- v2: [`synthetic_manifest__paddleocr-ko.json`](synthetic_manifest__paddleocr-ko.json)
       [`synthetic_manifest__paddleocr-en.json`](synthetic_manifest__paddleocr-en.json)
       [`synthetic_manifest__multi.json`](synthetic_manifest__multi.json)
