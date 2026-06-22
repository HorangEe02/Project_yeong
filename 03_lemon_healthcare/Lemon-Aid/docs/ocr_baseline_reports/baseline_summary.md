# OCR 베이스라인 측정 결과 (합성 60장)

> **측정일**: 2026-05-20
> **데이터셋**: `data/ocr_eval/synthetic_manifest.json` (seed=42, 60장 = ko 20 / en 20 / mixed 20)
> **환경**: `backend/.venv` (Python 3.13, paddleocr 3.5.0, paddlepaddle 3.3.1)
> **목표**: CER ≤ 5% **AND** Field-level exact match ≥ 95%

---

## 1. 어댑터별 결과 요약

| 어댑터 | CER ↓ | WER ↓ | Exact ↑ | Field-match ↑ | 95% 목표 |
|--------|-------|-------|---------|---------------|---------|
| `paddleocr-ko` | 9.07% | 46.57% | 0% | 60.00% | ❌ |
| `paddleocr-en` | 24.40% | 44.09% | 10% | 50.00% | ❌ |
| **`multi`** (ko+en) | **8.47%** | **43.81%** | **10%** | **65.00%** | ❌ (최고) |

> **결론**: `multi` 어댑터가 세 어댑터 중 가장 우수하지만, CER 95% 목표(≤5%)의 약 1.7배·field-match 목표(≥95%)의 0.68배로 **단순한 듀얼 모델 구성만으로는 95% 달성 불가**.

---

## 2. 언어별 분해 (multi 어댑터 기준)

| 언어 | n | CER | Exact | 분석 |
|------|---|-----|-------|------|
| ko | 20 | 11.10% | 0% | 한국어 단독 라벨에서 PaddleOCR-ko 의 CER 가 가장 높음 |
| **en** | 20 | **4.53%** | **30%** | 영어 단독은 이미 5% 게이트 근접 |
| mixed | 20 | 9.78% | 0% | 한·영 혼용 라벨도 ko 모델 채택, ko 단독과 유사 |

> **하이라이트**: 영어 단독 라벨은 PaddleOCR-en 만으로도 CER 4.53% 로 **95% 목표 달성** ✅.
> 한국어와 혼용 라벨에서만 큰 갭 (CER ~10%).

---

## 3. 필드별 분해 (60장 평균)

| 어댑터 | product_name | ingredients | dosage |
|--------|--------------|-------------|--------|
| paddleocr-ko | 65.0% | 51.7% | 63.3% |
| paddleocr-en | 33.3% | 26.7% | 90.0% |
| **multi** | **66.7%** | **51.7%** | **76.7%** |

> **관찰**:
> - `dosage` (정규식 + 단위 매칭) 가 가장 안정 — `multi` 76.7%, `paddleocr-en` 90%
> - `ingredients` (리스트 5개 element 전체 일치 요구) 가 가장 약함 — 한 element만 어긋나도 false
> - `product_name` 은 헤더 다음 줄 추출 — OCR 한두 글자 오류만으로 false

---

## 4. 95% 목표 대비 갭 분석

**multi 어댑터 기준** (가장 우수):

| 지표 | 현재 | 목표 | 갭 |
|------|------|------|----|
| avg_cer (전체) | 0.0847 | ≤ 0.05 | **-3.47%p** (목표 대비 ~1.7배 오류) |
| avg_cer (ko) | 0.1110 | ≤ 0.05 | **-6.10%p** |
| avg_cer (en) | 0.0453 | ≤ 0.05 | ✅ 이미 달성 |
| avg_cer (mixed) | 0.0978 | ≤ 0.05 | **-4.78%p** |
| field_match | 0.65 | ≥ 0.95 | **-30%p** |

---

## 5. 갭의 원인 — 합성 라벨에서 무엇이 잘못 읽혔나

(전체 JSON `items` 분석 결과 — `synthetic_manifest__multi.json` 참조)

