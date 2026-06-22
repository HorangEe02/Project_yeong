# 13. 에이전트/챗봇 릴리스 TODO

> Status: release-readiness TODO
> 작성일: 2026-05-31
> 기준 worktree: `feat/ai-agent-backend-integration`
> 이전 구현 기준선: [12-agent-chatbot-todo.md](./12-agent-chatbot-todo.md)
> 구현 로그: [09-grounded-chatbot-implementation-log.md](./09-grounded-chatbot-implementation-log.md)
> 갭 리뷰: [10-grounded-chatbot-gap-review.md](./10-grounded-chatbot-gap-review.md)
> 실행 리포트: [14-agent-chatbot-release-execution-report.md](./14-agent-chatbot-release-execution-report.md)

## 1. 목적

`12-agent-chatbot-todo.md`는 앱 컨텍스트 기반 건강 에이전트/챗봇 v1 구현 기준선으로
완료됐다. 이 문서는 다음 작업을 새 기능 확장보다 **릴리스 안정화, PR 분리, 운영 검증,
reviewed evidence 확장 루프** 중심으로 다시 정리한다.

## 2. 다음 단계 요약

우선순위는 아래 순서다.

1. dirty worktree를 PR 단위로 분리한다.
2. 테스트 환경 오염을 정리해 전체 검증 명령을 안정화한다.
3. Supabase live FastAPI smoke로 DB-backed evidence와 unknown backlog를 재확인한다.
4. SGLang structured output live smoke를 실행한다.
5. unknown backlog를 reviewed evidence coverage 확장 루프로 연결한다.

## 3. TODO 1. PR 정리와 변경 범위 분리

상태: `done`

목표:

- 현재 매우 큰 dirty worktree를 리뷰 가능한 PR 단위로 나눈다.
- 기존 사용자/에이전트 변경을 되돌리지 않고, 포함 파일과 제외 파일만 분명히 한다.

권장 PR 순서:

1. **문서/계약 정리 PR**
   - `05~13 Integration-docs`
   - `docs/README.md`, `docs/Integration-docs/README.md`
2. **backend agent/chatbot core PR**
   - `backend/ai_agent_chat/`
   - chatbot answerability, `AnswerCard`, `AnswerPlan`, renderer, golden eval
3. **backend app context data PR**
   - FoodRecord/UserMedication DB/API/schema/service/migration
   - user health context snapshot
4. **backend analysis/CTA PR**
   - today/health analysis snapshot
   - chat-triggered analysis confirmation/persistence
   - CTA response contract
5. **Flutter chat/CTA PR**
   - chat DTO
   - CTA panel
   - checklist modal/navigation wiring
6. **smoke/operations PR**
   - Supabase smoke scripts
   - unknown backlog report scripts
   - env/example and operational docs

해야 할 일:

- `git status --short`를 기준으로 변경 파일을 위 PR 후보에 배정한다.
- PR 후보별로 “포함 파일”, “보류 파일”, “필수 검증 명령”을 짧게 적는다.
- 한 PR에서 문서, backend core, Flutter UI가 과하게 섞이면 분리한다.

완료 기준:

- 각 PR 후보가 독립적으로 리뷰 가능한 수준으로 좁혀진다.
- 어떤 파일이 어떤 PR에 들어갈지 문서 또는 체크리스트로 확정된다.

실행 결과:

- [14-agent-chatbot-release-execution-report.md](./14-agent-chatbot-release-execution-report.md)의
  PR 분리표에 7개 PR 후보와 포함 파일, 보류 파일, 필수 검증 명령을 고정했다.

## 4. TODO 2. 테스트 환경 오염 정리

상태: `done`

목표:

- 전체 backend 테스트가 로컬 `.env` 값 때문에 깨지는 상황을 정리한다.
- 최소한 공식 전체 테스트 명령과 필요한 환경 변수 override를 문서화한다.

현재 관찰:

