# 2026-06-02 서버 응답 점검 기록

> 작성 기준: 2026-06-02
> 범위: local backend runtime, mobile API base URL, health/readiness/API 응답 확인

---

## 1. Summary

모바일에서 "서버가 응답하지 않는다"로 보일 수 있는 상황을 backend runtime 기준으로 먼저 분리 점검했다.

확인 결과, local backend 자체가 완전히 죽은 상태는 아니었다. `/api/v1/health`는 존재하지 않아 404가 발생했지만, 실제 health endpoint인 `/health`와 readiness endpoint인 `/ready`는 정상 응답했다. 또한 Android emulator Host header인 `10.0.2.2:8000`으로 들어오는 health 요청도 통과하도록 기본 개발 allowlist를 보완했다.

---

## 2. 확인한 엔드포인트

| 항목 | URL | 결과 | 해석 |
|---|---|---:|---|
| 잘못된 health prefix | `http://127.0.0.1:8000/api/v1/health` | 404 | health는 API v1 prefix 아래가 아님 |
| health | `http://127.0.0.1:8000/health` | 200 | backend process 응답 |
| readiness | `http://127.0.0.1:8000/ready` | 200 | DB/runtime readiness OK |
| dashboard summary | `http://127.0.0.1:8000/api/v1/dashboard/summary` | 200 | mobile 주요 API 응답 |
| analysis session 생성 | `POST http://127.0.0.1:8000/api/v1/supplements/analysis-sessions` | 201 | supplement analysis session 생성 가능 |
| Android emulator Host | `GET /health`, `Host: 10.0.2.2:8000` | 200 | emulator Host header 허용 확인 |

---

## 3. 원인 분리

현재까지 확인한 바로는 "서버 프로세스 미기동"이 아니라 다음 가능성이 더 크다.

- health check URL을 `/api/v1/health`로 잘못 호출해 404를 서버 장애처럼 본 경우
- Android emulator는 host backend 접근 시 `10.0.2.2:8000/api/v1`를 사용해야 하는데, iOS용 `127.0.0.1:8000/api/v1` 설정이 남아 있는 경우
- backend `ALLOWED_HOSTS` 또는 gateway header 설정이 Android Host header를 허용하지 않는 경우
- OCR/YOLO/Ollama 일부 기능이 degraded 상태여서 분석 기능 실패를 전체 서버 장애로 오해한 경우

---

## 4. 모바일 코드 확인 기준

- `mobile/lib/core/api/api_client.dart`
  - base URL은 path와 결합되므로 `LEMON_API_BASE_URL`은 `/api/v1`까지 포함해야 한다.
  - timeout은 `ApiError(statusCode: 408)`로 변환되어 사용자에게 서버 지연으로 보일 수 있다.
  - socket/client network failure는 `ApiError(code: network_unavailable, statusCode: 0)`로 변환한다.

- `mobile/lib/features/supplements/supplement_repository.dart`
  - dashboard, supplement analyze, meal analyze, analysis session API가 모두 base URL 기준 상대 path로 호출된다.

---

## 5. 이번 보완

- `backend/Nutrition-backend/src/config.py`: 개발 기본 `DEFAULT_ALLOWED_HOSTS`에 `10.0.2.2` 추가
- `backend/Nutrition-backend/tests/unit/test_security_middleware.py`: `Host: 10.0.2.2:8000` 통과 테스트 추가
- `mobile/lib/core/api/api_client.dart`: `SocketException`, `http.ClientException` 사용자 오류 변환 추가
- `mobile/test/unit/api_client_robustness_test.dart`: network failure 매핑 테스트 추가

## 6. 남은 확인 후보

- Android/iOS 각각의 `LEMON_API_BASE_URL` build define이 현재 실행 앱에 반영됐는지 확인
- 분석 실패가 서버 연결 실패인지, OCR/YOLO/Ollama pipeline degraded인지 로그로 분리
- 운영 배포에서는 개발 기본 allowlist가 아니라 환경별 `ALLOWED_HOSTS`를 명시 설정
