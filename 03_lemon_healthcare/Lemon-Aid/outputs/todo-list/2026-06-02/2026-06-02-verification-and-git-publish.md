# 2026-06-02 검증 및 GitHub 브랜치 푸시 기록

> 작성 기준: 2026-06-02
> 대상 브랜치: `docs/docs-2026-05-31-backend-ocr-security`

---

## 1. Git 기준

- Git root: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- Push remote: `origin`
- Push URL: `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 개인 repo remote `personal`은 이번 작업에서 사용하지 않는다.

---

## 2. 커밋 포함 파일

이번 커밋 포함 대상:

- `backend/Nutrition-backend/src/config.py`
- `backend/Nutrition-backend/tests/unit/test_config.py`
- `backend/Nutrition-backend/tests/unit/test_security_middleware.py`
- `mobile/lib/core/api/api_client.dart`
- `mobile/test/unit/api_client_robustness_test.dart`
- `outputs/todo-list/2026-06-02/README.md`
- `outputs/todo-list/2026-06-02/2026-06-02-server-runtime-response-check.md`
- `outputs/todo-list/2026-06-02/2026-06-02-server-network-hardening-summary.md`
- `outputs/todo-list/2026-06-02/2026-06-02-verification-and-git-publish.md`

명시적 제외 대상:

- `.env`, `.env.local`, `.vercel/.env.*.local`
- raw OCR/provider payload
- 원본 이미지 데이터셋
- 앱 실행 중 생성된 `.DS_Store`
- 이번 변경과 무관한 기존 untracked 산출물

---

## 3. 검증 명령

```bash
cd mobile
flutter test test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart
flutter analyze lib/core/api/api_client.dart lib/core/config/app_config.dart test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart
```

```bash
cd backend
.venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py
.venv/bin/python -m ruff check Nutrition-backend/src/config.py Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py
```

```bash
curl -sS -m 5 -i http://localhost:8000/health
curl -sS -m 5 -i http://127.0.0.1:8000/ready
curl -sS -m 5 -i http://localhost:8000/api/v1/dashboard/summary
curl -sS -m 5 -i -H 'Host: 10.0.2.2:8000' http://localhost:8000/health
```

```bash
git diff --check
git diff --cached --check
detect-secrets scan <staged files>
```

---

## 4. 검증 결과

### 모바일 단위 테스트

`flutter test test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart`

결과:

```text
17 passed
```

확인된 항목:

- timeout 오류가 기존 408 사용자 메시지로 유지됨
- socket failure가 `network_unavailable`으로 매핑됨
- `package:http` client failure가 `network_unavailable`으로 매핑됨
- iOS/Android/web/local base URL config 기본값 회귀 없음

### 정적 분석

`flutter analyze lib/core/api/api_client.dart lib/core/config/app_config.dart test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart`

결과:

```text
No issues found!
```

### Backend 테스트/린트

`pytest` 결과:

```text
75 passed
```

`ruff` 결과:

```text
All checks passed!
```

확인된 항목:

- default settings에 `10.0.2.2` 포함
- trusted host middleware가 `Host: 10.0.2.2:8000` 요청 허용
- 기존 security middleware 동작 회귀 없음

### Runtime 응답

```text
GET /health -> 200
GET /ready -> 200
GET /api/v1/dashboard/summary -> 200
GET /health with Host: 10.0.2.2:8000 -> 200
```

### Diff whitespace

`git diff --check`

결과:

```text
pass
```

`git diff --cached --check`

결과:

```text
pass
```

### Secret scan

`detect-secrets scan <staged files>`

결과:

```text
results: {}
```

---

## 5. 커밋 메시지 기준

Conventional Commits 형식을 사용한다.

```text
fix(api): harden local backend connectivity errors

Why:
Mobile clients could surface opaque server-response failures when the backend
port was unavailable or when Android emulator requests used the 10.0.2.2 Host
header. Normalizing network failures and allowing the emulator Host in local
defaults keeps simulator debugging actionable without broadening production
settings.

Tested:
- flutter test test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart
- flutter analyze lib/core/api/api_client.dart lib/core/config/app_config.dart test/unit/api_client_robustness_test.dart test/unit/app_config_test.dart
- .venv/bin/python -m pytest --no-cov Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py
- .venv/bin/python -m ruff check Nutrition-backend/src/config.py Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py
- git diff --check
- git diff --cached --check
```
