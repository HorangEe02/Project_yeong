# 14. 에이전트/챗봇 릴리스 실행 리포트

> Status: release-readiness execution report
> 작성일: 2026-05-31
> 기준 worktree: `feat/ai-agent-backend-integration`
> 기준 TODO: [13-agent-chatbot-release-todo.md](./13-agent-chatbot-release-todo.md)

## 1. 이번 작업 요약

`13-agent-chatbot-release-todo.md`의 릴리스 안정화 항목을 실제 실행 기준으로 정리했다.
핵심 결과는 아래와 같다.

- PR 분리 기준을 파일 경로 단위로 확정했다.
- 전체 backend pytest를 깨던 테스트 환경 오염을 수정했다.
- Supabase DB-backed evidence smoke와 FastAPI live smoke를 실행했다.
- SGLang live smoke는 Docker Desktop의 기존 `lemon-sglang` 컨테이너를 기동해 통과시켰다.
- unknown backlog의 반복 smoke trigger였던 `리튬 + 셀레늄 영양제`를 reviewed boundary로 승격했다.

## 2. PR 분리표

현재 dirty worktree는 한 PR로 올리기 크다. 아래 순서로 나누는 것을 기준으로 한다.

| PR | 목적 | 포함 파일 | 보류/제외 | 필수 검증 |
| --- | --- | --- | --- | --- |
| PR 1 | 문서/계약 정리 | `docs/Integration-docs/05~14-*.md`, `docs/Integration-docs/chatbot-unknown-backlog-report.md`, `docs/Integration-docs/README.md`, `docs/README.md` | backend/mobile 코드 변경 | `git diff --check -- docs` |
| PR 2 | agent/chatbot core | `backend/ai_agent_chat/src/lemon_ai_agent/`, `backend/ai_agent_chat/tests/`, `backend/scripts/ask_chatbot_agent.py`, `backend/scripts/eval_chatbot_golden.py` | FastAPI DB/API, Flutter UI | `python backend\scripts\eval_chatbot_golden.py`; `python -m pytest -q --no-cov backend/ai_agent_chat/tests` |
| PR 3 | DB-backed evidence/unknown backlog 운영 | `backend/Nutrition-backend/src/services/chatbot_evidence_retriever.py`, `chatbot_unknown_backlog*.py`, `backend/scripts/smoke_chatbot_db_evidence.py`, `backend/scripts/report_chatbot_unknown_backlog.py`, `backend/alembic/versions/0010~0013*.py`, 관련 tests | app context food/medication API | `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_* backend/Nutrition-backend/tests/unit/scripts/test_*chatbot*` |
| PR 4 | 앱 컨텍스트 데이터 API | `food_records.py`, `user_medications.py`, 관련 schema/model/service/API, `backend/alembic/versions/0014~0015*.py`, 관련 integration/unit tests | Flutter 화면 변경 | `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_food_records.py backend/Nutrition-backend/tests/integration/api/test_food_records_api.py backend/Nutrition-backend/tests/integration/api/test_user_medications_api.py` |
| PR 5 | 분석/CTA API 계약 | `app_health_analysis.py`, `user_health_context_snapshot.py`, `backend/Nutrition-backend/src/api/v1/ai_agent.py`, 관련 API/tests | Flutter UI 구현 | `python backend\scripts\eval_chatbot_golden.py`; `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_app_health_analysis.py backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py` |
| PR 6 | Flutter chat/CTA | `mobile/flutter_app/lib/features/chat/`, `mobile/flutter_app/lib/features/medications/`, `mobile/flutter_app/lib/features/dashboard/`, `mobile/flutter_app/lib/app.dart`, 관련 Flutter tests | backend migration/API 변경 | `C:\src\flutter\bin\flutter.bat test`; `C:\src\flutter\bin\flutter.bat analyze` |
| PR 7 | 릴리스 smoke/운영 | `backend/.env.example`, smoke/report PowerShell scripts, Supabase setup 문서, 운영 로그 | 기능 구현 코드 | Supabase smoke 3종; FastAPI smoke; unknown backlog report |

## 3. 테스트 환경 오염 수정

문제:

- `report_chatbot_unknown_backlog` 테스트가 운영 스크립트의 `_load_env_file()`을 호출하면서
  `DATABASE_URL`을 `os.environ`에 직접 남겼다.
- 이후 실행되는 `Settings()` 테스트들이 sync PostgreSQL URL을 읽어 79개 실패로 번졌다.
- production 설정 테스트는 로컬 `.env`의 `LOG_LEVEL=DEBUG`도 읽을 수 있었다.

수정:

