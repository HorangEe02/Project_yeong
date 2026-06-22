# 2026-05-29 Xcode/Flutter iOS Runner 복구 작업 요약

> 작성일: 2026-05-29
> 범위: `mobile/ios/Runner.xcworkspace` 기준 Flutter iOS 실행 환경 정리, Xcode 경고 원인 분리, 혼동을 일으키는 네이티브 iOS shell 제거 판단

---

## 1. 핵심 결론

이번 섹션에서 iOS 실행 대상은 `mobile/ios/Runner.xcworkspace`와 `Runner` scheme으로 고정했다. `mobile/Lemon-Aid-ios` 네이티브 Swift 프로젝트는 Flutter production flow와 다른 shell이므로 Xcode smoke 대상에서 제외하고, 오래된 혼동을 유발하는 파일로 분류했다.

`No such module 'Flutter'`는 `Runner.xcworkspace` 기준 CLI 빌드가 성공한 상태에서 Xcode SourceKit/index가 늦게 따라오는 증상으로 판단했다. 따라서 `AppDelegate.swift`의 `import Flutter`는 삭제하지 않고, Xcode clean/index refresh와 DerivedData 정리 방향으로 처리했다.

---

## 2. 진행한 작업

### 2.1 Xcode 프로젝트 경로 정리

- Flutter iOS 앱의 기준 경로를 `mobile/ios/Runner.xcworkspace`로 확정했다.
- `Runner.xcodeproj` 단독 열기 또는 `mobile/Lemon-Aid-ios` 네이티브 프로젝트 사용은 혼동 요인으로 분리했다.
- `mobile/Lemon-Aid-ios` 삭제 상태는 git staging에 남아 있으므로, 다음 작업자는 임의로 되돌리지 말고 목적을 확인한 뒤 정리해야 한다.

### 2.2 `No such module 'Flutter'` 분석

- `AppDelegate.swift`의 `import Flutter` 자체는 정상 Flutter iOS 구조에 필요한 import로 유지했다.
- CLI 기준 `xcodebuild` 빌드가 성공한 상태였으므로 코드/Pods가 실제로 깨진 상태가 아니라 Xcode index/SourceKit 지연 문제로 분류했다.
- Xcode에서는 `Product > Clean Build Folder`, 재빌드, 필요 시 Runner 전용 DerivedData 정리 순서로 접근하도록 정리했다.

### 2.3 Xcode warning 분류

- `AX Safe category...`, `FlutterSemanticsScrollView...`, `CA Event...` 계열은 앱 코드 실패가 아니라 Simulator/Xcode runtime 로그로 분류했다.
- `Search path ... Metal.xctoolchain ... not found`와 plugin deprecation warning은 Flutter plugin/Xcode runtime 경고로 분리했다.
- `Stale file ... outside of the allowed root paths`는 `mobile/build/ios/Debug-iphonesimulator` 아래 이전 build artifact가 남아 발생하는 경고로 정리 대상에 포함했다.

### 2.4 Simulator 화면 문제 정리

- 검은 화면은 앱 main LCD가 아니라 `iPhone 17 Pro - External Display` 보조 디스플레이 창을 보고 있었던 문제로 판단했다.
- 앱 화면 검증 기준은 `simctl io <device-id> screenshot`으로 캡처한 main LCD 화면으로 잡았다.

---

## 3. 유지해야 할 원칙

- `mobile/ios/Runner.xcworkspace`만 Xcode Flutter iOS 기준으로 사용한다.
- `mobile/Lemon-Aid-ios` 삭제 staged 상태는 사용자 요청 없이 되돌리지 않는다.
- Pods/plugin warning을 무리하게 직접 patch하지 않는다. 먼저 Flutter package update 또는 Xcode 설정 원인을 확인한다.
- Xcode runtime benign log와 실제 build failure를 구분한다.

---

## 4. 다음 TODO

- `git diff --cached -- mobile/Lemon-Aid-ios`로 삭제 의도를 최종 확인한다.
- `mobile/ios/Runner.xcworkspace` 기준 Xcode build를 재확인한다.
- stale build artifact warning이 남으면 Xcode 종료 후 `mobile/build/ios` 및 Runner 전용 DerivedData만 정리한다.
- `mobile/ios/Podfile`, `mobile/ios/Runner.xcodeproj/project.pbxproj`, `mobile/ios/Flutter/Profile.xcconfig` 변경은 별도 diff review 후 커밋 여부를 결정한다.

