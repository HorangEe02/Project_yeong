# Handoff — CLOVA→GT 완료 → Ollama 종료/메모리 확보 → OCR benchmark gate #1 → PaddleOCR baseline·fine-tune·95% gate

> **사용법.** 이 파일 전체를 다음 세션 첫 프롬프트로 붙여넣으세요. self-contained 입니다. 각 단계는 `[자동]`(에이전트 실행) / `[사람]`(운영자 판단 필요) / `[게이트]`(통과 증거 리포트)로 표시됩니다. 명령은 검증된 실제 인자입니다(이 핸드오프 작성 시 스크립트 원본 대조 완료).
>
> 작성 시각: 2026-06-06. 작성자 컨텍스트: CLOVA OCR 출력을 그대로 pseudo-GT(정답지)로 사용한다는 운영자 결정(사람 보정 없음). PaddleOCR는 그 정답지에 distill/측정. 목표: PaddleOCR 텍스트 추출 정확도 ≥ 95%.

---

## 0. 미션 한 줄

CLOVA→GT 채움을 완료(또는 가능한 만큼 확정) → Ollama 모델 언로드로 메모리 확보 → `GT 검증 → GT preflight → benchmark manifest → splits → 게이트 #1` → `PaddleOCR baseline 평가(.venv-paddle) → CLOVA GT 대비 정확도` → `PaddleOCR fine-tune → 재평가 → 95% 게이트`.

---

## 1. 검증된 현재 상태 (2026-06-06 기준, 직접 확인)

| 항목 | 값 | 증거 |
|---|---|---|
| CLOVA→GT 채움 | **134/215 ready** | `clova-ground-truth.summary.json`: `rows=215, processed=215, filled_with_ingredients=134, filled_no_ingredients=11, failed=70` |
| `ground-truth.todo.jsonl` | 215행, `ready_for_benchmark_after_review:true` **134건** | `grep -c '"ready_for_benchmark_after_review": true'` |
| 70건 failed 원인 | **Ollama를 중간에 강제 종료** → connection refused (이미지 자체 문제 아님 → 재실행 시 대부분 성공 예상) | 직전 세션 로그 |
| 11건 no-ingredient | CLOVA+Ollama가 ingredient 0개 추출 → 구조적으로 not-ready (재실행해도 ready 안 될 가능성 높음) | summary `filled_no_ingredients=11` |
| Ollama 데몬 | **재기동됨** (`/opt/homebrew/opt/ollama/bin/ollama serve`, brew services) — 단, **모델 미로딩 상태라 메모리 81% free** | `pgrep`, `memory_pressure` |
| PII 게이트 | 통과 (215 cleared by operator, strict preflight 215/unmatched 0) | `reconciled/pii-review-preflight.json` (38줄) |
| teacher-safe candidates | 215 | `reconciled/teacher-safe-ocr-candidates.jsonl` |
| GT bundle summary | **`ready_for_benchmark_rows: 0` (빌더 하드코딩), `ground_truth_template_row_count: 215`** | `ocr-ground-truth-review-bundle/summary.json` — ⚠️ **게이트 #1 차단 원인, §4 GAP-1 참조** |
| venvs | `.venv` = py3.13.7 (backend), `.venv-paddle` = py3.12.13 (paddlepaddle+paddleocr 3.6.0+rapidfuzz) | — |

**요약:** Chain A는 GT 채움 단계까지 와 있음. 게이트 #1 통과를 위해 (1) 가능한 만큼 ready 확보, (2) **§4의 3개 GAP 해소**가 필요. 이 GAP들은 기존 파이프라인 스크립트의 구조적 제약이며, 이전 세션 노트에는 없었고 이번에 게이트/빌더/테스트 원본을 읽어 발견함 — **반드시 먼저 읽을 것.**

---

## 2. 환경 변수 & 불변식 (먼저 셸에 export)

```bash
REPO="/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid"
BACKEND="$REPO/backend"
RD="$REPO/outputs/generated/supplement-learning/2026-06-05/operator-review"
BUNDLE="$RD/ocr-ground-truth-review-bundle"
PY="$BACKEND/.venv/bin/python"            # py3.13 backend
PYPADDLE="$BACKEND/.venv-paddle/bin/python" # py3.12 paddleocr
```

