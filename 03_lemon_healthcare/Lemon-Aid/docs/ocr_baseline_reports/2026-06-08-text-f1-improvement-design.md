# holdout text-F1 0.33 → 0.90~0.95 상세 개선 설계

작성: 2026-06-08. 근거: 멀티에이전트 웹리서치(6 레버) + 적대적 검증(4 핵심주장) + 코드/평가데이터 진단.
대상 지표: `normalized_text_F1`(char 단위 LCS, holdout 52). 현재 최적 모델 = A100 `v2_clean_p10`.

## 0. 현재 상태 (측정값)
| 모델 | holdout P | R | **text-F1** | field_match(macro) |
|---|---:|---:|---:|---:|
| baseline(mobile,det튜닝) | 0.306 | 0.493 | 0.300 | — |
| A100 v2_clean | 0.302 | 0.513 | 0.316 | 0.537 |
| **A100 v2_clean_p10** | **0.320** | **0.529** | **0.324** | 0.562 |

A100 학습은 recall(0.49→0.53)·F1(0.30→0.32)을 올렸으나 **precision은 0.30→0.32에 정체**.

## 1. 루트 원인 — precision "scope 상한" (검증된 정리)
char-level F1의 precision = `정답과겹치는_char / OCR가출력한_전체_char`.
- GT(reference)는 **섹션 한정**(ingredient_amounts/intake_method/precautions/allergen_warning) 4종뿐.
- det 설정(box0.15/thr0.1/unclip2.0)은 **recall 편향** = 라벨 전체(제품명·마케팅·영양성분표·바코드)를 다 읽음 → 여분 char가 전부 false-positive.
- per-image 증거: 203장 중 **57%가 precision<0.30**, 그런데 동일 fixture에서 field_match 0.8/recall 0.67인 경우도 precision 0.22.

**적대적 검증 결론(정리에 가까움):** full-image OCR을 섹션-GT와 char-LCS로 채점하는 한, **recognizer를 아무리 키워도 text-F1 상한 ≈ 0.68~0.71**. 즉 현재 구도에서 0.90은 **수학적으로 불가**. → 0.90~0.95의 진짜 레버는 **scope 정렬(+지표 재정의)**, recognizer는 그 다음.

## 2. 적대적 검증 4 주장 (정직한 요약)
1. ✅ "full-image vs 섹션-GT char-LCS는 precision 0.90 불가" — **확인**(코드·수치로). recognizer-only 상한 ≈ **0.68~0.71**.
2. ⚠️ "*학습된 image-space ROI 검출기*가 필수" — **부분 오류**. 필요한 건 **scoping**이지 *반드시 학습된 검출기*는 아님. **기존 `parse_label_layout`(src/parsing/layout_parser.py:218)로 text-space scoping** 이 즉시 가능(무학습). 검출기는 상한을 더 높이는 강화책.
3. ✅ "recognizer 단독은 <0.10 기여" — **확인**. scoping 없이는 0.33 정체; scoping 있어야 recognizer 향상이 in-scope F1로 반영.
4. ✅(정직 단서) "필드/엔티티 단위 지표면 0.90~0.95에 훨씬 빨리 도달" — **사실이나 일부는 '정의 변경'**. 정직하게 프레이밍 필요(지표 재정렬 vs 실제 품질 향상 구분).

## 3. 개선 레버 (리서치 종합, 효과/공수)
| 레버 | 타깃 | 공수 | 단독 예상 F1 | 비고 |
|---|---|---|---|---|
| **A. text-space scoping** (`parse_label_layout`+섹션분류로 4섹션만 채점/출력) | precision | low~med | 0.33→**0.50~0.63** | **무학습, 기존 코드. 1순위 즉시.** |
| **B. image-space ROI** (8섹션 검출기 학습→crop→in-crop OCR) | precision | high | 0.33→**0.78~0.90** | CLOVA per-field **박스 기하**로 라벨 자동생성(키워드 약지도 아님). YOLO 또는 PP-DocLayout_plus-L(RT-DETR). |
| B0. PP-StructureV3 zero-train 필터 | precision | low | +0.15~0.25 | table(영양표)·image(바코드/로고)·title(제품명) 영역 drop = 최대 FP 제거, 학습 0 |
| C. 지표 scope-aware 재정의 | metric | low | (헤드라인 정렬) | in-scope 기준 P/R, 또는 필드단위/ANLS*. 95% 게이트 재정의 동반 |
| D. det precision 프로파일(crop 내부) | precision | low | +0.02~0.08 | box_thresh↑(0.6~0.7)/unclip↓(1.5~1.7). crop 적용 시에만 유효 |
| E. recognize-then-filter(즉효) | precision | low | +0.08~0.18 | 바코드/숫자표/단토큰 정규식 drop + rec_score 필터. 검출기 전 임시 |
| F. recognizer 강화 | recall | med | +0.05~0.12(scoping 후) | 실사진 CLOVA crop + aug + 스케줄↑ + distillation. line-acc 0.80→0.86~0.90 |
| G. 후처리 lexicon/단위 정규화 | both | low | +0.01~0.06 | 성분명 SymSpell, mg/µg/IU 정규식 **GT·OCR 대칭** 적용(NFKC가 대부분) |
| H. GT 전략 | — | — | — | full-label 전사(Option A) **기각**(고비용·저가치). 섹션GT+ROI(Option B) 유지 |

