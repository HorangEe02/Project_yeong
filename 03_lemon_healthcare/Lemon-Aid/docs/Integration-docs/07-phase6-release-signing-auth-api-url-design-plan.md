# 07. Phase 6 Release Signing/Auth/API URL 정리 상세 설계 및 구현 플랜

- 작성일: 2026-05-17
- 범위: Flutter Android/iOS release signing, dev/staging/prod flavor, API URL/auth secret 정책, backend production/staging 보안 게이트
- 상태: 상세 설계 및 1차 구현 적용
- 선행 기준: [05. P2 Mobile Device Build and Simulator Run Plan](./05-p2-mobile-device-build-run-plan.md), [06. Phase 5 Mobile UX Integration](./06-phase5-mobile-ux-integration-design-plan.md)

## 1. 목표

Phase 6의 목표는 앱 기능 구현과 배포 준비를 분리된 release gate로 고정하는 것이다. 이 단계는 OCR, 추천, 모바일 UI 기능을 더 추가하는 단계가 아니라, 배포 가능한 binary와 public backend가 가져야 할 식별자, 서명, 인증, API URL, 운영 보안 조건을 정리하는 단계다.

핵심 원칙:

1. `com.example...` 식별자는 release artifact에 남기지 않는다.
2. Android release build는 debug signing으로 서명하지 않는다.
3. Android는 upload keystore와 Play App Signing 기준을 분리한다.
4. Flutter flavor는 `dev`, `staging`, `prod`를 분리하고, release URL은 HTTPS만 허용한다.
5. `LEMON_API_TOKEN`을 release binary에 박지 않는다.
6. iOS bundle identifier, distribution certificate, distribution provisioning profile을 App Store/TestFlight gate로 분리한다.
7. backend production과 public staging은 `AUTH_MODE=jwt`만 허용한다.
8. 운영 CORS/TrustedHost는 운영 도메인만 허용한다.
9. backend에는 rate limiting과 OCR/LLM provider readiness check가 있어야 한다.

## 2. 공식 기준

| 기준 | 공식 문서 | 설계 반영 |
| --- | --- | --- |
| Flutter Android release/signing | https://docs.flutter.dev/deployment/android | release app bundle은 `flutter build appbundle` 경로로 만들고, keystore는 app에서 참조하되 secret은 VCS에 저장하지 않는다. |
| Android App Signing | https://developer.android.com/studio/publish/app-signing | Google Play 배포용 app signing key와 개발자가 업로드 artifact에 쓰는 upload key를 분리한다. |
| Flutter flavors | https://docs.flutter.dev/deployment/flavors | `flavorDimensions`와 `productFlavors`로 staging/production 등 flavor별 application id suffix, app name, build variant를 분리한다. |
| Apple distribution provisioning profile | https://developer.apple.com/help/glossary/distribution-provisioning-profile/ | distribution provisioning profile은 App ID와 distribution certificate를 연결하며, export/upload 시 해당 certificate로 app bundle을 서명한다. |

## 3. 현재 구현 진단

### 3.1 Android

현재 파일:

- `mobile/flutter_app/android/app/build.gradle.kts`
- `mobile/flutter_app/android/app/src/main/AndroidManifest.xml`
- `mobile/flutter_app/android/app/src/debug/AndroidManifest.xml`
- `mobile/flutter_app/android/app/src/main/kotlin/com/example/lemon_aid_mobile/MainActivity.kt`

진단:

| 항목 | 현재 상태 | Phase 6 판단 |
| --- | --- | --- |
| application id | `com.example.lemon_aid_mobile` | release 차단. 실제 reverse domain 필요 |
| namespace | `com.example.lemon_aid_mobile` | Kotlin package와 함께 정리 필요 |
| MainActivity package | `com.example.lemon_aid_mobile` | application id 변경 시 package 경로 이동 필요 |
| release signing | `signingConfig = signingConfigs.getByName("debug")` | release 차단. debug signing으로 release 금지 |
| flavor | 없음 | `dev/staging/prod` 분리 필요 |
| debug cleartext | debug manifest에 `usesCleartextTraffic=true` | debug-only라 허용 가능. release manifest에는 없어야 함 |
| Android app label | `Lemon Aid` | flavor별 label 필요 |

