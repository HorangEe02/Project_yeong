# Lemon-Aid 다음 세션 핸드오프 — RLS Step 3 완료 + OCR 앙상블 재설계/활성화 (2026-06-14 #3)

> 새 세션 시작 시 이 파일을 그대로 붙여넣어 이어서 작업한다. 직전 핸드오프(`2026-06-14-next-session-handoff-2.md`)의 후속. 그 이후 진행분(ambient-tx Step 3 + OCR 3종 작업) + 남은 로드맵을 담는다.

---

## 0. 한 줄 요약

직전 핸드오프 이후: **ambient-tx Step 3(food_records) 완료**(커밋 a6b97d40) + **OCR 3종**(① 모바일 인식텍스트 폴백 7889fb8e · ② stale-mount 인프라 복구 · ③ Clova→Paddle→Gemma4 앙상블 OCR 재설계+라이브 활성화 db91f62d). **HEAD=`db91f62d`, 양 리모트 0 ahead.** 남은 큰 줄기 = **ambient-tx Step 4~8** + 기존 자료/인프라 게이트(섹션검출기·모바일Auth3·Supabase Auth 라이브·HC/push).

## 1. 환경

- **리포(외장 SSD)**: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`. 작업물·커밋 모두 이 경로.
- **브랜치**: `feat/ai-agent-chat-import`. **양 리모트 푸시**: `origin`(Lemon-Aid-KDT/Lemon-sin) + `personal`(HorangEe02/Project_yeong). main 아님. **현재 HEAD `db91f62d`, 양 리모트 0/0.**
- **백엔드**: `backend/.venv/bin/python`(3.13). 테스트 `cd backend && .venv/bin/python -m pytest Nutrition-backend/tests/unit Nutrition-backend/tests/integration -q`. **⚠️ 공유 서비스/db seam 변경 시 integration도 반드시 함께 실행.** alembic head = **0044**(supabase_db).
  - **CI 게이트는 `black --line-length=100 --check backend` + `ruff check backend`만**(mypy 미실행, 게이트 아님). black/mypy는 venv 미설치(이번 세션에 black만 pip install). **ruff isort는 src를 third-party 취급(known-first-party 미설정) → src import 앞 blank 줄 금지.** 리포 ruff/black 부채 다수 존재(비강제).
- **DB 토폴로지(필수)**: alembic CLI/.env(get_settings)=**supabase_db**(`...@127.0.0.1:56322/postgres`). 실행 백엔드 컨테이너=**lemon-aid-db-1**(`db:5432/lemon`, 호스트 미공개, docker exec만). 둘은 리비전 갈릴 수 있음 → 대상 DB 항상 확인. **사용자 food WIP 마이그레이션 `backend/alembic/versions/0045_upsert_food_nutrition_40class_v2.py`가 untracked(??)로 존재 → alembic head를 0045로 만들어 `test_alembic_setup` 2건 실패(사용자 WIP, OCR 무관).** [[local-db-topology]]
- **모바일**: Flutter. `cd mobile && flutter analyze` + `flutter test`(현재 402 통과).
- **실행 스택**: lemon-aid-backend-1(:8000, **이번 세션에 앙상블 코드로 리빌드+활성화 env 적용됨**), supabase 14컨테이너, lemon-aid-db-1, redis, **Ollama :11434**(host; 비전 `gemma4:e4b`, 텍스트 `qwen3.5:9b`, 그 외 다수).
- **lemon_app 로컬 비번**: throwaway `lemon_app_local_rls_verify`(Stage-2 gated 테스트용). 정리 `ALTER ROLE lemon_app PASSWORD NULL`.
- **A100**: `ssh -i ~/.ssh/lemon_a100_ed25519 -p 8875 lemon-aid@155.230.153.222`(승인 후).
- iOS sim UDID → [[ios-simulator-udid-fix]]. iOS는 `flutter build ios --simulator --debug`(기본 baseUrl 127.0.0.1:8000/api/v1, ATS `NSAllowsLocalNetworking=true`).

## 2. 적용 중인 규칙 (반드시 준수)

- **사용자 요청 없이 commit/push 금지.** 커밋: Conventional Commits + 본문 "왜" + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`(리포 관례). 양 리모트 푸시. **파일/헝크 명시 스테이징(사용자 WIP 절대 미혼입).**
- **TDD + 별도 리뷰 레인**: 작성/리뷰 분리, 같은 컨텍스트 self-approve 금지. 완료 주장 전 테스트 통과 + 증거.
- 수치·결과 추정 금지(확인값만). private image/raw OCR/secret/owner hash 커밋 금지. 원격(A100)·사적데이터 전송은 승인 후. 원본 dataset 불가침.
- **PR#4 보호(불가침)**: alembic 전체(0023a/b/c·0041), `ai_agent.py` LLM 가드, `app_health_analysis.py:269-271`·`analysis_results.py:192-193` add+commit 패턴, `learning/pipeline.py`·workers, `session.py` 엔진 설정. 필요 시 신규 0045+만(주의: 0045는 사용자 food WIP가 선점).
- framework 파라미터 변경 시 공식문서 확인 + URL 주석. 슬롭 경고 시 아키텍트 자문 후 구체 설계.
- 의료법: 금칙어(진단/처방/치료/효능) 금지 + 신뢰도 % 미노출 + 권고화면 `MedicalDisclaimer` 필수. 모바일: `design_tokens_v2`만, **해요체**, 시니어 최소치(본문 15px+/터치 48px+). 백엔드 공백 필드 날조 금지.
- **무관 기존 실패**(내 변경 무관): `test_supabase_local_config`(.mcp.json). + 사용자 food WIP로 `test_alembic_setup` 2건(0045).

