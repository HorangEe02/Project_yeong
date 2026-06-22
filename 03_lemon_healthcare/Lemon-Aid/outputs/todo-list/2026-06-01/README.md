# 2026-06-01 작업 문서 인덱스

> 작성 기준: 2026-06-01 섹션 작업
> 범위: Android 갤러리 샘플 보강, Android/iOS 앱 재설치, Vercel `project-yeong` 연동, taxonomy API/service, 모바일 분석/채팅 흐름, 다음 섹션 인계

---

## 문서 목록

- `2026-06-01-mobile-gallery-and-reinstall-summary.md`
  - Pixel 10 Pro 갤러리에 영양제 성분표/라벨 이미지 20장을 추가한 작업
  - Android dev 앱 삭제 후 재설치, iPhone 17 Pro Simulator 삭제 후 재설치 검증

- `2026-06-01-vercel-project-yeong-link-summary.md`
  - `frontend`를 Vercel `yeong0202-s-projects/project-yeong`에 연결한 작업
  - Vercel 프로젝트 Root Directory, Framework, Build 설정 반영 결과
  - Preview 환경변수 미등록으로 남은 blocker 정리

- `2026-06-01-next-section-handoff.md`
  - 다음 Codex 섹션에서 이어서 사용할 작업 프롬프트
  - Git/GitHub, env, stage 금지 항목, 검증 순서 포함

- `2026-06-01-analysis-result-review-ui-summary.md`
  - 분석 결과 화면에서 OCR 근거 표, 성분 체크박스, 선택 성분 수정, 누락 섹션 안내, 다중 영양제 탭을 구현한 내용
  - raw OCR/provider payload를 노출하지 않는 UI 검토 기준 정리

- `2026-06-01-analysis-result-review-ui-verification.md`
  - `flutter test`, `flutter analyze`, `git diff --check` 검증 결과
  - 이번 커밋/푸시 스코프와 stage 제외 항목 정리

- `2026-06-01-taxonomy-api-service-summary.md`
  - 영양제/음식 taxonomy catalog, 사용자 영양제/식단 조회 필터, `meal:read` scope 구현 내용
  - DB migration, API 계약, owner scope/soft-delete/RLS 기준 정리

- `2026-06-01-taxonomy-api-service-verification.md`
  - backend ruff, targeted pytest 42개, mobile targeted test/analyze 검증 결과
  - stage 포함/제외 기준 정리

---

## 현재 핵심 상태

- Android Pixel 10 Pro Emulator에는 `Pictures/LemonAID-Readable-Labels` 앨범 기준 영양제 라벨 이미지 20장이 추가되어 MediaStore 인덱싱까지 확인됐다.
- Android dev 앱 `com.example.lemon_aid_mobile.dev`는 삭제 후 `app-dev-debug.apk`로 재설치됐다.
- iOS Simulator `iPhone 17 Pro`에는 Flutter Runner 앱 `com.example.lemonAidMobile`이 삭제 후 재설치 및 실행됐다.
- 중복으로 남아 있던 예전 native iOS 앱 `yeongs.Lemon-Aid`는 시뮬레이터에서 제거됐다.
- Vercel `project-yeong`은 `03_lemon_healthcare/Lemon-Aid/frontend` Next.js 앱을 바라보도록 연결됐다.
- 모바일 분석 결과 화면은 저장 전 OCR 근거 표와 성분별 체크박스 수정 흐름을 제공한다.
- 다중 영양제 분석 결과는 상단 탭으로 각 영양제 결과를 전환할 수 있다.
- backend는 영양제 category와 음식 cuisine/course/item taxonomy를 조회 API와 사용자 데이터 필터에 연결했다.
- 식단 조회는 `meal:read`, 식단 이미지 분석/확정은 `meal:write`로 scope가 분리됐다.
- local LLM 설명 실패 또는 impact check 실패 시에도 등록 결과를 유지하고, chat 탭으로 사용자 확인용 설명 draft를 전달하는 흐름을 추가했다.

현재 남은 blocker는 코드가 아니라 배포 환경 준비 문제다. Vercel Preview에 실제 OCR/YOLO/Supabase 연결용 환경변수가 아직 없고, Vercel serverless runtime에서 접근 가능한 public HTTPS backend `/api/v1`이 필요하다.