불변식:
- **env-split (절대 위반 금지):** paddlepaddle/paddleocr는 **`.venv-paddle`(py3.12)에만** 설치. backend(`.venv` py3.13)에는 paddle 미설치(설치 불가). 따라서 paddle 실행 스크립트는 `$PYPADDLE`로만.
- **백엔드 스크립트 실행 위치:** `cd "$BACKEND"` 후 `PYTHONPATH=Nutrition-backend "$PY" scripts/<x>.py ...`. (CLOVA→GT는 DB/설정 접근 → `PGPASSWORD=postgres` 도 유지.)
- **`.env` 위치:** `$REPO/.env` (repo 루트, gitignored). config `ENV_FILE_CANDIDATES=(PROJECT_ROOT/.env, BACKEND_ROOT/.env)` 라 CWD 무관하게 로드됨. CLOVA(`ENABLE_CLOVA_OCR=true`, `ALLOW_EXTERNAL_OCR=true`, `OCR_PRIMARY_PROVIDER=clova`, `CLOVA_OCR_API_URL/SECRET`) + Ollama 설정 포함. **`.env`는 절대 Read+print 하지 말 것**(기존 시크릿 노출 금지). 수정 필요 시 append/in-place만.
- **프라이버시(redaction, 거부 스캔이 강제):** outputs에 raw OCR 텍스트 / provider payload / 로컬·절대 경로 / source ref / 제품 폴더 literal 저장 금지. 새 스크립트도 이 규칙 준수(숫자 점수·카운트·safe basename·sha256만).
- **PII 판정은 사람(운영자) 행위** — AI가 대신 clear 금지(이미 완료됨).
- **macOS:** `timeout` 바이너리 없음. NFD 파일명 → `unicodedata.normalize("NFC", ...)`.
- **커밋/푸시는 사용자 요청 시에만.** 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **품질:** ruff clean + type hints + Google docstrings + `git diff --check`.

---

## 3. 실행 절차

### Step A — `[자동]` CLOVA→GT 완료(또는 확정)

Ollama 모델이 올라와야 파서가 동작. 데몬은 떠 있으니 모델만 워밍.

```bash
# 1) Ollama 가동 확인 + 파서 모델 워밍업(예: gemma 계열). 모델 미로딩이면 첫 요청에서 로드됨.
pgrep -ifl "ollama serve" || (brew services start ollama 2>/dev/null || ollama serve &)
# 2) CLOVA→GT 재실행 — 멱등: ready 행은 skip, failed(70)+no-ingredient(11)만 재시도
cd "$BACKEND" && PGPASSWORD=postgres PYTHONPATH=Nutrition-backend "$PY" \
  scripts/build_clova_ground_truth.py \
  --bundle-dir "$BUNDLE" --apply \
  --summary "$RD/clova-ground-truth.summary.json"
```

- 멱등성: `ready_for_benchmark_after_review is True` 행은 `--force` 없으면 skip. 70건 failed는 Ollama 살아있으면 대부분 성공할 것.
- ⚠️ **이 스크립트는 끝에 한 번에 기록**(증분 체크포인트 없음). 중간 종료 시 그 회차분 유실 → 재실행으로 복구.
- **외부 호출 발생**(CLOVA). 운영자 결정상 허용됨.
- 종료 후 `clova-ground-truth.summary.json`의 `filled_with_ingredients`(=새 ready 합계) 확인. 11건 no-ingredient는 ready 안 될 수 있음 → §4 GAP-1에서 ready-only로 스코프.

### Step B — `[자동]` Ollama 모델 언로드 → 메모리 확보 (paddle 전 필수)

OOM의 원인은 **로딩된 모델 + paddle 동시 실행**(이전에 PP-OCRv5 server-det 4000px + Ollama = exit 137). idle `ollama serve` 자체는 메모리 거의 안 씀(현재도 81% free).

```bash
ollama stop 2>/dev/null || true            # 로드된 모델 언로드(가능 시)
pkill -9 -if "llama-server" 2>/dev/null || true   # 모델 러너 강제 종료
# 데몬까지 완전히 내리려면(선택): brew services stop ollama  /  pkill -9 -if "ollama serve"
memory_pressure | grep -i "free percentage"  # 높은지 확인 후 paddle 진행
```

규칙: **paddle 실행 중에는 Ollama 모델을 절대 로드하지 말 것.** paddle은 mobile det + max-side 2048 다운스케일로만(내 스크립트 기본값).

### Step C — `[자동]` GT 검증 (ready / failures)

