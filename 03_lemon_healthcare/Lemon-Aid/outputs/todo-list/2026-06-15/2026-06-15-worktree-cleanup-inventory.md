# 워크트리 정리 인벤토리 & 클린업 플랜

- 작성일: 2026-06-15
- 브랜치: `feat/ai-agent-chat-import`
- HEAD: `81574be9` (RLS Step 8 Phase C2 — **이 세션 중 커밋됨**; 직전 `11230a26` Phase C1)
- 범위(감사 시점): 수정 88 + untracked 51 → (현재) 수정 84(+`.gitignore`) + untracked 49
- 방법: 10개 에이전트 병렬 감사(9개 파일 그룹 + 엔탱글먼트/커밋플랜 합성), 모든 파일을 실제 diff로 분류
- ⚠️ 이 문서는 **분석·계획**이다. 아래 git 명령은 **참고용**이며, 커밋/stash/rm 같은 되돌리기 어려운 작업은 **사용자 승인 후** 실행한다.

> ### 📌 이 세션 중 실제 변경 (2026-06-15)
> - ✅ **rls-step8 (스트림 A) = 완료**: 사용자가 감사 진행 중 Phase C2를 커밋함 → `81574be9` (5파일: `ai_agent.py`, `db/dependencies.py`, `test_ai_agent_api.py`, `test_rls_context_dependency.py`, `test_chatbot_analysis_rls_stage2.py`, +675/−145). 완전·누락 없음.
> - ✅ **multi-image-supplement (스트림 B) = 커밋 완료**:
>   - 백엔드 `e6f2ceed` (supplements 병합 게이팅 + ollama 한글(English) 계약 + supplement_parser 줄분리 함량 추출; 단위테스트 38 + 통합 14 green). ⚠️ 발견: ollama 계약 문구가 길어져 `test_ollama_parser_bounds_long_ocr_text_in_prompt`가 working-tree에서 red였음(감사·메모리는 "foreign"으로 오판) → 프롬프트 템플릿 오버헤드 허용 bound를 +1_000→+1_200로 정정(OCR 압축 보장은 불변).
>   - 모바일 `ee359669` (묶음 토글·1결과 병합·한글(English) 표기; flutter 66 green, stash-test로 커밋 스냅샷 검증). 엔탱글된 `app_controller.dart`(+`_test`)의 OCR-provider 기본값 hunk는 **헝크 격리로 제외**(food-yolo-ocr 소속, 미스테이지로 보존).
> - ✅ **노이즈 안전 정리 적용**: `.gitignore`에 `outputs/generated/supplement-learning/**/a100-paddleocr-best-snapshots/` + `**/*.zip`(184MB 모델 zip)과 `mobile/uiux/figma/`(~35MB) 추가. `git check-ignore`로 무시 확인. (`.DS_Store`는 256·391행에 이미 존재 → 추가 안 함.)
> - ⏸️ **food-yolo-ocr WIP = 손대지 않음**(사용자 결정). stage/커밋/스크립트 변경 없음. app_controller(_test)의 food hunk도 미스테이지로 보존됨.

---

## 0. TL;DR

- 워크트리에 **서로 독립적인 작업 스트림 5종**이 한 브랜치에 섞여 있다:
  1. **rls-step8 (Phase C2)** — RLS write-path 마이그레이션 마지막 조각. 깨끗·완결, 커밋 가능.
  2. **multi-image-supplement** — 영양제 여러 장 → 1결과 병합(+ 한글(English) 표기). 깨끗, 커밋 가능.
  3. **food-yolo-ocr** — 사용자의 **활성 foreign WIP**(YOLO 음식 분류기/CLIP/PaddleOCR 파인튜닝/섹션검출기). 미완·테스트 red 가능성.
  4. **config-infra** — `.mcp.json` 등 잡다한 설정.
  5. **docs & 노이즈** — 설계·핸드오프 문서, 대용량 바이너리, 생성물.
- **혼재(entangled) 소스 파일은 단 3개**: `config.py`, `mobile/lib/app_controller.dart`, `mobile/test/unit/app_controller_test.dart`. 나머지는 파일 단위로 깔끔히 스트림이 갈린다.
- **즉시 처리 권장(코드 아님)**: 184MB 모델 zip 커밋 금지, `mobile/uiux/figma/`(~35MB 바이너리) gitignore/LFS 결정, `.DS_Store` 제거, `operator-review/` 트리(이미 `.gitignore` 매칭인데 tracked)·특히 `review_pii_screening*.jsonl` 추적 해제 검토.
- **권장 커밋 순서**: rls-step8 → multi-image-supplement → food-yolo-ocr → config-infra → docs.
- **절대 금지**: `git add -A` / `git commit -a` / 전체 파일 `black`·`dart format`. (foreign WIP 혼입 + 포맷 노이즈 재혼입 위험)

