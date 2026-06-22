# ML 팀원 인수인계 — 영양제 OCR 통합 테스트용

> 이 문서는 ML 팀원이 `Lemon_Aid` 코드를 받아 OCR 모델을 백엔드/모바일에 통합 테스트할 때 필요한 **별도 전달 파일/키** 안내서.
> Git 에는 보안상 안 올라가 있으니 **카톡 1:1 / 1Password / USB 등 안전한 채널**로 따로 받아야 함.

---

## 1. 필요한 별도 파일 (4개)

### (1) `backend/.env`
백엔드 (FastAPI) 실행에 필요한 시크릿.

```env
# Database (Docker 로 자동 기동)
POSTGRES_USER=lemon
POSTGRES_PASSWORD=lemon1234
POSTGRES_DB=lemon_aid
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# JWT (개발용 — 운영 시 회전)
JWT_SECRET=<태동에게 받기>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis (Docker 로 자동 기동)
REDIS_URL=redis://localhost:6379/0

# 구글 OAuth (실제 키 받기)
GOOGLE_CLIENT_ID=<태동에게 받기>

# 카카오 OAuth (실제 키 받기 — 또는 비워둬도 OK)
# KAKAO_REST_API_KEY=

# 이메일 발송 (인증 코드 — Resend)
RESEND_API_KEY=<태동에게 받기>
EMAIL_FROM=Lemon Aid <noreply@lemonade.ai.kr>
```

**받는 방법**: 태동에게 1:1 카톡으로 요청.

---

### (2) `data/.env` (선택 — OCR 모델 외 데이터 수집 안 하면 불필요)
크롤링/데이터셋용 API 키들. **OCR 통합 테스트만 할 거면 안 받아도 됨.**

필요한 경우만:
```env
NAVER_CLIENT_ID=<>
NAVER_CLIENT_SECRET=<>
PUBLIC_DATA_API_KEY=<>
MFDS_API_KEY=<>
HUGGINGFACE_TOKEN=<>
ROBOFLOW_API_KEY=<>
WANDB_API_KEY=<>
```

---

### (3) 모바일 빌드 키 (dart-define 으로 주입)
모바일 앱 빌드 시 환경변수로 넘김. **`.env` 파일 X — PowerShell 환경변수**.

```powershell
# 한 번만 등록 (User scope)
[System.Environment]::SetEnvironmentVariable("KAKAO_NATIVE_APP_KEY", "<태동에게 받기>", "User")
[System.Environment]::SetEnvironmentVariable("GOOGLE_SERVER_CLIENT_ID", "<태동에게 받기>", "User")

# 백엔드 API URL (실기기 또는 다른 PC 면 호스트 IP)
[System.Environment]::SetEnvironmentVariable("LEMON_API_BASE_URL", "http://10.0.2.2:8000", "User")
```

⚠️ 등록 후 VS Code / 터미널 **완전히 닫고 재시작**.

또는 빌드 명령어에 직접 박기 (1회용):
```powershell
flutter run `
  --dart-define=KAKAO_NATIVE_APP_KEY=xxxxx `
  --dart-define=GOOGLE_SERVER_CLIENT_ID=xxxxx.apps.googleusercontent.com `
  --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

OCR 만 테스트하면 KAKAO/GOOGLE 키는 필수 아님 (이메일 가입으로 진행 가능).

---

### (4) (선택) 영양제 이미지 샘플
- 위치: `D:\Lemon_Aid_data\downloads_tampermonkey\lemon-aid\_inbox\tampermonkey\naver\<카테고리>\` (현재 약 14만 장)
- 용량 크니까 USB 또는 외장 SSD 로 받아가는 게 빠름
- 또는 카테고리 1~2개만 골라서 받기 (5천~1만 장 정도)
- Git 에는 절대 안 올라감

---

## 2. 받은 후 환경 세팅 순서

### Step 1. 저장소 클론
```powershell
git clone -b taedong-design https://github.com/Lemon-Aid-KDT/Lemon-sin.git
cd Lemon-sin
```

### Step 2. 백엔드 셋업
```powershell
# .env 파일을 backend/ 아래에 직접 만들거나 받은 거 복사
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Docker (Postgres + Redis) 기동
cd ..
docker compose up -d