### ⚠️ 이번 세션 교훈 (반드시 인지)
- **위임 에이전트 신뢰 금지**: 최종 메시지를 자주 숨김(전사본 JSONL에서 추출: `tasks/<agentId>.output` 또는 tool-results 파싱), **환각**(모바일 리뷰어가 없는 `_ocrHint` 평가), **스코프 위반**(executor가 사용자 food WIP 테스트 추가 + read-only 지시 위반). → **항상 실코드/테스트로 직접 검증**하고 스코프 크리프 정리할 것.
- **config.py는 사용자 food WIP와 심하게 섞임** → 격리 커밋은 `git diff -- config.py` 후 OCR 헝크만 추출해 `git apply --cached`(이번 세션 방식). 다른 파일은 100% 격리되면 통째 add.
- **Docker stale 바인드 마운트 복구**: 외장 SSD 바인드가 stale되면 컨테이너 내부 "Bad file descriptor" + 추천 500. **`docker restart`/`docker start`는 VM 레벨 stale로 실패하며 백엔드를 내림** → **Docker Desktop 전체 재시작**(`osascript -e 'quit app "Docker"'`→`open -a Docker`→데몬 polling) 후 `docker start lemon-aid-backend-1`(unless-stopped라 수동) + `docker start supabase_edge_runtime_...`(restart:no). [[local-db-topology]]
- **컨테이너는 빌드 이미지(소스 미마운트)** — 코드 변경 반영은 `docker compose build backend` 필요. env는 `.env`(secret, gitignored) + docker-compose `environment:` 블록 plumbing.

## 3. 이번 세션 완료분 (양 리모트 푸시; 신→구)

| 커밋 | 내용 |
|---|---|
| `db91f62d` | **앙상블 OCR**: Clova→Paddle line-union 보충 병합 → Gemma4 Vision 검증(warn-only) → 파서. config-gated 기본 OFF. (§4 상세) |
| `7889fb8e` | **OCR 단기 UX**: analysis_result_screen `_ingredientInfoTable` 3-tier — 구조화 성분 빔+labelSections 텍스트 있으면 인식텍스트 표시(Tier B). flutter 402. |
| `a6b97d40` | **ambient-tx Step 3**: food_records create/update/delete persist_scope 전환 + /me/food-records 4라우트 get_rls_context_session 채택. 신규 gated 테스트 2(food_records Stage-2 격리·OWN-mode 실엔진). unit+integration 2244 passed. |

- **OCR stale-mount 인프라 복구**(커밋 아님): Docker Desktop 재시작으로 추천 500→200 복구.

## 4. 앙상블 OCR 현황 (라이브 활성화됨 — 상세)

