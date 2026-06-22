# GPU/MPS 가속 도입 가능성 평가 — 결론: macOS Apple Silicon 에서는 불가

> **측정 환경**: macOS, Apple Silicon (M-series), paddlepaddle 3.3.1, paddleocr 3.5.0

## 1. paddlepaddle 자체 점검

| 항목 | 결과 |
|------|------|
| paddle.is_compiled_with_cuda() | **False** (CUDA 미컴파일) |
| paddle.device.is_compiled_with_mps() | 속성 없음 (MPS 비지원) |
| paddle.device.cuda.device_count() | 0 |
| Apple Silicon ARM64 native build | 사용 중 (NEON SIMD 자동 활용) |

## 2. PaddleOCR 3.5 init params (28개) 점검

device / gpu / mkldnn / precision 류 매개변수 **전무**:
- model_name, model_dir, batch_size, use_* (보조 단계 토글)
- text_det_limit_side_len, text_det_thresh, text_det_box_thresh, text_det_unclip_ratio
- text_rec_score_thresh, return_word_box

`kwargs` 가 있어 일부 paddlepaddle global config 를 우회 주입할 수는 있으나 device 자체는 OS · paddlepaddle 빌드에 종속.

## 3. 결론

**Apple Silicon macOS 에서 paddlepaddle GPU/MPS 가속은 불가능.**
- paddlepaddle 의 MPS 백엔드 구현 없음 (paddlepaddle 공식 로드맵에도 없음, 2026-05 현재)
- 현재 build 는 ARM64 native — NEON SIMD 는 이미 자동 활용 중
- CUDA 는 macOS 자체가 지원 종료 (2018+)

## 4. 대안 — 가속을 위한 가능한 path

| # | 옵션 | 효과 추정 | 비용 |
|---|------|---------|------|
| **A** | **`text_det_limit_side_len` 조정** (default ~960 → 768 등) | 1.3-1.5x ↑, 정확도 약간 ↓ | env 변수만 |
| B | **ONNX 변환** + onnxruntime CoreML EP | 2-3x ↑, 변환 작업 大 | 모델 변환 + 어댑터 재작성 |
| C | **Linux + NVIDIA GPU** 환경으로 측정 이전 | 10x ↑ | 하드웨어 / 클라우드 인스턴스 |
| D | **PaddleOCR mobile rec** 만 (det 는 server 유지) | 1.2-1.5x ↑ | text_recognition_model_name 설정 |

옵션 **A** 가 가장 즉시 시도 가능 — 이미 옵션 1 (lightweight) / 옵션 4 (ROI) 측정 후 결합해서 검증 가치 있음.

옵션 **B** (ONNX) 는 단발성 큰 작업이지만 paddlepaddle 의존성 자체를 제거할 수 있어 장기적으로 유망. 별도 PR 단위.

## 5. 권고

GPU/MPS 가속은 macOS 에서 paddlepaddle 자체 한계로 도입 불가. 대신:
1. **lightweight + ROI + text_det_limit_side_len 조정**의 조합으로 추론 시간 최적화
2. 정확도가 95% 도달이 더 중요하다면 **server det 유지** + 이미지 작게 + 실사 측정에 충분한 timeout 부여 (예: 300s)
3. 장기적으로는 ONNX 변환 검토
