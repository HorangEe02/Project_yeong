# OCR 프로젝트 구현·정확도 종합 평가 보고서

> 작성일: **2026-05-21** · 작성자: Claude Code (codex/p1-5-stabilization 브랜치 기준)
> 범위: Lemon Healthcare 영양제 라벨 OCR 파이프라인 (한글+영문, 목표 90~95% 인식 정확도)
> 산출 근거: `outputs/generated/ocr-eval/` 하위 실측 보고서, 핵심 소스 코드, 최근 11일치 todo-list

---

## 0. Executive Summary (한 페이지 요약)

| 평가축 | 신호등 | 한 줄 요약 |
|---|---|---|
| 파이프라인 인프라 | 🟢 | 3계층 OCR 캐스케이드 + Adapter/Factory + Audit + UoW + Alembic까지 모두 구현 완료 |
| 텍스트 추출 정확도 | 🟡 | Stage 0 baseline에서 `text_non_empty_rate = 0.92` — 목표 0.95까지 −3%p 갭 |
| 의미 파싱 정확도 | 🔴 | `ingredient_name_exact_rate = 0.0` — Ollama 텍스트 파서가 수집 경로에 미연결, **측정 자체가 불가** |
| 한/영 분리 메트릭 | 🔴 | 언어별 CER/WER 분리 측정 인프라 부재 — 사용자가 요구한 "한글, 영문" 별도 정확도 답변 불가 |
| Ground truth | 🟠 | 1/9 product만 라벨링 완료 (~11%) — 게이트 조건 ≥30 fixture 미달 |
| 테스트·안전 회귀 | 🟢 | pytest 648 passed / 6 skipped, raw 데이터 미저장 5종 모두 통과 |

**총평**: 파이프라인 골격과 안전망은 견고하다. 그러나 **"한글·영문 OCR이 90~95% 정확도를 만족하는가"라는 질문에 현재 답변할 수 없다.** 두 가지 근본 원인이 있다.

1. Ollama 텍스트 파서가 `collect_supplement_ocr_observations.py`에 wire-up되지 않아 `ingredient_name_exact_rate`가 0.0으로 고정 (이게 의미 정확도의 핵심 지표)
2. Ground truth 라벨링이 1/9에 그쳐 비교 기준이 거의 없음

현재 측정 가능한 유일한 정확도는 "텍스트가 비어있지 않은 비율(text_non_empty_rate)"이며, 이마저 92%로 목표(95%)에 3%p 미달한다. 게다가 본 fixture는 광고/박스 사진 90%+ 편중이라 운영 환경 대표성도 의심된다.

---

## 1. 측정 환경과 데이터셋

출처: [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md:15-27](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md), [stage0-summary.md:50-55](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md)

| 항목 | 값 |
|---|---|
| Branch | `codex/p1-5-stabilization` |
| HEAD (당시) | `50e5bf0f` (Stage 0 baseline) → 현재 `101df18e` (textline revert) |
| OS | macOS arm64 (Darwin 25.5.0) |
| Python | 3.13.9 (`backend/.venv` 재생성본) |
| PaddleOCR | 3.5.0 / paddlepaddle 3.3.1 (CPU; macOS arm64에 GPU wheel 부재) |
| OCR 모델 | `PP-OCRv5_server_det` + `korean_PP-OCRv5_mobile_rec` |
| Ollama | `qwen3.5:9b`, `gemma4:e4b` 로컬 사용 가능 |
| Fixture | 50장 naver detail_page (16 카테고리, 100% consented) |
| 외부 OCR | 사용 안 함 (완전 로컬 정책) |

**Fixture 카테고리(16종)**: BCAA_EAA, HMB_타우린, 강황_커큐민, 관절_MSM_콘드로이친, 글루코사민, 기타, 남성_쏘팔메토, 뇌_은행잎, 다이어트_체지방, 단백질_프로틴, 루테인_눈, 마그네슘, 멀티비타민, 밀크씨슬_간, 비타민A, 비타민B

