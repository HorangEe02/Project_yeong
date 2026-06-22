# v2 CLOVA teacher pass — section 커버리지 (Stage 2 결과)

작성: 2026-06-08. 입력 297 candidate(전부 resolve, sha 무결성 OK), CLOVA 297/297 labeled, 0 failed, section bbox 1,402개(avg 4.7/img). teacher 텍스트/박스는 gitignored `datasets/supplement-section-roi-v2/`.

## 섹션 커버리지 (candidate 297 기준)
| section | candidates | 비율 |
|---|---:|---:|
| ingredient_amounts | 268 | **90%** |
| supplement_facts | 53 | 18% |
| precautions | 41 | 14% |
| functional_claims | 40 | 13% |
| **intake_method** | **2** | **0.7%** |
| (섹션 없음/empty) | 26 | 9% |

## 해석
- **ingredient_amounts ROI는 강력(90%)** — 이것이 주 병목(ingredient_recall 0.466, ingredient_all_missed 33%)을 직접 때리는 라벨이므로, ROI 검출기/structured GT의 핵심 목적은 달성.
- **intake_method는 사실상 미확보(0.7%)** — 원인: candidate 선택 시 프록시의 intake 신호가 "1일"을 포함해 "1일 영양성분 기준치"(facts)에 오탐 → "fragmented(94)"가 실제 intake 분리가 아니었음. 실제 섭취방법/복용방법 패널은 선택되지 않은 다른 detail 이미지에 존재.
- empty 26개(9%)는 low_signal/분류 실패 → 사람 주석 또는 제외 대상.

## 권고 (다음)
1. **intake-targeted 보강 패스**(별도): 각 제품의 *비선택* detail 이미지를 **엄격 intake 키워드**(섭취방법/복용방법/섭취하/드십시오, 단 bare "1일" 제외)로 재스캔 → intake 패널 이미지 선택 → CLOVA → intake_method bbox 확보. (추가 CLOVA 비용 발생 → 승인 필요)
2. ingredient_amounts ROI는 그대로 Stage 3(사람 bbox 리뷰)로 진행 가능.
3. empty 26개는 리뷰 큐에서 별도 처리(주석 또는 제외).

## intake 보강 패스 결과 (업데이트)
- 무료 로컬 discovery(`select_supplement_v2_intake_panels.py`): 비선택+proxy-intake-flag 이미지 152개 재스캔(엄격 intake 키워드) → **intake 패널 12개**(12제품, train 8/test 4) 발견. 나머지 ~140은 "1일"-only facts 오탐(엄격 스캔이 정상 기각).
- 12 패널 CLOVA → `_classify_section` 기준 intake로 분류된 건 **1개**뿐(나머지는 ingredient/facts/claims로 분류).
- **핵심 결론(재확인)**: 키워드 기반 `_classify_section`은 **ingredient_amounts(금액 정규식)만 신뢰성 있게 자동 검출**, intake_method 등 키워드 섹션은 CLOVA per-box 단편에서 거의 안 잡힘(앞선 약지도 93% 미분류와 동일 한계). 또한 크롤링 상세페이지는 섭취방법을 **그래픽/인포그래픽**으로 렌더해 OCR 텍스트로 안 잡히는 경우가 많아 **intake 패널 자체가 희소**(전체 ≈14장).

## 시사점 / 권고 (intake)
1. **자동 부트스트랩의 한계**: ingredient_amounts bbox는 자동(90%)으로 충분하나, intake_method + 기타 섹션은 **Stage 3 사람 주석 필수**(자동 pre-fill 불가). 후보 이미지 선택은 되어 있으니 사람이 박스를 그림.
2. **intake 희소성**: 크롤링 코퍼스에서 intake 패널이 적음 → intake_method 평가/학습은 (a) **frozen 203의 intake GT 활용**(이미 일부 보유), (b) 필요 시 전체 비선택 이미지 풀 재스캔(추가 비용, 소폭 기대), (c) intake는 v2에서 제한적으로 수용.
3. **주 병목은 ingredient_recall** — 이건 ingredient_amounts ROI(90%)로 직접 해소되므로 v2의 1차 목표는 유효.

> redaction: 본 문서는 카운트만. 원문/박스 좌표는 gitignored datasets/teacher에만.
