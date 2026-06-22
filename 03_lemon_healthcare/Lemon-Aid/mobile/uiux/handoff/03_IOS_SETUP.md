# iOS 셋업 가이드 (macOS 팀원용)

> Windows 에서 작업하다 보니 iOS 프로젝트가 미생성 상태.
> 이 문서대로 한 번만 셋업하면 iOS 시뮬레이터/실기기에서 카카오·구글 로그인 작동.

---

## 1. iOS 프로젝트 생성

```bash
cd mobile
flutter create --platforms=ios .
```

→ `ios/Runner.xcodeproj`, `ios/Runner/Info.plist`, `ios/Podfile` 등 자동 생성.

```bash
cd ios
pod install
cd ..
```

---

## 2. Info.plist 수정

`ios/Runner/Info.plist` 열고 `</dict>` 직전에 아래 추가.

### (A) 카카오 SDK URL Scheme

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>kakaoe77b0826818850493f5ffeb1014a0833</string>
    </array>
  </dict>
</array>

<key>LSApplicationQueriesSchemes</key>
<array>
  <string>kakaokompassauth</string>
  <string>kakaolink</string>
</array>
```

⚠️ `kakao` 뒤 문자열은 카카오 네이티브 앱 키. 위 값(`kakaoe77b...`)이 우리 앱 키.

### (B) 카메라/사진/마이크 권한 description (사용자 보이는 안내문)

```xml
<key>NSCameraUsageDescription</key>
<string>영양제·식품 사진을 분석하기 위해 카메라가 필요해요.</string>

<key>NSPhotoLibraryUsageDescription</key>
<string>저장된 사진을 불러와 분석하기 위해 권한이 필요해요.</string>

<key>NSMicrophoneUsageDescription</key>
<string>음성 입력 기능 사용 시 필요해요.</string>
```

### (C) 다크모드 강제 OFF (앱이 항상 라이트 톤)

```xml
<key>UIUserInterfaceStyle</key>
<string>Light</string>
```

---

## 3. 카카오 디벨로퍼스 — iOS 앱 정보 등록

https://developers.kakao.com → 내 애플리케이션 → 플랫폼 → iOS

- **번들 ID**: `com.lemonaid.lemon_aid`
- **스토어 URL**: (빈칸 OK)

---

## 4. 구글 OAuth — iOS 클라이언트 (이미 발급 완료, 아래 값 그대로 사용)

- **iOS Client ID**:
  `402778318501-r0voee5fga2cso9sf1musmp6mj8t4r4a.apps.googleusercontent.com`
- **iOS URL 스킴 (Reversed Client ID)**:
  `com.googleusercontent.apps.402778318501-r0voee5fga2cso9sf1musmp6mj8t4r4a`

`Info.plist` 의 `CFBundleURLTypes` array 에 카카오와 함께 추가:

```xml
<key>CFBundleURLTypes</key>
<array>
  <!-- 카카오 -->
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>kakaoe77b0826818850493f5ffeb1014a0833</string>
    </array>
  </dict>
  <!-- 구글 (Reversed iOS Client ID) -->
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>com.googleusercontent.apps.402778318501-r0voee5fga2cso9sf1musmp6mj8t4r4a</string>
    </array>
  </dict>
</array>
```

⚠️ `.env` 의 `GOOGLE_SERVER_CLIENT_ID` 는 **Web Client ID** (백엔드 검증용) 그대로 유지.
   iOS Client ID 는 native SDK 만 사용 — `Info.plist` 에만 박힘.

---

## 5. .env 셋업

```bash
cp .env.example .env
```

`.env` 열어서 값 채우기 (태동에게 받은 값):

```
KAKAO_NATIVE_APP_KEY=e77b0826818850493f5ffeb1014a0833
GOOGLE_SERVER_CLIENT_ID=xxxxx.apps.googleusercontent.com
API_BASE_URL=http://localhost:8000
```

⚠️ mac iOS 시뮬레이터: `localhost:8000`
⚠️ mac Android 에뮬레이터: `10.0.2.2:8000`

---

## 6. 빌드 & 실행

```bash
cd mobile
flutter pub get
flutter run -d "iPhone 17 Pro"
```

또는:

```bash
open ios/Runner.xcworkspace  # Xcode 로 열기
# Xcode 에서 실기기 선택 → Run
```

---

## 트러블슈팅

| 증상 | 해결 |
|---|---|
| `pod install` 실패 | `sudo gem install cocoapods` 후 재시도 |
| `Could not find Generated.xcconfig` | `flutter pub get` 먼저 실행 |
| 카카오 로그인 fail (앱 안 뜸) | Info.plist 의 URL Scheme 다시 확인 (kakao + 키) |
| 구글 로그인 fail | iOS Client ID 별도 발급 필요 (Web Client ID 아님) |
| 한글 폰트 깨짐 | Pretendard 가 `pubspec.yaml fonts:` 에 등록됐는지 확인 |

문의: 태동 (1:1 카톡)