⚠️ **Fixture 편중 경고**: 본 데이터는 네이버 상세페이지에서 추출된 **광고/박스/리뷰 crop이 90% 이상**이며 영양·기능정보 dense table은 거의 없음. 운영 환경(사용자가 라벨을 정면 촬영하는 케이스)과 분포가 다르다. → [stage1-l1h-comparison.md:39-42](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-comparison.md)

---

## 2. 구현 완료/부분/미구현 기능 평가

### 2.1 ✅ 완료된 기능 (실측 검증됨)

| 기능 | 상태 | 핵심 파일 |
|---|---|---|
| 3계층 OCR 캐스케이드 (L1 Google Vision → L2 PaddleOCR → L3 CLOVA) | ✅ | `backend/Nutrition-backend/src/ocr/base.py`, `factory.py`, `providers/` |
| Adapter ABC + Factory 패턴 | ✅ | `src/ocr/base.py` (OCRAdapter ABC) |
| PaddleOCR 로컬 통합 (방향/textline 옵션 노출) | ✅ | `src/ocr/providers/paddle.py`, `config.py` |
| Ollama LLM 어댑터 (텍스트/비전) | ✅ (코드만) | `src/llm/ollama.py` |
| OCR 관찰 수집 스크립트 | ✅ | `backend/scripts/collect_supplement_ocr_observations.py` (39.8KB) |
| 3계층 매니페스트 빌더 | ✅ | `backend/scripts/build_three_tier_manifest.py` |
| 4-way 회귀 분리 실험 인프라 | ✅ | env override 기반 (`LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY` 등) |
| Audit 트레일 (`audit_ocr_attempts`) + UoW + Idempotency + Alembic | ✅ | Phase C 완료, [2026-05-20 세션 요약](yeong-Lemon-Aid/outputs/todo-list/2026-05-20/) |
| Privacy 게이트 (raw 이미지/텍스트/payload 미저장) | ✅ | 양 stage 모두 `false` 확인 ([stage1-l1h-comparison.md:59](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-comparison.md)) |
| 안전 회귀 테스트 5종 + 전체 pytest | ✅ | **648 passed / 6 skipped** ([stage1-l1h-comparison.md:61](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-comparison.md)) |
| L1-E 영문 anchor 6종 (layout_parser SECTION_KEYWORDS) | ✅ | `src/parsing/layout_parser.py` (테스트 +2 추가됨) |
| Phase 0 Baseline Validator (synthetic 6 fixture) | ✅ | V2/V3 schema 검증 6/6 통과 ([stage0-summary.md:41-48](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md)) |

### 2.2 ⚠️ 부분 구현 (블로커)

| 기능 | 상태 | 영향 |
|---|---|---|
| **Ollama 텍스트 파서 → collect 스크립트 wire-up** | 코드 ✅, 연결 ❌ | `ingredient_name_exact_rate`가 0.0으로 고정 — **의미 정확도 측정 자체가 불가** |
| Ground truth ingredient 라벨링 | 1/9 product (~11%) | 비교 기준 부재. 게이트 ≥30 fixture 미달 |
| Sample expected snapshot | auto-seed로 일부 채워짐 (`provisional`) | garbage 포함 (`s(`, `정(`, `mgx608(` 등) — 비교 기준으로 부적합 ([stage0-summary.md:79](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md)) |

### 2.3 ❌ 미구현 / 향후 계획

| 항목 | 상태 |
|---|---|
| 한국어/영문 언어별 CER/WER 메트릭 분리 | ❌ 인프라 부재 |
| L1-G domain correction + nutrient_code_matcher 정식 연결 | ❌ (`parse_supplement_analysis_ocr_text` 경로) |
| Vision 모델 통합 (gemma4:e4b, Claude Vision) | ❌ 후보만 정의 |
| GPU 가속 | ❌ (macOS arm64에 paddlepaddle-gpu wheel 부재) |
| V3 schema `evidence_spans` 마이그레이션 | ❌ 정의만 완료 |
| 모바일 오프라인 큐 (SQLite drift 추적) | Phase 2 계획 |
| naver_sunghoon source 추가 라운드 | 선택 사항 (50장 추가 가능) |