- `python -m pytest -q --no-cov backend`는 `backend/.env`의 sync PostgreSQL
  `DATABASE_URL`이 `Settings()` 단위 테스트에 주입되어 실패한다.
- `DATABASE_URL`을 asyncpg URL로 덮어쓰면 대부분 통과하지만, 기본값 기대 config test와
  production `LOG_LEVEL` 환경 오염 케이스가 남는다.

해야 할 일:

- 테스트 실행 시 `.env`를 읽을지, `_env_file=None`을 강제할지, 테스트 전용 env 파일을 둘지 결정한다.
- `Settings()` 단위 테스트가 외부 `.env`에 의존하지 않도록 격리한다.
- 공식 전체 테스트 명령을 README 또는 운영 문서에 고정한다.

검증 명령:

```powershell
python -m ruff check backend
python -m pytest -q --no-cov backend
```

완료 기준:

- 전체 backend pytest가 로컬 기본 테스트 환경에서 통과한다.
- 실패가 남는다면, 실패 원인이 구현 결함인지 환경 전제인지 문서에서 분리된다.

실행 결과:

- `report_chatbot_unknown_backlog` 테스트가 남기던 `DATABASE_URL` 환경 오염을 정리했다.
- production config 테스트 baseline에 `_env_file=None`을 추가해 로컬 `.env`와 분리했다.
- `python -m ruff check backend`: 통과.
- `python -m pytest -q --no-cov backend`: `668 passed, 5 skipped, 3 warnings`.

## 5. TODO 3. Supabase live FastAPI smoke

상태: `done`

목표:

- DB-backed reviewed evidence, `sources[]`, unknown backlog persistence가 실제 FastAPI 경로에서
  동작하는지 확인한다.

해야 할 일:

- Supabase pooler `DATABASE_URL`을 로컬 secret으로만 주입한다.
- FastAPI smoke에서 reviewed source 질문과 unknown 질문을 함께 실행한다.
- unknown backlog row 증가와 privacy-safe 저장을 확인한다.

검증 명령:

```powershell
python backend\scripts\smoke_chatbot_db_evidence.py
python backend\scripts\smoke_chatbot_db_evidence.py --preset magnesium-blood-pressure-med
python backend\scripts\smoke_chatbot_db_evidence.py --preset unknown-herbal-blend
python backend\scripts\smoke_chatbot_db_evidence.py --preset unknown-lithium-selenium
python backend\scripts\smoke_ai_agent_server.py --skip-db-upgrade --skip-sglang-check
```

완료 기준:

- reviewed source 질문은 `answerability=answerable` 또는 `answerable_with_caution`이다.
- unknown 질문은 `unknown_no_reviewed_source`이고 `sources[]`가 비어 있다.
- unknown backlog delta가 증가한다.
- raw prompt, raw OCR, 대화 전문은 backlog에 저장되지 않는다.

실행 결과:

- DB evidence smoke 3종이 통과했다.
- FastAPI smoke는 첫 실행에서 `food_records` 테이블 미적용으로 실패했고,
  alembic `0015_create_food_records` 적용 후 통과했다.
- unknown backlog delta는 `2 -> 3`, `+1`로 확인했다.

## 6. TODO 4. SGLang structured output live smoke

상태: `done`

목표:

- deterministic/golden 경로뿐 아니라 실제 SGLang OpenAI-compatible 응답에서도 structured output과
  fallback이 안전하게 동작하는지 확인한다.

해야 할 일:

- SGLang 서버 연결 상태를 preflight로 확인한다.
- 정상 JSON schema 응답, schema 불일치 응답, 금지 표현 응답을 각각 확인한다.
- fallback이 발생해도 user-facing 응답이 `AnswerCard`/boundary/unknown 계약을 유지하는지 본다.

검증 명령:

```powershell
python backend\scripts\check_ai_agent_runtime_prereqs.py
python backend\scripts\ask_chatbot_agent.py --preset hypertension-sodium-dinner --llm sglang
python backend\scripts\ask_chatbot_agent.py --preset magnesium-blood-pressure-med --llm sglang
python backend\scripts\eval_chatbot_golden.py
```

