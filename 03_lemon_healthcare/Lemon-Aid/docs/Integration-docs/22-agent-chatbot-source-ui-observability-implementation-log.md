# 22. 에이전트/챗봇 Source UI와 Observability 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 왜 했나

`15-agent-llm-gap-audit.md`의 마지막 순서는 source detail UI와 raw-free 운영 관측성이다.
backend가 `sources[]`를 내려도 mobile이 새 metadata를 읽지 못하면 사용자에게 근거 추적성이 약하고,
운영 리포트가 raw prompt를 복사하면 privacy/safety 원칙을 깨게 된다.

## 2. 구현

변경 파일:

- `mobile/flutter_app/lib/features/chat/domain/chat_models.dart`
- `mobile/flutter_app/lib/features/chat/presentation/chat_screen.dart`
- `mobile/flutter_app/test/confirmed_payload_test.dart`
- `mobile/flutter_app/test/widget_test.dart`
- `backend/Nutrition-backend/src/services/chatbot_unknown_backlog_report.py`
- `backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py`

구현 내용:

- `ChatbotSource`가 backend `sources[].boundary_code`를 `boundaryCode`로 파싱한다.
- chat source label에 `boundaryCode`를 포함한다.
- `chatbot_runtime_report_payload()`를 추가해 answerability, provider, fallback reason,
  source expiry, boundary code를 집계한다.
- report payload는 raw prompt, raw answer, conversation을 복사하지 않는다.

## 3. 안전 경계

- source UI는 reviewed metadata를 보여주는 경로일 뿐, 개인 병용 가능/불가를 판정하지 않는다.
- 운영 리포트는 raw question, raw prompt, raw OCR, raw conversation, provider payload를 포함하지 않는다.
- `boundary_code`는 내부 운영/근거 추적 metadata이며, 의학적 결론이 아니다.

## 4. 검증

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py
```

결과:

```text
8 passed
```

```powershell
C:\src\flutter\bin\flutter.bat test test\confirmed_payload_test.dart test\widget_test.dart
```

결과:

```text
All tests passed! (9 Flutter tests)
```

참고:

- `backend/Nutrition-backend/tests/unit/mobile/test_flutter_ai_agent_contract.py` 전체는 현재 dashboard/supplement capture 관련
  기존 dirty UI 상태 때문에 unrelated failure가 남아 있다. 이번 변경과 직접 관련된 Dart parsing/widget 경로는 위 테스트로 확인했다.

## 5. 2026-06-01 로컬 URL 연결 확인

문서 기준 연결 흐름을 실제 로컬 URL에서 다시 확인했다.

확인 환경:

- FastAPI: `http://127.0.0.1:18080`
- Flutter static verification server: `http://localhost:52100`
- Flutter build API base: `LEMON_API_BASE_URL=http://localhost:18080`

실행 확인:

```powershell
curl.exe -sS http://127.0.0.1:18080/health
C:\src\flutter\bin\flutter.bat build web --dart-define=LEMON_API_BASE_URL=http://localhost:18080
```

결과:

```text
FastAPI health: {"status":"ok","version":"0.1.0"}
Flutter build web: Built build\web
```

API smoke:

- `POST /api/v1/me/privacy/consents/sensitive_health_analysis`
  - `granted=true`
- `POST /api/v1/ai-agent/chat`
  - 나트륨/저녁 follow-up 질문은 `answerability=answerable`, `provider=deterministic`,
    `sources=[kdca-healthinfo, kdris-2025]`로 응답했다.
  - 리튬/셀레늄 병용 질문은 `answerability=medical_decision_boundary`,
    `sources=[medlineplus-lithium]`로 응답했다.

화면 확인:

- Agent 홈: `mobile/flutter_app/verified-flutter-web-build.png`
- 챗봇 화면: `mobile/flutter_app/verified-chat-web-build-hash.png`

참고:

- 현재 실행 중인 FastAPI CORS 허용 origin은 `http://localhost:52100`이다.
- 기존 `52100` Flutter debug web server는 Chrome headless capture에서 앱 본문 대신 loader만
  캡처됐고 사용자 브라우저에서도 빈 화면 증상이 있었다. 해당 `dartvm` dev server를 종료하고,
  동일 포트 `52100`에 `flutter build web` 결과를 Python 정적 서버로 다시 띄웠다.
- 실제 챗봇 입력까지 확인할 때는 `http://localhost:52100/#/chat`을 사용한다.

추가 CORS/API 확인:

```powershell
curl.exe -i -sS -X OPTIONS http://127.0.0.1:18080/api/v1/ai-agent/chat -H "Origin: http://localhost:52100" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"
curl.exe -i -sS -X OPTIONS http://127.0.0.1:18080/api/v1/ai-agent/chat -H "Origin: http://127.0.0.1:52101" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"
```

결과:

```text
Origin http://localhost:52100: 200 OK, access-control-allow-origin=http://localhost:52100
Origin http://127.0.0.1:52101: 400 Bad Request, Disallowed CORS origin
```

최종 수정 후 확인:

```powershell
curl.exe -i -sS http://localhost:18080/health
curl.exe -i -sS -X OPTIONS http://localhost:18080/api/v1/ai-agent/chat -H "Origin: http://localhost:52100" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"
```

결과:

```text
http://localhost:18080/health: 200 OK
Origin http://localhost:52100 -> http://localhost:18080/api/v1/ai-agent/chat: 200 OK
동의 API: 201, access-control-allow-origin=http://localhost:52100
챗봇 API: 200, access-control-allow-origin=http://localhost:52100
```

최종 화면 캡처:

- `mobile/flutter_app/verified-chat-localhost-52100-fixed.png`

## 6. 2026-06-01 챗봇 식단 계획 분류 수정

사용자 화면에서 “당뇨 수치가 요즘 계속 오르네. 오늘 점심, 저녁 식단을 짜줘.”가
`추가 정보 필요`로 떨어지는 문제를 확인했다. API 연결 실패가 아니라 `ContextResolver`가
“오늘 + 점심/저녁”을 모두 특정 음식 기록 조회로 오인한 것이 원인이었다.

수정:

- “어제 점심에 내가 뭐 먹었지?” 같은 기록 조회 질문은 계속 `needs_structured_lookup`으로 둔다.
- “오늘 점심/저녁 식단을 짜줘”, “어떻게 먹으면 좋아?” 같은 계획/추천 질문은 snapshot 기반
  일반 식단 guidance로 진행한다.
- 당뇨 식단 계획 fallback에 점심/저녁 후보를 직접 포함했다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
C:\src\flutter\bin\flutter.bat test test\confirmed_payload_test.dart test\widget_test.dart
```

결과:

```text
backend/ai_agent_chat/tests: 126 passed, 1 skipped
chatbot DB/source focused tests: 65 passed
Flutter focused tests: All tests passed! (9 Flutter tests)
```

실제 API 확인:

```text
질문: 당뇨 수치가 요즘 계속 오르네. 오늘 점심, 저녁 식단을 짜줘.
결과: 200, access-control-allow-origin=http://localhost:52100, answerability=answerable
답변 핵심: 점심은 현미밥/잡곡밥 소량 + 두부/달걀/생선구이 + 채소, 저녁은 밥/면/빵 양을 줄이고 채소/단백질 중심

질문: 어제 점심에 내가 뭐 먹었지?
결과: 200, answerability=needs_more_info, needs_structured_lookup 유지
```

## 7. 현재 완료 상태

`15-agent-llm-gap-audit.md`의 권장 작업 순서 기준으로 1차 구현은 모두 완료했다.