---

## 3. 정확도 실측 수치 (Stage 0 baseline)

출처: [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md:31-39](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md)

### 3.1 Three-Tier Provider Metrics (50 fixture)

| Provider | Calls | text_non_empty_rate | parser_success_rate | avg latency (ms) | ingredient_name_exact_rate | errors |
|---|---:|---:|---:|---:|---:|---:|
| **paddleocr_local** | **50** | **0.92** | **0.92** | **9,140.4** | **0.0** | 4 (`ocrerror`) |

→ "텍스트 추출 92%" = 50장 중 46장에서 비어있지 않은 텍스트 추출 성공. 4장은 PaddleOCR detector가 실패.

### 3.2 목표 대비 갭 분석

| 메트릭 | 실측 | 목표(사용자 명시) | 갭 | 평가 |
|---|---|---|---|---|
| text_non_empty_rate | 0.92 | 0.95 | **−3%p** | 🟡 근접하나 미달 |
| parser_success_rate | 0.92 | 0.95 | **−3%p** | 🟡 근접하나 미달 |
| ingredient_name_exact_rate | **0.00** | 0.95 | **−95%p** | 🔴 **측정 자체 불가** (Ollama 파서 미연결) |
| 한글 CER/WER | 미측정 | (미정의) | — | 🔴 메트릭 부재 |
| 영문 CER/WER | 미측정 | (미정의) | — | 🔴 메트릭 부재 |

**핵심 진단**:
- "한글/영문 OCR 정확도 90~95%"라는 질문에 대해 **현재 답변할 수 없다.** 측정 인프라가 갖춰져 있지 않다.
- 가장 근접한 지표(`text_non_empty_rate = 0.92`)는 "텍스트가 추출되었는가" 수준이며, **그 텍스트가 라벨 원문과 얼마나 일치하는지(=정확도)**는 측정되지 않았다.

---

## 4. L1-H 회귀 원인 분리 측정 (4-way isolation, 50 fixture)

출처: [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-isolation.md:14-19](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-isolation.md)

| 조합 (ori/txt) | completed | errors | text_non_empty | parser_success | avg latency | p95 latency | char median |
|---|---:|---:|---:|---:|---:|---:|---:|
| `off/off` (Stage 0 baseline) | **46** | 4 | **0.920** | 0.920 | 9,935 ms | 18,858 ms | 269 |
| **`on/off` (orientation only)** ⭐ | **43** | 7 | 0.860 | 0.860 | **6,342 ms** | **8,629 ms** | **307** |
| `off/on` (textline only) | 41 | 9 | 0.820 | 0.820 | 7,168 ms | 12,058 ms | 243 |
| `on/on` (both, L1-H combined) | 41 | 9 | 0.820 | 0.820 | 6,722 ms | 9,468 ms | 243 |

### 4.1 핵심 발견

1. **textline_orientation이 회귀 주범** — `off/on`과 `on/on`이 동일하게 41 completed / 9 errors. textline 활성화 단독으로 5건의 추가 ocrerror 유발. 본 fixture의 광고 사진에서 textline classifier가 텍스트 행 방향을 잘못 추정.
2. **orientation_classify는 비용 대비 가치 큼** — errors +3건 회귀 vs char_median +14%, latency p95 **−54%** (18.9s → 8.6s).
3. **`on/off`가 sweet spot** — char 추출 풍부 + 가장 빠른 latency + 회귀는 −6%p로 제한적.

### 4.2 적용된 결정 (최근 커밋)

```
101df18e fix(ocr): revert PaddleOCR textline_orientation default after isolation finding
```

→ `local_ocr_use_doc_orientation_classify=True` 유지, `local_ocr_use_textline_orientation=False`로 revert 완료. 본 보고서의 4-way 분리 측정 결과가 evidence로 채택됨.

**기대 효과** (본 fixture 기준): success rate 0.82 → 0.86 회복 + p95 latency 9.5s → 8.6s 개선 + char_median 243 → 307 증가.

---