- `test_report_chatbot_unknown_backlog.py`에서 테스트가 주입한 `DATABASE_URL`을 `finally`에서 제거했다.
- `test_config.py`의 production baseline kwargs에 `_env_file=None`을 추가해 로컬 `.env`와 분리했다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_report_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/test_config.py
python -m ruff check backend
python -m pytest -q --no-cov backend
```

결과:

```text
report/config focused tests: 51 passed
ruff backend: All checks passed
backend full pytest: 668 passed, 5 skipped, 3 warnings
```

## 4. Supabase/FastAPI smoke 결과

DB evidence smoke:

```text
hypertension-sodium: ok, answerability=answerable, source_count=2
magnesium-blood-pressure-med: ok, answerability=answerable_with_caution, source_count=1
unknown-herbal-blend: ok, answerability=unknown_no_reviewed_source, source_count=0
unknown-lithium-selenium: ok, answerability=medical_decision_boundary, source_count=1, source_id=medlineplus-lithium
```

FastAPI live smoke:

- 첫 실행은 `--skip-db-upgrade` 상태에서 `food_records` 테이블이 없어 실패했다.
- `smoke_ai_agent_server.py --skip-sglang-check --timeout 120`로 alembic upgrade를 적용했고,
  `0015_create_food_records` migration 후 통과했다.

결과:

```text
status: ok
chat_provider: sglang
chat_answerability: answerable
chat_source_count: 2
unknown_answerability: unknown_no_reviewed_source
unknown_source_count: 0
unknown_backlog_before: 5
unknown_backlog_after: 6
unknown_backlog_delta: 1
```

## 5. SGLang smoke 결과

첫 preflight에서는 Docker daemon이 꺼져 있었고, conda `lemon-sglang` env도 Python/sglang/torch가
정상 준비된 환경이 아니었다. Docker Desktop을 시작하자 기존 `lemon-sglang` 컨테이너가
`127.0.0.1:30000`에 올라왔고, 모델 로딩 완료 뒤 `/v1/models`가 정상 응답했다.

Preflight 결과:

```text
SGLang port 127.0.0.1:30000: ok
RUN_SGLANG_SMOKE: ok
SGLANG_MODEL: ok
sglang Python package: missing
torch Python package: missing
```

`sglang`/`torch` package는 host Python에는 없지만, smoke는 Docker 컨테이너의
OpenAI-compatible endpoint를 대상으로 수행하므로 통과 조건에는 영향을 주지 않았다.

`ask_chatbot_agent.py --llm sglang` 결과:

```text
hypertension-sodium-dinner: provider=sglang, answerability=answerable
magnesium-blood-pressure-med: provider=sglang, answerability=answerable_with_caution
```

SGLang 관련 테스트:

```text
test_sglang_smoke.py: passed
test_sglang_client.py: passed
test_chatbot_structured_json_output_is_rendered_to_answer_sections: passed
```

FastAPI live smoke도 SGLang readiness required 상태로 통과했다.

```text
sglang_check: required
first_provider: sglang
second_provider: sglang
chat_provider: sglang
chat_answerability: answerable
unknown_answerability: unknown_no_reviewed_source
unknown_backlog_delta: 1
```

해석:

- daily-coaching 경로는 실제 SGLang provider로 응답했다.
- chatbot FastAPI smoke는 실제 SGLang readiness를 확인한 뒤 `provider=sglang`으로 응답했고,
  answerability/source 계약을 유지했다.

## 6. Reviewed Evidence 운영 루프

최신 unknown backlog report:

```text
total_groups: 1
total_events: 6
open topic: medication_supplement_caution / supplement_drug_interaction / no_match
```

다음 evidence 승격 작업:

1. `supplement_drug_interaction` 중 반복 smoke trigger였던 `리튬 + 셀레늄 영양제`를
   `p0_lithium_selenium_supplement` boundary로 승격했다.
2. 공식 source는 MedlinePlus Lithium Drug Information으로 고정했고,
   source id는 `medlineplus-lithium`이다.
3. source metadata와 boundary allowed/blocked wording은
   `0016_seed_lithium_supplement_boundary` migration에 함께 넣었다.
4. golden test는 `p0_lithium_selenium_supplement` case로 고정했다.
5. `리튬 + 타우린`처럼 아직 검수 source가 없는 병용 질문은 계속
   `unknown_no_reviewed_source`로 닫힌다.

검증:

```powershell
python backend\scripts\report_chatbot_unknown_backlog.py --format markdown
python backend\scripts\eval_chatbot_golden.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

결과:

```text
unknown backlog report: 1 group, 6 events
golden eval: pass, 20 cases
answer card/chatbot focused tests: 80 passed
```

## 7. 남은 블로커와 후속 작업

- 릴리스 TODO 기준 차단 블로커는 현재 없다.
- Supabase FastAPI smoke는 현재 dev DB migration이 `0016_seed_lithium_supplement_boundary`까지 적용된 상태를 전제로 통과한다.
- chatbot FastAPI smoke에서 SGLang readiness와 `provider=sglang` 응답을 확인했다.
  SGLang 답변 품질과 prompt/renderer 튜닝은 다음 PR 범위에서 계속 다룬다.
- reviewed evidence coverage의 다음 실제 확장 대상은 신규 unknown backlog report에서 다시 고른다.
