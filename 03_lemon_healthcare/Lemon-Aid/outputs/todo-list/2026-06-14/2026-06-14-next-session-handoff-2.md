# Lemon-Aid 다음 세션 핸드오프 — RLS 라우트 마이그레이션 이어가기 (2026-06-14 #2)

> 새 세션 시작 시 이 파일을 그대로 붙여넣어 이어서 작업한다. 직전 핸드오프(`2026-06-14-next-session-handoff.md`)의 후속이며, 그 이후 진행분 + 남은 로드맵을 담는다.

---

## 0. 한 줄 요약

직전 세션에서 핸드오프 잔여(alembic 0044·RLS 격리테스트·알림 정합성·det thresh·Supabase Auth E2E·모바일 Auth seam)를 처리하고, **RLS Stage-2 라우트 채택을 위한 ambient-transaction 리팩터**를 시작했다(토대 Step 0 + 감사 차단 해소 Option A + 첫 라우트 채택 Step 2, 10커밋 양 리모트). **남은 큰 줄기 = ambient-tx Step 3~8(owner 쓰기 서비스 persist_scope 전환 → DATABASE_URL flip)** + 기존 자료-게이트 항목들(섹션 검출기·모바일 Auth 3 라이브·Supabase Auth 백엔드 활성화·Health Connect/push).

## 1. 환경

- **리포(외장 SSD)**: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`. 작업물·커밋 모두 이 경로(임시경로 지양).
- **브랜치**: `feat/ai-agent-chat-import`. **양 리모트 푸시**: `origin`(Lemon-Aid-KDT/Lemon-sin) + `personal`(HorangEe02/Project_yeong). main 아님. **현재 HEAD `03d34a65`, 양 리모트 0 ahead.**
- **백엔드**: `backend/.venv/bin/python`(3.13). 테스트 `cd backend && .venv/bin/python -m pytest Nutrition-backend/tests/unit -q`. **⚠️ 공유 서비스(예: record_audit_event)·db seam 변경 시 `Nutrition-backend/tests/integration`도 반드시 함께 실행**(직전 세션에서 unit만 돌려 통합 테스트 회귀 40건을 놓쳤음). alembic head = **0044**.
- **DB 토폴로지(필수 인지 — 메모리 local-db-topology와 동일)**: Postgres가 둘. **alembic CLI/.env(get_settings)는 supabase_db**(`postgresql+asyncpg://postgres:***@127.0.0.1:56322/postgres`). **실행 백엔드 컨테이너는 lemon-aid-db-1**(`db:5432/lemon`, 호스트 미공개 — docker exec로만). 둘은 리비전이 갈릴 수 있으니 "대상 DB"를 항상 확인.
- **모바일**: Flutter 3.41.9. `cd mobile && flutter analyze` + `flutter test`. 패키지 `lemon_aid_mobile`.
- **A100**: `ssh -i ~/.ssh/lemon_a100_ed25519 -p 8875 lemon-aid@155.230.153.222`(Windows PowerShell `-ExecutionPolicy Bypass`).
- **lemon_app 로컬 비번**: 직전 세션이 RLS/Stage-2 테스트 실행을 위해 supabase_db의 `lemon_app` 역할에 **throwaway 비번 `lemon_app_local_rls_verify`**를 설정함. 정리하려면 `ALTER ROLE lemon_app PASSWORD NULL`. gated 테스트 실행에 이게 필요.
- **작업트리 미커밋(주의)**: `backend/Nutrition-backend/src/config.py`에 **사용자의 의도적 편집**(det thresh `local_ocr_text_det_box_thresh` 기본값을 0.4→None으로 되돌리고 0.4는 env-tunable 후보로 표기)이 있다. **건드리지 말 것**(되돌리지 말 것). RLS 커밋엔 절대 섞지 말 것(파일 명시 스테이징). 그 외 outputs/·scripts 등 직전 세션 무관 dirt도 그대로 둔다.

## 2. 적용 중인 규칙 (반드시 준수)

