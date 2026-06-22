# Lemon Aid 프론트엔드 가이드

> 머신러닝 / 디자인 / 백엔드 팀이 모바일 앱 코드를 받아 볼 때 읽는 안내서.
> 현재 시점: 회원가입 플로우(10 step) + 로그인 + 약관 모달 + 디자인 시스템(LADS) 완성.

---

## 1. 빠른 시작 (앱 한 번 띄워보기)

### 필요한 거
- Flutter SDK 3.24+ (Dart 3.4+)
- Android Studio 또는 Android SDK + 에뮬레이터 (Pixel 7 API 34 권장)
- (선택) VS Code + Flutter extension

### 명령
```powershell
cd Lemon_Aid/mobile
flutter pub get
flutter run
```

에뮬레이터 자동 감지 후 빌드 → 설치 → 실행.
재실행 빠르게: `r` (Hot Reload) / `R` (Hot Restart, 코드 구조 변경 시).

### 빌드 깨질 때
```powershell
flutter clean
flutter pub get
flutter run
```

---

## 2. 디자인 시스템 (LADS)

**위치**: `lib/utils/design_tokens_v2.dart`

모든 색·간격·폰트는 이 파일 토큰 통해서만 사용. 직접 hex/숫자 박지 말 것 (§17 일관성).

### 컬러
```dart
AppColor.brand        // #FFC700 (Lemon Yellow — 메인 브랜드)
AppColor.brandDeep    // #C99100 (강조 텍스트, floating label)
AppColor.brandSoft    // #FFF6CC (옅은 노랑 — 면책 박스)
AppColor.ink          // #1A1F2C (본문 텍스트)
AppColor.inkSecondary // #5A6478 (서브 텍스트)
AppColor.inkTertiary  // #8A92A5 (플레이스홀더, 미세 안내)
AppColor.surface      // #FFFFFF (카드/박스 배경)
AppColor.bg           // #FFFFFF (페이지 배경)
AppColor.border       // #EEF1F6 (얇은 분리선)
AppColor.section      // #F2F4F6 (섹션 배경, 회색 버튼)
AppColor.danger       // #FF4D4F (에러)
```

### 간격
```dart
AppSpace.xs  4
AppSpace.sm  8
AppSpace.md  12
AppSpace.lg  16
AppSpace.xl  24
AppSpace.sectionGap  28  // 섹션 사이
AppSpace.page        24  // 페이지 좌우 padding 표준
AppSpace.pageTop     24
AppSpace.pageBottom  32
AppSpace.cardInside  20
```

### 폰트 (Pretendard, AtoZ Display)
```dart
AppText.display      // 28px, w800 — 대제목 (환영해요)
AppText.title        // 22px, w700 — 페이지 헤더
AppText.subtitle     // 18px, w600 — 카드 타이틀
AppText.bodyLg       // 17px, w500 — 입력 텍스트
AppText.body         // 15px, w500 — 본문
AppText.caption      // 13px, w500 — 부가 설명
AppText.micro        // 11px, w500 — © 같은 작은 글
```

### 라운드
```dart
AppRadius.xs   8
AppRadius.sm   12   // 박스/버튼 표준
AppRadius.md   16
AppRadius.lg   20
AppRadius.xl   24
AppRadius.full 999
```

---

## 3. 표준 위젯 (재사용)

### AppPrimaryButton (utils/design_tokens_v2.dart)
브랜드 노랑 메인 버튼. accent=true 면 노랑+검정, 기본은 색 지정 가능.

```dart
AppPrimaryButton(
  label: '다음',
  accent: true,
  enabled: true,
  onPressed: () { ... },
)
```

### AppSecondaryButton (utils/design_tokens_v2.dart)
흰 배경 + soft 그림자 버튼 (구글 로그인, 회원가입 보조 등).

```dart
AppSecondaryButton(
  label: '구글로 계속하기',
  leading: SvgPicture.asset('assets/icons/google_g.svg'),
  onPressed: () { ... },
)
```

### _FloatingField (screens/auth/signup_flow_screen.dart 내부)
토스 스타일 floating label 입력. 빈 상태에서 라벨이 placeholder 위치, 포커스/입력 시 위로 슬라이드.

```dart
_FloatingField(
  label: '이름',
  controller: _name,
  hasValue: (data.name?.isNotEmpty ?? false),
  onChanged: (v) => ...,
)
```

### _StepHeader
페이지 헤더 (타이틀 + 서브타이틀, 진입 시 stagger fade+slide).

```dart
const _StepHeader(
  title: '어떻게 불러드릴까요?',
  subtitle: '정확한 분석을 위해 기본 정보가 필요해요.',
)
```

### _StaggeredColumn
콘텐츠 항목들을 순차적으로 fade+slide 등장.

```dart
_StaggeredColumn(
  initialDelay: const Duration(milliseconds: 900),  // 헤더 후
  stagger: const Duration(milliseconds: 130),       // 항목 간격
  children: [
    Widget1(),
    Widget2(),
    ...
  ],
)
```