## 4. 단계별 로드맵 (누적 F1 목표)
- **S0 — scope oracle + 지표 정직화 (2~3일, 무학습)**: CLOVA per-field 박스로 "이상적 scope" 상한 측정 → 달성가능 천장 확정. 평가에 **in-scope precision/recall**(섹션 매칭 후) 추가 산출(기존 char-LCS도 병행 보고). → 헤드라인 재정렬의 정당성 확보.
- **S1 — text-space scoping (~1주, 무학습)**: `parse_label_layout` + 섹션 분류로 OCR 출력을 4 GT 섹션으로 게이팅 후 채점 + E(필터) + G(대칭 정규화). **예상 F1 0.33→0.55~0.65**.
- **S2 — image-space ROI (~1~2주, A100)**: CLOVA 박스→8섹션 라벨 생성 → 검출기 학습(YOLO 또는 PP-DocLayout_plus-L) → crop → in-crop OCR + D(precision det). **예상 F1 →0.78~0.88**.
- **S3 — recognizer + 후처리 (~1주, A100)**: 실사진 CLOVA crop 재학습 + aug + 단위/lexicon + CER 타깃 hard-example. **예상 F1 →0.88~0.93**.
- **S4 — 지표 reconciliation + 게이트**: 필드/엔티티 KPI(ANLS\*/field_match) 승격 + 95% 게이트를 **localization 게이트 + recognition(CER) 게이트**로 분리. scope-aware/field 기준에서 **0.90~0.95 의미화**.

## 5. 현실적 상한 (경로별)
| 경로 | text-F1 상한 |
|---|---|
| 현행(full-image char-LCS, recognizer만) | **~0.68~0.71** (0.90 불가) |
| + text-space scoping(S1) | ~0.55~0.70 |
| + image-space ROI(S2) | ~0.80~0.90 |
| + recognizer/후처리(S3) | ~0.90~0.93 |
| 필드/ANLS\* 지표(S4, KIE 관점) | **0.90~0.95 달성 가능 + 더 의미 있음** |

## 6. 지표 정직성 (반드시 명시)
- 0.90~0.95 도달의 일부는 **지표 재정렬(정의)**, 일부는 **실제 품질(scoping+recognizer)**. 둘을 **분리 보고**해야 함(섞으면 과장).
- 현행 char-LCS 95% 게이트는 **구조적으로 도달 불가** → scope-fair하게 재정의(아니면 영원히 continue_training_loop).
- 권장 헤드라인 KPI = **필드 단위 추출 정확도**(field_match/ANLS\*) + 보조로 **in-scope CER/WER**. 이게 "라벨에서 필요한 항목을 정확히 뽑았는가"라는 제품 목표와 일치.

## 7. 권장 첫 2주
- **Week 1**: S0(scope oracle + in-scope 지표 산출) → S1(`parse_label_layout` 게이팅 + 필터/정규화) 구현·측정. 산출: 0.55~0.65 + 정직한 지표 2종 병행.
- **Week 2**: S2 착수 — CLOVA 박스→섹션 라벨 빌더(기하 기반, 기존 키워드 약지도 대체) → A100 검출기 학습 → in-crop OCR 평가(목표 0.78+). 동시에 PP-StructureV3 zero-train 필터를 빠른 baseline으로 비교.

## 8. 자산 매핑
- 무학습 scoping: `src/parsing/layout_parser.py:parse_label_layout`(이미 analysis에 연결됨 :781/:1514).
- ROI 라벨: CLOVA per-field 박스(teacher) → 섹션 기하 클러스터링(주의: 직전 `build_crawling_yolo_section_dataset.py`의 **라인-키워드 약지도는 93% 미분류로 부적합** → 박스-기하 방식으로 교체).
- 검출기: `learning.retraining.SUPPLEMENT_SECTION_CLASS_NAMES`(8) + YOLO 또는 PP-DocLayout_plus-L. 평가: `paddleocr_clova_eval.py`(--rec-model-dir) + 게이트 체인.
- GPU: A100(155.230.153.222, key 등록됨). recognizer는 v2_clean_p10 inference 회수 완료.

## 9. 참고(웹)
- YALTAi(YOLO region-det ≫ pixel-seg, 소량 라벨로도): arxiv 2207.11230
- PP-DocLayout_plus-L(RT-DETR, 레이아웃 영역검출): arxiv 2503.17213 / HF PaddlePaddle/PP-DocLayout_plus-L
- PP-StructureV3(region→OCR): paddleocr.ai PP-StructureV3
- PaddleX det 임계값 튜닝(box_thresh↑/unclip↓ for precision): paddlepaddle.github.io/PaddleX text_detection
- ANLS\*(구조화 추출 지표): 검색 "ANLS* document understanding metric"

> 핵심 한 줄: **recognizer는 이미 충분(val 0.80)**. text-F1 0.33의 90%는 **scope 불일치**다. **scoping(S1 무학습→S2 ROI) + 정직한 지표(S0/S4)** 가 0.90~0.95의 길이며, recognizer/후처리(S3)는 마무리 +0.05~0.10.
