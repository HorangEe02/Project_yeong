# 2026-06-19 PaddleOCR 0.85/0.90 Gate 재설계 가이드라인 (웹 리서치 + 적대적 검증 종합)

> 작성 방법: 6개 차원(recognizer / detection / synthetic-data / layout-table / document-VLM / eval-flywheel)
> 병렬 웹 리서치 → 차원별 적대적 검증(사실오류·과장·제약 부적합 색출) → 종합. 모든 수치는
> **공식 문서값**과 **Lemon-Aid holdout 실험값**, **검증으로 정정된 값**을 구분해 표기한다. raw OCR text /
> provider payload / private image / holdout GT 는 이 문서에 포함하지 않는다.
>
> 권위 선행 문서: [`2026-06-17-ingredient-recall-085-redesign.md`](2026-06-17-ingredient-recall-085-redesign.md),
> [`2026-06-18-best-model-recovery-and-085-090-redesign.md`](2026-06-18-best-model-recovery-and-085-090-redesign.md),
> [`2026-06-12-ocr-field-match-design-and-team-guideline.md`](2026-06-12-ocr-field-match-design-and-team-guideline.md),
> [`2026-06-06-a100-remote-paddleocr-finetune-guide.md`](2026-06-06-a100-remote-paddleocr-finetune-guide.md).

---

## 0. TL;DR (결론 먼저)

**게이트를 막고 있는 것은 recognizer(글자 인식)가 아니라 "성분명+함량+단위 페어링(field_match)"과
"성분명 substring 커버리지(ingredient_recall)"다. 가장 싼 0.85 경로는 A100 재학습이 아니라 parser/fusion
계층 + layout-aware 추출 + 측정 규율에 있다.**

따라서 우선순위를 뒤집는다.

1. **측정 규율 먼저** — n=41로는 0.85를 통계적으로 인증할 수 없다(Wilson 하한 ~0.63). Wilson 하한 +
   paired McNemar를 모든 게이트 판정에 도입하고, locked holdout을 **≥100 product**로 확장한다. **A100 시간을
   쓰기 전 전제조건.**
2. **bottleneck 실측** — 기존 `build_roi_first_oracle_bundle.py`에 `GT-OCR-text → parser` leg을 추가해
   per-fixture 4단 ladder로 ROI/recognition/parser 중 무엇이 binding인지 **증명**한다.
3. **CPU/근(近)-GPU 레버 선투입** — (a) gemma4:e4b layout 구조화 프롬프트를 evidence_union 후보로 추가 +
   **span-grounding**(모든 amount/unit 토큰은 OCR 텍스트의 substring이어야 함 = "함량 추측 금지"), (b) field_match
   normalizer에 정확히 키 맞춘 **정밀 alias/단위 정규화**(정확 동의어만, broad fuzzy 금지), (c) **PaddleOCR-VL-0.9B
   zero-shot** 2차 recognizer 후보(무학습, A100 80GB에 ~44GB로 적재).
4. **recognizer 재학습은 마지막 수단** — 진행 중인 stage7 `v7_mix`는 **replay(~1:1) + LR 상향 + RecConAug**를
   먼저 반영한 뒤 판정한다(무replay x8 oversample은 0.518→0.037 붕괴와 같은 구조). server_rec 풀 재학습은
   oracle ladder가 "recognition-bound"를 증명할 때만, 기대이득 **~+0.03**으로 예산 책정.

예상 경로(밴드, 측정 전 단정 금지): parser/alias/fusion + gemma 구조화 = `0.75 → ~0.82`, VLM 후보 +
detector sweep = `~0.82 → ~0.85`, recognizer 재학습(필요 시) + 데이터 확장 = `0.85 → 0.90`.

---

## 1. 현재 상태 요약 (근거: 06-17 / 06-18 / 06-12)

| 항목 | 값 |
|---|---|
| 최고 deployable (locked holdout41, `evidence_union`) | field_macro **0.781** / field_micro **0.766** / ingredient_recall **0.747** |
| holdout27 (`evidence_union`) | 0.7096 / 0.7183 / 0.7045 |
| 게이트 | field_match macro&micro ≥ **0.85**, ingredient_recall ≥ **0.85** (aux norm_edit_dis ≥ 0.90), 스트레치 = 전부 ≥ 0.90 |
| 남은 실패 (holdout41, n=41) | `field_zero=2`, `ingredient_all_missed=5` |
| 실패 원인 분류(sanitized) | `ocr_rec_or_alias_gap=3`, `roi_or_detection_miss=1`, `metric_or_ocr_confusion_fuzzy_recoverable=1` |
| 진행 중 학습 | stage7 `v7_mix_base1066` (base v2 + train-only hardcase ×8 oversample, frozen 1066-dict, init=b128 best, lr 2e-5, b192, 40 ep) |
| 과거 사고 | 합성-only 2-epoch CPU finetune → field_match 0.518→**0.037** (catastrophic forgetting); broad RapidFuzz alias → Vitamin C→D false positive |

**게이트 metric의 정확한 정의(코드 기준, 06-12)** — 재설계의 모든 레버는 이 정의에 묶여야 한다:

