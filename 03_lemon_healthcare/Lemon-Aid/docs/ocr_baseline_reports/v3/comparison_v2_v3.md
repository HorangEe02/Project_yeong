# OCR 베이스라인 v2 → v3 비교 (PaddleOCR mobile det 전환 결과)

> **측정일**: 2026-05-20
> **변경**: `PP-OCRv5_server_det` → `PP-OCRv5_mobile_det` + lightweight pipeline (doc_orient/unwarp/textline_orient 비활성)
> **데이터셋**: 합성 60장 (동일, seed=42)

---

## 1. 전체 결과 (어댑터별)

| 어댑터 | v2 (server) CER | v3 (mobile_lite) CER | Δ | v2 field | v3 field | Δ |
|--------|----------------|---------------------|------|---------|---------|------|
| paddleocr-ko | 8.55% | **29.33%** | **+20.78%p ↑** ❌ | 64.44% | 34.44% | -30%p |
| paddleocr-en | 24.39% | 29.33% | +4.94%p ↑ | 50.00% | 34.44% | -15.56%p |
| **multi** | 8.03% | **29.33%** | **+21.30%p ↑** ❌ | 68.33% | 34.44% | -33.89%p |

> **결론**: mobile det 모델은 95% 목표 달성에 **부적합**. server 대비 평균 +20%p CER 악화.

## 2. 언어별 분해 (multi 어댑터 기준)

| 언어 | v2 (server) | v3 (mobile_lite) | Δ |
|------|-------------|-----------------|------|
| ko | 10.32% | **54.42%** | **+44.10%p ↑** ❌ |
| en | 4.53% | 6.45% | +1.92%p (영문은 거의 영향 없음) |
| mixed | 9.24% | 27.12% | +17.88%p ↑ |

> **mobile det 모델은 한글 detection이 매우 약함** — server는 PP-OCRv5_server_det가 한·영 모두에 강한 백본을 쓰지만 mobile은 영문 중심 학습.

## 3. 측정 시간

| 측정 | 60장 × 3 어댑터 | 평균/장 |
|------|----------------|-------|
| v2 (server) | ~480초 (8분) | ~2.7초 |
| v3 (mobile_lite) | **205초 (3.4분)** | **~1.1초** | (server 대비 2.4배 빠름)

## 4. 핵심 인사이트

### 검증된 사실
- **mobile det = 속도 2-3배 향상**: 확인 ✅
- **mobile det = 한글 정확도 5배 악화**: 확인 ❌
- **mobile det = 영문 정확도는 유지**: 확인 ✅
- multi 어댑터가 ko/en 결과와 동일한 이유: ko가 영문만 인식해 confidence 높게 나옴 → multi 가 ko 결과 채택. mobile det에서 한글 detection 실패.

### 95% 목표 도달 path 재평가
mobile det는 **합성 라벨에서 이미 부적합** 판정. 실사 측정은 더 큰 문제 발생할 것이므로 시도 보류.

## 5. 다음 lever 권장 (재정렬)

| # | 옵션 | 예상 효과 | 비용 | 우선순위 |
|---|------|---------|------|---------|
| **1** | **Lightweight only (server det 유지)** — `use_lightweight_pipeline=True` 만 적용 | 추론 시간 1.5배 단축, 정확도 유지 | 즉시 (env 변수만) | ⭐⭐⭐ |
| 2 | preprocess 이미지 크기 1024 → 768px | 추론 빨라짐, 정확도 약간↓ | 1줄 변경 | ⭐⭐ |
| 3 | Google Vision OCR 로 전환 | 정확도↑, 비용 발생 | API 키 설정 | ⭐⭐ |
| 4 | GPU/Apple MPS 가속 | 추론 10x | 환경 셋업 | ⭐ |
| 5 | YOLO ROI + server det (이미 구현됨) | 합성 +7.42% smoke 검증, 실사도 가능 가설 | 별도 작업 없음 | ⭐⭐ |

## 6. 즉시 권장 다음 시도

**옵션 1 (lightweight only)** — server det 유지하면서 보조 단계만 끔:
- `OCR_BENCHMARK_LIGHTWEIGHT=1` (mobile_det 미설정)
- 추론 시간: server 8분 → 약 5-6분 추정
- 정확도: v2 multi 8.03% 거의 유지 또는 약간 개선 (회전된 라벨이 적은 합성에서)

만약 lightweight 만으로 실사 7장이 timeout 안에 끝난다면, v3 실사 측정도 가능해짐.

## 7. 산출물

- [`synthetic_manifest__paddleocr-ko_mobile_lite.json`](synthetic_manifest__paddleocr-ko_mobile_lite.json)
- [`synthetic_manifest__paddleocr-en_mobile_lite.json`](synthetic_manifest__paddleocr-en_mobile_lite.json)
- [`synthetic_manifest__multi_mobile_lite.json`](synthetic_manifest__multi_mobile_lite.json)

## 8. 결론

**Mobile det 전환은 95% 목표 달성에 실패**. server det 의 한글 detection 정확도는 mobile 로 대체 불가. 다음 path 는:

1. **lightweight only**로 추론 속도만 단축하고 server det 정확도 유지
2. **YOLO ROI + server det** 조합으로 실사 timeout 회피 시도
3. **Google Vision OCR** 또는 **GPU 가속** 으로 정확도 + 속도 모두 잡기
