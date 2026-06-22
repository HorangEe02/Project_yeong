# Lemon-Aid 다음 세션 핸드오프 — ambient-tx Step 7 Phase 2 (BackgroundTasks) (2026-06-15)

> 직전 세션에서 ambient-tx Step 6 전부 + Step 7 Phase 1 커밋·푸시 완료. 이 문서는 **Step 7 Phase 2(learning post-commit BackgroundTasks 아키텍처)** 재개용. 권위 설계 = `outputs/todo-list/2026-06-14/2026-06-14-step7-8-design.md`(특히 §2 설계결정·§11 Phase 분할). ambient-tx 전체 권위 = `outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md`.

## 0. 현 상태 (정확)
- 브랜치 `feat/ai-agent-chat-import`, **HEAD `9fae5a6d`**, 양 리모트(origin Lemon-Aid-KDT/Lemon-sin + personal HorangEe02/Project_yeong) **0/0**.
- 직전 세션 커밋(전부 푸시): `397d5e34`(6a regulated) · `bdfe986a`(6 meal, 헝크격리) · `823b4a4b`(6b privacy+analysis, Option-A audit out-of-band) · `9fae5a6d`(Step 7 Phase 1 supplement owner-data persist_scope).
- **Step 7 Phase 1 완료**: 오케스트레이터 owner-data write 5사이트 persist_scope(behavior-preserving OWN, 라우트 미스왑). 전체 2311 passed.
- ⚠️ **워킹트리 미커밋 사용자 WIP(절대 미혼입·커밋 금지)**: meal_image_analysis.py·test_meal_image_analysis.py(food-YOLO WIP) · food_yolo.py·test_food_yolo.py · config.py · .env.example · .mcp.json · docker-compose.yml · alembic 0045 · scripts/outputs 다수. supplement 파일들은 클린(WIP 없음).

## 1. Step 7 Phase 2 목표 (핵심 = learning enqueue를 request tx 밖으로)
**문제(확정)**: `analyze_supplement_image`(supplement_image_analysis.py:207)가 두 write를 request 세션에 mid-오케스트레이션 commit →
- `maybe_store_learning_image_object`(**learning/pipeline.py:192 add + 194 commit, DO-NOT-TOUCH**), 호출처 supplement_image_analysis.py:342, `session=session`·`analysis=result_record` 전달.
- `_enqueue_supplement_section_annotation_task_if_available`(supplement_image_analysis.py:799 commit, **수정가능**), 호출처 :352, `learning_object` 의존(None이면 no-op).

participate(get_rls_context_session) 모드서 이 mid-commit이 GUC 드롭 → 후속 owner write WITH CHECK 거부. + learning store는 analysis 행이 **durable한 후**라야 FK 유효(participate에선 의존성-exit까지 미commit). → **post-commit background 필수.**

**권장 설계(Option A, design §2)**: 라우트 레벨 FastAPI BackgroundTasks.
1. `analyze_supplement_image`(서비스)에서 learning store + annotation enqueue(:341-358) **제거**. post-commit에 필요한 입력(user, analysis record id, image_bytes, image_metadata, learning_consents, ocr_result, settings, learning_object_store)을 결과/별도로 반환.
2. 신규 post-commit 함수(예 `store_supplement_learning_artifacts(...)`): **fresh session**(sessionmaker) 열어 analysis 행 재조회 → maybe_store_learning_image_object → annotation enqueue. (learning/pipeline은 자기 commit 유지=DO-NOT-TOUCH 준수, fresh session이라 request tx 무관.)
3. **라우트**(supplements.py 3곳 1170/1521/1748): 오케스트레이터 → 감사(record_sensitive_audit_event, ambient) → `background_tasks.add_task(store_supplement_learning_artifacts, ...)` → 응답. BackgroundTasks는 응답 후(=의존성-exit commit 후) 실행 → analysis durable → FK 유효. **코드베이스에 BackgroundTasks 패턴 전무 → 신규 도입(테스트 패턴 포함).**

