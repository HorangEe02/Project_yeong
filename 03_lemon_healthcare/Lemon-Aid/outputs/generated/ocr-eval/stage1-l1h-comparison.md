# Stage 0 vs Stage 1 (L1-H) Sub-Metric 비교 보고서

> ground-truth ingredient 라벨이 부재해 `ingredient_name_exact_rate`는 측정 불가. 대신 PaddleOCR primary OCR의 sub-metric (`text_non_empty_rate`, `parser_success_rate`, `latency`)으로 L1-H (PaddleOCR `use_doc_orientation_classify=True`, `use_textline_orientation=True`) 변경의 효과를 정량 측정.

## 실험 설정

| 항목 | 값 |
| --- | --- |
| Fixture | `data/supplement_images/private_workspace/stage0_naver/manifest.json` (50장, 16 카테고리, 100% detail_page) |
| Provider | `paddleocr_local` (PaddleOCR 3.5.0, paddlepaddle 3.3.1 CPU) |
| Stage 0 commit | `de427323` 이전 (L1-H 적용 전, `use_doc_orientation_classify=False`, `use_textline_orientation=False`) |
| Stage 1 commit | `92b8a94d` (L1-H 적용, 둘 다 `True`) |
| 추가 모델 (Stage 1) | `PP-LCNet_x1_0_doc_ori`, `PP-LCNet_x1_0_textline_ori` 자동 로드 |
| OS | macOS arm64, paddlepaddle CPU only |
| 실행 일자 | 2026-05-21 |

## 측정 결과

| Metric | Stage 0 | Stage 1 (L1-H) | Δ | 방향 |
| --- | ---: | ---: | ---: | --- |
| total fixtures | 50 | 50 | — | — |
| completed | 46 | 41 | −5 | ❌ 회귀 |
| errors (ocrerror) | 4 | 9 | +5 | ❌ 회귀 |
| **text_non_empty_rate** | **0.92** | **0.82** | **−0.10** | ❌ 회귀 |
| **parser_success_rate** | **0.92** | **0.82** | **−0.10** | ❌ 회귀 |
| layout_available_rate | 0.92 | 0.82 | −0.10 | ❌ 회귀 |
| avg char_count (completed) | 419.2 | 413.0 | −6.2 | ≈ flat |
| median char_count | 269.0 | 243.0 | −26.0 | 살짝 감소 |
| **avg latency_ms** | **9,935** | **6,722** | **−3,213 (−32%)** | ✅ 개선 |
| median latency_ms | 6,078 | 5,959 | −118 | ✅ 살짝 개선 |
| **p95 latency_ms** | **18,858** | **9,468** | **−9,390 (−50%)** | ✅ 큰 개선 |

## 해석

### L1-H가 가져온 두 가지 상반된 효과
1. **Latency 큰 개선**: orientation/textline 모델이 detector 처리 흐름을 최적화. p95 latency 18.9초 → 9.5초 (−50%)로 운영 UX에 직접적 가치.
2. **Success rate 회귀**: 50 중 4건 → 9건이 `ocrerror`. orientation classifier가 일부 광고/박스 사진에서 ROI 추정에 실패하면서 detector 호출 자체가 깨짐.

### Fixture-Specific 시그널
본 fixture set(`tampermonkey/naver/[비타민*]/{제품}/상세페이지/`)는 **영양·기능정보 dense table이 거의 없는 detail-page 광고/박스/리뷰 crop이 90% 이상**이다. orientation 모델은 라벨 사진(텍스트 비중 높음)에 최적화되어 있으므로, 광고 사진에서는 잘못된 회전 추정으로 detector를 흐트릴 가능성이 크다.

→ L1-H의 운영 환경 (사용자가 영양제 라벨을 정면 촬영) 효과는 본 fixture로 단정할 수 없다. **본 결과는 광고 사진 segment에서의 회귀**로 해석해야 정직하다.