- **구조**: Clova(primary) → 신규 `_supplement_ensemble_ocr_if_allowed`(supplement_image_analysis.py, Clova 직후) = Paddle 항상 1회(풀이미지) 실행 → `_merge_cross_provider_ocr_results`로 line-union 병합(정규화 dedup + SequenceMatcher near-dup 0.92 + Clova 순서 보존 + 보충 상한 40·반복 상한 200) → 기존 fallback 체인(앙상블 시 no-op) → Gemma 검증(`_should_run_multimodal_verification` always_on_merge "+"마커 분기 / inherit_sample 샘플) **warn-only**(의료법상 교정/날조 안 함) → 파서.
- **config 4개**(전부 기본 disabled/inherit_sample = byte-for-byte 기존 동작): `ocr_secondary_merge_policy`·`ocr_merge_dedup_threshold(0.92)`·`ocr_merge_max_supplement_lines(40)`·`ocr_ensemble_verification_mode`. 어댑터 필드 `secondary_merge_ocr`(Paddle, fallback과 분리). 트랜잭션 미접촉(순수 in-memory, ambient-tx Step7 영역 보존).
- **검증**: 단위 merge 10+서비스 ensemble+통합 wiring+config = 109 통과, ruff/black 클린, 독립 리뷰 APPROVE(6 findings 반영).
- **라이브 활성화(현 컨테이너, 미커밋 env)**: `.env`에 `OCR_SECONDARY_MERGE_POLICY=always`·`OCR_ENSEMBLE_VERIFICATION_MODE=inherit_sample`·`MULTIMODAL_VERIFICATION_SAMPLE_RATE=0.2`·`ENABLE_MULTIMODAL_LLM=true`·`ENABLE_MULTIMODAL_VERIFICATION=true`. docker-compose `backend.environment`에 5개 plumbing 추가. 이미지 리빌드+재생성. **end-to-end 확인: provider=`clova_ocr+paddleocr_local` 병합 + Gemma 검증 동작**.
- **지연 실측**: Paddle warm 0.3s(병목 아님). **Gemma4(gemma4:e4b) 검증이 무거움(~10-30s)** → 처음 always_on_merge(매 스캔 ~33s)에서 **inherit_sample+0.2(약 20% 스캔만 검증)로 전환**(샘플링 게이트 200회 직접 측정 23% 확인). 평균 지연 대폭↓.
- **튜닝**(.env만 수정 후 `docker compose up -d backend`, 리빌드 불필요): sample_rate↑(커버리지)/↓(지연), `MULTIMODAL_VERIFICATION_THRESHOLD`(0.80, mismatch 오탐), `OCR_SECONDARY_MERGE_POLICY=low_confidence`(Paddle 약할 때만).
- **미커밋**: docker-compose.yml(앙상블 env plumbing)·.env(활성화 값, secret)는 사용자 WIP/secret이라 미커밋. **영구화하려면 docker-compose plumbing 라인만 별도 격리 커밋 가능**(사용자 결정).

## 5. 작업트리 미커밋 (사용자 WIP — 절대 건드리거나 커밋 금지)

- **사용자 food YOLO/CLIP WIP**: `config.py`(food 필드 11개+`_validate_food_detector_settings`+det thresh `local_ocr_text_det_box_thresh` 0.4→None), `meal_image_analysis.py`·`test_meal_image_analysis.py`(mtime ~14:2x), `0045_upsert_food_nutrition_40class_v2.py`(untracked), docker-compose/.env 일부. → `test_alembic_setup` 2건 실패는 이 WIP.
- **내 미커밋 활성화 편집**: docker-compose.yml(OCR 앙상블 env 5줄)·.env(활성화 플래그). 사용자 WIP와 혼재.
- scripts/outputs/docs 등 직전 세션 무관 dirt도 그대로 둔다.

## 6. 남은 작업

