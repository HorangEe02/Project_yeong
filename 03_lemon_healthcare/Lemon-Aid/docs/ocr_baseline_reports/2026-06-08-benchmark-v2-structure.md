# OCR benchmark v2 (500) — candidate pool 구조

생성: build_supplement_benchmark_v2_candidate_pool.py (로컬 OCR 프록시, CLOVA 미사용).

## 구조
- **frozen v1**: 203 fixtures (회귀 비교용 holdout, split 보존) — {'holdout': 52, 'test': 22, 'train': 129}
- **new candidates**: 297 (detector/ROI annotation pool), distinct products 274, 카테고리 31종
- **v2 total**: 500

## new pool product-level split (누수 없음, 203과 제품 분리)
{'test': 53, 'train': 212, 'val': 32}

## failure-targeted 강도 (new pool)
{'fragmented_product': 94, 'long_page': 57, 'low_signal': 7}
(long_page=상세페이지 길이≥3000px, fragmented_product=성분/섭취가 다른 페이지에 분리, low_signal=현행 OCR이 성분·섭취 미검출=하드)

## new pool 카테고리 분포 (top 15)
| category | n |
|---|---|
| [기타] | 59 |
| [유산균_프로바이오틱] | 55 |
| [멀티비타민] | 31 |
| [종합영양제] | 27 |
| [오메가3] | 24 |
| [비타민D] | 17 |
| [비타민B] | 15 |
| [마그네슘] | 12 |
| [비타민C] | 10 |
| [관절_MSM_콘드로이친] | 6 |
| [밀크씨슬_간] | 6 |
| [루테인_눈] | 5 |
| [코엔자임Q10] | 4 |
| [강황_커큐민] | 3 |
| [아연] | 3 |

## 최소 라벨 스키마 (각 candidate.annotation)
- bbox: ingredient_amounts, intake_method (필수), supplement_facts/product_identity (가능 시)
- structured_gt: ingredient_amounts[], intake_method[], precautions[], allergen_warnings[]
- (full-text LCS GT는 별도 벤치마크에서만)

## 다음 단계 (기존 운영 파이프라인 연결)
1. 이 candidate 매니페스트 → PII screening 배치 생성 → 운영자 검토(cleared).
2. cleared 이미지 → CLOVA teacher로 per-field bbox+text 자동 채움 → 운영자 검증(섹션 bbox + structured GT 확정).
3. benchmark manifest 병합(frozen 203 + new) → product-level split 확정 → 게이트.
4. 섹션 검출기 학습용 = new pool의 bbox; recognizer/holdout 회귀 = frozen 203.

> 매니페스트는 redaction 준수(해시/플래그/카운트만, 원문·literal 경로 없음). resolution map은 운영자용(gitignored).