## 5. 사용자 질문에 대한 직접적 답변

### Q1. "각 기능이 제대로 구현되었는지"

대부분의 인프라 기능은 **제대로 구현되었다** (섹션 2.1 참조). 다만 **두 개의 부분 구현이 정확도 측정을 가로막는다**:

1. **Ollama 텍스트 파서가 수집 경로에 연결되지 않음** — 코드 자체는 `src/llm/ollama.py`에 존재하나 `collect_supplement_ocr_observations.py`가 이를 호출하지 않는다. 따라서 PaddleOCR이 추출한 raw text가 구조화된 ingredient/amount/unit으로 변환되지 않으며, `parsed_ingredients` 필드가 비어 있다.
2. **Ground truth 라벨링 미완** — 30개 필요 게이트에 1개만 채워짐. 사람 검수 expected가 없으니 자동 비교 기준이 부재.

### Q2. "목표 수치 90~95% 정확도를 만족하는가"

**현재 답변할 수 없다.** 두 가지 의미로:

1. **측정 가능한 유일 지표**(text_non_empty_rate = 0.92)는 목표 0.95에 3%p 미달. 즉 "텍스트를 어떻게든 뽑아낸 비율" 기준으로도 **목표 미달**.
2. **진정한 의미의 OCR 정확도**(라벨 원문 vs 추출 텍스트 일치율, ingredient_name_exact_rate 등)는 **측정 인프라가 갖춰지지 않아 0.0으로 고정**되어 있다. 따라서 "90% 달성/미달" 판단 자체가 현 시점에서는 불가능.
3. **한/영 분리 측정 부재** — 사용자가 명시적으로 요구한 "한글, 영문 분리 정확도"는 메트릭 인프라가 없어 답변할 수 없다.

추가로, 본 fixture(네이버 광고 사진 90%+ 편중)는 운영 환경과 분포가 다르므로, 실측치 0.92조차 운영 환경 대표성이 의심된다. → [stage1-l1h-comparison.md:39-42](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-comparison.md)

### Q3. "어디까지 구현했고 앞으로 해야 할 것"

**구현 완료** (섹션 2.1 12개 항목): 파이프라인 골격, 3계층 캐스케이드, Audit/UoW/Alembic, Privacy 게이트, 안전 회귀, L1-E 영문 anchor, baseline validator.

**남은 일** (다음 섹션 6 우선순위표):
- 정확도 측정을 가능하게 하는 P0 3개 항목이 즉시 필요
- 그 다음 운영 환경 대표 fixture 수집 (P1)
- 마지막으로 확장 (Vision, GPU, V3, 모바일)

---

## 6. 미구현 항목 우선순위 로드맵

### 🔴 P0 — 정확도 측정을 가능하게 함 (블로커)

| # | 항목 | 예상 시간 | 산출물 |
|---|---|---|---|
| P0-1 | **Ollama 텍스트 파서 → collect 스크립트 wire-up** — `parse_supplement_analysis_ocr_text`를 `collect_supplement_ocr_observations.py`에 통합해 `parsed_ingredients`가 채워지도록 | 2~3시간 | `ingredient_name_exact_rate` 측정 가능 |
| P0-2 | **Ground truth ≥30개 라벨링** — 16 카테고리 중 일부(예: 비타민A, B, 마그네슘, 오메가3, 멀티비타민)부터 V2/V3 snapshot 라벨링 | 3~5일 (사용자) | `data/supplement_images/private_workspace/.../ground_truth/` |
| P0-3 | **한/영 분리 CER/WER 메트릭 추가** — `evaluate_ocr_three_tier.py` 또는 별도 helper에 언어별 토큰 분류 + CER 계산 추가 | 1일 | `text_accuracy_ko`, `text_accuracy_en` 메트릭 |

### 🟡 P1 — 정확도 향상