- `field_match`: 필드셋 = {product_name, manufacturer, 성분별 display_name, 성분별 **"amount unit" 결합 문자열**,
  intake_method}. 정규화 = NFKC → lower → 영숫자만, 그 후 rapidfuzz `partial_ratio >= 85`면 match.
  → **함량·단위가 한 row에서 같이 인식·결합되어야 점수가 난다(= 페어링 metric).**
- `ingredient_recall`: GT 성분명(정규화)이 hypothesis 정규화 문자열에 **substring 포함**되는 비율(micro=Σfound/Σtotal).
  → **성분명만 들어가면 됨(함량 불요) = 커버리지 metric.**

---

## 2. Binding constraint: 왜 "페어링/커버리지"인가 (recognizer 아님)

| 근거 | 내용 |
|---|---|
| metric 구조 | field_match는 "amount unit" **결합 문자열**을 채점 → 글자를 다 읽어도 line grouping이 틀리면(split-line/table-row) 실패. ingredient_recall은 **substring** → 정규화/별칭 문제. 둘 다 raw char accuracy와 직접 연동 안 됨. |
| 실패 분류 | 명명된 실패 6건 중 4건(`ocr_rec_or_alias_gap=3` + `fuzzy_recoverable=1`)이 parser/alias/fusion 계층 영역. detector-miss는 1건. |
| 균일 격차 | field_macro 0.781 / micro 0.766 / recall 0.747 — 세 지표가 균일하게 ~+0.08 부족 = **소수 제품의 파국적 오독이 아니라 체계적 페어링/커버리지 결손**의 signature (field_zero=2뿐). |
| 리서치 수렴 | server 재학습 기대이득은 정정 후 **~+0.03**(인쇄체 tier, 한국어 벤치 없음)으로 하향. 반면 gemma 구조화 프롬프트 +0.03~0.08, alias 정규화 "가장 싼 게이트-무버". |

**결론**: ROI는 대체로 충분, raw recognition은 "충분하지만 레버가 아님". **게이트는 parsing(페어링)과
fusion(커버리지)에서 먼저 갚는다.** detector는 2차 제약(최대 1~2/7)이며 box-coverage 진단으로 증명 후에만 손댄다.

---

## 3. 재설계 원칙 (제약 준수)

- **Holdout 규율**: holdout27/holdout41은 절대 학습에 넣지 않는다. train-only hardcase만 학습용. 확장 test split도
  학습에 미사용. 모든 dataset build에 **crop-level leakage 감사**(특히 ×8 oversample 라인).
- **Privacy**: raw OCR / CLOVA payload / label image / GT 는 git 커밋 금지. 합성 corpus는 **generic lexicon**에서만
  생성(holdout 제품명 채굴 금지).
- **단일 A100(Windows, no distributed)** + Mac은 dataset 준비·평가 전용.
- **"함량 추측 금지"**: VLM/LLM이 amount/unit을 만들어내면 안 됨. **JSON schema는 모양(shape)만 강제하고 진실(truth)은
  강제하지 못한다**("Let Me Speak Freely", arXiv 2408.02442) → 실제 guardrail은 **span-grounding**(OCR 텍스트 substring 검증).
- **비파괴 fusion**: 새 후보(VLM/gemma)는 항상 `evidence_union`에 **추가 후보**로만 합류(단독 소스 금지) → 최악의 경우 중립.

---

## 4. 재설계 아키텍처 (staged hybrid: OCR+parser 척추 유지, document-VLM은 fusion 후보로 추가)

```
                       image (phone photo: 박스 앞면 / 정보면 / 병)
                                        |
                                YOLO section detector
                  (ROI crop: supplement_facts / ingredient_amounts /
                   other_ingredients) + full-image fallback
                                        |
      ┌──────────────────────┬──────────────────────┬───────────────────────┐
   LANE A                 LANE B                  LANE C                  LANE D
   PaddleOCR PP-OCRv5     CLOVA cloud OCR         PaddleOCR-VL-0.9B       gemma4:e4b
   KOREAN mobile rec      (현재 라이브 primary)    zero-shot (~44GB,       layout 프롬프트:
   (frozen 1066-dict,                            학습창 밖, 선택)         "name|amount|unit|%DV"
   replay+LR 보정)                                                       per-row (가변해상도)
      │                      │                       │                       │
      └──── verbatim text ───┴──── verbatim text ────┘                  구조화 rows
                                        |                                    |
                       DETERMINISTIC + gemma4:e4b PARSER  ◄───────────────────┘
            (split-line, table-row, amount-first, bilingual alias, CFU/IU/mcg/%DV guard)
                                        |
            ★ NEW: SPAN-GROUNDING POST-VALIDATOR ★
   (모든 amount/unit 토큰은 union OCR 텍스트의 substring이어야 함 — 아니면 drop/flag = "함량 추측 금지")
                                        |
            ★ NEW: 정밀 ALIAS + 단위 정규화 ★
   (NFKC→lower→alnum 키 일치; 정확 동의어만; mg/mcg/µg/IU/CFU/%DV/억/조)
                                        |
            evidence_union MERGE [Paddle | CLOVA | PaddleOCR-VL | gemma-구조화]
              → 성분별 name + "amount unit" 문자열 + product 필드
                                        |
            ingredient evidence records → "저장 전 검토" UX
```