# DB 마이그레이션
cd backend
alembic upgrade head

# 서버 실행
uvicorn src.main:app --reload --port 8000
```

브라우저: `http://localhost:8000/docs` (Swagger UI) → API 동작 확인.

### Step 3. 모바일 셋업
```powershell
cd ..\mobile
flutter pub get
flutter run
```

에뮬레이터 자동 감지 → 빌드 → 회원가입 흐름 진행 가능.

---

## 3. OCR 통합 작업 시 손볼 위치

### 모바일 측
| 파일 | 역할 |
|---|---|
| `lib/screens/camera_screen.dart` | 카메라 촬영 화면 (현재 셸 상태) |
| `lib/services/api_client.dart` | Dio 기반 HTTP 클라이언트, 토큰 자동 갱신 |
| `lib/providers/analysis_provider.dart` | 분석 상태 Riverpod (촬영 → 백엔드 → 결과) |

### 백엔드 측
| 파일 | 역할 |
|---|---|
| `backend/src/api/` | API 라우터 — 분석 엔드포인트 추가 위치 |
| `backend/src/ocr/` | OCR 모듈 (PaddleOCR 통합 자리) |
| `backend/src/agents/` | 분석 에이전트 (5종 출력 로직) |
| `backend/src/algorithms/` | 영양소 계산 알고리즘 |

### 흐름 (구현 가이드)
1. 모바일: 카메라/갤러리에서 이미지 → multipart 로 백엔드 `/api/v1/analysis/supplement` 같은 엔드포인트로 POST
2. 백엔드: 이미지 받음 → `src/ocr/paddle.py` (신규) → 텍스트 추출 → `src/agents/supplement_analyzer.py` (신규) → 5종 출력 산출
3. 모바일: 결과 JSON 받음 → `analysis_provider` 에 저장 → 결과 화면 표시

---

## 4. 주의사항

### 보안
- ❌ `.env`, `.env.local`, API 키 절대 커밋 금지 (.gitignore 잡혀있긴 함)
- ❌ Slack/Discord 같은 공개 채널에 키 붙여넣기 금지
- ✅ 키 노출 의심 → 즉시 발급 회전 (구글 콘솔, 카카오 디벨로퍼스)

### 의료법 준수 (의료법 §27, 약사법 §65)
모든 사용자 보이는 출력에서 **절대 금지** 표현:
- "진단", "처방", "치료", "효능", "효과" (질병 특정)

OCR 결과를 화면에 표시할 때도 이 원칙 지킬 것. 면책 문구 무조건 노출.

### Git
- 작업 브랜치: `taedong-design` (메인 푸시 금지)
- 본인 작업은 별도 브랜치 (예: `sunghoon-ocr`) → PR
- 메인/main 브랜치 직접 푸시 절대 X

---

## 5. 막혔을 때

| 증상 | 해결 |
|---|---|
| `flutter pub get` 실패 | pubspec.yaml 의 핀된 버전 유지 (riverpod 2.5.1, google_sign_in 6.2.2). `--major-versions` 절대 X |
| 백엔드 500 | `docker ps` 로 Postgres 떠있는지 확인 |
| 401 Unauthorized | JWT_SECRET 일치 확인, 토큰 만료 시 자동 refresh |
| OAuth "키 미설정" 모달 | dart-define 환경변수 등록 후 VS Code 재시작 |
| 이메일 인증 코드 안 옴 | Resend 키 확인. 임시로 백엔드 로그에 `[email] 코드: 123456` 출력됨 |

---

## 6. 참고 문서
- `mobile/FRONTEND_GUIDE.md` — 모바일 코드 구조, 디자인 시스템, 위젯 가이드
- `PROJECT_GUIDE.md` — 프로젝트 전체 가이드 (5종 출력 메타, R&R 등)
- `HOTKEYS.md` — VS Code 단축키, Docker 명령어, 자주 막히는 거 해결법

---

## 문의

태동 (프론트엔드 / 팀장)