- 수치·결과 추정 금지(확인값만). private image/raw OCR/secret/owner hash 커밋 금지(집계·해시만). 원격(A100) 실행·사적데이터 전송은 승인 후. 원본 dataset(`rec_dataset\v2`) 불가침.
- **사용자 요청 없이 commit/push 금지.** 커밋: Conventional Commits + 본문 "왜" + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`(리포 관례).
- framework 파라미터 변경 시 공식문서 확인 + URL 주석.
- **PR#4 보호(불가침)**: alembic 전체(특히 0023a/b/c·0041), `ai_agent.py` LLM 가드, **`app_health_analysis.py:269-271`·`analysis_results.py:192-193` add+commit 패턴**, `learning/pipeline.py`·workers, `session.py` 엔진 설정. 필요 시 신규 마이그레이션(0045+)만.
- 의료법: 금칙어(진단/처방/치료/효능) 금지 + 신뢰도 % 미노출 + 권고 화면 `MedicalDisclaimer` 필수.
- 모바일 UI: `design_tokens_v2`만(legacy 금지). 한국어 **해요체**. 시니어 최소치(본문 15px+ `AppText.body`, 버튼 52px+, 터치 48px+).
- 백엔드 공백 필드 날조 금지. `.mcp.json` 미커밋 편집 커밋 금지(`test_supabase_local_config` 기존 실패 — 무관).
- **TDD + 별도 리뷰 레인**: 작성/리뷰 분리, 같은 컨텍스트 self-approve 금지. 완료 주장 전 테스트 통과 + 증거. (직전 세션: 모든 substantive 변경에 독립 적대적 리뷰 거침.)
- **무관 기존 실패**: `test_supabase_local_config`(.mcp.json), 단위-전용 실행 커버리지 77%(통합 미실행 아티팩트). 둘 다 내 변경 무관.

## 3. 직전 세션 완료 (전부 양 리모트 푸시; 신→구)

| 커밋 | 내용 |
|---|---|
| `03d34a65` | **RLS Step 2**: 카탈로그 read 라우트 3종 get_rls_context_session 채택 + request_manages_transaction 가드(통합 fake 회귀 수정) |
| `b22dfb72` | **Option A**: 권한 분리 audit writer(audit_logs는 lemon_app 미기록) + Stage-2 end-to-end 증명 통합 테스트 |
| `d34a99d6` | ambient-tx 계획에 CRITICAL 발견 기록(audit_logs lemon_app 미기록) |
| `bbb3f649` | **Step 0**: ambient-transaction seam(`src/db/tx.py` persist_scope + marker + record_audit_event ambient-aware) |
| `58f468e5` | 모바일 Supabase Auth 토큰 seam 스캐폴딩(AuthService+binder, supabase_flutter 미추가) |
| `66a9333a` | Supabase 토큰 검증 라이브 E2E 통합 테스트(ADR 39) |
| `c516ef49` | det box_thresh 기본값 0.4 채택(⚠️ 사용자가 작업트리에서 None으로 되돌리는 중 — §1 참조) |
| `0ac4e797` | 모바일 복약 알림 서버 동기화 정합성 3건(serverId 왕복·토글/삭제 disable) |
| `4e8fd3c2` | FORCE RLS 소유자 격리 통합 테스트(Stage-2 전제) |
| `e405e832` | check 제약 이중 래핑 정규화(alembic 0044) + 0019/0021/0024 교정 |

## 4. 남은 작업 #1 (PRIMARY): ambient-transaction 리팩터 Step 3~8

**권위 문서: `outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md`(반드시 읽고 시작).** 8단계 계획·사이트별 마이그레이션 규칙·risk register·DO-NOT-TOUCH·Stage-2 flip 게이트가 거기에 있다.

**현재까지**: Step 0(토대)·Option A(감사 권한 분리)·Step 2(카탈로그 read 라우트) 완료. seam(`src/db/tx.py`: `persist_scope`, `request_manages_transaction`)과 ambient audit(`services/privacy.py`)은 검증됨. Stage-2 동작은 lemon_app로 end-to-end 증명됨(격리+쓰기+감사 영속).

**다음 = Step 3: food_records 쓰기 서비스 persist_scope 전환 + /food-records POST/PATCH/DELETE 라우트 채택.** 그 뒤 Step 4(user_medications/notifications/health_profile) → 5(medical_records + consent-read closer 제거) → 6(async-with-begin 서비스군: privacy/meal_image_analysis/supplement_intake/analysis_results._persist_result/regulated·ocr_intake) → 7(supplement_image_analysis 4-commit 오케스트레이터, 최후) → 8(DATABASE_URL→lemon_app flip).

**Step 3+ 작업 패턴(서비스 1개씩)**:
1. 계획 §"사이트 마이그레이션 규칙"대로 서비스의 `add+commit`/`dirty-update+commit`/`async with session.begin()`를 `async with persist_scope(session):`로 교체(commit 제거, refresh는 flush 후 scope 안으로).
2. 그 서비스의 전이적 호출그래프에 commit/begin/`_commit_consent_read_transaction` 잔존 0 확인(grep 게이트).
3. ⚠️ **`persist_scope`는 `session.info[_OWN_DEPTH]`를 쓴다.** 가드(`request_manages_transaction`)는 read-audit 경로만 커버하므로, **persist_scope를 타는 서비스의 단위/통합 테스트 fake 세션에는 `.info: dict = {}`를 추가해야 한다**(없으면 own-mode에서 AttributeError). 실 AsyncSession은 항상 .info 보유.
4. 해당 라우트 `get_async_session`→`get_rls_context_session` 스왑 + 그 라우트를 호출하는 테스트에 `app.dependency_overrides[get_rls_context_session] = <fake>` 추가(get_async_session override만으론 안 됨).
5. 검증: `tests/unit` **+ `tests/integration`** 둘 다 그린(필수). Stage-2 lemon_app 시뮬로 owner 쓰기 격리+영속 + 감사 영속 확인.
6. 별도 적대적 리뷰 → 커밋(양 리모트, 서비스+라우트 원자적).

**Stage-2 lemon_app 테스트 실행법(직전 세션 검증됨)**:
```bash
cd backend
export TEST_DATABASE_URL="$(PYTHONPATH=Nutrition-backend .venv/bin/python -c 'from src.config import get_settings; print(get_settings().database_url)')"
export TEST_RLS_APP_DATABASE_URL="$(printf '%s' "$TEST_DATABASE_URL" | sed -E 's#://[^@]+@#://lemon_app:lemon_app_local_rls_verify@#')"  # pragma: allowlist secret
.venv/bin/python -m pytest Nutrition-backend/tests/integration/db/test_rls_owner_isolation.py Nutrition-backend/tests/integration/db/test_ambient_audit_stage2.py -q
```
(supabase 로컬 스택 기동 + lemon_app 비번 설정 상태에서. 미설정 시 skip.)

**Step 8 flip 게이트(라우트 채택 누적 후, DATABASE_URL→lemon_app 전 필수)**: ① `audit_database_url`(권한 DSN) 강제 — 미설정 시 감사 INSERT 런타임 실패(startup 검증 추가 권장). ② 풀 사이징/더블 체크아웃(요청당 audit 별도 커넥션). ③ **테이블별 RLS/grant 확인** — RLS-enabled·정책 0개(lemon_app 읽기 0행): `audit_logs, model_eval_results, model_registry, model_training_runs, users`. 이 테이블 읽는 owner 라우트가 있으면 정책 추가(신규 0045+).

## 5. 남은 작업 #2 (자료/인프라 게이트 — 직전 세션과 동일)

- 🔴 **섹션 검출기 학습**: 운영자 사적이미지 205건 bbox 주석(AI 불가) + A100. 런북: `2026-06-13-section-detector-training-gate-runbook.md`.
- 🟡 **모바일 Auth 3단계 라이브**: 라이브 Supabase URL/anon key + 소셜 OAuth 키(카카오/Apple/Google) 필요. seam(`mobile/lib/features/auth/auth_service.dart`+`auth_session_binder.dart`)은 선구축됨 — 키 도착 시 supabase_flutter 추가 + `SupabaseAuthService` 구현 + `token_session.dart` 토큰소스 교체.
- 🔴 **Supabase Auth 백엔드 라이브 활성화**: 코드(17f59eb0)·로컬 E2E(66a9333a) 완료. 라이브는 Supabase 프로젝트 대시보드에서 비대칭 키 전환 + `SUPABASE_PROJECT_REF`/JWT_* 설정 + 게이트 #2(ops).
- 🔵 **RLS Stage-2 활성화 인프라**: 위 ambient-tx 라우트 채택 완료 후 staging lemon_app 비번(아웃오브밴드)·DATABASE_URL 전환·0023c FORCE. 격리 통합 테스트(4e8fd3c2)·감사 경로(b22dfb72)는 검증돼 리스크 낮춤.
- 🔴 **Health Connect / 알림 push 전송(FCM/APNs)**: 가이드 08 의도적 스코프 제외. Android 기기 + `health` 플러그인 / Firebase+APNs 필요.

## 6. 자동 메모리

`~/.claude/projects/.../memory/`(MEMORY.md + ai-agent-chatbot-import-state.md + local-db-topology.md + ios-simulator-udid-fix.md)에 누적 상태가 있다 — 세션 시작 시 자동 로드. **`local-db-topology.md`(DB 이원화)와 ambient-tx 진행 항목 먼저 확인.**

---

## 다음 세션 시작 프롬프트 (복붙용)

> Lemon-Aid 작업을 이어서 진행해줘. 환경·규칙·남은 로드맵은 `outputs/todo-list/2026-06-14/2026-06-14-next-session-handoff-2.md`에, ambient-transaction 리팩터 상세는 `outputs/todo-list/2026-06-14/2026-06-14-ambient-transaction-refactor-plan.md`에 있다. 브랜치 feat/ai-agent-chat-import(HEAD 03d34a65), 커밋·푸시는 양 리모트(origin+personal), 요청 시에만. 규칙(수치 추정 금지·사적이미지/secret 커밋 금지·A100 승인 후·PR#4 alembic/감사패턴 불가침·의료 금칙어·design_tokens_v2·해요체·백엔드 공백 날조 금지·미커밋 .mcp.json/config.py 커밋 금지·TDD+별도 리뷰·공유서비스 변경 시 integration 테스트도 실행) 준수. 우선순위: **ambient-tx Step 3(food_records 쓰기 서비스 persist_scope 전환 + /food-records 라우트 채택)** — persist_scope 타는 테스트 fake에 .info 추가 필요, get_rls_context_session override 갱신, unit+integration 둘 다 그린 + Stage-2 lemon_app 시뮬 검증, 별도 리뷰 후 커밋. [또는 Step 4~8 / 자료-게이트 항목 중 택일 지시]. 사적이미지/라이브 키/A100는 게이트이니 막히면 보고하고 가능한 코드/문서부터.