비판적 판단: 현재 Android 설정은 release artifact 생성 자체는 가능하더라도, 배포 기준으로는 사용할 수 없다. 특히 debug signing release는 반드시 제거해야 한다.

### 3.2 iOS

현재 파일:

- `mobile/flutter_app/ios/Runner/Info.plist`
- `mobile/flutter_app/ios/Runner.xcodeproj/project.pbxproj`

진단:

| 항목 | 현재 상태 | Phase 6 판단 |
| --- | --- | --- |
| bundle identifier | `com.example.lemonAidMobile` | release 차단. 실제 App ID 필요 |
| code sign identity | `iPhone Developer` | simulator/debug 중심. distribution gate 필요 |
| provisioning | Automatic signing 흔적만 있음 | App Store/TestFlight distribution profile 확인 필요 |
| display name | `Lemon Aid Mobile` | 제품명 기준으로 정리 필요 |
| camera/photo permission | "Supplement label..." | 제품명과 목적은 있으나 App Review 기준으로 더 명확하게 정리 권장 |

비판적 판단: iOS는 실제 Apple Developer Team ID, App ID, distribution certificate/provisioning profile이 없으면 구현만으로 release signing을 완결할 수 없다. Phase 6 구현은 Xcode project 설정 skeleton까지 가능하지만, 실제 signing 검증은 계정/프로파일 준비 후 별도 gate로 둬야 한다.

### 3.3 Flutter runtime config

현재 파일:

- `mobile/flutter_app/lib/core/config/app_config.dart`

진단:

| 항목 | 현재 상태 | Phase 6 판단 |
| --- | --- | --- |
| API base URL | `LEMON_API_BASE_URL`, 기본값 `http://127.0.0.1:8000/api/v1` | dev 기본값으로는 적합. staging/prod release에는 HTTPS 강제 필요 |
| token | `LEMON_API_TOKEN` compile-time define | release binary에 JWT/token을 박는 방식은 금지해야 함 |
| auth runtime | bearer token optional | 실제 앱은 로그인/OIDC flow 또는 secure runtime token provider 필요 |

비판적 판단: `--dart-define=LEMON_API_TOKEN=...`는 local smoke test에는 편하지만 release 방식으로는 부적절하다. release build에서는 token define이 들어오면 build 또는 runtime assert로 실패해야 한다.

### 3.4 Backend

현재 파일:

- `backend/Nutrition-backend/src/config.py`
- `backend/Nutrition-backend/src/main.py`
- `backend/.env.example`

진단:

| 항목 | 현재 상태 | Phase 6 판단 |
| --- | --- | --- |
| production auth | `ENVIRONMENT=production`이면 `AUTH_MODE=jwt` 검증 있음 | 이미 일부 구현됨 |
| staging auth | default는 `AUTH_MODE=disabled`; staging public 여부 검증 없음 | public staging이면 jwt 강제 필요 |
| CORS/TrustedHost | middleware 있음, production wildcard/empty 검증 있음 | staging/prod 도메인 정책을 더 명확히 분리해야 함 |
| rate limiting | 구현 흔적 없음 | 추가 필요 |
| readiness | `/health`는 단순 ok/version | OCR/LLM/provider readiness endpoint 필요 |
| docs | production에서 docs/redoc off | 적절함 |

비판적 판단: production validation은 상당 부분 갖춰져 있지만, staging이 public endpoint로 열리는 순간 `AUTH_MODE=disabled`가 허용될 수 있다. 또한 `/health`가 단순 liveness라서 OCR/LLM provider 준비 상태를 배포 전에 확인할 수 없다.

## 4. 결정이 필요한 값

다음 값은 구현 전 팀이 확정해야 한다. 확정 전에는 placeholder로 구현하면 안 된다.