**현행 대비 변경점**: ①VLM은 후보로만 추가(비파괴). ②parser와 merge 사이에 deterministic 2단계 신설 —
span-grounding(진실 guardrail) + 정밀 alias/단위 정규화(가장 싼 게이트-무버), 둘 다 게이트 normalizer에 정확히 키 일치.
③recognizer 학습은 계속하되(replay+LR 보정 v7_mix) 게이트-종결 임계경로에서 **분리**(Lane A 품질만 개선, 0.85를 거는 레버가 아님).

---

## 5. 우선순위 레버 (정렬·metric 연결·official/experimental·정정 반영)

| # | 레버 | 공략 metric | 기대이득(밴드, 측정 전 단정 금지) | 노력 | 분류 |
|---:|---|---|---|---|---|
| 1 | **Wilson 하한 + paired McNemar** 보고를 모든 게이트 run에 도입; n=41 단일 delta < ~+0.10은 noise 처리 | 둘 다(측정 기반) | 직접이득 0 — 잘못된 go/no-go·A100 낭비 방지 | 낮음(CPU) | official(통계) |
| 2 | locked holdout **≥100 product**로 확장(±0.05엔 ~196), holdout27/41은 locked sub-slice 유지, GT off-git | 둘 다 | 0 — 게이트를 "인증 가능"하게 전환 | 중(라벨링, CPU) | official |
| 3 | **per-fixture oracle ladder**: `build_roi_first_oracle_bundle.py`에 `GT-OCR-text→parser` leg 추가 | 둘 다(귀속) | 0 — 다운스트림 노력 방향 결정(4~9의 게이트) | 낮음~중(CPU) | 내부 |
| 4 | **gemma4:e4b 하이브리드 구조화 헤드**(§9.1 실측 채택) → **OCR 텍스트(CLOVA/Paddle) + ROI crop**을 입력받아 `name\|amount\|unit\|%DV` row 재구성, evidence_union 후보 + **필수 span-grounding**. ⚠️ OCR-free 비전 단독 금지(실측서 함량 누락) | field_macro/micro(페어링) + 부수 recall | **+0.02~0.06** field(OCR 텍스트 품질 의존) | 낮음(모델 기배선) | experimental |
| 5 | **정밀 alias + 단위 정규화**(정확 동의어만, normalizer 키 일치) | 둘 다(특히 recall) | **+0.02~0.05** | 낮음(offline) | 내부(데이터) |
| 6 | **PaddleOCR-VL-0.9B zero-shot** 2차 recognizer 후보(vLLM, ~44GB, 학습창 밖) | recall + field_micro + aux norm_edit_dis | **+0.02~0.05**(rec-gap fixture) | 중(모델 다운로드) | experimental |
| 7 | 진행 중 **stage7 v7_mix 보정**: general-Korean **replay ~1:1**(real:hardcase 10:1~5:1로 cap) + **LR 2e-5→~1.5e-4**(warmup 2-3, cosine→1e-5) + frozen 1066-dict 영구 | field_match 회귀방지 + recall/norm_edit | 기존 field_match 보호 + **+0.01~0.03** recall | 낮음(in-flight config) | official(망각방지) |
| 8 | **RecConAug**(prob~0.4, ext_data_num 1-2) + **RecAug**(tia_prob~0.3) + **소량 in-domain 합성**(10-25% minority, 합성-only epoch 금지) + **minimal-pair hard-negative**(C/D, B6/B12, µg/mg, l/i/1, O/0) | recall/field_micro(table-row) + field_macro precision | **+0.01~0.03** | 낮음~중(Mac CPU) | official+내부 |
| 9 | **CONTINGENCY**(3 + box-coverage 진단 게이트 후): (a) detector **inference sweep**(server_det, limit_type=max, side_len 1280/1536, thresh **0.25-0.30**, box_thresh 0.5-0.6, unclip 2.0-2.5); (b) **최후** server_det/server_rec fine-tune(frozen dict, lr 5e-5~1e-4, warmup 2, 5-10 ep, ~1:1 general mix, eval-every-epoch early-stop) | recall + field_micro | sweep **+0.02~0.05**; server retrain **~+0.03**(불확실) | sweep 낮음 / retrain 높음 | sweep official / retrain experimental |

---

## 6. 평가 규율 재설계 (가장 먼저)

**왜**: n=41, field_macro 0.781의 Wilson 95% 구간은 ≈[0.634, 0.880] — 0.85가 구간 안에 있다. ingredient_recall
0.747 → ≈[0.597, 0.855]. 즉 **현재 "+0.07~0.10 격차" 전체가 noise 밴드 안**이라 단일 run delta로 승패를 못 가른다.
(주의: field_macro는 제품별 비율의 평균이라 binomial Wilson은 근사 — 방향성 결론은 불변.)