| # | 항목 | 비고 |
|---|---|---|
| P1-1 | 운영 환경 대표 fixture 수집 | 사용자가 직접 촬영한 한국 시판 영양제 라벨 (영양·기능정보 dense table 위주) |
| P1-2 | 운영 fixture로 L1-H 재평가 | `on/on` 조합이 라벨 정면 사진에서 양의 신호 내는지 확인 |
| P1-3 | L1-G domain correction + nutrient_code_matcher 정식 연결 | `parse_supplement_analysis_ocr_text` 경로 |
| P1-4 | L1-E 영문 anchor 효과 측정 | `evaluate_ocr_three_tier.py` 또는 endpoint 테스트 |
| P1-5 | naver_sunghoon source 추가 라운드 | 22 카테고리 + 50장 추가 sample (선택) |

### 🟢 P2 — 확장

| # | 항목 | 비고 |
|---|---|---|
| P2-1 | Vision 모델 통합 (gemma4:e4b, Claude Vision) | Adapter 패턴 그대로 적용 |
| P2-2 | GPU 가속 (Linux 환경 또는 Cloud) | 예상 1~3초대 latency (현재 9.1초) |
| P2-3 | V3 schema `evidence_spans` 마이그레이션 | 페이지/블록/단락/단어 경계박스 |
| P2-4 | 모바일 오프라인 큐 (SQLite drift 추적) | Phase 2 |

---

## 7. 95% 도달 권장 경로 (단계별 액션)

```
Step 1 (즉시, 2~3시간)
  └── P0-1: Ollama parser wire-up
       → ingredient_name_exact_rate가 의미 있는 수치로 채워짐 (현재 0.0)

Step 2 (사용자, 3~5일)
  └── P0-2: Ground truth ≥30개 라벨링
       → 자동 비교 기준 확보, 정확도 측정 게이트 통과

Step 3 (즉시, 1일)
  └── P0-3: 한/영 CER/WER 분리 메트릭
       → 사용자 요구 "한글, 영문 정확도" 답변 가능해짐

Step 4 (사용자 협업, ~1주)
  └── P1-1: 운영 환경 대표 fixture 수집
       → 광고 편중 fixture 한계 해소

Step 5 (재측정)
  └── 운영 fixture에서 Stage 0 (off/off) + L1-H 조합 재실행
       → 진짜 정확도 측정값 확보

Step 6 (Gap 분석 + 개선)
  └── P1-3, P1-4 (domain correction, 영문 anchor 효과)
  └── 측정값이 95% 미달이면 PaddleOCR 모델 변경 or Google Vision으로 L1 escalation 시점 조정
```

**예상 시점** (낙관적):
- ingredient_name_exact_rate 첫 측정값 확보: **+1주**
- 한/영 분리 정확도 첫 측정값 확보: **+1주**
- 운영 환경 90% 달성 검증: **+3~4주**
- 운영 환경 95% 달성 검증: **시점 미상** — Step 6의 gap에 따라 PaddleOCR 모델 교체 또는 Google Vision primary 승격 검토 필요

---

## 8. 위험 요소 (Risk Register)

| 위험 | 발생 가능성 | 영향 | 완화 방안 |
|---|---|---|---|
| Fixture 편중으로 실측 90% 정확도조차 운영 환경 대표성 부족 | **높음** | 잘못된 PR 결정으로 회귀 도입 | 운영 fixture 수집 우선, 본 측정은 fixture-specific 시그널로 해석 |
| Ollama parser wire-up 시 새 회귀 발생 | 중간 | 측정값 자체가 왜곡 | 회귀 테스트 5종 유지 + parser 출력 schema validation |
| Ground truth 라벨링이 사용자 시간 의존 | 높음 | P0 일정 지연 | 일부 카테고리 (5종)부터 빠르게 시작, 나머지는 점진적 |
| macOS arm64 CPU only → 운영 GPU 환경 latency 추정 어려움 | 중간 | UX 의사결정 지연 | Linux/GPU 환경에서 별도 benchmark 1회 측정 권장 |
| PaddleOCR korean_PP-OCRv5_mobile_rec가 한/영 혼용 라벨에서 성능 미보장 | 중간~높음 | 95% 목표 도달 실패 | 한/영 분리 메트릭 + 영문 라벨 별도 fixture 수집 + 모델 교체 옵션 |

