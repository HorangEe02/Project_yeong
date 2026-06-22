# L1-H 회귀 원인 분리 측정 보고서 (4-way comparison)

> Stage 1 L1-H (PaddleOCR `use_doc_orientation_classify` + `use_textline_orientation` 둘 다 default `True`)가 본 fixture에서 success rate −10%p 회귀를 일으킨 점을 분리 측정. 4가지 조합으로 어느 모델이 회귀 주범인지 확정.

## 실험 설계

- Fixture: `data/supplement_images/private_workspace/stage0_naver/manifest.json` (50장 naver detail_page, 16 카테고리)
- Provider: `paddleocr_local` (PaddleOCR 3.5.0, paddlepaddle 3.3.1 CPU)
- 변수: `local_ocr_use_doc_orientation_classify` (ori), `local_ocr_use_textline_orientation` (txt) 두 가지의 4가지 조합
- env override로 동일 코드/모델 + 동일 fixture에서 4 run 비교

## 측정 결과 (50 fixture, env override 4 run)

| Scenario | completed | errors | text_non_empty | parser_success | lat_avg (ms) | lat_p95 (ms) | char_median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `off/off` (Stage 0 baseline) | **46** | 4 | **0.920** | 0.920 | 9,935 | 18,858 | 269 |
| **`on/off` (orientation only)** | **43** | 7 | 0.860 | 0.860 | **6,342** | **8,629** | **307** |
| `off/on` (textline only) | 41 | 9 | 0.820 | 0.820 | 7,168 | 12,058 | 243 |
| `on/on` (Stage 1 L1-H combined) | 41 | 9 | 0.820 | 0.820 | 6,722 | 9,468 | 243 |

## 해석

### Finding 1 — textline_orientation이 회귀의 주된 원인
- `off/on`(textline only) 과 `on/on`(both) 가 **동일하게 41 completed / 9 errors / text_non_empty 0.82** → textline 활성화 단독으로 5건의 추가 ocrerror 유발.
- 본 fixture의 광고/박스 사진에서 textline classifier가 텍스트 행 방향을 잘못 추정해 PaddleOCR detector가 fail.

### Finding 2 — orientation_classify는 비용 대비 가치 큼
- `on/off`(orientation only): errors 4 → 7 (+3건), text_non_empty −0.06 로 회귀 적음.
- 그러나 **char_median 269 → 307 (+14%)**: 정상 처리된 case에서는 더 많은 텍스트를 추출 — orientation 보정이 효과적.
- **Latency 큰 개선**: avg 9,935 → 6,342 (−36%), p95 18,858 → 8,629 (−54%). 가장 빠른 조합.

### Finding 3 — orientation only가 sweet spot
| 기준 | 최선 조합 | 비교 |
| --- | --- | --- |
| Latency (avg/p95) | **on/off** | 6,342 / 8,629 — 가장 빠름 |
| char_count median | **on/off** | 307 — 가장 풍부 |
| text_non_empty/parser_success | off/off | 0.920 (그러나 latency 1.5x 느림) |
| errors 최소 | off/off | 4건 (orientation only는 7건) |

`on/off`는 baseline 대비 success rate −6%p 회귀 vs **latency −36%, char_count +14%** trade-off. 운영 환경의 영양제 라벨 정면 사진에서는 textline 부작용은 적고 orientation 효과가 더 클 가능성이 높지만, 본 광고 fixture 기준으로도 `on/off`가 가장 균형 잡힌 결과.

## 권장 변경

- `local_ocr_use_doc_orientation_classify=True` 유지 (현 default)
- `local_ocr_use_textline_orientation`을 **False로 되돌림** (L1-H의 textline 부분만 revert)

기대 효과:
- 본 fixture: success rate 0.82 → 0.86 (회복) + latency p95 9.5초 → 8.6초 (개선) + char_count median 243 → 307 (증가)
- 운영 환경: orientation의 라벨 정면 회전 보정 효과는 유지, textline의 광고 segment 부작용은 제거

## 다음 단계

1. **이 보고서를 evidence로 textline_orientation default revert** (`config.py:457` + `test_config.py`)
2. 같은 50 fixture에서 5번째 run (`on/off`를 default로) 결과 재기록 — 본 보고서 `on/off` 행이 그 결과와 동일하므로 추가 run 불필요
3. 운영 fixture 수집 후 `on/on` 재시도해서 textline이 라벨 정면 사진에서는 의미 있는지 확인. 양성 신호면 다시 `True`로 복귀 검토.

## 산출물

- `outputs/generated/ocr-eval/observations-stage0-naver/supplement-ocr-observations.jsonl` (off/off, 기존)
- `outputs/generated/ocr-eval/observations-stage1-naver-ori_only/supplement-ocr-observations.jsonl` (on/off, 신규)
- `outputs/generated/ocr-eval/observations-stage1-naver-txt_only/supplement-ocr-observations.jsonl` (off/on, 신규)
- `outputs/generated/ocr-eval/observations-stage1-naver/supplement-ocr-observations.jsonl` (on/on, 기존)
- `outputs/generated/ocr-eval/stage1-l1h-isolation.md` (본 파일)

## 재현 명령

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

# on/off (orientation only)
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=true LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-stage1-naver-ori_only \
  --providers paddleocr_local

# off/on (textline only)
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=false LOCAL_OCR_USE_TEXTLINE_ORIENTATION=true \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-stage1-naver-txt_only \
  --providers paddleocr_local
```