```bash
total=$(grep -c . "$BUNDLE/ground-truth.todo.jsonl")
ready=$(grep -c '"ready_for_benchmark_after_review": true' "$BUNDLE/ground-truth.todo.jsonl")
echo "GT total=$total ready=$ready"
cat "$RD/clova-ground-truth.summary.json"   # processed/failed/no-ingredient 카운트
```

리포트: ready 수, 남은 failed/no-ingredient 수. ready가 더 늘지 않으면 그 집합으로 진행.

### Step D — `[자동]` GT preflight

```bash
cd "$BACKEND" && PYTHONPATH=Nutrition-backend "$PY" \
  scripts/preflight_supplement_ocr_ground_truth_manifest.py \
  --ground-truth "$BUNDLE/ground-truth.todo.jsonl" \
  --required-expected-section ingredient_amounts \
  --required-expected-section intake_method \
  --min-ready-rows 1 \
  --output "$RD/reconciled/ocr-ground-truth-preflight.json" \
  --markdown-output "$RD/reconciled/ocr-ground-truth-preflight.md"
```

- 사용자 지정 required = `ingredient_amounts`, `intake_method` (2개). 통과 신호: `ready_for_benchmark_build: true`, `benchmark_ready_row_count > 0`.
- ⚠️ **단, 게이트 #1은 4개 섹션을 강제** → §4 GAP-2. preflight와 benchmark의 required 섹션 정합성 주의.

### Step E — `[자동]` Benchmark manifest

⚠️ **게이트 #1이 요구하는 4개 섹션 모두 선언**해야 통과(§4 GAP-2). 2개만 선언하면 `benchmark_missing_required_expected_sections=[precautions, allergen_warnings]` → 차단.

```bash
cd "$BACKEND" && PYTHONPATH=Nutrition-backend "$PY" \
  scripts/build_supplement_ocr_benchmark_manifest.py \
  --candidate-manifest "$RD/reconciled/teacher-safe-ocr-candidates.jsonl" \
  --ground-truth "$BUNDLE/ground-truth.todo.jsonl" \
  --required-expected-section ingredient_amounts \
  --required-expected-section intake_method \
  --required-expected-section precautions \
  --required-expected-section allergen_warnings \
  --output "$RD/reconciled/ocr-benchmark-manifest.jsonl"
```

- ⚠️ **확인 필요:** 빌더 인자는 `--candidate-manifest --ground-truth --output --source-run-id` 뿐. `--output`이 manifest(rows) 인지, 별도 `*.summary.json`(schema `supplement-ocr-provider-benchmark-manifest-v1`)을 옆에 쓰는지 **실행 후 산출물 확인**. 게이트의 `--benchmark-summary`에는 **summary JSON**(schema `...manifest-v1`, 필드 `benchmark_fixture_count`/`scoreable_fixture_count`/`required_expected_sections`)을 넘겨야 함.
- 통과 조건(게이트): `benchmark_fixture_count > 0` AND `scoreable_fixture_count == benchmark_fixture_count` AND 4개 섹션 모두 선언. allergen_warnings/precautions가 비어 있는 행은 scoreable에서 빠질 수 있음 → fixture 수 감소 가능(허용 가능한 결과로 리포트).

### Step F — `[자동]` Splits (leakage-safe)

```bash
cd "$BACKEND" && PYTHONPATH=Nutrition-backend "$PY" \
  scripts/assign_paddleocr_benchmark_splits.py \
  --benchmark-manifest "$RD/reconciled/ocr-benchmark-manifest.jsonl" \
  --output "$RD/reconciled/ocr-benchmark-splits.json" \
  --seed 42
# (필요 시 --holdout-ratio / --test-ratio 조정. holdout fixture > 0 필수)
```

통과 조건(게이트): `ready_for_holdout_eval: true`, `leakage_check_passed: true`, `row_count == benchmark_fixture_count`, `holdout > 0`. 출력 schema `paddleocr-benchmark-split-assignment-v1`.

### Step G — `[게이트] #1` OCR benchmark gate

먼저 **§4 GAP-1 해소**(bundle summary `ready_for_benchmark_rows == ground_truth_template_row_count > 0`)가 안 되면 무조건 `blocked_by_ground_truth_review`. 해소 후:

