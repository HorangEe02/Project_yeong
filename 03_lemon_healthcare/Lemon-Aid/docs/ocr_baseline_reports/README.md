# OCR 정확도 베이스라인 보고서

> 목표: 한국어 + 영어 영양제 라벨 OCR 정확도 **CER ≤ 5% AND Field-level exact match ≥ 95%**
> 측정 대상 어댑터: `paddleocr-ko`, `paddleocr-en`, `multi (ko+en)`

## 1. 측정 인프라 (구축 완료)

| 컴포넌트 | 경로 | 상태 |
|----------|------|------|
| 메트릭 모듈 (CER/WER/exact/field-match) | [`backend/src/ocr/metrics.py`](../../backend/src/ocr/metrics.py) | ✅ 31 unit tests passed |
| 듀얼 언어 어댑터 | [`backend/src/ocr/multilingual_adapter.py`](../../backend/src/ocr/multilingual_adapter.py) | ✅ 9 unit tests passed |
| 필드 추출기 | [`backend/src/ocr/field_extractor.py`](../../backend/src/ocr/field_extractor.py) | ✅ 20 unit tests + 60/60 round-trip |
| 합성 데이터셋 생성기 | [`scripts/synth_label_dataset.py`](../../scripts/synth_label_dataset.py) | ✅ 60장 (ko/en/mixed) 생성 |
| 실사 샘플링 (외장 드라이브) | [`scripts/sample_real_labels.py`](../../scripts/sample_real_labels.py) | ✅ 43 카테고리 × 2장 = 86장 샘플링 |
| 벤치마크 러너 | [`backend/tests/e2e/test_ocr_accuracy.py`](../../backend/tests/e2e/test_ocr_accuracy.py) | ✅ collection 통과 (3 parametrized) |

## 2. 데이터셋 현황

### 합성 데이터셋 (`data/ocr_eval/synthetic_manifest.json`)
- **60장** — ko 20 / en 20 / mixed 20 (결정론적, seed=42)
- GT 텍스트 + GT 필드 (product_name / ingredients[] / dosage) 완비
- 합성→추출 round-trip 60/60 일치 — 추출기 정확도 100% 보장

### 실사 데이터셋 (`data/ocr_eval/real_manifest.json`)
- **86장** — 43 영양제 카테고리(`[비타민C]`, `[오메가3]` 등) × 카테고리당 2장
- 외장 드라이브 `/Volumes/Corsair EX400U Media/.../naver` 에서 결정론적 샘플링
- **GT 라벨링 대기 중**: 각 item 의 `gt_text` / `gt_fields` 필드를 사람이 채워야 측정 가능 (현재는 `gt_text: ""`)

## 3. 실제 베이스라인 측정 — 환경 충돌로 보류

### 충돌 내용

```
PaddleOCR 3.4.0 → PaddleX retriever 컴포넌트
  → from langchain.docstore.document import Document
  → ModuleNotFoundError: No module named 'langchain.docstore'
```

원인: 현재 글로벌 환경에 설치된 `langchain 1.2.13` 은 신아키텍처로
``langchain.docstore`` 가 제거됨. PaddleX 는 ``is_dep_available("langchain")`` 가
True 면 무조건 ``docstore`` 를 import 한다.

### 영향

- **백엔드 자체 코드는 langchain 미사용** (`grep -rn langchain backend/src/` 결과 0건)
- PaddleX 가 transitive 의존성으로 langchain 을 import 시도하면서 충돌
- 벤치마크 러너는 `pytest.skip` 으로 graceful 처리: `OCR adapter unavailable in this env: No module named 'langchain.docstore'`

### 해결 옵션 (택 1 후 baseline 재측정)

| # | 옵션 | 영향 | 권장도 |
|---|------|------|-------|
| A | **백엔드 전용 venv 구축** — `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` | 글로벌 conda 격리, 가장 안전 | ⭐⭐⭐ |
| B | 글로벌 `pip uninstall langchain langchain-community` | 즉시 해결되지만 글로벌 환경 변경, 다른 프로젝트 영향 가능 | ⭐⭐ |
| C | `pip install 'langchain<1.0'` (구버전으로 다운그레이드) | docstore 복원되지만 LangChain 신아키텍처 사용 불가 | ⭐ |
| D | paddleocr 다운그레이드 (`paddleocr<3.0`) | 모델 API 변경, paddleocr_adapter.py 재작성 필요 | — |

