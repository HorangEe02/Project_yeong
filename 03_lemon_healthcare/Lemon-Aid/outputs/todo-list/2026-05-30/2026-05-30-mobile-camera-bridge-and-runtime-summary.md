# 2026-05-30 Mobile Camera Bridge 및 런타임 검증 요약

> 작성일: 2026-05-30
> 범위: Android/iOS emulator Mac camera bridge, Flutter camera preview 안정화, Android emulator 실행 이슈, 카메라 프로세스 종료

---

## 1. 핵심 결론

Android emulator에서 실제 영양제 촬영 화면에 Mac 카메라 프리뷰가 보이도록 `camera_screen.dart`의 bridge 경로와 preview rendering을 수정했다. 다만 이 기능은 앱 단독 기능이 아니라 개발용 Mac camera bridge가 살아 있어야 동작한다.

검증 과정에서 `launchctl` 백그라운드 job은 카메라 프레임을 받지 못했고, 사용자 세션의 `tmux`에서 실행한 bridge는 `/frame.jpg` JPEG 프레임을 정상 반환했다. 따라서 현재 개발 검증 방식은 `tmux` 기반 bridge 실행으로 기록한다.

---

## 2. 진행한 작업

### 2.1 Flutter camera screen 수정

- 대상 파일: `mobile/lib/screens/camera_screen.dart`
- Android/iOS emulator에서 Mac camera bridge를 사용할 수 있도록 분기했다.
- 기본 bridge URL:
  - Android emulator: `http://10.0.2.2:8755`
  - iOS simulator: `http://127.0.0.1:8755`
- `LEMON_MAC_CAMERA_BRIDGE_URL` dart-define override를 지원한다.
- `Image.memory` preview에 `gaplessPlayback: true`를 유지하고 `filterQuality: FilterQuality.low`를 적용해 렌더링 부담을 낮췄다.
- Mac preview polling interval을 180ms로 조정했다.
- 셔터 버튼에 `HitTestBehavior.opaque`를 적용해 터치가 뒤 UI로 새는 문제를 줄였다.

### 2.2 Widget test 보강

- 대상 파일: `mobile/test/widget/source_camera_screen_test.dart`
- iOS simulator Mac camera bridge preview/capture 테스트를 보강했다.
- Android emulator Mac camera bridge preview/capture 테스트를 보강했다.
- preview image가 `gaplessPlayback == true`, `filterQuality == FilterQuality.low`인지 검증했다.

### 2.3 Mac camera bridge 실행 검증

- 대상 파일: `mobile/scripts/dev_mac_camera_bridge.py`
- 현재 파일은 untracked 상태이므로 커밋 전 포함 여부를 확인해야 한다.
- `launchctl` 실행은 `/health`는 살아도 `/frame.jpg`가 `camera_preview_unavailable`로 실패했다.
- `tmux` 실행은 `/frame.jpg`가 720x1280 JPEG로 정상 확인됐다.
- 개발 검증용 실행 예:

```bash
tmux new-session -d -s lemon-camera-bridge \
  "python3 mobile/scripts/dev_mac_camera_bridge.py --listen-host 127.0.0.1 --listen-port 8755 --ffmpeg-bin /opt/homebrew/bin/ffmpeg --device 0"
```

### 2.4 Android emulator 및 ADB 이슈 분석

- 실제 장치 ID는 `emulator-5554`였다.
- `Pixel_10_Pro` AVD 재시작 시 `ANDROID_SDK_ROOT` 혼동으로 system image 경로를 찾지 못하는 문제가 있었다.
- `flutter emulators --launch Pixel_10_Pro`가 실패할 때는 실제 SDK와 `-sysdir`를 명시해야 했다.
- AVD stale `multiinstance.lock`는 실제 emulator/qemu 프로세스가 없는 것을 확인한 뒤에만 제거해야 한다.

---

## 3. 검증 기록

### 통과한 검증

```bash
flutter test test/widget/source_camera_screen_test.dart
flutter build apk --debug --flavor dev --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1
adb -s emulator-5554 install -r build/app/outputs/flutter-apk/app-dev-debug.apk
```

### 화면 캡처 evidence

- 실시간 프리뷰 1차: `/private/tmp/lemon-5554-newbuild-camera-live-1.png`
- 실시간 프리뷰 2초 후: `/private/tmp/lemon-5554-newbuild-camera-live-2.png`
- 셔터 후 미리보기: `/private/tmp/lemon-5554-newbuild-after-shutter.png`

### 확인한 동작

- `+` 버튼에서 영양제 촬영 메뉴 진입
- `영양제 촬영` 화면에서 Mac camera preview 표시
- 2초 후에도 preview 화면 유지
- 셔터 탭 후 `미리보기` 화면으로 전환

---

## 4. 카메라 종료 작업

검증 이후 Codex/Python 쪽에서 카메라가 계속 켜져 있다는 사용자 요청이 있었다.

확인 결과 Python bridge 본체가 아니라 bridge가 띄운 하위 `ffmpeg -f avfoundation ... -i 0:none` 프로세스가 고아 프로세스(PPID 1)로 남아 Mac 카메라를 계속 잡고 있었다.

처리 내용:

- `com.example.lemon_aid_mobile.dev` 앱 프로세스 강제 종료
- `lemon-camera-bridge` tmux 세션 종료
- 남아 있던 `ffmpeg` 카메라 캡처 프로세스 종료
- 마지막 PID `11346`은 일반 종료 신호로 종료되지 않아 `kill -9 11346`로 강제 종료
- 최종 확인:
  - `pgrep -x ffmpeg` 결과 없음
  - `dev_mac_camera_bridge` Python 프로세스 없음
  - `127.0.0.1:8755` bridge port 닫힘

---

## 5. 남은 TODO

- `mobile/scripts/dev_mac_camera_bridge.py`를 tracked helper로 포함할지 결정한다.
- bridge가 생성한 ffmpeg child process가 부모 종료 시 확실히 함께 종료되도록 script cleanup을 보강한다.
- `camera_screen.dart` 변경 diff를 최종 review하고, emulator 전용 기능이 release build에 노출되지 않는지 확인한다.
- `flutter analyze`를 다시 실행한다.
- 커밋 전 `git diff --check`와 관련 테스트를 다시 실행한다.

---

## 6. 커밋 전 주의사항

- 현재 working tree에는 iOS Runner, old native iOS shell 삭제, app icon, analysis screen 등 여러 변경이 섞여 있다.
- 카메라 bridge 관련 커밋을 만들 경우 최소 대상은 다음으로 제한한다.
  - `mobile/lib/screens/camera_screen.dart`
  - `mobile/test/widget/source_camera_screen_test.dart`
  - 필요 시 `mobile/scripts/dev_mac_camera_bridge.py`
  - 필요 시 이 문서
- `.env`, raw OCR text, provider payload, ngrok URL/token, 개인 이미지 산출물은 stage 금지.