### 계약/감사/테스트 영향 (구현 시 처리)
- `SupplementImageAnalysisResult`(supplement_image_analysis.py:183-184)의 `learning_image_object_created`/`annotation_task_created`: 오케스트레이터가 더는 learning 안 함 → 의미 변경(예 `learning_eligible`/`scheduled`) 또는 필드 제거. **모바일 응답 body엔 미노출(안전)** — `learning_image_object_created`은 supplements.py:1284 **audit event_metadata에만**, `annotation_task_created`은 내부 전용.
- 라우트 audit(supplements.py:1284 `result.learning_image_object_created`): post-commit이라 audit 시점에 미상 → 'scheduled'/'eligible'로 조정 또는 post-commit task가 자체 기록.
- 오케스트레이터 단위 테스트(test_supplement_image_analysis.py)의 learning/annotation 단언 → 라우트/통합 레벨로 이동. _FakePipelineSession은 Phase 1서 .info 보유.

## 2. Phase 3 (라우트 채택) — Phase 2 직후
- supplements.py 3 오케스트레이터 라우트(1170/1521/1748) `get_async_session`→`get_rls_context_session`. ⚠️ supplements.py 거대(3100+줄·다수 라우트) → 그 3개 dep만 정밀 스왑(다른 intake/카탈로그 라우트 주의; GET categories 2968은 이미 get_rls). 통합 fake `.info`는 Phase 1서 추가됨.
- grep 게이트: 3 라우트 transitive write가 전부 persist_scope/post-commit 경유 후에만 스왑(supplement_image_analysis.py에 잔존 session.commit = annotation:799→post-commit 이동 후 0이어야).

## 3. Phase 4~ (Stage-2 + 리뷰 + Step 8)
- **Stage-2(gated)**: `supplement_analysis_runs`(0023b Type A, owner_subject) + `supplement_image_evidence`(Type C child via analysis_run_id) owner 격리+영속, lemon_app FORCE RLS. **핵심 증명**: 6 owner-data write가 단일 request-tx 머무름(GUC 생존, mid-commit 0) + learning store가 post-commit fresh session 별도 실행(request tx 독립).
- **별도 리뷰**(적대 다중-렌즈) → 직접 재검증. learning/pipeline.py 미접촉·BackgroundTasks 실행시점·FK 안전 확인.
- **Step 8(flip, ops 의존)**: startup 가드(DATABASE_URL=lemon_app면 audit_database_url 필수+상이) + 풀 사이징 + RLS-정책0 테이블(users/audit_logs/model_*) owner 라우트 점검. 실제 DATABASE_URL flip은 ops(config/.env=사용자 WIP, 커밋 금지). design §7.

