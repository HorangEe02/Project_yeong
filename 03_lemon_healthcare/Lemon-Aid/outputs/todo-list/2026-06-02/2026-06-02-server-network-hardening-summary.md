# 2026-06-02 서버 연결 오류 처리 보완 요약

> 작성 기준: 2026-06-02
> 범위: backend `ALLOWED_HOSTS`, Flutter API client network exception handling, 관련 테스트

---

## 1. Summary

모바일에서 "서버가 응답하지 않는다"로 보일 수 있는 상황을 두 갈래로 나눠 보완했다.

- backend는 Android emulator가 Mac host를 바라볼 때 쓰는 `10.0.2.2` Host header를 개발 기본 allowlist에 포함한다.
- mobile API client는 서버 포트가 닫혔거나 네트워크 계층에서 실패한 경우를 일반 예외로 흘리지 않고 `network_unavailable` 사용자 오류로 정규화한다.

---

## 2. 원인 분리

확인된 backend runtime은 `/health`, `/ready`, `/api/v1/dashboard/summary`에서 정상 응답했다. 따라서 전체 서버 프로세스 장애보다는 다음 문제가 사용자 화면에서 서버 오류처럼 보일 수 있었다.

- `/api/v1/health`처럼 존재하지 않는 health prefix를 호출해 404를 장애로 오해하는 경우
- Android emulator에서 `10.0.2.2:8000` Host header가 기본 allowlist에 없어서 개발 실행 방식에 따라 요청이 거절될 수 있는 경우
- Flutter `SocketException` 또는 `http.ClientException`이 UI에 일관된 안내 문구로 변환되지 않는 경우

---

## 3. 변경 파일

- `backend/Nutrition-backend/src/config.py`
  - `DEFAULT_ALLOWED_HOSTS`에 `10.0.2.2` 추가
- `backend/Nutrition-backend/tests/unit/test_config.py`
  - 기본 allowed hosts에 Android emulator host가 포함되는지 검증
- `backend/Nutrition-backend/tests/unit/test_security_middleware.py`
  - `Host: 10.0.2.2:8000` 요청이 trusted host middleware에서 통과하는지 검증
- `mobile/lib/core/api/api_client.dart`
  - `SocketException`, `http.ClientException`을 `ApiError(code: network_unavailable, statusCode: 0)`로 변환
- `mobile/test/unit/api_client_robustness_test.dart`
  - socket failure와 package http client failure가 안전한 API 오류로 매핑되는지 검증

---

## 4. 검증 결과

### Runtime

```text
GET /health -> 200
GET /ready -> 200
GET /api/v1/dashboard/summary -> 200
GET /health with Host: 10.0.2.2:8000 -> 200
```

### Mobile

```text
flutter test test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart
17 passed

flutter analyze lib/core/api/api_client.dart lib/core/config/app_config.dart test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart
No issues found!
```

### Backend

```text
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py
75 passed

.venv/bin/python -m ruff check Nutrition-backend/src/config.py Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py
All checks passed!
```

---

## 5. 공식 문서 기준

- Dart `SocketException`: https://api.flutter.dev/flutter/dart-io/SocketException-class.html
- Dart `package:http` `ClientException`: https://pub.dev/documentation/http/latest/http/
- Starlette `TrustedHostMiddleware`: https://www.starlette.io/middleware/#trustedhostmiddleware

---

## 6. 남은 주의점

- 운영 환경에서는 `ALLOWED_HOSTS`를 명시 환경변수로 제한해야 한다. 이번 변경은 로컬 개발 기본값 보완이다.
- OCR/YOLO/Ollama degraded 상태는 서버 미응답과 별개로 표시해야 한다.
- Android/iOS 실행 앱의 `LEMON_API_BASE_URL`은 각각 실행 환경에 맞게 유지해야 한다.