---

## 1. 현황 스냅샷

```
브랜치: feat/ai-agent-chat-import
HEAD  : 11230a26  refactor(api): RLS Step 8 Phase C1 ...
변경  : 88 modified (tracked) + 51 untracked 엔트리
규모  : 코드(outputs 제외) 36파일 +2734 / -645,  전체 +4897 / -1801
staged: 없음 (전부 unstaged)
```

> ⚠️ 세션 시작 시 `git status`가 2k자 초과로 **truncated**였다. 감사에 표면화되지 않은 파일도 숨은 hunk를 가질 수 있으므로, 어떤 파일이든 stage 전 `git diff <file>`로 재확인할 것.

---

## 2. 작업 스트림 5종 (개요)

| 스트림 | 성격 | 대표 파일 | 상태 | 커밋 권장 |
|---|---|---|---|---|
| **A. rls-step8 (C2)** | RLS write-path 마이그레이션 (run_chatbot) | `db/dependencies.py`, `api/v1/ai_agent.py` + 테스트 3 | ✅ **커밋 완료 `81574be9`** | — (처리됨) |
| **B. multi-image-supplement** | 여러 장→1결과 병합, 한글(English) 표기 | `supplements.py`, `ollama.py`, `supplement_parser.py`, mobile 8 | ✅ **커밋 완료** `e6f2ceed`(BE) + `ee359669`(모바일) | — (처리됨) |
| **C. food-yolo-ocr** | 음식 YOLO+CLIP 분류기, PaddleOCR 파인튜닝, 섹션검출기 | `food_yolo.py`(+624), `meal_image_analysis.py`, scripts 36, config 일부 | **사용자 foreign WIP**, 테스트 red 가능 | ⚠️ 3순위·사용자 소유 |
| **D. config-infra** | 설정/툴링 | `.mcp.json`, config.py 블랙노이즈 hunk | 결정 필요 | 4순위 |
| **E. docs & 노이즈** | 설계/핸드오프 문서, 바이너리, 생성물 | docs/**, outputs/**, figma/ | 일부 gitignore/discard | 5순위 |

---

## 3. 스트림별 상세

### A. rls-step8 — RLS Step 8 Phase C2 (✅ 커밋 가능, 혼재 0)

`run_chatbot`을, 콜리(`store_app_health_analysis_result`)의 중간 commit+refresh를 견디는 라우트-소유 RLS 트랜잭션으로 이전. 5개 파일 모두 **단일 스트림, foreign-WIP 흔적 0**.

| 파일 | 변경 | 내용 |
|---|---|---|
| `backend/Nutrition-backend/src/db/dependencies.py` | M (+80/-2) | 신규 CM `rls_request_transaction_allow_inner_commit` + `after_begin` 리스너(매 tx begin마다 is_local owner GUC 재적용). append-only. |
| `backend/Nutrition-backend/src/api/v1/ai_agent.py` | M (+148/-145) | `run_chatbot` 본문을 위 CM으로 감쌈. **대부분 재들여쓰기**, 로직 무변. `run_daily_coaching`은 미변경(B1에서 이미 HEAD). |
| `tests/unit/db/test_rls_context_dependency.py` | M (+159/-1) | 신규 단위 4건(마커/리스너/롤백/이너커밋 skip). |
| `tests/integration/api/test_ai_agent_api.py` | M (+31/-1) | 라우트 테스트 fake 세션을 실제 sqlalchemy Session 기반으로 교체(리스너 타깃). |
| `tests/integration/db/test_chatbot_analysis_rls_stage2.py` | **untracked** (+204) | lemon_app 역할 Stage-2 통합 테스트(런게이트: `TEST_DATABASE_URL`+`TEST_RLS_APP_DATABASE_URL` 없으면 skip). |

→ **권장**: 5개를 한 커밋으로. (`git add` 안전. 단, staged diff 확인.)

### B. multi-image-supplement (✅ 커밋 가능)

**백엔드**

| 파일 | 변경 | 내용 |
|---|---|---|
| `src/api/v1/supplements.py` | M (+24/-2) | `_has_preview_review_content` 신설 + `_build_merged_multi_image_preview`가 내용 있는 preview만 필터, 없으면 None. **RLS 마커 0**(이미 HEAD). |
| `tests/integration/api/test_supplement_intake_api.py` | M (+3/-11) | 멀티이미지 3테스트의 `merged_preview is None` 단언 갱신(위 게이팅 대응). |
| `src/llm/ollama.py` | M (+5/-4) | 파서 프롬프트: 영문 라벨→`display_name`=한글/`original_name`=영문 "한글 (English)" 계약. 프롬프트 문구만. |
| `src/services/supplement_parser.py` | M (+130/-21) | 성분 추출 강화: `㎎` 단위·IGNORECASE, 줄분리(이름/함량) 페어링 2차 패스, `_clean_split_line_ingredient_name`, 단위 정규화. |
| `tests/unit/services/test_supplement_parser.py` | M (+51) | 줄분리 페어링·`㎎→mg`·`Serving Size` 제외 신규 테스트. |

**모바일** (대부분 단일 스트림 + dart-format reflow 노이즈)

| 파일 | 변경 | 내용 |
|---|---|---|
| `lib/app.dart` | M (+6/-4) | 라우터 콜백에 `sameSupplementBatch` 전달. |
| `lib/features/supplements/supplement_models.dart` | M (+39/-18) | `hasReviewContent`/`reviewContentScore`로 풍부도 랭킹. |
| `lib/screens/analysis_result_screen.dart` | M (+95/-42) | `lastSupplementBatchIsSingleProduct` 분기, `_bilingualIngredientName`("한글 (English)"). |
| `lib/screens/camera_screen.dart` | M (+124/-19) | "한 영양제 묶음 / 서로 다른 영양제" 토글 위젯. |
| `test/widget/analysis_result_screen_test.dart` | M (+21/-24) | 한글(English) 표기·`원문:` 숨김·per-product 분기 단언. |
| `test/widget/source_camera_screen_test.dart` | M (+39/-26) | 콜백 시그니처 확장(`sameSupplementBatch`). |
| `lib/app_controller.dart` ⚠️ | M (+24/-12) | **혼재** — §4 참조(멀티이미지 部分만 이 스트림). |
| `test/unit/app_controller_test.dart` ⚠️ | M (+174/-158) | **혼재** — §4 참조. |

**문서**: `docs/ocr_baseline_reports/2026-06-15-multi-image-single-supplement-merge-design-and-guideline.md` (untracked, 이번 세션 작성) = 이 스트림의 설계 앵커.

### C. food-yolo-ocr — 사용자 활성 foreign WIP (⚠️ 분리 필수)

> RLS/supplement 커밋에 **절대 혼입 금지**. 미완이며 워킹트리에서 테스트가 red일 수 있음(메모리·G3의 `test_ollama_parser` 플래그).

**소스/마이그레이션**

| 파일 | 변경 | 내용 |
|---|---|---|
| `src/vision/food_yolo.py` | M (+624/-8) | CLIP 음식/비음식 필터 + exp16b 크롭 분류기(class_en 재라벨) + predict **kwargs. |
| `src/services/meal_image_analysis.py` | M (+50/-9) | 분류기/CLIP를 meal preview 경로에 배선. **신규 config 필드 의존**(→ config.py 동반 필요). |
| `tests/unit/vision/test_food_yolo.py` | M (+113/-7) | 분류기 경로 테스트. |
| `tests/unit/services/test_meal_image_analysis.py` | M (+61) | 분류기 메타 저장 테스트. |
| `tests/unit/ocr/test_paddle_provider.py` | M (+8/-8) | box_thresh 미설정 시 미전달(2026-06-13 sweep). |
| `alembic/versions/0045_upsert_food_nutrition_40class_v2.py` | **untracked** | 40-class food_nutrition 업서트(0044 뒤). down_revision 체인 확인 필요. |
| `tests/unit/alembic/` (+`test_food_nutrition_40class_migration.py`) | **untracked** | 0045 검증 테스트. **`__pycache__/`는 제외**. |

**스크립트 (G7, 전부 foreign-wip)** — 36개: 수정 5(`paddleocr_clova_eval.py`, `run_a100_*`, `start_a100_*`, `validate_supplement_section_yolo_dataset.py`, `inject_v2_split_into_promote_template.py`) + untracked 29(스크립트) + untracked 2(테스트).
- **keep-worthy(재사용 툴링)**: `gate_supplement_section_detector_metrics.py`(+test), `merge_supplement_section_panel_boxes.py`(+test), `train_ultralytics_section_detector.py`, `evaluate_detector_roi_full_fallback_structured_extraction.py`, `build_roi_first_detector_bundle.py`, `build_other_ingredients_candidate_manifest.py`, `build_paddleocr_synthetic_general_corpus.py`, `scan_/merge_other_ingredients_*`.
- **throwaway 후보(머신/런 종속, 하드코딩 G:\\ 경로)**: `a100_section_detector_300_noearly*`(.ps1/.cmd ×5), `a100_*_register_task/launch_cmdstart/queue_keeper/status`, `start_a100_paddleocr_*bridge/followup/sequential_keeper`, `a100_compact_status_check_fixed.ps1`, `a100_watch_early_stop_stdout_v2.ps1`.

**config/infra 일부(이 스트림 소유)**: `.env.example`(OCR provider clova 플립 + food/CLIP/classifier 키), `docker-compose.yml`(b32 recognizer 마운트 + OCR ensemble env), `backend/pyproject.toml`(`transformers>=4,<5` vision extra), `config.py`의 **food hunk 4개**(→ §4).

### D. config-infra (4순위, 대부분 결정)

| 파일 | 변경 | 처리 |
|---|---|---|
| `.mcp.json` | M (+1/-1) | Supabase MCP URL에 기본값 하드코딩(`project_ref=weipsloxntjzcqjvzjax`, read_only=true). **needs-decision**: 팀 공용 기본값으로 둘지 vs 개인 설정이라 `${VAR}`로 되돌릴지/gitignore. (project_ref는 식별자, 토큰 아님) |
| `config.py` @@ -40 블랙노이즈 hunk | M | `DEFAULT_PRIVACY_HASH_SECRET` 줄바꿈 reflow. 별도 소소한 포맷 커밋 or `git checkout -p`로 폐기. |
| `docker-compose.yml` | M | 실제론 food-yolo-ocr 단일 스트림 → **food 그룹과 함께** 커밋(중복 커밋 X). |

### E. docs & 노이즈 (5순위, §5도 참조)

- **rls-step8 문서 묶음**: `outputs/todo-list/2026-06-14/2026-06-14-step6-design.md`, `…step7-8-design.md`, `…handoff-2/3/4.md`, `outputs/todo-list/2026-06-15/2026-06-15-step7-phase2-handoff.md`, `…step8-rls-policy0-read-audit.md`.
- **multi-image-supplement 문서**: `…2026-06-15-multi-image-single-supplement-merge-design-and-guideline.md`.
- **food-yolo-ocr 문서 묶음**: `docs/ocr_baseline_reports/` 수정 2 + untracked 4(2026-06-09 plan/eval-v2, 2026-06-12 roadmap, 2026-06-15 b32 runbook), `docs/deliverables/nutrition-40class/`(236K), `docs/handoff/food-detector/`(40K), `outputs/todo-list/2026-06-06|10/**`, `…2026-06-12-next-session-handoff-prompt-v2.md`, `…2026-06-14-yolo-section-bbox-review-runbook.md`.

---

## 4. ⚠️ 혼재(Entangled) 파일 3종 — hunk 격리 필수

> 한 파일 안에 두 스트림 hunk가 섞여 있다. `git add -p` / `git apply --cached`로 hunk 단위 분리. **포맷터는 분리 전 1회만** 돌리고, 두 커밋 사이에는 돌리지 말 것(reflow가 경계를 넘으면 재혼재됨).

| 파일 | 스트림 | hunk 지도 / 격리 방법 |
|---|---|---|
| `backend/Nutrition-backend/src/config.py` | food-yolo-ocr + 블랙노이즈 (RLS 아님) | **food 4 hunk**: `@@ -771`(box_thresh 0.4→None), `@@ -858`(11개 food 필드), `@@ -970`+`@@ -1220`(`_validate_food_detector_settings`). **노이즈 1 hunk**: `@@ -40`. → food hunk만 food 커밋, `@@ -40`은 분리/폐기. RLS pool(db_pool_size/max_overflow)·supplement 설정은 **이미 HEAD**(working delta에 없음). **food hunk는 meal_image_analysis/food_yolo/test_paddle_provider보다 먼저(같은 커밋) 들어가야 import 성공.** |
| `mobile/lib/app_controller.dart` | multi-image + food-yolo-ocr | **food는 단 1 hunk** `@@ -244`(`_defaultOcrProvider` 'configured'→'clova', `_diagnosticOcrProviders`→`['clova']` "PaddleOCR 재학습 중"). **나머지 전부 multi-image**(신규 필드/게터, `sameSupplementBatch` 배선, `'$display ($orig)'`). L244 vs L367+로 멀리 떨어져 `git add -p` 분리 깔끔. |
| `mobile/test/unit/app_controller_test.dart` | multi-image + food-yolo-ocr | 위의 거울. **food hunk**(상단 ~L123-330: ocrProviders 'configured'→'clova', CLOVA-only 테스트 리네임, fake 플립) + dart-format reflow. **multi-image hunk**: 비타민 D (Vitamin D) 단언. 소스와 **같은 스트림은 같은 커밋**(한쪽만 'clova'로 바꾸면 CI red). |

---

## 5. 🚨 즉시 처리 권장 (코드 아님 — 노이즈/대용량/PII)

1. **184MB 모델 zip — 커밋 금지.**
   `outputs/generated/supplement-learning/2026-06-10/a100-paddleocr-best-snapshots/.../best_accuracy.*.epoch40.zip`
   → `.gitignore`에 `outputs/generated/**/*.zip`(또는 스냅샷 디렉토리) 추가, LFS/외부 저장. **이 그룹 최우선.**
2. **`operator-review/` 트리: gitignore 매칭인데 tracked(~50파일).**
   `.gitignore`에 `outputs/generated/supplement-learning/**/operator-review/`(154행), `**/operator-review/**/*.jsonl`(146행)이 **이미 존재**한다. 그런데 ~50개가 추적 중 = ignore 규칙 추가 이전에 커밋됨. 특히 **`batches/review_pii_screening*.jsonl`(PII 스크리닝 데이터)** 는 추적 해제 권장:
   ```
   # 디스크엔 남기고 추적만 해제 (실행 전 팀 의도 확인)
   git rm -r --cached "outputs/generated/supplement-learning/2026-06-05/operator-review"
   ```
   → 결정 필요: 리포트 .md/.json은 의도적으로 추적할 수도 있으므로 **사용자 확인 후** 실행.
3. **`mobile/uiux/figma/` (~35MB 바이너리 .fig+PNG) — gitignore/LFS 결정.**
   코드 리포에 바이너리 35MB는 부담. `.gitignore` 또는 git-LFS. 블라인드 커밋 금지.
4. **`.DS_Store` 제거.** `mobile/uiux/figma/**`에 산재. `.gitignore`에 `.DS_Store` 추가 후 폐기.
5. **`__pycache__/`** (`tests/unit/alembic/__pycache__`) 제외 — 소스 `.py`만.

---

## 6. 권장 커밋 순서

> 각 단계 **커밋 전 `git diff --cached` 필수**. foreign WIP 혼입 방지.

1. ~~**rls-step8 (C2)**~~ — ✅ **완료** (`81574be9`, 이 세션 중 커밋). 5파일 전부 포함.
2. ~~**multi-image-supplement**~~ — ✅ **완료** (`e6f2ceed` BE + `ee359669` 모바일). app_controller(_test)의 멀티이미지 hunk만 커밋, OCR-provider hunk는 헝크 격리로 food 쪽에 남김.
3. **food-yolo-ocr** — 3순위, **사용자 소유**. 내부 순서: config.py food hunk(설정) → meal_image_analysis/food_yolo/test_paddle/alembic 0045 → app_controller OCR hunk+거울 → 스크립트 → .env.example/docker-compose/pyproject → OCR 문서. **테스트 red면 green-wash 커밋 금지** — 미스테이지로 남기거나 import-safe 서브셋만(사용자 확인 후).
4. **config-infra** — 4순위. config.py `@@ -40` 노이즈 분리, `.mcp.json` 결정(되돌리기/gitignore 유력).
5. **docs** — 5순위. 스트림별 문서 묶음을 해당 코드 커밋 뒤에. figma/outputs 바이너리·생성물은 **gitignore/discard**(커밋 X).

> **브랜치 위생**: 현재 `feat/ai-agent-chat-import` 한 곳에 5스트림이 섞여 있다. 특히 사용자 foreign food-yolo-ocr WIP는 **별도 브랜치/PR** 분리를 고려.

---

## 7. 리스크 체크리스트

- [ ] **foreign WIP 우발 커밋**: `git add -A`/`commit -a` 금지. 스트림별 명시 stage + `git diff --cached`.
- [ ] **숨은 WIP**: 세션시작 status truncated → "clean" 라벨도 stage 전 `git diff <file>` 재확인(특히 ollama.py/supplement_parser.py).
- [ ] **포맷터 부수효과**: 전체 `black`/`dart format` 금지(기존 포맷부채 재작성 → 노이즈·재혼재). staged hunk만, 분리 전 1회만.
- [ ] **혼재 파일 반쪽 커밋**: config.py food hunk는 food 소스와 동반. app_controller OCR hunk는 거울 테스트와 동반(한쪽만 'clova'→CI red).
- [ ] **RLS write-path 회귀**: C2는 audit_logs INSERT/분석 영속을 FORCE RLS 하에서 관장. 성공 audit 블록·GUC 생존 commit 누락 시 flip 후 silent fail-closed. `test_chatbot_analysis_rls_stage2`/`test_rls_context_dependency` 통과 확인.
- [ ] **외장볼륨 Docker 주의**: 리포가 `/Volumes/Corsair EX400U Media`(공백) VirtioFS 마운트. 백엔드 컨테이너 recreate 시 스턱→Docker Desktop 재시작만 해결. 검증은 **기존 컨테이너 `docker exec -i`(/opt/venv)** 로, `up --build` 금지.
- [ ] **대용량/생성 바이너리**: 184MB zip, figma 35MB, .DS_Store, 생성물 ~50 — stage 전 gitignore/discard 결정. `git add docs/`·`git add outputs/` 일괄 금지.
- [ ] **테스트 미검증**: 감사는 정적 분석(호스트 py3.13에 pytest/paddle 없음, 스위트는 docker). "committable-clean"은 정적 판정 → 커밋 전 docker에서 실제 실행 권장.

---

## 8. 참고 명령 (실행은 승인 후)

```bash
REPO="/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid"

# (1) rls-step8 C2 — 스트림 1
git -C "$REPO" add \
  backend/Nutrition-backend/src/db/dependencies.py \
  backend/Nutrition-backend/src/api/v1/ai_agent.py \
  backend/Nutrition-backend/tests/unit/db/test_rls_context_dependency.py \
  backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py \
  backend/Nutrition-backend/tests/integration/db/test_chatbot_analysis_rls_stage2.py
git -C "$REPO" diff --cached   # ← 반드시 검토 후 commit

# (2) multi-image-supplement — 백엔드(혼재 없음)
git -C "$REPO" add \
  backend/Nutrition-backend/src/api/v1/supplements.py \
  backend/Nutrition-backend/src/llm/ollama.py \
  backend/Nutrition-backend/src/services/supplement_parser.py \
  backend/Nutrition-backend/tests/integration/api/test_supplement_intake_api.py \
  backend/Nutrition-backend/tests/unit/services/test_supplement_parser.py
# 모바일 혼재 파일은 hunk 분리:
git -C "$REPO" add -p mobile/lib/app_controller.dart        # @@ -244 (OCR) 거절, 나머지 수락
git -C "$REPO" add -p mobile/test/unit/app_controller_test.dart
git -C "$REPO" add mobile/lib/app.dart mobile/lib/features/supplements/supplement_models.dart \
  mobile/lib/screens/analysis_result_screen.dart mobile/lib/screens/camera_screen.dart \
  mobile/test/widget/analysis_result_screen_test.dart mobile/test/widget/source_camera_screen_test.dart

# (3) 노이즈 gitignore (예시)
#   .gitignore 에 추가: .DS_Store / outputs/generated/**/*.zip / mobile/uiux/figma/
# (4) operator-review 추적 해제 (의도 확인 후)
#   git -C "$REPO" rm -r --cached "outputs/generated/supplement-learning/2026-06-05/operator-review"

# 테스트(기존 컨테이너):  docker exec -i <backend> bash -lc 'cd /app && /opt/venv/bin/pytest ...'
```

---

## 9. 사용자 결정 필요 항목

1. **foreign food-yolo-ocr WIP**를 (a) 이 브랜치에 같이 커밋 / (b) 별도 브랜치로 분리 / (c) 손대지 않고 그대로 둘지.
2. **`.mcp.json`**: 팀 기본값 유지 vs `${VAR}` 되돌리기/gitignore.
3. **`operator-review/` 트리 + PII jsonl**: 추적 해제(`git rm --cached`) 여부.
4. **figma 35MB**: gitignore vs git-LFS vs 커밋.
5. **184MB zip**: gitignore 확정(권장) — 이견 없으면 즉시 처리 가능.
