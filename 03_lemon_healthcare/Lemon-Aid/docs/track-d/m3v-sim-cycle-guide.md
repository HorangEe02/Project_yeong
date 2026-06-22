# M-3-V.B — iOS/Android sim 매뉴얼 e2e cycle guide

> Track D Phase M-3-V (모바일 supplement OCR e2e) 의 시뮬레이터 검증 가이드.
> 사용자가 step-by-step 실행 + 캡처/elapsed_ms/이슈 보고 → 보고서 갱신.

## 0. 준비물

### 하드웨어/툴
- macOS (Apple Silicon 권장 — Ollama LLM inference 속도)
- Xcode 15+ → iOS Simulator (iPhone 15 Pro, iOS 17+)
- Android Studio + AVD (Pixel 7, API 34, x86_64 emulator)
- Docker Desktop (compose v2)
- Flutter SDK ≥ 3.27 (`flutter doctor` 그린)

### 영양제 라벨 사진 5종 (5 시나리오)
| 시나리오 | 카테고리 | 파일명 (제안) | 특성 |
|---|---|---|---|
| A | 종합비타민 | `local-multivitamin-0001.jpg` | 일반 OCR / 다성분 (>=10 ingredients) |
| B | 오메가3 | `local-omega3-0001.jpg` | 영문/한글 혼합 라벨 |
| C | **프로바이오틱스** | `local-probiotics-0001.jpg` | **긴 OCR text (>1KB) — M-3-V.A 핵심 검증** |
| D | 비타민D | `local-vitamin-d-0001.jpg` | 작은 라벨 (OCR 신뢰도 낮음 케이스) |
| E | 칼슘 | `local-calcium-0001.jpg` | 영문 비중 높음 |

**저장 위치**: `backend/tests/fixtures/supplement_labels/`
**라이선스**: 본인 촬영 권장. 외부 출처는 [README.md](../../backend/tests/fixtures/supplement_labels/README.md) 가이드 따름.

---

## 1. 백엔드 가동

```bash
cd 03_lemon_healthcare/yeong-Vision-Nutrition/backend

# 1.1 Docker (Postgres + Redis)
docker compose up -d
docker compose ps              # postgres + redis 모두 healthy 확인
# 포트 매핑: postgres 127.0.0.1:5436, redis 127.0.0.1:6381

# 1.2 Python venv + deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 1.3 .env 설정 (없으면 .env.example 복사 + JWT_SECRET_KEY 채움)
cp .env.example .env  # 이미 있으면 skip
# 편집: JWT_SECRET_KEY=$(openssl rand -hex 32)
# 편집: DATABASE_URL=postgresql+asyncpg://lemon:devonly@localhost:5436/lemon

# 1.4 DB 마이그레이션
alembic upgrade head

# 1.5 uvicorn (background)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# 1.6 health check
curl http://localhost:8000/health
# → {"status":"ok"}

# 1.7 Ollama (사전 가동 확인)
ollama list | grep qwen3.5:9b  # 모델 존재 확인 (없으면 `ollama pull qwen3.5:9b`)
ollama serve &                  # 이미 background 가동중이면 skip
curl http://localhost:11434/api/tags | head -20
```

**예상 결과**: `/health` → 200 OK + Ollama tags 응답에 `qwen3.5:9b` 등장.

---

## 2. iOS Simulator cycle

```bash
cd ../mobile
flutter doctor                  # iOS section 그린 확인
open -a Simulator               # 시뮬레이터 열기
flutter run -d "iPhone 15 Pro"  # 또는 device id 직접 명시
```

### 2.1 회원가입 + 동의
| step | 동작 | [캡처] | 검증 |
|---|---|---|---|
| 2.1.1 | 앱 첫 화면 (Splash → Login redirect) | `ios-signup-01.png` | 로그인 화면 노출 |
| 2.1.2 | "회원가입" 탭 | `ios-signup-02.png` | 입력 폼 노출 |
| 2.1.3 | 이메일/비밀번호 입력 → "다음" | — | validation 통과 |
| 2.1.4 | 프로필 (성별/연령/키/체중) 입력 → "다음" | `ios-signup-03.png` | — |
| 2.1.5 | 동의 매트릭스 — 3개 toggle on (필수+분석+히스토리) | `ios-signup-04.png` | 모든 필수 동의 체크 |
| 2.1.6 | "가입 완료" → 자동 로그인 → 홈 redirect | `ios-signup-05.png` | 토큰 secure storage 저장 + 홈 화면 |

