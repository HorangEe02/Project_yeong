# OCR 3-Tier Fixture Evaluation Report

- Generated at: `2026-05-22T00:26:17.329127+00:00`
- Manifest: `outputs/generated/ocr-eval/2026-05-22-stage1-clova/manifest-with-clova-observations.jsonl`
- Fixtures: `16`
- Observations: `16`
- Missing image files: `0`
- Raw image artifacts stored: `False`
- Raw OCR text stored: `False`

## Provider Metrics

| Provider | Calls | Text non-empty | Parser success | Avg latency ms | Ingredient name exact | Errors | LLM attempts | LLM parse success | LLM ingredient exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clova_ocr | 16 | 0.9375 | 0.9375 | 1392.875 | 0.0 | 0 | 0 | None | None |

## Language-Segmented Error Rates (한국어/영문)

| Provider | CER ko (avg) | CER en (avg) | WER ko (avg) | WER en (avg) |
| --- | ---: | ---: | ---: | ---: |
| clova_ocr | None | None | None | None |

## 만성질환별 정확도 (B형 페르소나 시나리오)

Expected fixture 의 ``chronic_disease_indications`` 별로 분리한 ingredient_name_exact_rate.
값이 비어 있으면 해당 fixture set 에 그 만성질환 인디케이션 라벨이 없음을 뜻한다.

### clova_ocr

| Chronic condition | accuracy |
| --- | ---: |
| cardiovascular | 0.0 |
| diabetes | 0.0 |
| dyslipidemia | 0.0 |
| osteoporosis | 0.0 |