- **표본 수**: ±0.05 인증엔 n≈196, ±0.07엔 n≈100. → holdout을 **never-trained 제품 ≥100개**로 확장(TEST-only, off-git).
- **수용 규칙**: 매 run에 각 metric의 **Wilson 하한**을 보고하고, "더 좋다"는 판정은 **같은 fixture들에 대한 paired
  McNemar**가 유의할 때만. n=41 단일 delta < ~+0.10은 noise.
- **per-fixture oracle ladder**(결정 엔진): 기존 `build_roi_first_oracle_bundle.py`(ROI-oracle leg 이미 존재)에
  `GT-OCR-text→parser` leg 추가 후 4단:
  1. real ROI + real OCR + parser (baseline)
  2. **GT-ROI** + real OCR + parser → detection 격리
  3. **GT-ROI + GT-OCR-text** + parser → recognition 격리
  4. GT-ROI + GT-OCR + GT-parse → merge/alias 격리

  **결정 규칙**: (3)에서 이미 대부분 0.85 통과 → 게이트는 **CPU parser/alias/fusion 문제, server 재학습 불요**.
  (2)에서만 회복 → detection-bound. (3)에서도 미달 → recognition-bound(재학습 정당화).
- **detection 진단(CPU, 먼저, 오염 0)**: holdout41의 field_zero(2)+ingredient_all_missed(5) crop에 PP-OCRv5 det
  polygon을 overlay하고 "박스가 안 덮은 GT 성분 라인 수"를 센다 → detector-miss vs rec-misread 귀속.

---

## 7. 학습 재설계 (recognizer / detector)

### 7.1 Recognizer — **진행 중 stage7 v7_mix에 접어 넣기**(새 run 시작 금지, 판정 전 반영)

**불변(항상)**:
- **1066-char dict 영구 frozen**, base/hardcase/future byte-identical. **warm checkpoint에 dict hot-swap 금지**
  (dict 변경 → 최종 FC 미적재 → acc=0 → 정확히 0.518→0.037 붕괴). image_shape [3,48,320], max_text_length 25,
  init=b128 best_accuracy.
- **eval-every-N**: holdout-DISJOINT val + 고정 base/easy slice(Backward-Transfer 모니터). base slice 저하 또는
  holdout field_zero 증가 시 즉시 early-stop.

**config 델타(현행 stage7 대비)**:
- **REPLAY 추가**: 공개 `korean_PP-OCRv5` general crop을 `ratio_list`로 ~1:1 혼합, hardcase oversample은 real:hardcase
  10:1~5:1 내로 cap(현 무replay ×8에서 하향). general crop은 **공개 데이터에서만**(holdout 금지).
- **LR 상향**: 2e-5 floor → ~1.5e-4(공식 bs128 밴드 [1e-4, 2e-5]를 b192로 ~1.5배 스케일), warmup 2-3, cosine→~1e-5.
- **AUGMENT**: `RecConAug`(prob~0.4, ext_data_num 1-2)로 "name amount unit" 긴 라인 합성(split-line/table-row 직격),
  `RecAug`(tia_prob~0.3, 한글 jamo 과변형 회피). ※ rec head가 SVTR 기반인지 확인 후 RecAug vs SVTRRecAug 선택(open Q).

**합성(Mac CPU, TRAIN-only, 배치의 10-25% minority, 합성-only epoch 금지)**:
- in-domain-vocab 세트(SynthTIGER/KoTDG/TRDG): corpus는 **generic 보충제 lexicon**(KO+EN 비타민/미네랄, bilingual
  `한글 (English)`, mg/mcg/µg/IU/%/CFU/100억) — holdout 제품명 채굴 금지. 폰-사진 효과(perspective/skew/blur/jpeg
  downscale/noise) 강하게.
- minimal-pair hard-negative(소량): C/D, B6/B12, rn/m, l/i/1, O/0, µg/mg — **glyph 레벨 분리**로 "함량 추측 금지"
  지원 + field_match precision↑(fuzzy alias 대체). 전체 holdout로 모니터(타깃 쌍만 보지 말 것).
- facts-table **row crop**(다열 `비타민C 1000mg 100%`, dotted leader, ruling line, 우측정렬 amount) — YOLO가 내보내는
  라인/ROI granularity로.

### 7.2 Detector — **CONTINGENCY only**(box-coverage 진단이 detection-bound 증명 후)

- 먼저 **무학습 inference sweep**(server_det 확인; limit_type=max, side_len 1280/1536(32의 배수), thresh **0.25-0.30**,
  box_thresh 0.5-0.6, unclip 2.0-2.5)을 holdout field/recall로 게이트. ⚠️ thresh 0.20을 맹목적으로 내리지 말 것
  (낮은 thresh+높은 unclip → 라인 병합/오탐 박스 → recognizer에 garbage → 성분 false positive, 이미 겪은 FP class).
- 그래도 안 되면 PP-OCRv5_server_det fine-tune: init=student.pdparams, lr 5e-5~1e-4, warmup 2, 5-10 ep, train-only
  facts det 이미지 ≥500, **~1:1 general mix**(rec용 5:1 아님), 매 epoch holdout eval + early-stop. quad GT는 기존
  CLOVA/YOLO 박스에서 bootstrap, raw 이미지/GT 미커밋.