---

## 9. 재현 명령 (사용자가 직접 검증 가능)

출처: [stage0-summary.md:113-152](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md), [stage1-l1h-isolation.md:67-85](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-isolation.md)

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

# Stage 0 (off/off) — baseline 0.92 재현
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=false \
LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-stage0-naver \
  --providers paddleocr_local

# Sweet spot (on/off) — 0.86 + latency 최저 재현
RUN_PADDLEOCR_PROBE=1 ENABLE_LOCAL_OCR=true \
LOCAL_OCR_USE_DOC_ORIENTATION_CLASSIFY=true \
LOCAL_OCR_USE_TEXTLINE_ORIENTATION=false \
  .venv/bin/python scripts/collect_supplement_ocr_observations.py \
  --manifest ../data/supplement_images/private_workspace/stage0_naver/manifest.json \
  --output-dir ../outputs/generated/ocr-eval/observations-stage1-naver-ori_only \
  --providers paddleocr_local

# Redaction 회귀 (raw 데이터 미저장 확인)
grep -rn '"raw_artifacts_stored": *true\|"raw_ocr_text_stored": *true\|"raw_provider_payload_stored": *true' \
  ../outputs/generated/ocr-eval/ && exit 1 || echo "redaction OK"

# 전체 테스트
.venv/bin/pytest -q --no-cov
# 기대: 648 passed, 6 skipped
```

---

## 10. 결론

### 기능 구현 측면
파이프라인 골격, Adapter/Factory, Audit, Privacy, 회귀 테스트까지 **인프라는 잘 갖춰져 있다**. 아키텍처 의사결정도 evidence 기반(4-way isolation으로 textline revert)으로 진행되고 있다.

### 정확도 목표 달성 여부
**현재 답변 불가**. 측정 가능한 유일 지표(text_non_empty_rate 0.92)는 목표 0.95에 3%p 미달이며, 진정한 의미의 OCR 정확도(ingredient_name_exact_rate, 한/영 CER 등)는 **측정 인프라 자체가 갖춰지지 않아** 판단할 수 없다.

### 즉시 해야 할 일 (Top 3)
1. **Ollama 텍스트 파서를 collect 스크립트에 연결** (2~3시간) → 측정 가능 상태 해제
2. **Ground truth ≥30개 라벨링** (3~5일, 사용자) → 비교 기준 확보
3. **한/영 분리 CER/WER 메트릭 추가** (1일) → 사용자가 요구한 언어별 정확도 측정 가능

이 세 가지가 끝나야 비로소 "90~95% 정확도 목표를 만족하는가"라는 질문에 정직하게 답할 수 있다.

---

## 부록 — 핵심 출처 파일 목록

| 파일 | 용도 |
|---|---|
| [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-summary.md) | Stage 0 baseline 종합 (50 fixture, 0.92) |
| [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-comparison.md](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-comparison.md) | Stage 0 vs Stage 1 L1-H 비교 (회귀 발견) |
| [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-isolation.md](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage1-l1h-isolation.md) | 4-way isolation (textline 회귀 주범 확정) |
| [yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-labeling-worksheet.md](yeong-Lemon-Aid/outputs/generated/ocr-eval/stage0-labeling-worksheet.md) | Ground truth 라벨링 워크시트 |
| [yeong-Lemon-Aid/backend/scripts/collect_supplement_ocr_observations.py](yeong-Lemon-Aid/backend/scripts/collect_supplement_ocr_observations.py) | OCR 관찰 수집 메인 진입점 (39.8KB) |
| [yeong-Lemon-Aid/backend/Nutrition-backend/src/config.py](yeong-Lemon-Aid/backend/Nutrition-backend/src/config.py) | L1-H 옵션 default 정의 (textline revert 위치) |
| [yeong-Lemon-Aid/backend/Nutrition-backend/src/parsing/layout_parser.py](yeong-Lemon-Aid/backend/Nutrition-backend/src/parsing/layout_parser.py) | L1-E 영문 anchor 추가 위치 |

---

**보고서 끝.**