```bash
cd "$BACKEND" && PYTHONPATH=Nutrition-backend "$PY" \
  scripts/gate_supplement_ocr_benchmark.py \
  --pii-preflight "$RD/reconciled/pii-review-preflight.json" \
  --ground-truth-bundle-summary "$RD/reconciled/ocr-ground-truth-bundle-summary.finalized.json" \
  --ground-truth-preflight "$RD/reconciled/ocr-ground-truth-preflight.json" \
  --benchmark-summary "$RD/reconciled/ocr-benchmark-manifest.summary.json" \
  --benchmark-split-summary "$RD/reconciled/ocr-benchmark-splits.json" \
  --require-ready-for-teacher-ocr-eval \
  --output "$RD/reconciled/ocr-benchmark-gate.json" \
  --markdown-output "$RD/reconciled/ocr-benchmark-gate.md"
```

**통과 = `status: "ready_for_teacher_ocr_eval"`**, `external_teacher_ocr_eval_allowed: true`. (`--require-ready-for-teacher-ocr-eval`는 미통과 시 exit 1.) 게이트 JSON의 `status` + 모든 `*_ready`/`*_allowed` 필드를 증거로 리포트.

> 게이트 차단 상태 코드(원인 진단용): `blocked_by_pii_screening` / `blocked_by_no_teacher_safe_rows` / `blocked_by_ground_truth_review` / `blocked_by_benchmark_manifest` / `blocked_by_benchmark_split_assignment`.

### Step H — `[자동]` PaddleOCR baseline 평가 (.venv-paddle) → CLOVA GT 대비 정확도

두 경로가 있음. **빠른 baseline은 H-1**(오늘 바로 실행 가능), **게이트 연결은 H-2**(§4 GAP-3 해소 필요).

**H-1) 빠른 baseline (standalone, 권장 첫 실행):**
```bash
"$PYPADDLE" "$BACKEND/scripts/paddleocr_clova_eval.py" \
  --bundle-dir "$BUNDLE" \
  --output "$RD/reconciled/paddleocr-baseline-eval.json" \
  --apply
# 출력: mean_char_accuracy, ingredient_recall (schema paddleocr-clova-eval-v1)
```
- ready 행만 채점. mobile det + max-side 2048(OOM 회피). backend 미import(독립).
- ⚠️ 이 schema(`paddleocr-clova-eval-v1`)는 95% 게이트가 받지 않음 → 빠른 현황 파악용. 게이트 연결은 H-2.

**H-2) 형식 baseline (게이트 연결):** `run_paddleocr_baseline_eval.py` 가 정식 진입점(scripts/에 존재). 이건 `collect_supplement_ocr_observations.py`(→ paddle observations) → `merge_paddleocr_text_observations_into_benchmark.py` → `build_paddleocr_text_extraction_eval_summary.py`(schema `supplement-paddleocr-text-extraction-eval-summary-v1`) 체인을 따름. **§4 GAP-3** 때문에 paddle 관측을 py3.12에서 만들어 넘기는 브리지가 필요 → 먼저 `run_paddleocr_baseline_eval.py`를 읽고 venv 기대치 확인.

### Step I — `[게이트] #2 / 95% stop-gate` + fine-tune 루프

```bash
cd "$BACKEND" && PYTHONPATH=Nutrition-backend "$PY" \
  scripts/gate_paddleocr_text_extraction_target.py \
  --eval-summary "$RD/reconciled/<paddleocr-eval-summary>.json" \
  --min-fixtures 30 \
  --output "$RD/reconciled/paddleocr-text-target-gate.json" \
  --markdown-output "$RD/reconciled/paddleocr-text-target-gate.md"
```

- threshold 기본 `0.95`(`--target-threshold`로 조정). 받는 schema: `supplement-paddleocr-text-extraction-eval-summary-v1` 또는 `paddleocr-text-extraction-eval-summary-v1` (⚠️ H-1의 `paddleocr-clova-eval-v1`은 **불가** → H-2 또는 브리지 산출물 필요).
- **≥95% → `paddleocr_target_reached: true`, 학습 중단.** **<95% → fine-tune 루프:** scripts/에 정식 도구 있음 →
  `build_paddleocr_improvement_candidates.py` → (annotation tasks) `create_paddleocr_annotation_tasks_from_improvement_candidates.py` / `promote_paddleocr_annotation_tasks_to_dataset.py` → `materialize_paddleocr_dataset.py` / `export_training_manifest.py` → `build_paddleocr_finetune_run_plan.py` → `register_paddleocr_finetune_run_from_plan.py` → `run_paddleocr_finetune_plan.py` → `run_paddleocr_eval_from_finetune_plan.py` → `gate_paddleocr_finetune_against_baseline.py` → 재평가 → 다시 Step I. (fine-tune은 paddle 학습이므로 `$PYPADDLE`; OOM 주의.)

---