### 7.3 server_rec 풀 재학습 — **최후 recognizer 레버**

oracle ladder가 recognition-bound를 증명 + 싼 레버가 미달일 때만. 같은 frozen 1066-dict(server head 재초기화로
iter 0 acc=0 정상), ≥20-30 ep, bs128 A100 적재. **기대이득 ~+0.03으로 예산**(인쇄체 tier; **한국어 server_rec
공식 모델·벤치 부재** = 전이 가정 미검증). CTC-only vs CTC+NRTR MultiHead A/B를 같은 run에 묶어(헤드 1개 추가) 1회 비용으로.

---

## 8. 데이터 · 합성 · flywheel (holdout 규율·privacy 준수)

1. **TEST 확장(최우선 데이터 작업)**: never-trained 제품 ≥100개 라벨(±0.05엔 ~196), holdout27/41은 locked sub-slice.
   TEST-only, GT off-git. → 0.85/0.90 **인증 가능**의 전제.
2. **합성**(§7.1) — generic lexicon, real-majority, 합성-only epoch 금지(붕괴 가드).
3. **REPLAY corpus** — 공개 korean_PP-OCRv5 general crop ~1:1, 공개 소스만.
4. **disagreement active-learning flywheel**(human-in-loop):
   - 미라벨 crop을 (CLOVA↔Paddle 불일치) + (낮은 Paddle CTC confidence)로 랭킹해 **사람 검토 큐** 구성 →
     ocr_rec_or_alias_gap tail에 라벨링 집중.
   - ⚠️ **CLOVA-Paddle 합의로 auto-label 금지**: Paddle은 CLOVA에서 distill됐고 CLOVA가 GT/oracle 소스이기도 함
     → 합의 = 학생이 교사를 재현하는 것(순환). 쉬운 케이스만 인증하고 교사 오류를 고착. **독립 3차 신호**(gemma4
     vision 또는 비-CLOVA 엔진) + spot-audit 없이는 consensus 신뢰 금지.
   - CLOVA teacher crop은 confidence 필터 후 학습 투입.
5. **crop-level leakage 감사**: 제품-레벨 규율은 이미 적용 — 잔여 actionable은 holdout 제품 crop(특히 ×8 oversample
   hardcase 라인)이 crop 레벨로 학습에 새는지 감사.
6. **alias/단위 테이블**(offline, privacy-safe): generic lexicon에서 정확 bilingual 동의어 + 단위 정규화 큐레이션.
   exact-match only(모델 아님, 데이터). **가장 싼 게이트-무버.**

---

## 9. Document-VLM 통합 (gemma4:e4b + PaddleOCR-VL) + span-grounding

- **gemma4:e4b layout 구조화 프롬프트**(레버 4, 1순위 VLM): ROI crop에서 `name|amount|unit|%DV` row 추출 →
  evidence_union 후보. ✅ **정정**: gemma4:e4b는 **가변 해상도**(Gemma-3의 고정 896×896 아님) → "작은 dense text 파괴"
  반론은 이 모델엔 **거짓**. ⚠️ bilingual food-label Jaccard 0.836은 **클라우드 GPT-4V** 수치 — 로컬 gemma 기대값으로
  읽지 말 것. holdout이 유일한 심판.
- **PaddleOCR-VL-0.9B zero-shot**(레버 6): vLLM, **~43.7GB**(✅ 정정: 62.8GB 아님 → 80GB A100에 여유로 적재), 1.22
  pages/s. 공개 오픈 한국어 edit distance **0.052**(Qwen2.5-VL-72B 0.056보다 우수, 단 문서 벤치 — 폰 사진 전이 미검증).
  무학습 → 붕괴 위험 0. PaddlePaddle 생태계 동일 = 통합 비용 낮음. 학습창 밖에서 serialize.
- **dots.ocr**(선택 2차): MIT, vLLM. ⚠️ "1.7B"는 LLM 백본만 — 전체 VLM은 ~3B급(A100 적재 OK). 한국어 능력 미공개 →
  holdout으로만 판정.
- **span-grounding guardrail(필수)**: 어떤 VLM도 image→final-JSON free-generation 금지. VLM은 verbatim text를
  내보내 deterministic parser가 소비하거나, parser로 쓰되 **모든 amount/unit 토큰이 OCR 텍스트의 substring임을 검증**.
  근거: 제약 디코딩(JSON schema)은 shape만 강제, truth 미강제(arXiv 2408.02442). span-grounding이 진짜 guardrail.
  ⚠️ validator의 **precision/recall 분리 추적**(OCR가 망가뜨린 진짜 amount를 과도 drop하지 않는지) — 정규화
  substring(공백/NFKC) 허용.

---

## 9.1 gemma4:e4b document-VLM 헤드 실측 평가 (2026-06-19) — 재설계 결정

질문: "Qwen2.5-VL 대신 gemma4:e4b를 document-VLM 추출 헤드로 쓸 수 있는가?" → **실측으로 답한다.**
라이브 백엔드(OLLAMA_MODEL=OLLAMA_VISION_MODEL=gemma4:e4b)에서 두 모드를 직접 측정했다.