| 값 | 필요 이유 | 예시 형식 |
| --- | --- | --- |
| Android prod application id | Play Console package name은 사실상 영구 식별자 | `com.company.product` |
| Android staging application id | prod와 별도 설치/테스트 | `com.company.product.staging` |
| iOS prod bundle identifier | Apple App ID와 provisioning profile 매칭 | `com.company.product` |
| iOS staging bundle identifier | TestFlight/internal QA 분리 | `com.company.product.staging` |
| API dev URL | local emulator/simulator smoke | Android `http://10.0.2.2:8000/api/v1`, iOS `http://127.0.0.1:8000/api/v1` |
| API staging URL | public staging HTTPS endpoint | `https://staging-api.example.com/api/v1` |
| API prod URL | production HTTPS endpoint | `https://api.example.com/api/v1` |
| OAuth/OIDC issuer/audience/JWKS | release auth | provider-specific HTTPS values |
| Android upload keystore owner | release artifact signing | CI secret or release manager |
| Apple Team ID | distribution signing | Apple Developer account |

권장: reverse domain은 실제 소유 도메인 확인 후 확정한다. 이 문서는 임의의 실제 도메인을 발명하지 않는다.

## 5. Android 설계

### 5.1 식별자 정리

작업 대상:

- `android/app/build.gradle.kts`
- `android/app/src/main/kotlin/.../MainActivity.kt`

설계:

```kotlin
android {
    namespace = "RELEASE_ANDROID_NAMESPACE"

    defaultConfig {
        applicationId = "RELEASE_ANDROID_APPLICATION_ID"
    }

    flavorDimensions += "environment"
    productFlavors {
        create("dev") {
            dimension = "environment"
            applicationIdSuffix = ".dev"
            resValue("string", "app_name", "Lemon Aid Dev")
        }
        create("staging") {
            dimension = "environment"
            applicationIdSuffix = ".staging"
            resValue("string", "app_name", "Lemon Aid Staging")
        }
        create("prod") {
            dimension = "environment"
            resValue("string", "app_name", "Lemon Aid")
        }
    }
}
```

주의:

- prod `applicationId`는 한 번 Play Console에 올라가면 변경 비용이 크다.
- `namespace`, Kotlin package, AndroidManifest activity resolution을 함께 맞춘다.
- `android:label`은 `@string/app_name`으로 바꿔 flavor별 label을 사용한다.

### 5.2 release signing

현재 금지해야 할 코드:

```kotlin
release {
    signingConfig = signingConfigs.getByName("debug")
}
```

권장 구조:

- `android/key.properties`는 `.gitignore` 대상.
- CI에서는 secret env에서 임시 `key.properties`를 생성한다.
- release build는 upload keystore로 서명한다.
- Play App Signing은 Google Play가 app signing key를 관리하고, 팀은 upload key만 사용한다.

권장 gate:

1. `key.properties`가 없으면 release build fail.
2. debug keystore가 release signing에 연결되어 있으면 fail.
3. `flutter build appbundle --release --flavor prod`가 서명된 `.aab`를 생성해야 함.
4. upload certificate fingerprint를 Play Console App Signing 페이지의 upload certificate와 대조.

### 5.3 flavor별 API URL

Flutter compile-time define은 URL에만 사용한다.

권장 명령:

```sh
flutter run --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1

flutter build appbundle --release --flavor staging \
  --dart-define=LEMON_API_BASE_URL=https://staging-api.example.com/api/v1

flutter build appbundle --release --flavor prod \
  --dart-define=LEMON_API_BASE_URL=https://api.example.com/api/v1
```

금지:

```sh
flutter build appbundle --release --dart-define=LEMON_API_TOKEN=...
```

권장 구현:

- `AppConfig.fromEnvironment()`에서 release mode + non-empty `LEMON_API_TOKEN`이면 실패.
- release mode + non-HTTPS `LEMON_API_BASE_URL`이면 실패.
- dev mode만 `http://127.0.0.1` 또는 `http://10.0.2.2` 허용.
- 실제 인증은 Phase 6-2에서 OAuth/OIDC login flow 또는 platform secure storage 기반 runtime token provider로 분리한다.

## 6. iOS 설계

### 6.1 bundle identifier

현재:

- `com.example.lemonAidMobile`

필요:

