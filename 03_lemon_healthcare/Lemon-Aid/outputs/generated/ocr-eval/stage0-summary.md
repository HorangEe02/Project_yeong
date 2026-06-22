# Stage 0 OCR Baseline 결과 종합 (2026-05-21)

> 본 보고서는 [plan §I Final Roadmap](/Users/yeong/.claude/plans/stateless-sniffing-swan.md)의 Stage 0 게이트 평가용 사용자 검토 자료. 완전 로컬(PaddleOCR + Ollama Vision) 정책으로 영양제/보충제 라벨 OCR의 **현재 인식률 baseline을 처음으로 정량 측정**한 결과를 정리한다.

---

## 한 줄 요약

50장 naver 상세페이지 라벨에 대해 **PaddleOCR text 추출 92%, parser_success 92%, 평균 latency 9.1초**를 측정했다. ingredient_name_exact_rate는 0.0이며 이는 사용자가 인지한 한계 — Ollama text 파서가 collect 스크립트에 아직 연결되지 않았고, 사람 검수된 expected snapshot도 비어 있기 때문이다. Stage 0 게이트는 fixture 30장+, raw 미저장, 카테고리 다양성을 모두 통과했고, 이제 정량 비교의 기준선이 생겼다.

---

## 측정 환경

| 항목 | 값 |
| --- | --- |
| Branch | `codex/p1-5-stabilization` |
| HEAD | `50e5bf0f feat(ocr): record Stage 0 PaddleOCR baseline on 50 naver detail-page fixtures` |
| OS | macOS arm64 (Darwin 25.5.0) |
| Python | 3.13.9 (`backend/.venv` 재생성본) |
| PaddleOCR | 3.5.0 |
| paddlepaddle | 3.3.1 (CPU; macOS arm64에 GPU wheel 부재) |
| 사용 모델 | `PP-OCRv5_server_det` + `korean_PP-OCRv5_mobile_rec` (자동 로드, cache) |
| Ollama | 로컬 서버 실행 중 — `qwen3.5:9b`, `gemma4:e4b` 등 |
| Fixture source | `/Volumes/Corsair EX300U Media/.../tampermonkey/naver/` (외장 SSD, 본인 다운로드) |
| Sample 정책 | `detail_page_first_category_balanced_then_review_fallback`, seed 20260517, scan-limit 60000 |
| 외부 OCR | 사용 안 함 (완전 로컬 정책) |

---

## 핵심 측정 결과

### Three-Tier Provider Metrics (`outputs/generated/ocr-eval/three-tier-stage0-naver/`)

| Provider | Calls | text_non_empty_rate | parser_success_rate | average_latency_ms | ingredient_name_exact_rate | errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **paddleocr_local** | **50** | **0.92** | **0.92** | **9140.4** | **0.0** | 0 (status counter) |

> note: status counter의 `errors`는 `paddleocr` SDK가 raise한 예외만 카운트. 별도 observation row에서는 50중 4건이 `error_code: "ocrerror"`로 표시되어 success rate 0.92로 반영됨.

### Phase 0 Baseline Validator (`outputs/generated/ocr-eval/baseline-stage0/`, synthetic 6 fixture)

- fixture_count: 6 (synthetic, P1-5에서 commit된 합성 fixture)
- expected_snapshot_valid_count (V2): 6/6
- expected_snapshot_v3_valid_count: 6/6
- evidence_refs_dangling: false
- requires_user_confirmation_rate: 1.0
- raw_image_stored / raw_ocr_text_stored / raw_provider_payload_stored / raw_model_response_stored: 모두 false

### Sample 분포 (50/50)

- source_kind: 100% `detail_page` (review fallback 사용 안 됨)
- category_label 16개 (각 3~4장): BCAA_EAA, HMB_타우린, 강황_커큐민, 관절_MSM_콘드로이친, 글루코사민, 기타, 남성_쏘팔메토, 뇌_은행잎, 다이어트_체지방, 단백질_프로틴, 루테인_눈, 마그네슘, 멀티비타민, 밀크씨슬_간, 비타민A, 비타민B
- license_status / consent_status: 50/50 `consented`
- contains_personal_data: 50/50 false

---

## Stage 0 게이트 평가