### 측정 A — gemma4:e4b **비전 단독**(OCR-free, 이미지→구조화 JSON, Ollama `/api/chat` images)

| 이미지 | 라벨 실제(육안) | gemma4:e4b 비전 단독 결과 |
|---|---|---|
| mock(Omega-3, 깨끗) | Omega-3 1000mg | ✅ Omega-3 1000mg (정확) |
| 글루코사민 병 앞면(gt-1c6295cb) | 글루코사민/비타민D/망간, **글루코사민 황산염 1,500mg**, 1,350mg×120정 | ⚠️ "ARTICULAR CARTILAGE N GLUCOSAMINE"·"VITAMIN D MANGANESE"로 **뭉개짐**, **함량 전부 None**(1,500mg 누락), 한글 성분목록 미추출 |
| EAA 제품(gt-2687f611) | — | ⚠️ product만, 성분 0건 |
| Bone Restore 병(gt-d23de9d2) | 앞면 클로즈업, 성분 함량 없음 | ⚠️ product None, "Vitamin K2"만 |

### 측정 B — gemma4:e4b **텍스트 구조화**(OCR 텍스트→구조화, 앞서 §실측)

- 복합 한글 정보면 텍스트 8성분(µg/%DV/100억 CFU 포함) → **8/8 정확**. (대조: qwen3.5:9b 0/8)

### 측정 C — CLOVA OCR + parser (동일 글루코사민 라벨, 하이브리드 파이프라인)

- product+serving(1500mg)+성분 4건(글루코사민 황산염/비타민D/망간/황산염, 1350·1500mg 일부 포함) — **gemma 비전 단독(2건·함량0)보다 월등**. (parser 노이즈 잔존은 별개 과제)

### 결정

| 역할 | gemma4:e4b 적합성 | 결정 |
|---|---|---|
| **OCR-free 비전 인식 헤드**(Qwen2.5-VL/PaddleOCR-VL/dots.ocr가 벤치되는 역할) | ❌ 실제 소비자 사진서 함량 누락·뭉갬·성분 누락 | **Qwen2.5-VL/PaddleOCR-VL를 대체 불가.** 비전 인식 후보는 **PaddleOCR-VL-0.9B**(한국어 edit-dist 0.052) 유지 |
| **하이브리드 구조화 헤드**(OCR 텍스트 + ROI crop 레이아웃 컨텍스트 → name\|amount\|unit row) | ✅ 텍스트 구조화 8/8, 가변해상도, 이미 in-stack | **이 역할로 채택.** Lever 4 = gemma4:e4b 하이브리드 구조화 헤드 |

**재설계 결론**: gemma4:e4b는 **Qwen2.5-VL를 OCR-free 헤드로는 대체 못 하지만**, 우리 파이프라인엔 OCR-free 헤드가
필요 없다 — CLOVA(라이브)·PaddleOCR(로컬)·PaddleOCR-VL(후보)가 **글리프/함량의 source of truth**이고, gemma4:e4b는
그 OCR 텍스트를 **layout-aware하게 재구성(페어링)**하는 헤드로 쓴다. 따라서:

1. **gemma4:e4b 입력 = OCR 텍스트(필수) + ROI crop(레이아웃 보조)**. **이미지 단독(OCR-free) 호출 금지** —
   실측서 함량을 못 읽음.
2. **span-grounding은 선택이 아니라 필수**: gemma가 내는 모든 amount/unit은 **OCR 텍스트의 substring**이어야 함.
   (실측 근거: gemma 비전 단독은 보이는 1,500mg조차 누락 → 추측 amount는 더더욱 신뢰 불가.)
3. PaddleOCR-VL-0.9B(레버 6)는 **비전 인식 후보로 별도 유지** — gemma가 못 메우는 글리프 인식 격차 담당.
4. ⚠️ bilingual food-label Jaccard 0.836은 **클라우드 GPT-4V** 수치 — 로컬 gemma 기대값 아님(실측이 이를 확인).
   gemma4:e4b는 **가변 해상도**(Gemma-3 고정 896×896 아님)지만, 그것이 실제 소비자 사진의 함량 인식까지 보장하진 않음.

> CLOVA OCR 라이브 검증 동봉(2026-06-19): `ENABLE_CLOVA_OCR=true`·`OCR_PRIMARY_PROVIDER=clova` + analyze 202 +
> 백엔드 로그 `apigw.ntruss.com ... HTTP/1.1 200 OK` + OCR 에러 0 → **CLOVA 정상 동작 확인**. 로컬 OCR은 off
> (PaddleOCR 재학습 중), 즉 라이브 OCR primary는 CLOVA 단독이 정상 경로.

## 10. 순차 로드맵 (결정 게이트 포함)