- prod: 팀이 확정한 실제 bundle identifier
- staging: prod와 별도 bundle identifier

권장:

- Xcode build configuration 또는 Flutter flavor를 사용해 `PRODUCT_BUNDLE_IDENTIFIER`를 환경별로 분리한다.
- RunnerTests bundle id도 parent bundle id에 맞춰 변경한다.

### 6.2 distribution signing

Apple 공식 기준상 distribution provisioning profile은 App ID와 distribution certificate를 묶고, export/upload 시 그 certificate로 app bundle을 서명한다.

Phase 6 gate:

1. Apple Developer Team ID 확인.
2. App Store Connect app record 생성 또는 기존 record 확인.
3. prod/staging App ID 확인.
4. App Store distribution certificate 확인.
5. distribution provisioning profile 확인.
6. Xcode archive export 또는 `flutter build ipa --release --flavor prod` smoke.

주의:

- Codex가 임의로 certificate/profile을 만들면 안 된다.
- 개인 계정/팀 계정 권한이 필요하므로 수동 확인 checklist와 CI secret 연동으로 분리한다.

### 6.3 권한 문구

현재:

- `NSCameraUsageDescription`: supplement label OCR preview 목적을 설명
- `NSPhotoLibraryUsageDescription`: supplement label OCR preview 목적을 설명

권장 문구:

- `NSCameraUsageDescription`: "Lemon Aid uses the camera to capture supplement labels for review-only OCR extraction."
- `NSPhotoLibraryUsageDescription`: "Lemon Aid uses selected supplement label images to create review-only OCR previews."

한국어 localization을 추가할 경우:

- `InfoPlist.strings`에 한국어 권한 문구를 별도 관리한다.
- 문구는 "복용 추천"이 아니라 "라벨 확인/검토용 OCR preview"로 제한한다.

## 7. Backend 설계

### 7.1 auth mode

현재 production은 `AUTH_MODE=jwt`를 강제한다. Phase 6에서는 staging도 public endpoint면 동일하게 강제한다.

권장 설정:

| environment | endpoint 성격 | AUTH_MODE |
| --- | --- | --- |
| development | local only | `disabled` 허용 |
| staging | public or shared QA | `jwt` 필수 |
| staging | isolated local tunnel only | 예외적으로 `disabled` 가능하나 문서화 필요 |
| production | public | `jwt` 필수 |

권장 구현:

- `Settings`에 `public_endpoint: bool` 또는 `deployment_exposure: local/private/public` 추가.
- `environment in {"staging", "production"}` and public이면 `AUTH_MODE=jwt` 강제.
- staging/prod JWT URL은 HTTPS만 허용.

### 7.2 CORS/TrustedHost

현재:

- `TrustedHostMiddleware`와 `CORSMiddleware` 등록
- production wildcard/empty 방지 검증 있음

Phase 6 보강:

- staging public도 wildcard 금지.
- prod/staging `ALLOWED_HOSTS`는 API 도메인만 허용.
- prod/staging `ALLOWED_ORIGINS`는 모바일 deep link origin이 아니라 실제 web origin이 있을 때만 허용한다.
- 모바일 앱은 CORS 대상이 아니므로 mobile API 호출 때문에 wildcard를 열면 안 된다.

### 7.3 rate limiting

필요 이유:

- supplement image upload, OCR, recommendation explain은 비용과 악용 위험이 크다.
- public staging도 외부에서 접근 가능하면 rate limit이 필요하다.

권장 구조:

- `src/middleware/rate_limit.py`
- Redis 기반 token bucket 또는 sliding window
- key: authenticated subject 우선, 없으면 client IP
- route group별 정책:

| route group | 권장 제한 |
| --- | --- |
| `/api/v1/supplements/analyze` | 낮음. 이미지/OCR 비용 큼 |
| `/api/v1/supplements/analyses/*/ocr-text` | 중간. raw text 크기 제한과 병행 |
| `/api/v1/supplements/recommendations/explain` | 낮음. LLM 설명 보조 비용 |
| 일반 GET dashboard/list | 중간 |
| auth/privacy consent | 낮음. brute-force/abuse 방지 |