| 게이트 (plan §A6) | 통과 여부 | 비고 |
| --- | --- | --- |
| fixture ≥ 30 | ✅ 50장 | 단일 source(`naver`)에서 추출. naver_sunghoon source는 다음 라운드에 추가 가능 |
| raw image 미저장 | ✅ | manifest + observation + report 모두 `raw_image_stored: false` |
| raw OCR text 미저장 | ✅ | observation은 `text_hash`만 저장, 원문 텍스트는 in-memory 처리 |
| raw provider payload 미저장 | ✅ | `provider_artifact_stored: false` 검증 |
| segment 다양성 | ✅ 16 카테고리 + 100% detail_page | 한국어 only(naver) 단일. 영어 only / 한영 혼용은 fixture 확장에서 보강 필요 |
| PaddleOCR primary 동작 | ✅ 92% success | 4건 `ocrerror`는 별도 조사 후보 |
| Ollama 로컬 readiness | ✅ | `qwen3.5:9b`, `gemma4:e4b` 모델 사용 가능 |
| **ingredient_name_exact_rate 측정 가능** | ❌ | Ollama text 파서 미연결 + 사람 검수 expected 부재 |

종합: **Stage 0 인프라/정책 게이트는 통과**, **정확도 측정 게이트는 다음 작업 필요**.

---

## 알려진 한계와 그 출처

1. **`collect_supplement_ocr_observations.py`가 Ollama text 파서를 호출하지 않는다.** PaddleOCR raw text는 hash로만 저장되고, ingredient/amount/unit 구조화 변환은 일어나지 않는다. 따라서 현재 ingredient_name_exact_rate는 항상 0.0이다. → Stage 1 quick wins 또는 별도 PR에서 `parse_supplement_analysis_ocr_text`를 collect 경로에 통합해야 한다.
2. **사람 검수된 expected snapshot이 없다.** auto-seed로 채워진 expected.ingredients는 `verification_status: "provisional"`이며 첫 case에서도 `s(`, `정(`, `mgx608(` 같은 garbage가 들어가 있다. 정확도 비교의 기준이 없어 0.0 결과는 "라벨링 부재"의 신호일 뿐 PaddleOCR이 못 읽었다는 뜻이 아니다.
3. **macOS arm64에 paddlepaddle-gpu wheel이 없다.** 본 측정은 CPU 기반이고 외장 SSD i/o도 포함되어 평균 latency 9.1초가 나왔다. Linux/GPU 환경에서는 1~3초대로 떨어질 것으로 예상하지만, 본 baseline 수치는 그 가정에 의존하지 않는다.
4. **scan-limit 60,000으로 외장 데이터(181,841장) 중 약 33%만 봤다.** sample은 detail_page label_score 우선이라 편향은 크지 않지만, 라운드 확장 시 scan-limit을 늘리거나 카테고리별 source-root 호출 분할이 필요하다.
5. **`paddlepaddle`이 ccache 부재 경고를 띄운다.** 영향 없음, 향후 brew install ccache로 무음화 가능.
6. **Three-tier 평가 입력 schema 차이**: prepare 출력(JSON object cases list) ↔ collect 출력(observation JSONL row) ↔ three-tier 입력(row에 `observations[]` 내포 JSONL)이 서로 다르다. 이번에 추가한 `scripts/build_three_tier_manifest.py` (179줄)가 이 join을 결정론적으로 처리한다.

---

## 다음 액션

### 단기 (Stage 0 마무리)

1. **사용자 ground-truth 라벨링**: 16 카테고리 중 일부(예: 비타민A, 비타민B, 마그네슘, 오메가3, 멀티비타민)부터 V2/V3 snapshot 라벨링. 카테고리 폴더명을 `case_id` 접두로 사용해 추적. 라벨링 표준은 [`data/supplement_images/README.md`](../../../data/supplement_images/README.md) §④.
2. **naver_sunghoon source 라운드 추가** (선택): `--source-root .../tampermonkey/naver_sunghoon` 으로 22 카테고리 fixture 추가 수집 → 50장 추가 sample.
3. **Ollama text 파서 wiring**: `scripts/collect_supplement_ocr_observations.py`가 PaddleOCR raw text를 `parse_supplement_analysis_ocr_text`로 보내 structured ingredient를 observation에 함께 기록하도록 확장.

### Stage 1 Quick wins (plan §I)

라벨링 작업과 병렬로 시작 가능 — 코드 변경이 ground-truth 부재에 의존하지 않음.

