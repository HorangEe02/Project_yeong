# 02. AI Agent Worktree Integration Plan

> Status: integration baseline
> Primary branch: `feat/ai-agent-backend-integration`
> Reference branches: `changmin-aiagent`, `feat/ai-agent-local-llm`, `taedong-design`, `feat/mobile-chat-prototype`
> Last local review: 2026-05-28

## Purpose

이 문서는 Lemon Aid AI Agent 통합 작업에서 어떤 worktree를 기준으로 삼고, 어떤 변경을
PR로 나누며, 어떤 보안/개인정보/검증 게이트를 통과해야 하는지 고정한다.

핵심 판단은 다음과 같다.

- API, backend, DB, mobile 계약은 `ai-agent-backend-integration`을 기준으로 한다.
- `changmin-aiagent`와 `ai-agent-pr`는 blind merge하지 않고 `knowledge`,
  `SafetyGuard`, LLM client, 설명 문서처럼 필요한 단위만 비교해 선별한다.
- `taedong-design`과 `ui-chat-prototype`는 UI 참고축으로만 사용한다.
- `localhost:8000` UI prototype 계약은 통합 기준으로 채택하지 않는다.

## Preflight

커밋 또는 PR 작성 전에는 `.env` 내용을 출력하지 말고 추적 여부만 확인한다.

```powershell
python scripts\check_ai_agent_integration_preflight.py
git status --short --branch
git status --ignored --short --untracked-files=all
```

허용되는 환경 파일은 문서용 `backend/.env.example`뿐이다. 실제 로컬 `.env`, `.env.local`,
`.env.production`, provider key, service-account JSON은 커밋하지 않는다.

PR diff에서 제외해야 하는 산출물은 다음과 같다.

- Flutter `build/`, `.dart_tool/`, `.flutter-plugins*`
- Python `__pycache__/`, `.pytest_cache/`, `.coverage`, `htmlcov/`
- local runtime output `.local/`, `logs/`, `*.log`, `*.err`, `*.out`
- generated `.env` 복제물과 local-only KDCA topic id 파일

## PR Split

| PR | Scope | Required Gate |
|----|-------|---------------|
| PR 1 | 보안, ignore, 산출물 diff 정리 | preflight script, `git status --ignored` review |
| PR 2 | `/api/v1/ai-agent/daily-coaching`, `/api/v1/ai-agent/chat`, `agent_memory`, `agent_runs` | AI agent API tests, chat/daily-coaching contract tests |
| PR 3 | `/api/v1/notifications/reminders`, `reminder_preferences` | consent-required tests, reminder approval-boundary tests |
| PR 4 | Flutter API 연동, CORS, port 정리 | `flutter analyze`, `flutter test`, local smoke against `18080` |
| PR 5 | `PROJECT_GUIDE.md`, runtime docs, operations docs 정합화 | `python -X utf8 scripts\sync_guide.py --check` |

`main`과 `develop`에는 직접 push하지 않는다. 각 PR은 `origin/develop` 기반 feature/fix/docs
브랜치에서 작성하고, large integration branch의 내용을 그대로 squash하지 않는다.

## Contract Baseline

통합 기준 포트는 다음과 같이 분리한다.

| Runtime | Port |
|---------|------|
| dev FastAPI | `18080` |
| smoke FastAPI override | `18081` |
| SGLang OpenAI-compatible `/v1` | `30000` |
| Flutter web | `52100` 계열 |

Backend/mobile 계약 기준:

- daily coaching: `POST /api/v1/ai-agent/daily-coaching`
- chat: `POST /api/v1/ai-agent/chat`
- reminders: `/api/v1/notifications/reminders`
- persistence: `agent_memory`, `agent_runs`, `reminder_preferences`
- local provider split: Ollama is the dev default, SGLang is the self-hosted runtime candidate.

## Safety And Privacy Gates

건강 문구는 진단, 치료, 처방을 확정하지 않는다. 일반 식사 조언은 공식 출처 기반 조정
가이드를 우선하고, 약물/진단/검사/응급/자해 같은 고위험 의도에서만 전문가 상담 경계를
강하게 둔다.

민감 건강 분석은 `sensitive_health_analysis` 동의 뒤에서만 동작해야 한다.

각 PR은 다음을 확인한다.

- raw OCR, raw prompt, internal trace, full provider payload가 응답에 노출되지 않는다.
- `agent_memory`와 `agent_runs`는 confirmed input 기반 요약만 저장한다.
- unconfirmed OCR preview는 memory/run log를 쓰지 않는다.
- privacy deletion flow가 `agent_memory`와 `agent_runs`를 포함한다.
- reminder는 제안까지 허용하고 실제 알림 활성화는 사용자 승인 뒤에만 가능하다.

## Verification Matrix

| Area | Command Or Check |
|------|------------------|
| Security | `python scripts\check_ai_agent_integration_preflight.py` |
| Backend/API | `python -m pytest -q --no-cov backend\ai_agent_chat\tests backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py` |
| DB | Alembic head 단일성, `0007_create_agent_memory_tables`, `0008_create_reminder_preferences` 순서 확인 |
| Safety | safety guard tests, chat fallback tests, raw trace non-exposure tests |
| Mobile | `flutter analyze`, `flutter test` in `mobile\flutter_app` |
| Docs | `python -X utf8 scripts\sync_guide.py --check` when `PROJECT_GUIDE.md` changes |

## Documentation Rule

`main/PROJECT_GUIDE.md`는 프로젝트 가이드의 canonical source다. `guide.html`은 직접 수정하지
않고 `scripts/sync_guide.py` 결과로만 갱신한다. 현재 문서는 integration branch의 실행 기준을
고정하기 위한 운영 문서이며, PR 5에서 `main/PROJECT_GUIDE.md`와 정합화한다.