정확한 수치는 운영 트래픽 목표가 없으므로 이 문서에서 발명하지 않는다. Phase 6 구현 시 기본값은 보수적으로 두고 환경변수로 조정한다.

권장 env:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_URL=redis://...
RATE_LIMIT_DEFAULT_PER_MINUTE=60
RATE_LIMIT_IMAGE_UPLOAD_PER_MINUTE=5
RATE_LIMIT_LLM_EXPLAIN_PER_MINUTE=10
```

### 7.4 OCR/LLM provider readiness check

현재 `/health`는 liveness만 제공한다. Phase 6에서는 readiness를 분리한다.

권장 endpoint:

- `GET /health` : liveness. DB/OCR/LLM 호출하지 않음.
- `GET /ready` : infrastructure readiness.
- `GET /api/v1/admin/readiness/providers` : 인증/관리자 전용 provider readiness.

readiness 항목:

| provider | check |
| --- | --- |
| DB | simple connection or migration head 확인 |
| Redis | ping |
| Google Vision | 설정 presence + credentials mode + optional dry-run metadata |
| CLOVA | API URL/secret presence + optional lightweight vendor check |
| Local OCR | dependency import/runtime availability |
| Ollama | `/api/tags` 또는 configured model presence |
| KDRI | official 2025 dataset path/manifest status |

보안:

- readiness response는 secret 값을 노출하지 않는다.
- provider failure는 sanitized code로 반환한다.
- production readiness endpoint는 admin scope 또는 private network만 허용한다.

## 8. 상세 구현 플랜

### Phase 6-0. 배포 식별자 확정

목표: irreversible identifier를 먼저 고정한다.

작업:

1. Android prod/staging application id 확정.
2. iOS prod/staging bundle identifier 확정.
3. Apple Team ID와 Play Console app ownership 확인.
4. staging/prod API HTTPS endpoint 확정.
5. OAuth/OIDC issuer/audience/JWKS 확정.

완료 기준:

- 문서화된 identifier matrix가 있고, `com.example`가 남지 않는다.
- API endpoint는 HTTPS이고 `/api/v1` suffix를 포함한다.

### Phase 6-1. Android flavor/signing 구현

작업:

1. `namespace`, `applicationId`, `MainActivity` package 변경.
2. `android:label`을 `@string/app_name`으로 변경.
3. `flavorDimensions += "environment"` 추가.
4. `dev/staging/prod` flavor 추가.
5. release debug signing 제거.
6. upload keystore `key.properties` loader 추가.
7. `.gitignore`에 keystore/key.properties 보장.
8. `flutter build appbundle --release --flavor prod` smoke.

완료 기준:

- release build가 debug signing을 참조하지 않는다.
- `com.example` 검색 결과가 release config에 없다.
- prod/staging/dev가 별도 설치 가능한 application id를 가진다.

### Phase 6-2. Flutter API URL/token guard

작업:

1. `AppConfig`에 release URL guard 추가.
2. release mode에서 `LEMON_API_TOKEN`이 있으면 실패.
3. release mode에서 non-HTTPS API URL이면 실패.
4. dev/staging/prod runbook 명령 추가.
5. 향후 로그인/OIDC token provider TODO를 별도 issue로 분리.

완료 기준:

- release binary에 token을 compile-time define으로 넣을 수 없다.
- staging/prod URL은 HTTPS만 통과한다.

### Phase 6-3. iOS identifier/signing 정리

작업:

1. `PRODUCT_BUNDLE_IDENTIFIER`를 flavor/build configuration별로 분리.
2. display name 정리.
3. 권한 문구를 제품명 기준으로 갱신.
4. App Store distribution profile checklist 문서화.
5. `flutter build ipa --release --flavor prod` 또는 Xcode archive smoke.

완료 기준:

- `com.example` bundle id가 없다.
- distribution profile/certificate가 App ID와 매칭된다.
- permission string이 OCR preview 목적을 정확히 설명한다.

### Phase 6-4. Backend staging/prod auth gate

작업:

1. `Settings`에 deployment exposure flag 추가.
2. staging public이면 `AUTH_MODE=jwt` 강제.
3. staging/prod wildcard CORS/host 금지.
4. `.env.example`을 dev/staging/prod 섹션으로 나눈다.
5. 설정 검증 테스트 추가.

완료 기준:

- public staging에서 `AUTH_MODE=disabled`가 validation error를 낸다.
- staging/prod CORS/TrustedHost wildcard가 validation error를 낸다.

### Phase 6-5. Backend rate limiting

작업:

1. rate limit settings 추가.
2. Redis 기반 middleware 또는 dependency 추가.
3. route group별 limit mapping 추가.
4. 429 response schema와 OpenAPI example 추가.
5. integration tests 추가.

완료 기준:

- image upload/explain endpoint가 제한 초과 시 429를 반환한다.
- auth subject 기준 제한이 IP 기준보다 우선한다.
- Redis 장애 시 fail-open/fail-closed 정책이 명확하다. 권장: production은 fail-closed for costly OCR/LLM, fail-open for `/health`.

### Phase 6-6. Provider readiness

작업:

1. `/ready` endpoint 추가.
2. provider readiness service 추가.
3. Google Vision/CLOVA/local OCR/Ollama/KDRI readiness check 구현.
4. secret redaction 테스트 추가.
5. production admin/private access 정책 적용.

완료 기준:

- `/health`는 가볍게 유지된다.
- `/ready`는 provider 준비 상태를 sanitized code로 반환한다.
- OCR/LLM secret은 response/log에 노출되지 않는다.

### Phase 6-7. CI/release runbook

작업:

1. Android dev/staging/prod build 명령 문서화.
2. iOS archive/export 명령 문서화.
3. backend staging/prod env validation 명령 문서화.
4. release checklist를 PR template 또는 docs에 추가.
5. 보호 브랜치에서는 PR 기반 release를 기본값으로 한다.

완료 기준:

- 팀원이 로컬/CI에서 같은 명령으로 release gate를 재현할 수 있다.
- direct push 대신 PR 기반 release gate를 통과한다.

## 9. 1차 구현 체크포인트

2026-05-17 기준 실제 코드 반영 범위:

| 항목 | 반영 파일 | 상태 |
| --- | --- | --- |
| Flutter release URL/token guard | `mobile/flutter_app/lib/core/config/app_config.dart`, `mobile/flutter_app/test/unit/app_config_test.dart` | release mode에서 `LEMON_API_TOKEN`과 non-HTTPS URL을 차단 |
| Android flavor/signing gate | `mobile/flutter_app/android/app/build.gradle.kts`, `mobile/flutter_app/android/key.properties.example`, `mobile/flutter_app/android/gradle.properties` | `dev/staging/prod` flavor 추가, release debug signing 제거, release task에서 real application id와 keystore 필수화 |
| iOS 권한 문구 | `mobile/flutter_app/ios/Runner/Info.plist` | 제품명과 OCR preview 목적 기준으로 문구 정리 |
| Backend public staging auth gate | `backend/Nutrition-backend/src/config.py`, `backend/Nutrition-backend/tests/unit/test_config.py` | `ENVIRONMENT=staging` + `DEPLOYMENT_EXPOSURE=public`이면 JWT, HTTPS JWKS, explicit host/origin, rate limit 필수 |
| Backend rate limiting | `backend/Nutrition-backend/src/middleware/rate_limit.py`, `backend/Nutrition-backend/src/main.py` | 단일 프로세스 fixed-window middleware 추가, image upload/explain bucket 분리 |
| Backend provider readiness | `backend/Nutrition-backend/src/services/readiness.py`, `backend/Nutrition-backend/src/models/schemas/readiness.py`, `backend/Nutrition-backend/src/main.py` | `/ready` endpoint와 secret redaction 테스트 추가 |

남은 release blocker:

1. 실제 Android `LEMON_ANDROID_APPLICATION_ID`와 Kotlin package/namespace 최종 확정.
2. 실제 iOS prod/staging bundle identifier, Apple Team ID, distribution profile 확정.
3. staging/prod HTTPS API endpoint와 OAuth/OIDC issuer/audience/JWKS 확정.
4. rate limit store를 Redis 공유 저장소로 교체할지 결정. 현재 구현은 single-process smoke/staging guard이며 multi-instance production에는 부족하다.

## 10. 테스트 계획

### Android

```sh
cd yeong-Lemon-Aid/mobile/flutter_app
flutter build apk --debug --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
flutter build appbundle --release --flavor staging \
  --dart-define=LEMON_API_BASE_URL=https://staging-api.example.com/api/v1
