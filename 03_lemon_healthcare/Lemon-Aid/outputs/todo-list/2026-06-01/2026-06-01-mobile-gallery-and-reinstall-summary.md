# 2026-06-01 Mobile Gallery 및 앱 재설치 요약

> 작성 기준: 2026-06-01
> 범위: Android Pixel 10 Pro Emulator 갤러리 이미지 추가, Android dev 앱 재설치, iPhone 17 Pro Simulator 재설치

---

## 1. Android 갤러리 이미지 추가

요청 범위:

- 사용 이미지 경로는 아래 두 곳으로 제한했다.
  - `data/nutrition_reference/crawling-image`
  - `data/nutrition_reference/sample-image`
- `sample-image`는 현재 이미지 파일이 0장이라 실제 후보는 `crawling-image`에서만 선별했다.
- `crawling-image`의 `상세페이지` 하위 이미지 중 성분표, Supplement Facts, 제품 라벨이 눈으로 식별되는 후보를 골랐다.

적용 결과:

- Pixel 10 Pro Emulator에 아래 앨범을 생성했다.

```text
/sdcard/Pictures/LemonAID-Readable-Labels
```

- 성분표/라벨 확인용 JPEG 20장을 추가했다.
- Android MediaStore scan을 요청했다.
- MediaStore 기준 `LemonAID-Readable-Labels` 이미지 20장 인덱싱을 확인했다.

검증 명령 요약:

```bash
adb push /private/tmp/lemon-readable-label-gallery-20260601-final/. /sdcard/Pictures/LemonAID-Readable-Labels/
adb shell 'for f in /sdcard/Pictures/LemonAID-Readable-Labels/*.jpg; do am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://$f >/dev/null; done'
adb shell find /sdcard/Pictures/LemonAID-Readable-Labels -type f -name '*.jpg' | wc -l
adb shell "content query --uri content://media/external/images/media --projection _display_name:relative_path | grep LemonAID-Readable-Labels | wc -l"
```

주의:

- 갤러리용 임시 export 파일은 `/private/tmp`에 생성했으며 repo에 추가하지 않았다.
- 원본 이미지 전체 경로 목록이나 OCR 원문은 문서에 남기지 않았다.

---

## 2. Android dev 앱 재설치

목적:

- 런처 아이콘이 기존 설치 앱/런처 캐시 때문에 바로 바뀌지 않을 수 있어 앱 삭제 후 재설치를 진행했다.

대상:

```text
com.example.lemon_aid_mobile.dev
```

실행 결과:

- 기존 dev 패키지 삭제 성공
- `mobile/build/app/outputs/flutter-apk/app-dev-debug.apk` 재설치 성공
- `pm path`로 설치된 `base.apk` 경로 확인

검증 명령 요약:

```bash
adb uninstall com.example.lemon_aid_mobile.dev
adb install mobile/build/app/outputs/flutter-apk/app-dev-debug.apk
adb shell pm path com.example.lemon_aid_mobile.dev
```

---

## 3. iOS Simulator 앱 삭제 후 재설치

확인한 대상:

```text
iPhone 17 Pro
UDID: 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB
Runtime: iOS 26.5
```

확인 결과:

- `flutter devices`에서 iPhone 17 Pro Simulator가 연결됨
- `simctl list devices booted`에서 같은 UDID가 Booted 상태임
- Flutter Runner bundle id는 `com.example.lemonAidMobile`

실행 결과:

- `com.example.lemonAidMobile` 실행 중지
- `simctl uninstall`로 기존 Flutter iOS 앱 삭제
- XcodeBuildMCP로 `Runner.xcworkspace` / `Runner` 빌드, 설치, 실행 성공
- 설치 후 새 `Runner.app` 컨테이너 생성 확인
- 화면 캡처로 앱 foreground 실행 확인

중복 앱 정리:

- 예전 native iOS 앱 `yeongs.Lemon-Aid`가 같은 시뮬레이터에 남아 있어 런처에서 `Lemon-Aid`와 `LemonAidMobile`이 함께 보였다.
- 해당 native bundle은 삭제했다.
- 삭제 후 `yeongs.Lemon-Aid` app container 조회가 실패하는 것으로 제거를 확인했다.

검증 명령 요약:

```bash
flutter devices --device-timeout 5
xcrun simctl list devices booted
xcrun simctl uninstall 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB com.example.lemonAidMobile
xcrun simctl get_app_container 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB com.example.lemonAidMobile app
xcrun simctl uninstall 7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB yeongs.Lemon-Aid
```

---

## 4. 남은 주의사항

- 실제 물리 iPhone `박준영의 iPhone`은 아직 `flutter devices`에서 연결되지 않는 경고가 남아 있다.
- 이번 iOS 작업은 부팅된 iPhone 17 Pro Simulator 기준으로 완료했다.
- 촬영 화면의 `Mac camera bridge 8755` 연결 실패 메시지는 앱 재설치 문제가 아니라 bridge 프로세스 미실행 상태다.
- `dev_mac_camera_bridge.py` 또는 동등한 bridge 프로세스를 켜야 Simulator에서 Mac 카메라 preview를 받을 수 있다.