### _ToggleRow + _BrandToggle
Flat 2.0 + Soft UI 토글 (걸음수·운동·활동량 등).

```dart
_ToggleRow(
  label: '걸음수',
  value: data.healthSteps,
  onChange: (v) { data.healthSteps = v; ... },
)
```

---

## 4. 파일 구조 (mobile/)

```
mobile/
├── lib/
│   ├── main.dart                      ← 진입점, KAKAO_NATIVE_APP_KEY 등 환경변수 주입
│   ├── app.dart                       ← 앱 셸 (테마 + 라우터)
│   ├── screens/
│   │   ├── splash_screen.dart         ← 골드 마스코트 로티
│   │   ├── auth/
│   │   │   ├── login_screen_v3.dart   ← 로그인 메인 (카카오/구글/Apple/이메일)
│   │   │   ├── consent_modal.dart     ← 약관 동의 모달 (회원가입 진입 직전)
│   │   │   ├── signup_flow_screen.dart ← 회원가입 10-step PageView (핵심)
│   │   │   ├── signup_screen.dart     ← (legacy) 단순 이메일/비번 폼
│   │   │   ├── verify_email_screen.dart ← 이메일 인증 코드 입력
│   │   │   └── consent_screen.dart    ← (legacy) 약관 전체 화면
│   │   ├── dashboard_screen.dart      ← 메인 (P0 작업 중)
│   │   ├── camera_screen.dart         ← 카메라 촬영
│   │   ├── chat_screen.dart           ← AI 챗
│   │   ├── score_screen.dart          ← 점수
│   │   ├── raffle_screen.dart         ← 추첨/리워드
│   │   ├── health_screen.dart         ← HealthKit/Health Connect
│   │   ├── settings_screen.dart       ← 설정
│   │   └── onboarding_screen.dart     ← (legacy)
│   ├── widgets/                       ← 공용 위젯
│   │   ├── common/
│   │   │   ├── main_shell.dart        ← 5탭 셸 (StatefulShellRoute)
│   │   │   ├── app_modals.dart        ← 공용 bottom sheet
│   │   │   └── ...
│   │   └── ...
│   ├── services/                      ← API/저장소 추상
│   │   ├── api_client.dart            ← Dio + 토큰 자동 갱신
│   │   ├── auth_service.dart          ← /signup, /login, /kakao, /google
│   │   ├── oauth_service.dart         ← 카카오/구글 SDK 호출
│   │   └── token_storage.dart         ← flutter_secure_storage
│   ├── providers/                     ← Riverpod 상태
│   │   ├── auth_provider.dart         ← 인증 상태 + 컨트롤러
│   │   ├── profile_provider.dart
│   │   ├── analysis_provider.dart
│   │   ├── chat_provider.dart
│   │   └── raffle_provider.dart
│   ├── models/                        ← 데이터 모델 (D2 셸 다수)
│   ├── utils/
│   │   ├── design_tokens_v2.dart      ← LADS 토큰 (색/간격/폰트/버튼)
│   │   ├── design_tokens_v3.dart      ← (실험) 새 토큰
│   │   ├── router.dart                ← go_router 정의
│   │   ├── tokens.dart                ← Material 테마 빌더
│   │   └── oauth_config.dart          ← 카카오/구글 키 dart-define
│   └── devtools/
│       └── tokens_preview.dart        ← 디버그 빌드: 토큰 미리보기
├── assets/
│   ├── icons/                         ← SVG (카카오, 구글, Apple 등)
│   ├── illustrations/                 ← PNG (로그인 캐릭터 등)
│   ├── mascot/                        ← 마스코트 (gold-frames, hello-mascot.png 등)
│   ├── animations/                    ← Lottie JSON
│   ├── fonts/                         ← Pretendard, AtoZ, GmarketSans
│   ├── design_system/                 ← 디자인 시안 ref
│   └── app_icon/
├── android/                           ← Android native (manifest, gradle)
├── pubspec.yaml                       ← 의존성 + asset 등록
└── FRONTEND_GUIDE.md                  ← 이 문서
```

---

## 5. 주요 라우트 (lib/utils/router.dart)

| 경로 | 화면 | 비고 |
|---|---|---|
| `/` | Splash | 부트스트랩 + 인증 분기 |
| `/login` | LoginScreenV3 | 메인 로그인 |
| `/signup` | SignupFlowScreen | 회원가입 10-step (?oauth=1, ?consented=1, ?name=, ?email=) |
| `/signup-legacy` | SignupScreen | (legacy) 단순 폼 |
| `/verify-email` | VerifyEmailScreen | 이메일 인증 |
| `/shell/home` | DashboardScreen | 메인 셸 (5탭 첫 화면) |
| `/shell/camera` | CameraScreen | |
| `/shell/chat` | ChatScreen | |
| `/shell/score` | ScoreScreen | |
| `/shell/settings` | SettingsScreen | |

### 가드
- 토큰 없음 + 보호 라우트 → `/login`
- 토큰 있음 + `/login` 직진 → `/shell/home`
- signup_complete 플래그 없으면 OAuth 신규 사용자 흐름

---