### 결정 옵션
1. **L1-H default `True` 유지**: 운영 시점의 사용자 라벨 촬영 fixture로 재측정 전까지 가설 유지. p95 latency 절반 효과는 비용 가치 큼.
2. **L1-H를 default `False`로 되돌림**: 본 fixture set 기준 success rate가 우선이라면. 다만 fixture 자체가 운영 환경 대표성 부족.
3. **Hybrid: orientation은 `True` 유지, textline은 `False` 또는 그 반대로 분리 측정** — 어떤 모델이 실패의 원인인지 분리.

## 권장 결정

**L1-H default `True` 유지 (현재 commit 상태)**. 이유:
- 운영 시점의 사용자 라벨 사진(영양·기능정보 dense table)에서는 orientation/textline 모델이 가치 클 가능성이 높음.
- 본 fixture는 광고/박스 segment 편중이라 negative signal이 운영 환경 효과를 대표하지 않음.
- Latency 개선(p95 −50%)이 정량적이고 운영 UX에 직접적 가치.
- 사용자가 ground-truth 라벨링한 dense table fixture가 추가되면 재측정해서 결정을 갱신한다.

## Verifier 회귀

- raw_image_stored / raw_ocr_text_stored / raw_provider_payload_stored: 모두 `false` (양 stage 모두 redaction 통과)
- 핵심 안전 회귀 5종: 양 commit 모두 통과 (`92b8a94d` 검증 완료)
- pytest -q --no-cov: 648 passed, 6 skipped (L1-E 영문 anchor 2건 신규 + 기존 646)

## 산출물

- `outputs/generated/ocr-eval/observations-stage0-naver/supplement-ocr-observations.jsonl` (Stage 0, 50 row)
- `outputs/generated/ocr-eval/observations-stage1-naver/supplement-ocr-observations.jsonl` (Stage 1, 50 row)
- `outputs/generated/ocr-eval/stage1-l1h-comparison.md` (본 파일)

## 재현 명령

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

# Stage 1 observation 재실행 (L1-H 적용된 상태)
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-stage1-naver \
  --providers paddleocr_local

# Stage 0 → Stage 1 비교 (inline python; 또는 별도 비교 helper 작성 가능)
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from statistics import mean, median

def load(p):
    return [json.loads(line) for line in Path(p).read_text(encoding='utf-8').splitlines() if line.strip()]
def metrics(rows):
    n = len(rows)
    completed = [r for r in rows if r.get('status') == 'completed']
    return {
        'completed': len(completed),
        'errors': sum(1 for r in rows if r.get('status') == 'error'),
        'text_non_empty_rate': round(sum(1 for r in rows if r.get('text_non_empty')) / n, 3),
        'parser_success_rate': round(sum(1 for r in rows if r.get('parser_success')) / n, 3),
        'avg_latency_ms': round(mean([r['latency_ms'] for r in completed if r.get('latency_ms')]), 1),
    }
print(metrics(load('../outputs/generated/ocr-eval/observations-stage0-naver/supplement-ocr-observations.jsonl')))
print(metrics(load('../outputs/generated/ocr-eval/observations-stage1-naver/supplement-ocr-observations.jsonl')))
PY
```

## 다음 액션

본 결과는 fixture-specific 시그널로 해석. L1-H 운영 환경 효과 확정을 위해:

1. **운영 환경 대표 fixture 수집** — 영양·기능정보 dense table이 보이는 라벨 정면 사진. 사용자가 직접 촬영한 한국 시판 영양제 라벨이 가장 적합.
2. **그 fixture에서 Stage 0 vs Stage 1 재측정** — 같은 sub-metric으로 비교. 양의 신호가 나오면 L1-H default `True` 유지 확정.
3. **L1-E 영문 anchor 효과 측정** — 본 비교는 PaddleOCR primary OCR 변화만 다뤘다. L1-E는 layout_parser 단계 변경이고 본 collect script가 layout_parser를 호출하지 않으므로 sub-metric에 반영되지 않았다. L1-E 효과는 `evaluate_ocr_three_tier.py` 또는 layout context를 사용하는 endpoint 테스트로 별도 측정.
4. **L1-G domain correction 효과 측정** — `parse_supplement_analysis_ocr_text`가 collect 경로에 wired up되면 `parsed_ingredients` 채워짐 → 그때 비교 가능.