## 4. 알려진 GAP (게이트 통과 전 반드시 해소) — 이번 세션에서 원본 읽고 발견

### GAP-1 — GT bundle summary `ready_for_benchmark_rows`가 영구 0 (게이트 #1 핵심 차단)
- **사실:** `build_supplement_ocr_ground_truth_review_bundle.py`의 `_summary()`는 `ready_for_benchmark_rows: 0`을 **하드코딩**(L432). 또 `_read_template_rows()`는 `ready_for_benchmark_after_review != False`인 행을 **거부**(L197) → **채워진 todo.jsonl로 빌더 재실행 불가**.
- **게이트 요구:** `gate_supplement_ocr_benchmark.py`의 `gt_review_ready`(L225-229) = `bundle.ready_for_benchmark_rows > 0` AND `== bundle.ground_truth_template_row_count`. 빌더 출력으로는 **절대 충족 불가**(0 > 0 = false). 테스트(`test_gate_supplement_ocr_benchmark.py` `_gt_payload`)는 이 summary를 **수작업으로** ready==template로 만들어 통과시킴 → 즉 프로덕션에 **finalize 도구가 없음**.
- **해소(권장):** 작은 finalize 스크립트 신규 작성 — 예 `scripts/finalize_supplement_ocr_ground_truth_bundle_summary.py`:
  - 채워진 `ground-truth.todo.jsonl`을 읽어 `ready_for_benchmark_after_review is True` 행 수 `N` 계산.
  - schema `supplement-ocr-ground-truth-review-bundle-v1`로 summary 출력하되 **`ground_truth_template_row_count = ready_for_benchmark_rows = N`** (= benchmark를 ready 행으로 스코프). 나머지 redaction 플래그(`raw_*_stored:false`, `absolute_paths_stored:false` 등) 모두 유지.
  - 이 산출물을 Step G의 `--ground-truth-bundle-summary`로 사용(`...bundle-summary.finalized.json`).
  - 의미상 정당: benchmark manifest 빌더도 이미 ready 행만 fixture로 필터하므로 "benchmark 집합 = 완전 검토된 집합"으로 일치.
- **대안:** 모든 215행을 ready로 만들기 → 11건 no-ingredient 때문에 비현실적.

### GAP-2 — 게이트는 4개 섹션 강제, 사용자 절차는 2개
- **사실:** 게이트의 `REQUIRED_BENCHMARK_EXPECTED_SECTIONS = (ingredient_amounts, intake_method, precautions, allergen_warnings)` (4개, L66-71). benchmark summary가 4개 모두 선언 안 하면 `benchmark_required_sections_ready=false` → `blocked_by_benchmark_manifest`.
- **충돌:** 사용자 절차의 GT preflight required는 2개(`ingredient_amounts, intake_method`)뿐. preflight는 2개로 OK지만 **benchmark manifest는 4개로 빌드**해야 게이트 통과(Step E).
- **영향:** CLOVA→GT의 `allergen_warnings`는 키워드 기반 best-effort 추출이라 비어있는 행 多 → 4개 강제 시 scoreable fixture 감소 가능. fixture 수를 리포트하고, 필요 시 운영자에게 (a) 4개 유지(행 감소 감수) vs (b) 게이트 정책 완화(코드 변경=승인 필요) 결정 요청.

### GAP-3 — PaddleOCR 관측을 만드는 정식 collect가 py3.13에서 paddle 실행 불가
- **사실:** `collect_supplement_ocr_observations.py`는 `from src.ocr.providers.paddle import PaddleOCRAdapter`(L47) 사용. `paddle.py` 어댑터는 paddleocr를 **런타임 lazy-import**(L154 `import_module("paddleocr")`) — 미설치면 `OCRError("PaddleOCR is not installed...")`. backend `.venv`(py3.13)엔 paddle 미설치 → **collect가 paddle 관측 생산 불가**.
- **결과:** 정식 95% 게이트가 받는 `supplement-paddleocr-text-extraction-eval-summary-v1`를 만드는 체인이 py3.13에서 끊김. 내 standalone `paddleocr_clova_eval.py`(py3.12)는 동작하지만 schema가 달라 게이트 비호환.
- **해소 옵션:** (a) paddle 관측을 `$PYPADDLE`에서 생성해 manifest에 merge하는 브리지 추가; (b) `run_paddleocr_baseline_eval.py`가 내부적으로 cross-venv/subprocess를 처리하는지 먼저 확인 후 그 경로 사용; (c) `paddleocr_clova_eval.py` per-image 점수를 eval-summary schema로 변환하는 작은 어댑터. **먼저 `run_paddleocr_baseline_eval.py` 원본을 읽어 의도된 경로 파악할 것.**

