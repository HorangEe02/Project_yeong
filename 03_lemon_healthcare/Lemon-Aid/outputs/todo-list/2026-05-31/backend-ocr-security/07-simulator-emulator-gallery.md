# 07. 시뮬레이터/에뮬레이터 갤러리에 naver 샘플 삽입

> 브랜치 성격: chore(test-fixture)
> 대응 커밋: 없음 (helper 스크립트는 의도적 미커밋)
> 핵심 파일: `mobile/scripts/select_naver_gallery_samples.py` (untracked)

---

## 1. 목표

영양제 라벨 OCR 흐름을 실기기 유사 환경에서 테스트하기 위해, naver 스크랩 이미지(상세페이지 + 리뷰)를 시뮬레이터/에뮬레이터 갤러리에 삽입.

소스: `/Volumes/Corsair EX400U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver` (~138k장, 42개 카테고리, 한국어 `상세페이지`/`리뷰` 구조)

---

## 2. 헬퍼 스크립트 복원

작업 중 글리치된 잘못된 진단으로 정상 스크립트를 깨진 버전(영어 `detail`/`review` 폴더 가정)으로 덮어쓴 사고가 있었음 → **원본 복원**(한국어 `상세페이지`/`리뷰` 인식, py_compile OK). 156장 정상 스테이징으로 증명.

스테이징: `/tmp/lemon-naver-samples` (카테고리별 detail/review 혼합, ASCII-safe 파일명 + manifest CSV)

---

## 3. 삽입 결과 ✅

| 기기 | 런타임 | 삽입 |
|---|---|---|
| iPhone 17 | iOS 26.5 (`B37C1E07…`) | 155장 (153 jpg + 2 png) |
| iPhone 17 Pro | iOS 26.5 (`7B2E1A72…`) | 155장 |
| iPhone 17 Pro | iOS 26.4 (`852A1323…`) | 155장 (런타임 착오로 먼저 삽입, 무해) |
| Android `lemon_pixel_8_api_36` | API 36 | 156장 (webp 포함) |

- iOS: `xcrun simctl addmedia` — Photos DB 자산 수로 검증(기본 6 + naver). **webp 1장은 simctl 미지원으로 제외**(iOS만).
- Android: `adb push` → `/sdcard/Pictures/` + 미디어 스캔. MediaStore 156행 인덱싱 검증. Android는 webp 지원.
- 시각 확인: 보관함/갤러리에 영양제 상세·리뷰 이미지 표시. Android는 앱 picker→OCR 분석까지 동작 확인.

---

## 4. 환경 한계 (참고)

- `open -a Simulator` TCC 권한으로 스크린샷이 검게 캡처되는 경우 있음 → Photos DB 직접 조회로 교차검증.
- 헬퍼 스크립트는 테스트 fixture라 git 커밋하지 않고 작업트리에만 유지.