### #1 (PRIMARY): ambient-transaction 리팩터 Step 4~8
**권위 문서: `outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md`(반드시 읽고 시작).** Step 0~3 완료. **다음 = Step 4(user_medications + notifications + health_profile 쓰기 서비스 persist_scope 전환 + 라우트 get_rls_context_session 채택)** → 5(medical_records + consent-read closer 제거) → 6(async-with-begin 서비스군: privacy/meal_image/supplement_intake/analysis_results/regulated) → 7(supplement_image_analysis 4-commit 오케스트레이터, 최후) → 8(DATABASE_URL→lemon_app flip + 게이트: audit_database_url 강제·풀 사이징·테이블별 RLS/grant).
- **Step 4+ 패턴(서비스 1개씩)**: add+commit/dirty-update+commit/`async with session.begin()`→`async with persist_scope(session):`(commit 제거, refresh는 flush 후 scope 안). ⚠️ **persist_scope 타는 서비스 테스트 fake에 `.info: dict={}` 필요**(OWN-mode가 session.info[_OWN_DEPTH] 사용). 라우트 dep 스왑 + 그 라우트 테스트에 `app.dependency_overrides[get_rls_context_session]` 추가. grep 게이트(commit/begin 잔존 0). **unit+integration 둘 다 그린** + (가능 시)Stage-2 lemon_app 시뮬. 별도 리뷰 후 커밋.
- **Stage-2 gated 테스트 실행법**:
  ```bash
  cd backend
  export TEST_DATABASE_URL="$(PYTHONPATH=Nutrition-backend .venv/bin/python -c 'from src.config import get_settings; print(get_settings().database_url)')"
  export TEST_RLS_APP_DATABASE_URL="$(printf '%s' "$TEST_DATABASE_URL" | sed -E 's#://[^@]+@#://lemon_app:lemon_app_local_rls_verify@#')"  # pragma: allowlist secret
  .venv/bin/python -m pytest Nutrition-backend/tests/integration/db/test_food_records_stage2.py Nutrition-backend/tests/integration/db/test_persist_scope_own_mode.py Nutrition-backend/tests/integration/db/test_rls_owner_isolation.py Nutrition-backend/tests/integration/db/test_ambient_audit_stage2.py -q --no-cov
  ```

### #2: 자료/인프라 게이트 (직전과 동일)
- 🔴 **섹션 검출기 학습**(운영자 205 bbox + A100) — OCR 구조화 필드 빈약의 **근본 해결**(Tier-B 폴백·앙상블은 완화책). 런북: `2026-06-13-section-detector-training-gate-runbook.md`.
- 🟡 **모바일 Auth 3단계**(라이브 Supabase URL/anon key + 소셜 OAuth 키). seam 선구축.
- 🔴 **Supabase Auth 백엔드 라이브 활성화**(대시보드 비대칭 키 + SUPABASE_PROJECT_REF + ops).
- 🔵 **RLS Stage-2 활성화 인프라**(라우트 채택 누적 후 staging lemon_app 비번·DATABASE_URL flip·0023c FORCE).
- 🔴 **Health Connect / push(FCM/APNs)** — 가이드 08 의도적 제외.

### #3: OCR 앙상블 후속 (선택)
- 최종 검증 sample_rate 결정(현재 0.2). docker-compose env plumbing 격리 커밋 여부.

## 7. 자동 메모리

`~/.claude/projects/.../memory/`(MEMORY.md + ai-agent-chatbot-import-state.md + local-db-topology.md + ios-simulator-udid-fix.md) 세션 시작 시 자동 로드. **local-db-topology(DB 이원화·Docker stale 복구)와 ai-agent-chatbot-import-state(ambient-tx 진행·앙상블 OCR) 먼저 확인.**

---

## 다음 세션 시작 프롬프트 (복붙용)

> Lemon-Aid 작업을 이어서 진행해줘. 환경·규칙·남은 로드맵은 `outputs/todo-list/2026-06-14/2026-06-14-next-session-handoff-3.md`에, ambient-transaction 리팩터 상세는 `outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md`에 있다. 브랜치 feat/ai-agent-chat-import(HEAD db91f62d), 커밋·푸시는 양 리모트(origin+personal), 요청 시에만, 파일/헝크 명시 스테이징(사용자 food WIP 미혼입). 규칙(수치 추정 금지·사적이미지/secret 커밋 금지·A100 승인 후·PR#4 alembic/감사패턴 불가침·의료 금칙어·design_tokens_v2·해요체·백엔드 공백 날조 금지·미커밋 config.py/.mcp.json/docker-compose/.env 커밋 금지·TDD+별도 리뷰·공유서비스 변경 시 integration도 실행) 준수. **위임 에이전트는 출력 숨김·환각·스코프 위반이 잦으니 항상 실코드/테스트로 직접 검증.** 우선순위: **ambient-tx Step 4(user_medications/notifications/health_profile persist_scope 전환 + 라우트 채택)** — persist_scope 타는 테스트 fake에 .info 추가, get_rls_context_session override 갱신, unit+integration 둘 다 그린 + Stage-2 lemon_app 시뮬 검증, 별도 리뷰 후 커밋. [또는 Step 5~8 / 자료-게이트 / 앙상블 OCR sample_rate 결정 중 택일 지시]. 사적이미지/라이브 키/A100는 게이트이니 막히면 보고하고 가능한 코드/문서부터.
