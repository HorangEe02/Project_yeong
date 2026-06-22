# 2026-05-31 React 모바일 웹 UI 구현 요약

> 작성 기준: 2026-05-31
> 범위: `frontend` Next.js 앱, Flutter/Android Studio에서 검증한 Lemon AID 모바일 UI 재현

---

## 1. 핵심 결론

Android Studio에서 확인한 Lemon AID 모바일 앱의 화면 구조를 React/Next.js 웹 앱으로 맞췄다. 기존 웹 화면이 Flutter 앱과 다르게 보이던 문제를 해결하기 위해 홈, 챗, 중앙 카메라, 점수, 설정 5탭 구조와 전체 화면 카메라 촬영 UI를 구현했다.

카메라 화면은 브라우저 `getUserMedia` 기반 실시간 preview, 이미지 파일 업로드, 영양제/식단 모드 전환, 셔터 캡처 흐름을 포함한다. 백엔드가 없거나 일부 vision 모델이 준비되지 않은 상황에서도 UI 흐름을 확인할 수 있도록 fallback 결과 표시를 유지했다.

---

## 2. 주요 구현 내용

### 2.1 모바일 앱 UI 정렬

- 대상: `frontend/src/components/lemon-web-app.tsx`
- Lemon AID 모바일 앱과 유사한 phone shell, 5탭 bottom navigation, 중앙 촬영 버튼을 구성했다.
- 홈 화면에 건강 점수, OCR/YOLO/LLM/WIKI 흐름 카드, 최근 분석 결과 영역을 배치했다.
- 카메라 진입 시 앱 내부 설명 페이지가 아니라 실제 촬영 UI가 첫 화면으로 보이도록 조정했다.

### 2.2 실시간 카메라 preview

- 브라우저 카메라 권한을 받아 `<video>` preview를 표시한다.
- preview를 보고 영양제 성분표나 식단 영역을 가이드 frame 안에 맞출 수 있게 했다.
- 셔터를 누르면 현재 video frame을 canvas로 캡처해 분석 요청 payload로 사용한다.
- 파일 선택 fallback을 유지해 카메라 권한이 없거나 desktop 검증 중에도 이미지 분석 흐름을 확인할 수 있다.

### 2.3 영양제 OCR / 식단 YOLO 흐름 연결

- 영양제 모드: `POST /api/lemon/supplements/analyze`
- 식단 모드: `POST /api/lemon/meals/analyze-image`
- 웹 브라우저는 same-origin `/api/lemon/*`만 호출하고, Next.js route handler가 FastAPI backend `/api/v1`로 proxy한다.
- raw OCR text, provider payload, image 원문은 smoke 출력이나 UI debug에 노출하지 않는 방향을 유지했다.

### 2.4 Hydration warning 대응

- Chrome extension이 `<html>`에 `data-hwp-extension` 속성을 주입해 Next.js hydration warning overlay가 표시됐다.
- 앱 코드에서 생성한 mismatch가 아니라 브라우저 확장 주입으로 분류했다.
- `frontend/src/app/layout.tsx`의 root html에는 hydration warning 완화를 위해 `suppressHydrationWarning`을 적용했다.

---

## 3. 관련 파일

- `frontend/src/components/lemon-web-app.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/app/api/lemon/supplements/analyze/route.ts`
- `frontend/src/app/api/lemon/meals/analyze-image/route.ts`
- `frontend/src/app/api/lemon/ready/route.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/lemon-backend.ts`
- `frontend/src/lib/types.ts`

---

## 4. 공식 참고

- Media Capture and Streams specification: https://www.w3.org/TR/mediacapture-streams/
- Next.js App Router route handlers: https://nextjs.org/docs/app/building-your-application/routing/route-handlers
- Next.js CLI: https://nextjs.org/docs/app/api-reference/cli/next