flutter build appbundle --release --flavor prod \
  --dart-define=LEMON_API_BASE_URL=https://api.example.com/api/v1
```

Negative tests:

- release + `LEMON_API_TOKEN` should fail.
- release + `http://` should fail.
- release signing missing keystore should fail.

### iOS

```sh
cd yeong-Lemon-Aid/mobile/flutter_app
flutter build ios --simulator --debug --flavor dev \
  --dart-define=LEMON_API_BASE_URL=http://127.0.0.1:8000/api/v1
flutter build ipa --release --flavor prod \
  --dart-define=LEMON_API_BASE_URL=https://api.example.com/api/v1
```

Negative tests:

- `com.example` bundle id remains should fail review gate.
- release + non-HTTPS API URL should fail.
- missing distribution profile should fail signing gate.

### Backend

```sh
cd yeong-Lemon-Aid/backend
ENVIRONMENT=production AUTH_MODE=disabled ../.venv/bin/python -c "from src.config import Settings; Settings()"
ENVIRONMENT=staging DEPLOYMENT_EXPOSURE=public AUTH_MODE=disabled ../.venv/bin/python -c "from src.config import Settings; Settings()"
../.venv/bin/python -m pytest Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/unit/test_security_middleware.py -q --no-cov
```

Negative tests:

