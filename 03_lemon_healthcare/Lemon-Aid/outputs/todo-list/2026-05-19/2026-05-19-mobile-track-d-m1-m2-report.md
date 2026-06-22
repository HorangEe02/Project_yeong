# 2026-05-19 — Mobile Track D Phase M-1 + M-2 작업 보고

작성: 2026-05-19
브랜치: `claude/inspiring-cannon-a70b91`
베이스: `f7c698c6` (트랙 B 완료점 = OCR/Ollama/KDRIs/JWT/disclaimer 풀스택)
worktree: `.claude/worktrees/inspiring-cannon-a70b91/03_lemon_healthcare/yeong-Vision-Nutrition/mobile/`

## 1. 개요

빈 `mobile/` 디렉터리(`CLAUDE.md` 631줄만 존재) 에 Flutter 모바일 트랙(트랙 D) 을 부트스트랩하고 인증 + 회원가입 + 동의 매트릭스 흐름까지 완성했다. 트랙 D 의 전체 5 phase 중 **M-0/M-1/M-2** 가 완료되어 PR 가능 상태.

| Phase | 상태 | 산출물 |
|---|---|---|
| M-0 | ✓ artifact | `/Users/yeong/.claude/plans/lemon-mobile/INDEX.md` + 5 phase plan 파일 |
| M-1 | ✓ commit `c1fb3205` | Flutter 부트스트랩 (Riverpod + Dio + go_router + secure_storage + 면책 위젯) |
| M-2 | ✓ commit `72d842a2` | 인증 + 회원가입 + 동의 매트릭스 + 401 refresh interceptor |
| M-3 | 대기 | 영양제 사진 등록 (capture → upload → result) |
| M-4 | 대기 | 면책 / 응급자원 / 상담권장 위젯 polish |
| M-5 | 대기 | Patrol full-flow E2E |

## 2. 결과 지표

| 항목 | 값 |
|---|---|
| flutter analyze | **No issues found** (0 warnings) |
| flutter test | **All 24 tests passed** (M-1 10 + M-2 14) |
| build_runner | **812 outputs** (riverpod / freezed / json_serializable 생성 파일) |
| 시크릿 staged | **0건** (.env / GOOGLE_APP / JWT_SECRET 검사 통과) |
| 의료 금지표현 grep | **0건** (사용자 노출 텍스트 전수 검수) |
| 신규 파일 (mobile/) | 28 Dart source + 4 test + 4 native config + 2 meta |
| 라인 변경 | +4,266 (M-1 +2,656 / M-2 +1,610) |
| 신규 Flutter 의존성 | 14 deps + 11 dev_deps |

## 3. Phase M-1 (commit `c1fb3205`)

### 핵심 산출