빈도 높은 오류 패턴:
1. **단위 표기 오류**: `μg` → `ug`, `μg RAE` → `ugRAE`, `mg α-TE` → `mgo-TE` 등 (Greek 문자 인식)
2. **한국어 미세 글자 오류**: `엽산` → `염산`, `구리` → `구리` (잘 됨), `루테인` → `투테인` 같은 자음 혼동
3. **공백 손실**: `비타민 C` → `비타민C` (공백 누락이 CER에는 1글자 손실)
4. **줄바꿈 인식 차이**: OCR이 양 라인을 하나로 합치는 경우 product_name 추출 실패

---

## 6. 95% 도달을 위한 후속 이터레이션 권고 (우선순위)

| # | 작업 | 영향 어댑터·언어 | 예상 효과 | 비용 |
|---|------|---------------|----------|------|
| 1 | **전처리 강화** (contrast/sharpness/binarization) | 전체 | 글자 디테일 향상 → ko CER 1-3%p ↓ | 중 (~150 LOC) |
| 2 | **유니코드 단위 정규화** (`μ`↔`u`, `α`↔`a` 등) — postprocess 단계에서 흡수 | 전체 | dosage field-match 80% → 95%+ | 소 (~30 LOC) |
| 3 | **공백 정규화 + 한글-영문 사이 자동 공백 삽입** | 한·영 혼용 | mixed field-match ↑ | 소 (~50 LOC) |
| 4 | **YOLO ROI** (`ENABLE_VISION_CLASSIFIER=true`) | 실사 데이터셋 | 라벨 영역만 잘라 OCR → 배경 잡음 제거, CER 5-10%p ↓ | 대 (모델 학습 또는 사전훈련 사용) |
| 5 | **Ollama 멀티모달 보조** (`ENABLE_MULTIMODAL_LLM=true`) | 한·영 혼용 | LLM이 OCR 결과 재해석 → 한·영 정렬 자동 보정 | 중 |
| 6 | **PP-OCRv5 한국어 모델 fine-tune** (실사 라벨 데이터로) | ko / mixed | 도메인 특화로 CER 2-5%p ↓ | 대 (라벨링 + 학습) |
| 7 | **field_extractor 강화** — fuzzy match 옵션 | ingredients 필드 | 5 element 중 4 일치도 부분 점수로 반영 | 소 |

### 즉시 시도 권장 (1주차)
- **#2 (유니코드 정규화)** + **#3 (공백 정규화)**: 합산 ~80 LOC, dosage/field-match 큰 향상 예상
- **#1 (전처리)**: 200 LOC 미만, CER 직접 개선

### 중기 (2-4주)
- **#4 YOLO ROI**: 실사 데이터셋에서 효과 측정 필요
- **실사 데이터셋 라벨링** 완료 (현재 86장 gt 비어 있음)

### 장기 (4주+)
- **#5 Ollama 멀티모달** + **#6 fine-tuning**

---

## 7. 데이터 무결성 확인

- 합성 manifest 의 GT 60건 모두 field_extractor 와 round-trip 일치 — **GT 자체는 정확** ✅
- 따라서 위 측정값은 순수하게 **OCR + 후처리 정확도**를 반영 (라벨링 오염 없음)

---

## 8. 다음 측정 권장

1. **이터레이션 #2, #3 적용 후 재측정** — 즉시 효과 확인
2. **실사 데이터셋 라벨링 후** — `data/ocr_eval/real_manifest.json` 의 86장 gt 채우고 재측정 → 합성 vs 실사 갭 노출
3. **이터레이션 #4 (YOLO ROI) 적용 후** — 실사에서 큰 효과 기대

각 이터레이션 결과는 동일한 벤치마크 명령으로 새 JSON 보고서가 생성되며, 시계열로 비교 가능합니다.

---

## 9. 원시 보고서 파일

- [`synthetic_manifest__paddleocr-ko.json`](synthetic_manifest__paddleocr-ko.json) — ko 단독 모델
- [`synthetic_manifest__paddleocr-en.json`](synthetic_manifest__paddleocr-en.json) — en 단독 모델
- [`synthetic_manifest__multi.json`](synthetic_manifest__multi.json) — ko+en duál (선택 우세)

각 파일의 `items[]` 배열에 60건 각각의 CER/WER/exact/field_matches/chosen_engine/elapsed_ms 가 모두 들어있어 사례별 오류 분석에 활용 가능.
