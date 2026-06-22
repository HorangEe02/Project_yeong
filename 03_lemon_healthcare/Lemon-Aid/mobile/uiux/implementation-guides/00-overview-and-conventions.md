# Lemon-Aid UI/UX 구현 가이드 — 00 총괄·공통 규약

> 기준일 2026-06-12 · 디자인 소스: `mobile/uiux/figma` (DS v2.0 · SoT v1.1, 원본 file key `tabLE08wPC1EQ0XdfgCwII`) · 브랜치 `feat/ai-agent-chat-import`
> 빌드 타깃: Android Studio — Pixel 10 Pro(Android 17, targetSdk 36) / Xcode — iPhone 17 Pro(iOS 26.5, deployment target 15.0)
> 라이브 피그마 링크(`xFRRFjiMhMnEuiZ6VlrVmv`, LemonAid 복사본)는 Dev Mode MCP 비활성으로 미조회 — 로컬 내보내기가 권위 스냅샷. 라이브 동기화 필요 시 Figma 데스크톱 Preferences → Enable Dev Mode MCP Server.

---

## 1. 문서 세트 구성

| 문서 | 범위 | 상태 비중 |
|---|---|---|
| [01-auth-onboarding-signup](01-auth-onboarding-signup.md) | 스플래시·로그인·가입 9단계·인증 복구·온보딩 | 신규 (P2 백엔드 결정 포함) |
| [02-home-dashboard](02-home-dashboard.md) | 홈 탭 (점수/달력/식단/복약/영양제/상호작용) | as-built + 잔여 |
| [03-capture-analysis-flows](03-capture-analysis-flows.md) | 카메라·검출·음식 후보·다중 촬영 | as-built + 잔여 |
| [04-analysis-results](04-analysis-results.md) | 분석 결과 C/D·영양제 최종·성분 상세 | as-built + 잔여 |
| [05-chat-lemonbot](05-chat-lemonbot.md) | 챗 레몬봇 | as-built + 잔여 |
| [06-today-analysis-tab](06-today-analysis-tab.md) | 분석 탭 '오늘의 분석' | as-built + 추이 잠금해제 |
| [07-records-calendar](07-records-calendar.md) | 캘린더·오늘의 기록·직접 입력 | 신규 |
| [08-settings-profile-health](08-settings-profile-health.md) | 설정·프로필·Health Connect·복약 알림·알림 센터 | 신규 |
| [09-backend-route-imports](09-backend-route-imports.md) | 백엔드 보강 (복약/식사기록/알림 라우트, 점수 영속) | 백엔드 |

권장 실행 순서: **09(백엔드 선행) → 02 잔여 → 07 → 08 → 03 → 04 잔여 → 06 추이 → 01(P2)**. 05는 의존 없음(폴리시).

## 2. 권위 체계 (충돌 시 우선순위)

1. **SoT v1.1** (`figma/00_Source_of_Truth`) — 제품 결정·의료법 워딩·시니어 최소치
2. **DS v2.0** (`figma/01_Design_System`) + 코드 단일 출처 `mobile/lib/utils/design_tokens_v2.dart` + `brand_palette.dart`(4테마)
3. **UI 보드** (`figma/03_UI_Design`, 85프레임 — ID는 `figma/_frames_index.md`)
4. 기확정 결정: D1 과다=review 앰버·주의=danger 레드 / D2 신뢰도 % 비노출(등급 칩: 높음≥0.85·보통≥0.6·직접 확인) / D3 폰트 Pretendard / D4 탭=홈·챗·+FAB·분석·설정

## 3. 코드 컨벤션 (전 문서 공통)

- **토큰만 사용**: `AppColor/AppText/AppSpace/AppRadius/AppShadow` — hex·px 하드코딩 금지. 테마색은 `Theme.of(context).colorScheme.primary`(동적) 또는 `AppColor.brand`(정적, 점진 마이그레이션 주석)
- **API**: `lib/core/api/api_client.dart`(http) — baseUrl이 `/api/v1` 포함 → **경로에 접두사 금지**. 403 `consent_required` → 해당 동의 1회 POST 후 재시도(패턴: `lib/features/chat/chat_repository.dart`)
- **Repository 패턴**: 화면→repository→ApiClient. 모델은 null-safe `fromJson` + 단위 테스트 동반
- **상태/모달 템플릿(필수 재사용)**: `shared/widgets/status_state_view.dart`(빈/실패/권한/분석실패/알림빈/검색0건), `widgets/common/app_modals.dart`(상호작용 경고 소프트블록·삭제 확인·축하·실행취소 토스트), `shared/widgets/low_confidence_banner.dart`
- **의료법 가드**: 사용자 문구 해요체, 금칙어(진단/처방/치료/효능) 금지 — 신규 문구는 금칙어 부재 테스트 동반. 모든 분석/권고 화면 하단 `MedicalDisclaimer`(단일 출처: `lib/widgets/common/medical_disclaimer.dart`)
- **시니어 최소치(SoT §9.1)**: 본문 15px+(AppText.body), 중요 안내 16px+, 버튼 높이 52px+, 터치 48px+, 색+아이콘+텍스트 병행

## 4. 현재 완료 상태 (2026-06-12, 검증값)

