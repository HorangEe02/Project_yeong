# 실사 OCR 측정 — v3 진행 현황과 한계

> 측정일: 2026-05-20
> 데이터셋: `data/ocr_eval/real_manifest.json` (86장 샘플링, 7장 사람 검수 완료)

## 1. 완료된 인프라

| # | 항목 | 상태 |
|---|------|------|
| 1 | 외장 드라이브 영양제 사진 → manifest 샘플링 (43 카테고리 × 2장 = 86장) | ✅ |
| 2 | PaddleOCR bootstrap pseudo-labeling (60s timeout) — 39/86 성공 | ✅ |
| 3 | Claude 멀티모달 시각 검수 — 7장 GT 확보 (`labeled=true`) | ✅ |
| 4 | NFC unicode 정규화 (HFS/외장 → manifest IDs 표준화) | ✅ |
| 5 | YOLO ROI 인프라 (`YoloLabelDetector`, `crop_to_roi`) | ✅ |
| 6 | 벤치마크 러너 ROI 통합 (`OCR_BENCHMARK_USE_ROI=1`) | ✅ |
| 7 | `OCR_BENCHMARK_LABELED_ONLY=1` 옵션 (검수된 항목만 측정) | ✅ |
| 8 | `OCR_BENCHMARK_TIMEOUT_SEC` 환경변수 (PaddleOCR per-call timeout) | ✅ |

## 2. 검수 완료 GT (7장)

| ID | 언어 | 상품 |
|----|------|------|
| real_뇌_은행잎_002 | mixed | 닥터린 이노시톨 40:1 |
| real_비타민K_002 | en | Life Extension Bone Restore (Calcium + Vitamin K2) |
| real_비타민C_002 | mixed | natural plus 비타민C 1000 플러스 |
| real_콜라겐_001 | mixed | CENOVIS 콜라겐 비타민 젤리 |
| real_효소_소화_001 | mixed | natural plus 파인애플 효소 |
| real_글루코사민_001 | mixed | natural plus 관절연골엔 글루코사민 비타민D 망간 |
| real_식이섬유_001 | mixed | 종근당 장건강 프로젝트 365 차전자피 식이섬유환 |

## 3. 측정 결과 — 부분 실패

### 시도 1: ROI 없이 (30s timeout, 3 어댑터)
- ❌ 3/3 모두 FAILED — `PaddleOCR timeout after 30.0s`

### 시도 2: 90s timeout, paddleocr-ko + en
- ❌ 2/2 모두 FAILED — 한 이미지에서 90초도 초과

### 시도 3: ROI + 90s timeout, paddleocr-ko 단일
- ⚠️ Silent stop — PaddleOCR 모델 로딩 후 출력 중단, 보고서 미생성
- 원인 추정: PaddleOCR PP-OCRv5_server_det 모델이 CPU 환경에서 실사 한국어 라벨(글자 dense)을 처리 못함

### Smoke 비교 — 합성 6장 + ROI는 정상 작동
- 동일 어댑터 + ROI 가 **합성 라벨** 6장에선 97초 (≈16초/장) 안에 완료, CER 7.42%
- 실사는 글자가 dense하고 영역 크고 색상 다양해 detection 부담 큼

## 4. 근본 원인 — PP-OCRv5 *server* det 모델의 CPU 한계

PaddleOCR 3.5 default 는 `PP-OCRv5_server_det` 사용. 이 모델은 GPU 사용을 가정한 무거운 detection 백본 (CSPNet 등). CPU 환경(macOS, GPU 없음)에서는 1024×1365 이미지에서 detection 단계에만 10-30초/장 걸림. dense Korean text 가 있으면 OCR 후처리 시간이 추가로 30초+. → 90s 초과.

또 ROI 적용은 입력 픽셀을 줄이지만, ROI 자체가 라벨 전체를 잡아 여전히 큰 영역.

## 5. 95% 목표 달성 path — 옵션

| # | 옵션 | 효과 추정 | 비용 | 상태 |
|---|------|---------|------|------|
| A | **PaddleOCR mobile det 모델** 로 명시 전환 (`PP-OCRv5_mobile_det`) | 추론 시간 1/3~1/5, 정확도 약간 ↓ | 어댑터 코드 ~30 LOC | 미시도 |
| B | **Google Vision OCR** 로 전환 (이미 어댑터 있음) | 정확도 ↑, GCP 비용 발생 | API 키 + GCP 설정 | 미시도 |
| C | **GPU 사용** (CUDA / MPS) | 추론 10x 빨라짐 | 환경 셋업 필요 | 미시도 |
| D | **PaddleX 의 lightweight pipeline** (det 만, doc orient·textline orient 비활성) | 추론 시간 1/2 | 어댑터 코드 ~20 LOC | 미시도 |
| E | **이미지를 더 작게 리사이즈** (1024 → 768px) | 추론 빨라짐, 정확도 ↓ | preprocess 1줄 | 미시도 |

권장: **A (mobile det) + D (lightweight pipeline)** 결합. PaddleOCR API 가 둘 다 지원하며 어댑터 한 줄 변경.

## 6. 현재 보장된 측정 — 합성 60장 결과 (v1, v2)

실사 측정은 위 한계로 보류되었으나, 합성 데이터셋 결과는 모든 인프라가 작동함을 입증합니다:

| 어댑터 | CER (v1) | CER (v2) |
|--------|---------|---------|
| paddleocr-ko | 9.07% | 8.55% |
| paddleocr-en | 24.40% | 24.39% |
| **multi** | 8.47% | **8.03%** |

목표 95% (CER ≤ 5%) 까지 현재 갭: 약 3%p.

## 7. 즉시 권장 다음 단계

1. **옵션 A 적용** (PaddleOCR mobile det 전환) — 가장 간단, 큰 효과 기대
2. 동일 7장 GT로 v3 재측정 (이번엔 timeout 안에 끝나야 함)
3. 결과 분석 후 95% 달성까지 남은 lever 평가

또는 **GPU 환경 (Apple Silicon MPS)** 으로 전환하면 별도 코드 변경 없이 추론 속도 향상 가능.