| Step | 작업 | 환경 | 결정 게이트 |
|---:|---|---|---|
| 0 | eval에 Wilson 하한 + paired McNemar 도입; 1066-dict frozen 불변 고정 | CPU | 이후 모든 go/no-go가 이를 사용; delta<~+0.10@n=41=noise |
| 1 | detection box-coverage 진단(holdout41 7실패 overlay) | CPU | 7중 몇 개가 detection-recoverable(예상 1-2)인지 |
| 2 | oracle ladder(`GT-OCR-text→parser` leg 추가) 4단 실행 | CPU | **master gate**: (iii) GT-OCR→parser가 대부분 0.85↑ → server 재학습 SKIP; (ii)만 회복 → detection-bound; (iii)도 미달 → recognition-bound |
| 3 | span-grounding + 정밀 alias/단위 정규화 + gemma 구조화 후보 추가(각각 독립 McNemar) | CPU/GPU-inf | 결합 field/recall 상승; holdout + 확장 test 1차 slice에서 ≥0.85 하한이면 후보 게이트-통과 |
| 4 | holdout ≥100 product 확장(TEST-only, off-git); disagreement 큐 구축(consensus auto-label 금지) | CPU/라벨 | 확장셋에서 Step3 재측정; ≥0.85 Wilson **하한**만 인증 |
| 5 | PaddleOCR-VL-0.9B zero-shot(학습창 밖); 선택 dots.ocr | GPU-inf | McNemar 통과 union 후보만 유지 |
| 6 | stage7 v7_mix에 replay+LR+RecConAug/RecAug+minority 합성+minimal-pair 반영(in-flight) | GPU | Backward-Transfer base slice 무회귀 + holdout field_zero 무증가 + McNemar-유의 recall/norm_edit 이득만 수용 |
| 7 | **CONTINGENCY**: Step2가 detection-bound 증명 + sweep 소진 → server_det; recognition-bound 증명 + 싼레버 미달 → server_rec(예산 +0.03) + CTC/NRTR A/B | GPU | 확장 test에서 union baseline 대비 McNemar-유의 margin 아니면 revert |
| 8 | untouched 확장 test에서 field macro&micro≥0.85 + recall≥0.85 + norm_edit≥0.90 전부 Wilson **하한**으로 확인 → 0.90 스트레치 시도 → 승리 evidence_union 전략 lock | CPU | 인증 |

---

## 11. 리스크 · 완화

| 리스크 | 완화 |
|---|---|
| VLM amount hallucination(잘못된 함량 auto-fill) | **span-grounding 하드 게이트**(OCR substring 아닌 amount/unit drop). schema-shape는 guardrail 아님 |
| span-grounding 과도 reject(진짜 amount 손실) | validator precision/recall **분리** 추적; 정규화 substring 허용 |
| alias FP 재발(C→D) | **정확 동의어만**, 큐레이션, 변경마다 holdout precision 가드. broad RapidFuzz 금지 |
| 망각 재발(무replay ×8) | replay ~1:1 + frozen dict + Backward-Transfer early-stop, **stage7 판정 전** 적용 |
| n=41 noise 추격 | Wilson 하한 + McNemar + ≥100 확장 test = 전제조건 |
| consensus auto-label 순환(CLOVA=교사=GT) | 합의 auto-label 금지; 독립 3차 신호 + spot-audit |
| server 재학습 과투자(미검증 KO 전이) | oracle ladder가 recognition-bound 증명 시에만; 이득 +0.03 예산 |
| PaddleOCR-VL serving 경합 | 학습창 밖 serialize(inference-only=망각 0) |
| privacy 유출 | GT/label/합성 소스 off-git, build script·CI에서 강제 |
| detector 오탐 박스 | 모든 det 설정을 holdout field/recall로 게이트(박스 수 아님); thresh 0.25>0.20; 없는 'vertical-merge-tolerance' knob 무시 |

---

## 12. Open questions (먼저 해소)

1. 라이브 PaddleOCR 호출이 **server_det vs mobile_det**인가? det-only crop 경로가 unwarp/orientation 전처리를
   bypass하는가? (코드 확인 필요 — detection 레버를 게이트) ★
2. PP-OCRv5 **KOREAN mobile rec head가 SVTR 기반인가?**(RecAug vs SVTRRecAug 결정 — 실제 학습 config 확인)
3. **oracle ladder (iii) GT-OCR-text→parser가 대부분 0.85를 통과하는가?** = A100 재학습이 애초에 필요한지 결정하는
   최고 레버리지 미지수. ★
4. ~~gemma4:e4b의 실제 한국어 폰-사진 추출 능력?~~ **→ §9.1서 실측 답함**: 비전 단독은 약함(함량 누락) →
   OCR-free 헤드 불가, 하이브리드 텍스트-구조화 헤드로 채택. (잔여: 하이브리드 헤드의 holdout field_match/recall
   정량은 Step 3 ablation서 측정)
5. PaddleOCR-VL 0.052(문서 벤치)가 **곡면/glare 병 사진**에 전이되는가? zero-shot eval이 테스트.
6. 로컬 recognizer 배포 타깃이 **latency/VRAM 민감**한가?(server backbone 승격 시 로컬 추론 비용)
7. **PP-OCRv6**(2026-06-11 출시, +4.6% det/+5.1% rec)를 **detector-only** 실험으로? ⚠️ Korean 미확인 → Korean 1066-dict
   recognizer drop-in 절대 불가, detector-side probe 한정.
8. span-grounding validator의 recall이 수용 가능한가?(OCR 망가짐으로 진짜 amount 과도 drop?) precision/recall 분리 측정.