P0 완료 — Flutter `flutter analyze` 0건 / 테스트 170개 통과, 백엔드 유닛 스위트 사용자 WIP 2건 외 통과:
- 챗 실연동(`10cbc199`) · 홈 실데이터+건강점수(`4fab30d6`+`b43b9bfd`) · 분석결과 C+5카드(`f6400e09`) · 오늘의 분석 탭(`88c3ef4b`) · 테마 단일화 4색(`eb11363c`) · 상태/모달 템플릿(`547713b1`) · 플랫폼 픽스(`784687ce`)
- 챗봇 백엔드 통합 완료(라우트 2종 + 마이그레이션 0030~0041 + FORCE RLS). **`alembic upgrade head` 라이브 DB 1회 실행은 미수행** — 모든 신규 기능 스모크 전 선행 필수
- 일일 건강 점수: `GET /dashboard/summary`의 `health_score` 블록 (보류 결정 10건: `outputs/todo-list/2026-06-11/2026-06-11-daily-health-score-decisions.md`)

## 5. 화면 × 엔드포인트 매트릭스 (총괄)

| 화면/기능 | 핵심 엔드포인트 | 동의 | 상태 |
|---|---|---|---|
| 홈 점수·요약 | GET `/dashboard/summary` (health_score 포함) | sensitive_health_analysis | ✅ |
| 홈 식단/캘린더 | GET `/meals` (+cuisines/foods) | — | ✅/07 |
| 홈 영양제 | GET `/supplements` | — | ✅ |
| 상호작용 카드 | GET `/supplements/recommendations/latest` | sensitive | ✅ |
| 복약 카드/알림 | user_medications·notifications 라우트 | sensitive | **09 임포트 후** |
| 카메라→영양제 분석 | POST `/supplements/analyze`(+sessions/multi)→`/analyses/{id}/ocr-text·explain`→POST `/supplements` | ocr_image_processing(+sensitive 등록) | ✅ |
| 카메라→음식 분석 | POST `/meals/analyze-image`→POST `/meals/{id}/confirm`→`/meals/{id}/explain` | food_image_processing | ✅(후보 UI 잔여) |
| 분석결과 5카드 | POST `/supplements/analyze/comprehensive` | (인증만) | ✅ |
| 챗 | POST `/ai-agent/chat` | sensitive | ✅ |
| 오늘의 분석 | POST `/ai-agent/daily-coaching` | sensitive | ✅(추이 잠금) |
| 추이 차트 | POST/GET `/analysis-results` (+점수 타입 신설) | sensitive | **09 영속 후** |
| 프로필/신체 | POST·GET `/health/profile-snapshots` | sensitive | 08 |
| 건강 프로필(질환) | POST `/medical-records`+`/confirm` | sensitive | 08 |
| 워치 동기화 | POST `/health/sync`, GET `/health/daily-summary` | health_device_data | 08(Android 먼저) |
| 동의/탈퇴 | GET·POST·DELETE `/me/privacy/consents/*`, POST `/me/data-deletion-requests` | — | ✅/08 |
| 인증(소셜/이메일) | `/auth/*` | — | **백엔드 공백(P2, 01)** |
| 리워드 | — | — | 백엔드 전무(범위 외) |

## 6. 플랫폼 매트릭스

| 항목 | Android (Pixel 10 Pro·17) | iOS (iPhone 17 Pro·26.5) |
|---|---|---|
| dev API | `http://10.0.2.2:8000/api/v1` (debug 전용 cleartext 오버레이 ✅) | `http://127.0.0.1:8000/api/v1` (ATS LocalNetworking ✅) |
| 권한 문구 | 매니페스트 카메라/미디어 ✅ | 한국어 카메라/사진 ✅ · Light 고정 ✅ |
| 건강 연동 | Health Connect — 08 문서 (P1) | HealthKit — SoT상 v2 보류 |
| 로컬 알림 | POST_NOTIFICATIONS + flutter_local_notifications (08) | UNUserNotificationCenter (08) |
| 소셜 로그인 | Kakao/Google 키 — 01 문서 (P2) | URL 스킴/LSApplicationQueriesSchemes (P2) |
| 빌드 | `flutter build apk --debug --dart-define=LEMON_API_BASE_URL=...` | `flutter build ios --no-codesign`, 시뮬레이터 iPhone 17 Pro |

## 7. 검증 게이트 (모든 작업 공통 DoD)

1. `cd mobile && flutter analyze` 0건, `flutter test` 전체 통과(기준 170개+신규)
2. 백엔드 변경 시 `backend/.venv/bin/python -m pytest Nutrition-backend/tests -q -o addopts=""` — 허용 실패 = 사용자 WIP 2건(.mcp.json supabase, OCR readiness)뿐 + `ruff check` 클린
3. 보안 회귀: `release_security_config_test` 통과(main 네트워크 설정 cleartext 금지 — debug 오버레이만), 신규 PII 테이블은 0041 RLS 패턴
4. 의료법: 신규 사용자 문구 금칙어 부재 assert, 신뢰도 % 비노출, 면책 푸터
5. 실기기 스모크: 양 플랫폼에서 촬영→분석→저장→홈→챗 1사이클 (dev 스택: Postgres + `alembic upgrade head` + uvicorn, PYTHONPATH에 `backend/ai_agent_chat/src`)
