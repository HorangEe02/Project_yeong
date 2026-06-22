# 2026-06-21 Demo Video Editing and Mobile Builds

## 기준

- Repo: `Lemon-Aid` / 작성일: `2026-06-21 KST`
- 주제: 영양제/챗봇 데모 화면녹화 편집(로딩 구간 압축) + GIF + iPhone/Pixel 빌드 배포

## 오늘 완료한 작업

### 데모 영상 편집 (ffmpeg, 장면검출 기반)

- [x] 영양제 등록 데모: 117.8초 → **58.2초**(<1분) — AI 로딩 정적구간(12.4~76.2초) 16배 압축
  - 출력: `data/Simulator Screenshot/lemonaid_supplement_demo_1min.mp4`
- [x] 풀 데모(식단+영양제+챗봇): 172.9초 → **63.4초**(<2분) — AI 로딩(67초) 16배 + 저장→챗봇 전환(12초) 6배 + 챗봇(35초) 3배 압축
  - 출력: `~/Desktop/lemonaid_full_demo_under2min.mp4`
- [x] GIF 생성: `~/Desktop/lemonaid_full_demo.gif`(11MB, 360×782, 10fps, 팔레트 최적화)
- 방법: `ffmpeg select='gt(scene,0.10)'`로 정적(로딩) 구간 검출 → trim+setpts 구간별 속도 + concat; 검증은 프레임 몽타주

### 모바일 빌드 (백엔드 수정 반영용)

- [x] iPhone 17 Pro (iOS 26.5, UDID `7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB`): `flutter build ios --simulator --debug`(--flavor 불가) + `simctl install`/`launch` — 홈 화면 정상
- [x] Pixel 10 Pro (`emulator-5554`): `flutter build apk --debug --flavor dev` + `adb install`/launch — 온보딩 화면 정상

## 함정 / 교훈

- iOS는 Xcode 커스텀 스킴 없음 → `--flavor` 사용 불가, **dart-define만**(LEMON_APP_ENV=dev, LEMON_API_BASE_URL=http://localhost:8000/api/v1)
- Android는 `--flavor dev` 사용, 백엔드 URL = `http://10.0.2.2:8000/api/v1`
- 에뮬레이터 영속: `emulator -avd ... < /dev/null`(파이프 금지, stdin 분리) 아니면 SIGTERM으로 종료됨
- 에뮬 `INSTALL_FAILED_INSUFFICIENT_STORAGE`: 구버전 `adb uninstall` + `pm trim-caches`로 해결
- 빌드 디렉터리 = `mobile/`, 진입점 `lib/main.dart`
