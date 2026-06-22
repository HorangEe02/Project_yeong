# Lemon Aid Flutter App

초기 모바일 MVP shell입니다. 현재 실제 API flow는
`/api/v1/me/privacy/consents/sensitive_health_analysis` 동의 생성 후
`/api/v1/ai-agent/daily-coaching` 또는 `/api/v1/ai-agent/chat`을 호출하는
AI Agent daily coaching/chatbot입니다.

## Local API 연결

백엔드 smoke 서버가 `http://127.0.0.1:18080`에서 실행 중이면 기본값으로 바로 붙습니다.

```bash
flutter pub get
flutter run --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:18080
```

Android emulator는 기본값이 `http://10.0.2.2:18080`이고, Flutter web은
`http://localhost:18080`을 기본값으로 사용합니다. web으로 확인할 때는 FastAPI를
`scripts/start_ai_agent_dev_stack.ps1 -FlutterWebOrigin http://localhost:52100`처럼
실제 Flutter web origin을 CORS 허용 목록에 넣고 실행합니다.

챗봇 화면에서 질문을 보내면 앱은 동의 endpoint를 먼저 호출한 뒤 `/api/v1/ai-agent/chat`
응답의 `message`, `provider`, `answerability`, `sources`, `ctas`를 화면에 표시합니다.
4xx 응답은 답변처럼 렌더링하지 않고 오류 패널로 닫습니다.

JWT 인증 모드에서는 토큰을 앱 storage adapter로 넣기 전까지 개발용 dart define으로만 주입합니다.

```bash
flutter run \
  --dart-define=LEMON_API_BASE_URL=https://staging-api.example.com \
  --dart-define=LEMON_AUTH_TOKEN=<access-token>
```

토큰과 민감 건강 데이터는 로그에 남기지 않습니다. 화면은 백엔드 결과를 표시만 하며,
영양/의료 판단은 백엔드 API와 Agent contract를 단일 진실로 둡니다.