## 4. 불변 규칙 (전 세션 동일, 반드시 준수)
- **커밋·푸시는 사용자 요청 시에만**, 양 리모트, **파일/헝크 명시 스테이징**(사용자 food-YOLO WIP·config·.env·docker-compose·.mcp.json·alembic 0045 절대 미혼입). 커밋 트레일러 = `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. 브랜치 직접 커밋 OK(요청 시).
- **TDD + 별도 리뷰 레인**(같은 컨텍스트 self-approve 금지; code-reviewer/critic 별도). **완료 주장 전 테스트 통과 + 증거.**
- **persist_scope 타는 서비스 테스트 fake엔 `.info: dict` 필수**(OWN-mode가 session.info[_OWN_DEPTH] 사용) + flush/commit/rollback. 라우트 채택 시 통합 테스트 override는 `get_rls_context_session`.
- **PR#4 불가침**: alembic 전체 · app_health_analysis.py:269-271 · analysis_results.py store_daily_health_score_result · ai_agent.py LLM 가드 · **learning/pipeline.py(maybe_store_learning_image_object 포함)·upsert_worker.py·pgvector_store.py·media/retention.py** · session.py 엔진. privacy.py `record_audit_event`/`_write_audit_out_of_band`/`_build_audit_log` 불가침.
- 수치 추정 금지 · 사적이미지/secret 커밋 금지 · A100 승인 후 · 의료 금칙어 · 모바일 design_tokens_v2/해요체.
- ⚠️ **위임 에이전트(워크플로/아키텍트/리뷰어)는 출력 숨김·환각·스코프 위반 잦음 → 항상 실코드/테스트로 직접 검증**(전사본 추출 포함).
- ⚠️ **컨테이너 검증**: 실행 백엔드는 `/opt/venv/bin/python`(`docker exec ... sh -l`은 PATH를 /usr/local로 리셋해 paddle 없음). heredoc 스모크는 `docker exec -i` 필수. paddleocr 이미 설치+동작.

## 5. 테스트·게이트
- 전체: `cd backend && PYTHONPATH=Nutrition-backend .venv/bin/python -m pytest Nutrition-backend/tests/unit Nutrition-backend/tests/integration -q --no-cov`. **공유 서비스/seam 변경 시 integration도 함께.** 무관 실패 상수: alembic 0045×2(사용자 food WIP) + .mcp.json. OCR 단위 2건은 로컬 `.env` 누수 → `OCR_SECONDARY_MERGE_POLICY=disabled` prepend.
- **Stage-2 gated**: lemon_app throwaway 비번 절차 —
  ```bash
  cd backend
  ADMIN_URL="$(PYTHONPATH=Nutrition-backend .venv/bin/python -c 'from src.config import get_settings; print(get_settings().database_url)')"
  # ALTER ROLE lemon_app PASSWORD 'lemon_app_local_rls_verify' (admin 엔진으로)
  export TEST_DATABASE_URL="$ADMIN_URL"
  export TEST_RLS_APP_DATABASE_URL="$(printf '%s' "$ADMIN_URL" | sed -E 's#://[^@]+@#://lemon_app:lemon_app_local_rls_verify@#')"  # pragma: allowlist secret
  # pytest 실행 후 ALTER ROLE lemon_app PASSWORD NULL 정리
  ```
  `get_settings().database_url` = supabase_db(DB=postgres, superuser). 0023b/0023c RLS+FORCE 적용됨. lemon_app NOSUPERUSER/NOBYPASSRLS. ⚠️ out-of-band audit 쓰는 Stage-2는 `_stage2_engines` finally에 `dispose_engine()` 추가(모듈-레벨 엔진 event-loop 충돌 방지) — 6b의 `test_privacy_consent_stage2.py` 참고.
- 헝크격리(food WIP 동거 파일 커밋 시): 편집 前 working-tree 스냅샷 → `git diff --no-index <snapshot> <repo-rel-path>` + sed로 헤더 a/b=repo-루트-상대(`backend/Nutrition-backend/...`)·`/^index /d` → **repo 루트에서** `git apply --cached`(cwd=Nutrition-backend면 인덱스 경로 불일치로 조용히 no-op) → 깨끗한 파일만 `git add`. (Phase 2/3은 supplement 클린 파일이라 불필요.)

## 6. 자동 메모리
`ai-agent-chatbot-import-state.md`에 Step 6 전부+Step 7 Phase 1 커밋·OPEN 해소 기록됨. local-db-topology·ios-udid 참고.

---

## 다음 세션 시작 프롬프트 (복붙용)
> Lemon-Aid 이어서. ambient-tx **Step 7 Phase 2** 진행. 권위: `outputs/todo-list/2026-06-15/2026-06-15-step7-phase2-handoff.md` + `2026-06-14-step7-8-design.md`(§2 설계·§11 Phase) + `2026-06-14-ambient-transaction-refactor-plan.md`. 브랜치 feat/ai-agent-chat-import(HEAD 9fae5a6d), 양 리모트 0/0. **Phase 2 = learning(maybe_store_learning_image_object, learning/pipeline.py=DO-NOT-TOUCH)+annotation enqueue(supplement_image_analysis:799)를 라우트 레벨 FastAPI BackgroundTasks+fresh session으로 post-commit 이동**(코드베이스 BackgroundTasks 전무→신규). SupplementImageAnalysisResult 계약·라우트 audit(1284)·오케스트레이터 테스트 재구조화. 모바일 응답 body엔 learning 미노출(안전). 이어 Phase 3(supplements.py 3라우트 1170/1521/1748 get_rls)→Stage-2(supplement_analysis_runs Type A+evidence Type C)→리뷰. 규칙: 커밋·푸시는 요청 시·양 리모트·헝크 명시(사용자 food/config WIP 미혼입)·TDD+별도리뷰·persist_scope fake에 .info·PR#4(learning/pipeline.py 포함) 불가침·위임 출력숨김→직접검증·컨테이너 /opt/venv+docker exec -i. TDD+Stage-2+별도리뷰 후 승인 시에만 커밋. 막히면 보고.