완료 기준:

- 정상 structured output은 section renderer를 통과한다.
- schema parse 실패, 금지 표현, unsupported fact는 deterministic fallback으로 전환된다.
- 내부 trace, tool 이름, raw context가 사용자 응답에 노출되지 않는다.

실행 결과:

- Docker Desktop 시작 후 기존 `lemon-sglang` 컨테이너가 `127.0.0.1:30000`에 올라왔다.
- `RUN_SGLANG_SMOKE=1` 기준 preflight에서 SGLang port와 smoke gate가 통과했다.
- `ask_chatbot_agent.py --llm sglang` 2종은 실제 `provider=sglang`로 응답했다.
- SGLang live smoke, OpenAI-compatible JSON schema payload test,
  structured JSON renderer test가 함께 통과했다.
- FastAPI live smoke도 SGLang readiness required 상태로 통과했다.
  이때 daily-coaching은 `provider=sglang`, chatbot endpoint는 deterministic fallback으로
  안전 계약을 유지했다.

## 7. TODO 5. Reviewed evidence coverage 운영 루프

상태: `done`

목표:

- unknown backlog를 단순 적재가 아니라 reviewed evidence 확장 작업으로 연결한다.
- LLM-WIKI 후보는 바로 답변에 쓰지 않고 공식 source 검수 후 승격한다.

해야 할 일:

- `chatbot-unknown-backlog-report.md` 또는 report script 결과에서 반복 topic을 고른다.
- topic마다 공식 source, source version, expiry, allowed wording, blocked wording을 정한다.
- evidence seed/migration과 golden test를 함께 추가한다.
- P0 상호작용 후보는 reviewed policy boundary로만 승격한다.

검증 명령:

```powershell
python backend\scripts\report_chatbot_unknown_backlog.py --format markdown
python backend\scripts\eval_chatbot_golden.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

완료 기준:

- 반복 unknown topic이 reviewed evidence 또는 명시적 boundary로 승격된다.
- golden test가 새 coverage를 고정한다.
- 검수 source가 없는 topic은 계속 unknown으로 닫힌다.

실행 결과:

- `chatbot-unknown-backlog-report.md`를 최신화했다.
- 현재 open group은 `supplement_drug_interaction` 1개, 6 events다.
- 반복 smoke trigger였던 `리튬 + 셀레늄 영양제` 질문을 `p0_lithium_selenium_supplement`
  boundary로 승격했다.
- reviewed source로 MedlinePlus Lithium Drug Information을 `medlineplus-lithium`에
  등록했고, `0016_seed_lithium_supplement_boundary` Alembic seed를 추가했다.
- golden eval의 `p0_lithium_selenium_supplement` case가 `medical_decision_boundary`,
  `source_id=medlineplus-lithium`, 금지 문구 차단을 고정한다.
- `리튬 + 타우린`처럼 아직 검수 source/boundary가 없는 병용 질문은 계속
  `unknown_no_reviewed_source`로 닫힌다.

## 8. 고정 검증 세트

다음 단계 작업 후 최소 검증:

```powershell
python -m ruff check backend
python backend\scripts\eval_chatbot_golden.py
C:\src\flutter\bin\flutter.bat test
C:\src\flutter\bin\flutter.bat analyze
git diff --check
```

릴리스 후보 검증:

```powershell
python -m pytest -q --no-cov backend
python backend\scripts\smoke_ai_agent_server.py --skip-db-upgrade --skip-sglang-check
```

## 9. 문서 연결 원칙

- `12-agent-chatbot-todo.md`는 완료된 v1 구현 TODO로 유지한다.
- 릴리스 안정화와 운영 TODO는 이 문서에서 관리한다.
- 세부 구현 로그는 `09-grounded-chatbot-implementation-log.md`에 계속 누적한다.
- gap 판단이 바뀌면 `10-grounded-chatbot-gap-review.md`를 갱신한다.