---

## 5. 핵심 caveat 체크리스트
- [ ] **OOM:** paddle 실행 중 Ollama 모델 로드 금지. paddle은 mobile det + max-side 2048만. server-det/4000px 금지.
- [ ] **env-split:** paddle=`$PYPADDLE`(3.12), backend=`$PY`(3.13). 섞지 말 것.
- [ ] **candidate manifest는 `teacher-safe-ocr-candidates.jsonl`(215)** 사용. (과거 stale `supplement-review-ocr-ground-truth-candidates.jsonl`은 overlap 3 → 금지.)
- [ ] **bundle 이미지 경로는 `images/...` 상대경로**여야 함(`_safe_relative_image_path`가 강제; 절대경로/`..`/`images/` 밖 거부).
- [ ] **CLOVA→GT는 끝에 일괄 기록.** 중간 종료 시 그 회차 유실 → 재실행(멱등).
- [ ] **redaction:** 모든 신규 산출물에 raw OCR/payload/경로 금지(거부 스캔 통과해야 함).
- [ ] **커밋은 사용자 요청 시에만.**

---

## 6. 검증된 스크립트 인자 치트시트 (이 핸드오프 작성 시 원본 대조)
- `build_clova_ground_truth.py` → `--bundle-dir --output --limit --force --summary --apply` (in-place 기본; py3.13; DB/CLOVA/Ollama 필요)
- `preflight_supplement_ocr_ground_truth_manifest.py` → `--ground-truth --output --markdown-output --required-expected-section(append, choices) --min-ready-rows`
- `build_supplement_ocr_benchmark_manifest.py` → `--candidate-manifest --ground-truth --output --source-run-id --required-expected-section(append)`
- `assign_paddleocr_benchmark_splits.py` → `--benchmark-manifest --output --seed --holdout-ratio --test-ratio`
- `gate_supplement_ocr_benchmark.py` → `--pii-preflight(=--pii-decision-preflight) --ground-truth-bundle-summary --ground-truth-preflight --benchmark-summary --benchmark-split-summary --require-ready-for-teacher-ocr-eval --output --markdown-output`
- `paddleocr_clova_eval.py` (standalone, **`$PYPADDLE`**) → `--bundle-dir --output --limit --max-side --apply`
- `gate_paddleocr_text_extraction_target.py` → `--eval-summary --output --markdown-output --target-threshold(=0.95) --min-fixtures`
- `build_paddleocr_text_extraction_eval_summary.py` → `--benchmark-manifest --output --provider --eval-split`
- `collect_supplement_ocr_observations.py` → `--manifest --output-dir` (⚠️ paddle은 py3.13에서 런타임 실패 — GAP-3)
- fine-tune 정식 체인(scripts/ 존재): `build_paddleocr_improvement_candidates` → `create_paddleocr_annotation_tasks_from_improvement_candidates` → `promote_paddleocr_annotation_tasks_to_dataset` → `materialize_paddleocr_dataset` / `export_training_manifest` → `build_paddleocr_finetune_run_plan` → `register_paddleocr_finetune_run_from_plan` → `run_paddleocr_finetune_plan` → `run_paddleocr_eval_from_finetune_plan` → `gate_paddleocr_finetune_against_baseline`

---

## 7. Definition of Done (이 핸드오프의 목표)
1. CLOVA→GT ready 수 최대 확정(또는 ready-only 스코프 결정).
2. Ollama 모델 언로드 + 메모리 확보 확인.
3. **게이트 #1 `status: ready_for_teacher_ocr_eval`** (GAP-1/2 해소 포함) — JSON 증거 리포트.
4. PaddleOCR baseline 정확도(H-1 빠른값 + 가능하면 H-2 게이트 호환값) 산출.
5. **게이트 #2: ≥95% → 중단 / <95% → fine-tune 루프** 진입, 결과 리포트.

> 별도 트랙(Chain B, 본 핸드오프 범위 밖): YOLO section bbox 205건 — 운영자가 Label Studio(:8081)에서 박스 그린 뒤 `fetch_label_studio_yolo_annotations.py`(REST pull) → `convert_label_studio_yolo_annotations.py` → reconcile/preflight/promote/materialize/validate → `gate_supplement_yolo_section_dataset.py`(게이트 #3).