- **L1-E**: `src/parsing/layout_parser.py SECTION_KEYWORDS`에 영문 anchor 6종 추가 (`Supplement Facts`, `Serving Size`, `Daily Value`, `Amount Per Serving`, `Ingredients`, `% Daily Value`).
- **L1-H**: PaddleOCR `local_ocr_use_doc_orientation_classify=True`, `local_ocr_use_textline_orientation=True` 기본 활성화. production validator 보강.
- **L1-G**: `parse_supplement_analysis_ocr_text` 경로에 `apply_parser_domain_corrections` + `nutrient_code_matcher` 정식 연결.

각 PR마다 동일 Stage 0 evaluation 명령(prepare → collect → build_three_tier_manifest → evaluate_ocr_three_tier)을 재실행해서 누적 정확도 변화를 추적.

### Stage 0 통과 조건 충족 시점

- ground-truth ≥ 30장 검수 완료
- Ollama text 파서가 collect 경로에 통합되어 `parsed_ingredients`가 0이 아닌 값으로 채워짐
- 같은 50 fixture에서 `ingredient_name_exact_rate` 측정값이 산출됨 (수치가 0.85에 미달해도 baseline으로 의미 있음)

---

## 재현 명령

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

# 0. PaddleOCR readiness
.venv/bin/python scripts/probe_paddleocr_runtime.py

# 1. Prepare manifest (외장 SSD 또는 사용자 inbox)
.venv/bin/python scripts/prepare_supplement_ocr_live_manifest.py \
  --source-root "/Volumes/Corsair EX300U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver" \
  --work-dir "../data/supplement_images/private_workspace/stage0_naver" \
  --sample-size 50 --scan-limit 60000 \
  --min-width 320 --min-height 240 \
  --max-bytes 20000000 --min-label-score 2 \
  --manifest-name manifest.json

# 2. Observation 수집 (완전 로컬, secret 불필요)
RUN_PADDLEOCR_PROBE=1 .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-stage0-naver \
  --providers paddleocr_local \
  --auto-expected-provider paddleocr_local \
  --auto-expected-manifest ../data/supplement_images/private_workspace/stage0_naver/manifest-with-observations.json

# 3. Three-tier JSONL 변환 (이번에 추가된 helper)
.venv/bin/python scripts/build_three_tier_manifest.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest-with-observations.json \
  --observations ../outputs/generated/ocr-eval/observations-stage0-naver/supplement-ocr-observations.jsonl \
  --output ../data/supplement_images/private_workspace/stage0_naver/manifest-three-tier.jsonl

# 4. Three-tier 평가
.venv/bin/python scripts/evaluate_ocr_three_tier.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest-three-tier.jsonl \
  --output-dir ../outputs/generated/ocr-eval/three-tier-stage0-naver

# 5. Redaction 회귀
grep -rn '"raw_artifacts_stored": *true\|"raw_ocr_text_stored": *true\|"raw_provider_payload_stored": *true' \
  ../outputs/generated/ocr-eval/ && exit 1 || echo "redaction OK"
```

---

## 산출물 목록 (commit `50e5bf0f`에 포함, push됨)

- `backend/scripts/build_three_tier_manifest.py` (helper, 179 lines, black/ruff/mypy strict 통과)
- `data/supplement_images/raw/friend_contributed/inbox/CONSENT.md` (외부 source 2행 추가)
- `outputs/generated/ocr-eval/baseline-stage0/{supplement-ocr-baseline.json,md}` (synthetic 6 fixture validator)
- `outputs/generated/ocr-eval/observations-stage0/supplement-ocr-observations.jsonl` (1차 tampermonkey-root attempt, 50 fixtures)
- `outputs/generated/ocr-eval/observations-stage0-naver/supplement-ocr-observations.jsonl` (2차 naver-root attempt, 50 fixtures × 16 카테고리)
- `outputs/generated/ocr-eval/three-tier-stage0/{json,md}` (example manifest 검증)
- `outputs/generated/ocr-eval/three-tier-stage0-naver/{json,md}` (**Stage 0 첫 baseline 보고서**)
- 본 파일 `outputs/generated/ocr-eval/stage0-summary.md`

raw 이미지는 `data/supplement_images/private_workspace/`에 두며 `.gitignore`로 git history에서 차단.
