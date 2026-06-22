# 2026-06-11 다음 단계 / 사용자 액션

> 근거: [세션 요약](2026-06-11-session-summary.md), [P1 체크리스트](2026-06-11-uiux-p1-execution-todo.md), [점수 보류 결정](2026-06-11-daily-health-score-decisions.md)

## 사용자가 직접 해야 하는 것

1. **중복 칩 세션 3개 정리** — ollama loopback 가드 / VISION_ROI 드리프트 / 테스트 순서 오염 칩으로 시작한 워크트리 세션들은 **모두 이 세션에서 이미 수정·커밋됨**(`1f7ef6fc`, `ce8275c3`). 해당 세션 닫기.
2. **개인 GitHub 푸시** — 에이전트 크로스-계정 차단. `git push personal feat/ai-agent-chat-import` 사용자 직접. (origin 푸시/PR 여부도 팀과 결정 — 커밋 18개 누적)
3. **(제품 결정) 점수 가중치 0.6/0.4 확정** — 활동 우선 휴리스틱(evidence C). figma 78점/84링을 같은 값으로 둘지, 활동 서브점수 링으로 분리할지 포함. → 보류 결정 문서 #5
4. **(운영 결정) wiki vector RAG 활성화 여부** — 현재 lexical 파일직독 폴백으로 동작. 정밀 grounding 원하면 3단계(플래그 ON → 임베딩 적재 → entity 링크 시드) 실행 필요. → 보류 결정 #8
5. **(정책 확인) `.mcp.json` 수정 의도 확인** — supabase 테스트가 기대하는 strict `${SUPABASE_PROJECT_REF}` 형식과 현재 기본값 폴백(`:-weipsloxntjzcqjvzjax`)이 충돌 — 의도 수정이면 테스트 갱신, 아니면 원복.

## 에이전트가 이어서 할 수 있는 것 (우선순위 순)

1. **[최우선] 실기기 E2E 스모크** — dev 스택 기동(Postgres + `alembic upgrade head` **첫 실행**, 챗 테이블 0030~0041 적용) → uvicorn(:8000, PYTHONPATH에 `ai_agent_chat/src`) → Pixel 10 Pro 에뮬레이터/iPhone 17 Pro 시뮬레이터에서 촬영→분석→저장→홈 점수→챗 질문→오늘의 분석 풀 사이클. LLM은 Ollama(gemma4:e4b) 없이도 결정론적 답변으로 데모 가능.
2. **[P1] 복약 관리 라우트 임포트** — 팀원 워크트리(`external/Lemon-sin-ai-agent-branch`)의 `user_medications.py`/`food_records.py`/`notifications.py` API 라우트 선별 임포트(백엔드 통합 때와 동일 방식) → 홈 복약 카드 실연동 + 상호작용 카드 약 기준 점검.
3. **[P1] 캘린더/오늘의 기록 화면** — 플랜 §3.7 (GET /meals + /supplements 날짜 집계).
4. **[P1] 설정 서브화면 4종 + 건강 프로필** — medical-records/profile-snapshots 연동 (플랜 §3.6).
5. **[P1] Health Connect(Android)** — health 패키지 + 권한 + `POST /health/sync` → 활동 서브점수 실데이터화.
6. **[P1] 음식 후보 선택 UI** — food_candidates 일치율 + 섭취량 스테퍼 (플랜 §3.4).

## 게이트/활성화 현황

| 항목 | 상태 |
|---|---|
| 챗봇 백엔드(/ai-agent/chat·daily-coaching) | 코드 통합 완료, **라이브 DB 마이그레이션 미실행** |
| Flutter P0 (챗/홈/분석결과/오늘의 분석/테마/상태템플릿) | 완료 — analyze 0, 170 tests |
| 일일 건강 점수 | dashboard summary 배선 완료, HR 보정은 0.7 고정(워치 분 데이터 동기화 전) |
| production 챗 fail-closed | 의료 소스 거버넌스 DB 시드 전까지 보수 답변 — 데모는 dev 환경 |
| 인증(/auth/*) | 백엔드 부재 — P2 결정 필요(Supabase Auth 우선 검토) |
| 리워드/포인트 | 백엔드 전무 — 범위 외 |