- production/staging public wildcard `ALLOWED_ORIGINS=["*"]` fails.
- production/staging public wildcard `ALLOWED_HOSTS=["*"]` fails.
- readiness response does not include API keys, secrets, JWTs, OCR payloads, or raw model outputs.

## 11. Release gate checklist

배포 전 반드시 모두 통과해야 한다.

- [ ] Android prod application id 확정.
- [x] Android release signing에서 debug key 제거.
- [ ] Android upload keystore가 VCS에 없음.
- [ ] Play App Signing upload certificate 등록 확인.
- [ ] Android `dev/staging/prod` flavor build 성공.
- [ ] iOS bundle identifier 확정.
- [ ] Apple distribution provisioning profile과 distribution certificate 확인.
- [x] iOS permission string 제품명 기준 정리.
- [ ] staging/prod API URL HTTPS.
- [x] release build에 `LEMON_API_TOKEN` 미포함 guard.
- [x] backend production `AUTH_MODE=jwt`.
- [x] public staging `AUTH_MODE=jwt`.
- [x] CORS/TrustedHost 운영 도메인만 허용하도록 validation 보강.
- [x] rate limiting enabled validation 및 middleware 추가.
- [x] OCR/LLM provider readiness check 추가.
- [x] secret redaction 테스트 추가.

## 12. 예상 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| application id/bundle id를 나중에 변경 | store identity, push, auth redirect, analytics 모두 영향 | Phase 6-0에서 확정 전 구현 금지 |
| release debug signing 잔존 | Play/App Store 배포 부적합, 보안 리스크 | CI에서 debug signing 문자열 grep gate |
| release binary token 주입 | 인증 우회/토큰 유출 | `LEMON_API_TOKEN` release guard |
| staging auth disabled | public QA endpoint 데이터 노출 | `DEPLOYMENT_EXPOSURE=public`이면 jwt 강제 |
| wildcard CORS/host | origin/host abuse | staging/prod wildcard validation |
| OCR/LLM readiness 미흡 | 배포 후 분석 기능 장애 | `/ready`와 provider-specific sanitized checks |
| rate limit 부재 | OCR/LLM 비용 폭증, abuse | costly route 우선 rate limit |
| signing secret 관리 미흡 | keystore/certificate 유출 | VCS 제외, CI secret, rotation runbook |