### 2.2 시나리오 A — 종합비타민 (갤러리, 일반 케이스)
1. 홈 → "영양제 등록" 버튼 탭 → 캡처 화면 진입
2. **시뮬레이터에 사진 등록**: Photos 앱 → drag&drop `local-multivitamin-0001.jpg` 또는 `xcrun simctl addmedia booted local-multivitamin-0001.jpg`
3. 앱에서 "갤러리에서 선택" 탭
4. **권한 첫 요청**: "허용" 선택 → 캡처 `ios-A-permission.png` (다이얼로그 확인)
5. 사진 선택 → `image_cropper` 진입 → 라벨 영역 crop → "Done"
6. upload progress 표시 → 캡처 `ios-A-upload.png`
7. 결과 화면 노출 → 캡처 `ios-A-result.png`
   - ingredient list (>=5 성분)
   - 하단 안전 위젯 3종: MedicalDisclaimer(supplement) + EmergencyResources + ConsultProfessional
8. **측정**: 캡처→결과 elapsed (예: 8.2s)

### 2.3 시나리오 B — 오메가3 (카메라)
1. 홈 → "영양제 등록" → "카메라" 탭
2. 시뮬레이터 카메라는 가짜이므로 → 갤러리 fallback (실 기기 테스트 권장)
3. 또는 갤러리에서 `local-omega3-0001.jpg` 선택
4. crop → upload → 결과 (영문/한글 혼합 ingredient name 파싱 확인)
5. 캡처 `ios-B-result.png` + elapsed 기록

### 2.4 시나리오 C — 프로바이오틱스 (긴 OCR, **M-3-V.A 핵심**)
1. `local-probiotics-0001.jpg` 선택 (라벨에 균주명 다수, 영문 비중 큼 → OCR text >1KB)
2. crop → upload
3. **중요**: M-3-V.A 적용 전이면 60s timeout → 500 → AppError("서버 오류")
4. M-3-V.A 적용 후 (read_timeout 120s) → 정상 결과 (60-100s elapsed 예상)
5. 캡처 `ios-C-upload-progress.png` + `ios-C-result.png` + elapsed (특히 중요)

### 2.5 시나리오 D — 비타민D (작은 라벨, OCR 신뢰도 낮음)
1. `local-vitamin-d-0001.jpg` 선택
2. upload → 결과 화면에서 신뢰도 < 0.85 표시 확인
3. OCR text 수정 화면 진입 가능한지 확인 (Phase M-3 의 manual review path)
4. 캡처 `ios-D-low-conf.png` + `ios-D-manual-review.png`

### 2.6 시나리오 E — 칼슘 (영문 비중)
1. `local-calcium-0001.jpg` 선택
2. crop → upload → 영문 ingredient name 파싱 확인 (`name_en` 필드)
3. 캡처 `ios-E-result.png` + elapsed

### 2.7 안전 위젯 클릭 검증
- 결과 화면에서 EmergencyResources 의 전화번호 (예: 1577-0199) 탭
- 시뮬레이터의 dialer 미지원 → 현재 빈 알림 (M-4 에서 Clipboard fallback 추가 예정)
- 캡처 `ios-emergency-tap.png`
- M-4 적용 후 재검증 시 SnackBar "전화번호가 복사되었습니다" 노출 확인

---

## 3. Android Emulator cycle

```bash
# AVD 가동
$ANDROID_HOME/emulator/emulator -avd Pixel_7_API_34 &
adb devices  # emulator-5554 확인
flutter run -d emulator-5554
```