- **`pubspec.yaml`** — flutter_riverpod / dio / pretty_dio_logger / go_router / flutter_secure_storage / image_picker / image_cropper / permission_handler / google_fonts / url_launcher / intl / logger + dev (very_good_analysis / build_runner / riverpod_generator / freezed / json_serializable / mocktail / patrol)
- **`analysis_options.yaml`** — very_good_analysis include + strict-casts/inference. mobile/CLAUDE.md 와 충돌하는 룰 (omit_local_variable_types, always_use_package_imports, sort_pub_dependencies 등) 비활성
- **`lib/main.dart` + `lib/app.dart`** — ProviderScope + MaterialApp.router + Material 3 + Noto Sans KR + Locale('ko','KR')
- **`lib/core/`** — config(Env), theme(Lemon Yellow #FFD700 + Material 3), routing(@riverpod GoRouter), network(Dio + 3 interceptors), storage(flutter_secure_storage 래퍼 + TokenStorage), utils(logger)
- **`lib/shared/widgets/`**:
  - `disclaimer.dart` — `MedicalDisclaimer(variant)` + `DisclaimerVariant` enum (main/supplement/weightPrediction) + `DisclaimerStrings` const (백엔드 `safety/disclaimer.py` 와 1:1 동기)
  - `emergency_resources.dart` — 응답 + 자체 본문 (정신건강위기 1577-0199 / 자살예방 109 / 응급의료 1339) + url_launcher tel:
  - `consult_professional.dart`, `app_loading.dart`, `app_error.dart`
- **`lib/shared/models/`** — Freezed: `ApiError`, `EmergencyContact`
- **iOS `Info.plist`** — NSCameraUsageDescription / NSPhotoLibraryUsageDescription / NSPhotoLibraryAddUsageDescription (한국어) + LSApplicationQueriesSchemes(tel)
- **Android `AndroidManifest.xml`** — INTERNET / CAMERA / READ_MEDIA_IMAGES / READ_EXTERNAL_STORAGE(maxSdkVersion 32) + queries tel
- **테스트** — auth_interceptor_test (Bearer 첨부 / TokenStorage 라이프사이클), disclaimer_test (3 variant), emergency_resources_test (fallback 3건 + 전달 시나리오)

### 의식적 deviation (dev-guide 10 → 사용자 prompt)

| 항목 | 변경 | 사유 |
|---|---|---|
| HTTP | retrofit 제외, raw Dio + freezed | 사용자 deps 목록 |
| 로깅 | dio_logger → pretty_dio_logger | 실제 pub.dev 패키지명 정합 |
| HealthKit | 제외 | 트랙 D 스코프 외 |
| fl_chart | 제외 | 대시보드 스코프 외 |

## 4. Phase M-2 (commit `72d842a2`)

### 핵심 산출 (auth feature, 신규 10 파일)

- **`features/auth/domain/`**
  - `auth_models.dart` (Freezed): `TokenResponse`, `ProfileInput`, `Sex` enum, `ConsentAccept`, `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `User`. `fieldRename: FieldRename.snake` + `MedicationMap` typedef (freezed `@Default(<Map<...>>)` 파서 버그 회피)
  - `auth_state.dart`: sealed `AuthState` (Unauthenticated / Authenticating / Authenticated(User) / AuthFailed(message))
  - `auth_errors.dart`: `ConsentRequiredException` / `EmailAlreadyExistsException` / `InvalidCredentialsException` / `RefreshFailedException`
- **`features/auth/data/auth_repository.dart`** — Dio raw call. 422 + `detail.code == "consent_required"` → `ConsentRequiredException(missing: List<String>)` 매핑. 409 → `EmailAlreadyExistsException`. 401 → `InvalidCredentialsException` / `RefreshFailedException`
- **`features/auth/presentation/providers/auth_notifier.dart`** — `@riverpod AuthNotifier`. `build()` 에서 `TokenStorage.hasTokens()` 로 초기 상태. `login` / `register` / `logout` / `refresh`. register 의 `ConsentRequiredException` 은 호출처가 Step3 복귀시키도록 rethrow
- **`features/auth/presentation/screens/login_screen.dart`** — email/password + 로그인 + 회원가입 진입 + SnackBar 한국어 에러
- **`features/auth/presentation/screens/register_screen.dart`** — 3-step `Stepper`: 계정 → 프로필 → 동의 → register API → 자동 로그인 → `/home`
- **`features/auth/presentation/widgets/`**
  - `email_password_form.dart` — 이메일 정규식 (백엔드 pattern 과 동일) + 비밀번호 8-128자 validator
  - `profile_form.dart` — age slider (1-120) / sex segmented / 키·체중 / 임신·수유·흡연 switch / 만성질환 chip multi-select. medications dynamic list 는 후속 트랙
  - `consent_matrix.dart` — **docs/10 §5.2 별도 동의 화면 원칙**. 필수 2 (`service_terms`, `general_profile`) + 조건부 2 (`chronic_disease` / `medications` — profile 데이터 있을 때만 노출) + 선택 1 (`image_history`). 묶음 동의 X — 각 항목 별도 토글

### 인프라 수정

| 파일 | 변경 핵심 |
|---|---|
| `core/network/interceptors.dart` | `AuthInterceptor` 시그니처 확장 — `TokenStorage` + `refresh` callback + `onLogoutRequested` callback + `retryDio`. 401 + non-/auth/* 경로 시 `_singleFlightRefresh` (Completer 기반 thundering herd 방지) → 새 토큰 저장 → `retryDio.fetch(clone)` 재시도. 실패 시 logout |
| `core/network/dio_provider.dart` | 콜백 wiring — lazy `ref.read` 로 `authRepositoryProvider` / `authNotifierProvider` 와 순환 dep 회피 |
| `core/routing/app_router.dart` | `/login`, `/register`, `/` (home) 라우트 + AuthNotifier 상태 변경 listen → `_RouterRefreshNotifier` 트리거 → `refreshListenable` 로 redirect 재평가. `Unauthenticated` + protected path → `/login`, `Authenticated` + auth route → `/` |
| `features/home/presentation/screens/home_screen.dart` | AppBar logout 버튼 + ConsumerWidget 으로 변경 |
| `analysis_options.yaml` | `strict-raw-types` 일시 비활성 (Dio JSON Map 호환). `cascade_invocations` / `use_if_null_to_convert_nulls_to_bools` 비활성 |

### 테스트 (신규 14 케이스)

- `test/unit/auth/auth_repository_test.dart` — 8 케이스 (login 200/401, register 200/409/422 consent_required (missing 정확 매핑), refresh 200/401)
- `test/widget/auth/consent_matrix_test.dart` — 3 케이스 (필수+선택 표시, 조건부 토글 추가, 필수 모두 on 시 List 전달)
- `test/widget/auth/login_screen_test.dart` (EmailPasswordForm) — 4 케이스 (이메일 빈/형식 오류, 비밀번호 짧음, 정상)
- `test/unit/core/network/auth_interceptor_test.dart` — AuthInterceptor 새 시그니처 (callbacks + retryDio) 헬퍼로 업데이트

### 의식적 deviation (이번 phase)

| 항목 | 결정 | 사유 |
|---|---|---|
| medications 필드 | `typedef MedicationMap = Map<String, Object?>` + `List<MedicationMap>` | freezed `@Default(<Map<String, dynamic>>[])` 의 nested generic 파서 버그 (`>>` malformed) 회피 |
| register 성공 흐름 | 자동 로그인 → `/home` | UX 디폴트 (dev-guide 미상세) |
| LoginScreen 전체 widget test | EmailPasswordForm 단독 test 로 격하 | ProviderScope + AuthNotifier mock 헬퍼는 M-3 와 함께 도입 예정 |
| AuthInterceptor 시그니처 | `Ref` → `TokenStorage` + callbacks 직접 | 테스트 단순화 + DI 명시성 (M-1 변경 + M-2 확장) |

## 5. 컴플라이언스 / 보안 검수

- ✅ **mobile/CLAUDE.md Rule 1** — 사용자 노출 텍스트 의료 금지표현 0건
- ✅ **mobile/CLAUDE.md Rule 5** — 토큰은 `flutter_secure_storage` 만 (SharedPreferences 평문 저장 X)
- ✅ **docs/10 §2.3** — 면책 위젯 (`MedicalDisclaimer`) 모든 권고 화면 하단 필수 (home, supplement_result(M-3))
- ✅ **docs/10 §5.2** — ConsentMatrix 별도 토글 (묶음 동의 X, 조건부 항목은 profile 데이터 있을 때만)
- ✅ **iOS Info.plist / Android Manifest** — 한국어 사용 목적 명시
- ✅ **HTTPS** — `Env.apiBaseUrl` dev/prod 환경 분리 가능 (`--dart-define`)

## 6. PR 구성

- **branch**: `claude/inspiring-cannon-a70b91`
- **base**: `main` (Track B 백엔드 6 commits + docs 2 + scaffold 1 + Mobile M-1/M-2 도 포함됨 — Track B 가 아직 별도 PR 미머지 상태이므로 동시 포함)
- **scope (review focus)**: `03_lemon_healthcare/yeong-Vision-Nutrition/mobile/**`
- **commits ahead of main**: 10 (Track B 7 + Mobile 2 + docs 1)

## 7. 다음 단계 (M-3 ~ M-5)

| Phase | 신규 파일 추정 | 핵심 |
|---|---|---|
| **M-3** | ~13 | SupplementRepository (Dio multipart), SupplementNotifier 4 state, CaptureScreen + 권한 + image_picker + image_cropper, ResultScreen + IngredientCard + StatusChip, DioException → 한국어 매핑 |
| **M-4** | ~3 + tests | EmergencyResources canLaunchUrl 분기 + Clipboard fallback, Disclaimer 다크모드 polish |
| **M-5** | 2 + 1 자산 | Patrol full-flow 시나리오 + simulator 사진 prep 스크립트 |

## 8. 참조

- 루트 plan: `/Users/yeong/.claude/plans/lemon-healthcare-snug-bee.md`
- 트랙 D plan: `/Users/yeong/.claude/plans/lemon-mobile/INDEX.md` + `phase-m{1..5}-*.md`
- mobile 작업 규약: `03_lemon_healthcare/yeong-Vision-Nutrition/mobile/CLAUDE.md`
- 부트스트랩 가이드: `docs/dev-guides/10-mobile-flutter-setup.md`
- 컴플라이언스: `docs/10-compliance-checklist.md` §2.3, §5.2, §10
- 트랙 B 완료점 (백엔드): commit `f7c698c6`