## 6. 회원가입 플로우 (signup_flow_screen.dart)

PageView 9 page (이메일 가입 기준):
1. Welcome (환영해요)
2. Profile (이름·생년월일·성별)
3. Email (이메일·인증·비밀번호) — OAuth면 자동 스킵
4. Purpose (도움 목적 — 만성질환·영양제 등)
5. Concerns (관심사 grid)
6. Body (키·몸무게)
7. Healthkit (걸음수·운동·활동량 토글)
8. Review (입력 정보 확인)
9. Dashboard (가입 완료 안내)
10. Terms (약관) — `?consented=1` 면 자동 스킵

### query param
- `oauth=1` : OAuth(카카오/구글) 신규 사용자 → Email 단계 스킵
- `consented=1` : 약관 사전 동의 (login 화면 모달) → Terms 단계 스킵
- `mk=0|1` : 마케팅 동의 여부
- `name=`, `email=` : OAuth 측에서 받은 프로필 프리필

### 데이터 모델 (SignupData)
```dart
class SignupData {
  String? email, password, name, sex;
  DateTime? birthDate;
  bool emailVerified = false;
  Set<String> purposes = {};   // 'chronic' | 'supplement' | 'diet' | 'blood'
  Set<String> concerns = {};   // 'fatigue' | 'chronic' | ... (9종)
  int? heightCm;
  double? weightKg;
  bool healthSteps, healthWorkout, healthActivity;
  bool termsAgree;
}
```

---

## 7. 백엔드 연동 (auth_service.dart)

| 엔드포인트 | 메서드 | 비고 |
|---|---|---|
| `/api/v1/auth/signup` | POST | email/password/displayName |
| `/api/v1/auth/login` | POST | email/password |
| `/api/v1/auth/kakao` | POST | kakao access_token |
| `/api/v1/auth/google` | POST | google id_token |
| `/api/v1/auth/email/send-code` | POST | 인증코드 발송 |
| `/api/v1/auth/email/verify-code` | POST | 인증코드 검증 |
| `/api/v1/auth/refresh` | POST | refresh → access |
| `/api/v1/auth/logout` | POST | refresh 무효화 |

### 토큰 저장
`flutter_secure_storage` → access / refresh JWT + last_login_provider

### 401 자동 처리
`api_client.dart` 의 interceptor 가 401 → refresh 시도 → 실패 시 `onSessionExpired` 콜백.

---

## 8. 카카오/구글 키 주입

빌드 시 dart-define 으로:
```powershell
flutter run \
  --dart-define=KAKAO_NATIVE_APP_KEY=xxxxx \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=xxxxx.apps.googleusercontent.com
```

또는 PowerShell 환경변수 등록 후 자동 주입 (HOTKEYS.md 참조).

---

## 9. 의료법 컴플라이언스 (반드시 지킬 것)

§14 — 모든 사용자 보이는 카피에서 다음 단어 **절대 금지**:
- "진단"
- "처방"
- "치료"
- "효능", "효과" (질병 특정)

허용 표현:
- "건강 관리 도움"
- "정보 참고용"
- "영양 분석"

모든 분석 결과 화면 하단에 의료 면책 문구 노출 (LADS §14.5).
약관 모달에도 면책 박스 표시.

---

## 10. 자주 묻는 거

### Q. 새 화면 추가하려면?
1. `lib/screens/내화면.dart` 작성
2. `lib/utils/router.dart` 에 GoRoute 등록
3. 디자인 토큰만 사용 — 직접 hex/숫자 X
4. 헤더는 `_StepHeader` 또는 동일 톤 위젯 사용
5. 입력은 `_FloatingField`, 버튼은 `AppPrimaryButton/Secondary`

### Q. 회원가입 step 추가/삭제는?
1. SignupData에 필드 추가
2. PageView children 에 새 StepXxx 위젯 추가
3. `_stepKey()` 배열 순서에 키 추가
4. `_canNext()` 에 검증 로직 추가
5. `_TOTAL_STEPS` 상수 조정

### Q. 빌드 안 됨, version solving failed
- pubspec.yaml 에 핀된 버전 (riverpod 2.5.1, google_sign_in 6.2.2 등) 유지
- `flutter pub upgrade --major-versions` 절대 금지 (이전에 사고 남)

### Q. Hot Reload 안 먹는 변경
- main.dart, app.dart, design_tokens, InputDecoration 같은 build-time 변경은 Hot **Restart** (`R`) 또는 `flutter clean` 후 재실행

---

## 11. 디자인 원칙 (요약)

1. **§17 일관성 1순위** — 토큰 외 하드코딩 금지
2. **Flat 2.0 + Soft UI** — 단색 + 옅은 그림자 (blur 16, offset y:5, alpha 20%). 테두리 X
3. **토스 스타일 motion** — 진입 시 stagger fade+slide, easeOutCubic/Quart 600~700ms
4. **시니어 친화** — 라벨 17px+, 충분한 여백 (sectionGap 28)
5. **의료 면책 우선** — 의심되는 표현은 무조건 빼기

---

## 문의

태동 (프론트엔드 리드 / 팀장)