---

## 13. 리서치 사실-점검 정정 노트 (적대적 검증이 잡은 오류 — 잘못된 수치로 행동 금지)

| 항목 | 리서치 주장 | 정정(검증) |
|---|---|---|
| server vs mobile rec | "hard text에서 +4~16pt, 정확히 supplement regime" | **인쇄체(라벨에 해당) tier는 +2.5~4pt**; +16은 **손글씨** 한정. 일본어는 mobile이 우위. **한국어 벤치 없음** = 전이 미검증. server 재학습 이득 **~+0.03** 예산 |
| 한국어 server_rec | (암묵) 존재 가정 | **공식 모델 zoo에 한국어 server_rec 없음**(mobile만). 재학습 = from-scratch 가정 |
| PaddleOCR-VL VRAM | 62.8GB / 1.62 pps | **43.7GB / 1.22 pps**(vLLM, A100) — 80GB에 여유. "학습과 충돌" 우려 과장 |
| gemma 896×896 | "고정 896×896이 작은 글씨 파괴" + 42.9% | **Gemma-3-27B 수치** — 앱 모델 **gemma4:e4b는 가변 해상도**라 거짓 |
| food-label Jaccard 0.836 | (암묵) 로컬 기대값처럼 | **클라우드 GPT-4V** 수치. 저자명 'Aldahmani'는 오기(실제 Assiri/Alahmadi 외). 로컬 gemma 기대값 아님 |
| detector knob | "vertical merge tolerance 낮춰 라인 병합 회피" | **그런 파라미터 없음**(PaddleOCR). unclip_ratio/box 기하만. det thresh 0.2-0.25는 인용 출처 근거 없음 → 0.25 권장 |
| detector mix ratio | "general 5:1 혼합" | 5:1은 **recognition/합성**용. detection general+domain은 **~1:1** |
| CopyPaste | "기본 증강에 포함" | v5 det 기본 config에서 **null(비활성)**, IaaAugment만. 명시적 on 필요 |
| 합성 이득 인용 | "real finetune +6.3% CRNN, +4.3% TRBA" | TRBA는 **+1.8%**(Baek CVPR'21); +4.3%는 오기. 인용 URL도 교차됨 |
| dots.ocr 크기 | "1.7B VLM" | **LLM 백본만 1.7B**, 전체 ~3B급. MIT |
| oracle ablation | "신규 harness 구축" | **`build_roi_first_oracle_bundle.py` ROI-oracle leg 이미 존재** — `GT-OCR-text→parser` leg만 신규 |
| consensus 라벨 | "CLOVA-Paddle 합의 → trusted auto-label" | **순환**(Paddle=CLOVA distill, CLOVA=GT). 독립 3차 신호 필수 |
| PP-OCRv6 | (미언급) | 2026-06-11 출시(+4.6/+5.1%), **Korean 미확인** → detector-only probe 한정 |
| 미인증 수치 | 88.0% Korean line acc "5,007 이미지/+65% vs v4" | line acc 88.0%만 확인, 5,007·+65%는 미확인 |

---

## 참고 (공식/검증 출처 — caveat 포함)

- PaddleOCR OCR Pipeline: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR Text Recognition module(한국어 PP-OCRv5): https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html
- PaddleOCR recognition 학습/eval/export: https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
- PP-OCRv5 알고리즘(서버 vs 모바일 벤치): http://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html
- PaddlePaddle Windows pip(단일 GPU, no NCCL): https://www.paddlepaddle.org.cn/documentation/docs/install/pip/windows-pip_en.html
- Korean PP-OCRv5 config: https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/configs/rec/PP-OCRv5/multi_language/korean_PP-OCRv5_mobile_rec.yml
- PaddleOCR-VL(arXiv 2510.14528; 43.7GB/1.22pps vLLM, 한국어 edit-dist 0.052 — 문서 벤치): https://arxiv.org/abs/2510.14528
- dots.ocr(MIT, ~3B): https://github.com/rednote-hilab/dots.ocr
- "Let Me Speak Freely"(제약 디코딩은 shape만 강제): https://arxiv.org/abs/2408.02442
- "LoRA Learns Less and Forgets Less"(LLM 대상 — VLM 미특정, 방향성만): https://arxiv.org/abs/2405.09673
- SynthTIGER(CLOVA, ICDAR'21): https://github.com/clovaai/synthtiger
- Ultralytics YOLO Predict/Crop: https://docs.ultralytics.com/modes/predict/
- RapidFuzz fuzz API: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html
- bilingual food-label 추출(Assiri 외, J. Imaging 2025; 클라우드 VLM): https://doi.org/10.3390/jimaging11080271
- scikit-learn StratifiedGroupKFold(group leakage): https://scikit-learn.org/stable/modules/cross_validation.html

> 생성 근거: 2026-06-19 다중 에이전트 리서치 워크플로(14 agents, 6 차원 web research + 적대적 검증 + 종합).
> 모든 성능 수치는 밴드/추정이며, locked holdout/확장 test의 Wilson 하한 측정 전에는 단정 금지. best_accuracy
> 같은 training metric은 승격 근거가 아니다.