### 3.1 환경 차이 처리
- **백엔드 URL**: Android emulator 는 host loopback `127.0.0.1` 미접근 → `10.0.2.2:8000` 사용
- `lib/core/config/env.dart` 의 `API_BASE_URL` 환경변수 또는 dart-define 활용:
  ```bash
  flutter run -d emulator-5554 --dart-define=API_BASE_URL=http://10.0.2.2:8000
  ```
- network_security_config.xml 의 cleartext domain (`10.0.2.2`) 확인 (Phase M-3-V 추가됨)

### 3.2 시나리오 A-E 반복
iOS 와 동일한 step 흐름. 차이점만 별도 캡처:
- `and-A-permission.png` — Android 권한 다이얼로그 모양 다름
- `and-A-crop-ucrop.png` — UCropActivity (Phase M-3-V) 진입 확인
- `and-C-result.png` — 긴 OCR 시나리오 / read_timeout 120s 효과 확인
- 각 시나리오 결과 화면 + elapsed 기록

### 3.3 Android 특화 검증
- UCropActivity 안정성 (Activity 등록 확인)
- back stack: crop 도중 back → 캡처 화면으로 정상 복귀
- cleartext 도메인 통신 (HTTPS 강제 아님)

---

## 4. 결과 수집

### 4.1 양식 채우기
[`m3v-sim-cycle-report-template.md`](./m3v-sim-cycle-report-template.md) 복사:
```bash
cp m3v-sim-cycle-report-template.md m3v-sim-cycle-results-$(date +%Y-%m-%d).md
```

각 row 의 ✓/✗ + 캡처 파일명 + elapsed_ms + 비고 기입.

### 4.2 캡처 저장 위치
```
03_lemon_healthcare/yeong-Vision-Nutrition/docs/track-d/captures/<date>/
  ├── ios-signup-01.png
  ├── ios-A-result.png
  ├── ...
  ├── and-A-permission.png
  └── ...
```
파일 크기 < 500KB 권장 (PNG 압축 또는 JPEG 변환).

### 4.3 발견 이슈 분류
- **회귀** (이전 M-3 에서 통과했는데 깨짐): 즉시 별도 issue + revert 검토
- **신규 UX 이슈** (스크롤 / 키보드 / 로딩 지연): 보고서 §이슈에 기록 → M-4 또는 별도 phase
- **컴플라이언스 위반** (금지 표현 / 위젯 누락): 즉시 fix + commit

### 4.4 보고서 commit
```bash
git add docs/track-d/m3v-sim-cycle-results-*.md docs/track-d/captures/<date>/
git commit -m "docs(track-d): M-3-V.B sim cycle results $(date +%Y-%m-%d) — <PASS/FAIL summary>"
```

---

## 5. DoD (Definition of Done)

- [ ] 백엔드 + Ollama 가동 확인 (health + tags 200)
- [ ] iOS 5 시나리오 (A-E) 모두 ✓ 또는 ✗ + 캡처
- [ ] Android 5 시나리오 (A-E) 모두 ✓ 또는 ✗ + 캡처
- [ ] 회원가입 + 동의 cycle (2.1) 1회 통과
- [ ] 시나리오 C (긴 OCR) 가 120s 안 통과 — **M-3-V.A 회귀 검증**
- [ ] 발견 이슈 모두 분류 + 후속 액션 명시
- [ ] 보고서 commit + push

---

## 6. 참조

- M-3-V.A timeout 분리: [twinkly-splashing-hejlsberg.md](/Users/yeong/.claude/plans/twinkly-splashing-hejlsberg.md) Phase M-3-V.A
- 백엔드 supplement endpoint: [backend/src/api/v1/supplements.py](../../backend/src/api/v1/supplements.py)
- 모바일 supplement notifier: [mobile/lib/features/supplement/presentation/providers/supplement_notifier.dart](../../mobile/lib/features/supplement/presentation/providers/supplement_notifier.dart)
- 안전 위젯: [mobile/lib/shared/widgets/](../../mobile/lib/shared/widgets/)
- 컴플라이언스: [docs/10-compliance-checklist.md](../10-compliance-checklist.md)