## 4. 베이스라인 측정 실행 절차 (환경 조치 후)

```bash
# 1. 합성 데이터셋 (60장) 생성 (이미 생성됨, 재실행 시 결정론)
python scripts/synth_label_dataset.py --count 60 --seed 42

# 2. 실사 데이터셋 라벨링 — 86장의 gt_text/gt_fields 사람이 채움
# data/ocr_eval/real_manifest.json 의 각 item 편집

# 3. 벤치마크 실행 — 합성 데이터셋
cd backend
RUN_OCR_BENCHMARK=1 \
  OCR_BENCHMARK_MANIFEST=../data/ocr_eval/synthetic_manifest.json \
  OCR_BENCHMARK_OUTPUT=../docs/ocr_baseline_reports \
  pytest tests/e2e/test_ocr_accuracy.py -v -s --no-cov

# 출력 파일:
#   docs/ocr_baseline_reports/synthetic_manifest__paddleocr-ko.json
#   docs/ocr_baseline_reports/synthetic_manifest__paddleocr-en.json
#   docs/ocr_baseline_reports/synthetic_manifest__multi.json

# 4. 실사 데이터셋도 동일하게
RUN_OCR_BENCHMARK=1 \
  OCR_BENCHMARK_MANIFEST=../data/ocr_eval/real_manifest.json \
  OCR_BENCHMARK_OUTPUT=../docs/ocr_baseline_reports \
  pytest tests/e2e/test_ocr_accuracy.py -v -s --no-cov
```

## 5. 보고서 스키마

각 어댑터 × 데이터셋 조합으로 다음 JSON 보고서가 생성됩니다:

```json
{
  "adapter": "multi:paddleocr_v3_korean+paddleocr_v3_en",
  "manifest_path": "data/ocr_eval/synthetic_manifest.json",
  "total": 60,
  "skipped": 0,
  "avg_cer": 0.0,                       // 95% 목표: ≤ 0.05
  "avg_wer": 0.0,
  "exact_match_ratio": 0.0,
  "field_match_ratio": 0.0,             // 95% 목표: ≥ 0.95
  "field_match_breakdown": {
    "product_name": 0.0,
    "ingredients": 0.0,
    "dosage": 0.0
  },
  "by_language": {
    "ko":    {"count": 20, "avg_cer": 0.0, "exact_match_ratio": 0.0},
    "en":    {"count": 20, "avg_cer": 0.0, "exact_match_ratio": 0.0},
    "mixed": {"count": 20, "avg_cer": 0.0, "exact_match_ratio": 0.0}
  },
  "items": [/* 개별 item 측정값 */]
}
```

## 6. 95% 목표 달성을 위한 후속 이터레이션

베이스라인 측정 후 다음 순서로 개선:

1. **Bottleneck 분석**: `by_language` 분해로 ko/en/mixed 중 어떤 그룹이 가장 부진한지 파악
2. **전처리 강화**: `backend/src/ocr/preprocessor.py` 에 contrast/sharpness/deskew/binarization 추가
3. **YOLO ROI**: 게이트 #2 (`ENABLE_VISION_CLASSIFIER`) 활성화 → 라벨 영역만 잘라 OCR
4. **Ollama 멀티모달 보조**: 게이트 #1 (`ENABLE_MULTIMODAL_LLM`) 활성화 → 한·영 혼용 라벨에서 보조
5. **모델 업그레이드**: PP-OCRv5 한국어 모델로 업그레이드 (출시 시)
6. **도메인 fine-tuning**: 실사 데이터셋(라벨링 완료 후) 으로 PP-OCR det/rec 모델 fine-tune

각 단계 후 동일 벤치마크 재실행 → `docs/ocr_baseline_reports/` 비교로 진척 추적.
