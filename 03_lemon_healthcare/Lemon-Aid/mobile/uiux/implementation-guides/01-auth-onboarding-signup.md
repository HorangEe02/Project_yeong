# 구현 가이드 01 — 인증 · 온보딩 · 가입

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

---

## ① 범위 / 목표

| 구분 | 내용 |
|---|---|
| 담당 화면 | 00 Splash · 01 Login(3변형) · 02 Signup 12프레임 · 13 인증 복구(4) · 상태 Edge(이메일 인증 3) · 08 온보딩 3장 |
| 핵심 제약 | **백엔드에 `/auth/*` 라우트가 존재하지 않음** (`backend/Nutrition-backend/src/api/v1/router.py` 등록 라우터에 auth 없음 — 확인 완료). 현 인증은 외부 OIDC JWT 붙여넣기(`lib/app.dart`의 `_BearerTokenLoginScreen`) + dev bypass |
| 전략 | 토큰 로그인 유지를 전제로 한 **3단계 점진 도입**: ①약관 동의 바텀시트를 동의 게이트 UI로 선적용 → ②백엔드 없이 가능한 가입 위저드 단계(프로필/신체→`/health/profile-snapshots`, 목적·관심사→로컬) → ③auth 백엔드 결정(Supabase Auth vs 자체 OIDC) 후 소셜/이메일 |
| 목표 | P2 auth 결정 전에도 시안의 동의 UX·프로필 수집 UX를 사용자에게 먼저 제공하고, auth 도입 시 화면 재작업이 없도록 위저드를 단계 모듈로 설계 |

비범위: 리워드(10-②, 백엔드 전무), Apple Health 연동(SoT상 v2 이후), 푸시 알림 서버화.

---

## ② 디자인 스펙

Figma 파일 키 `tabLE08wPC1EQ0XdfgCwII`, 페이지 `03_UI_Design`(0:1) · `04_Clickable_Prototype`(5:6). 프레임 ID는 `mobile/uiux/figma/_frames_index.md` 기준.

### 2.1 프레임 맵

| 그룹 | 프레임 ID | 내용 |
|---|---|---|
| Splash | `827:24` | S-01 Splash — Lottie `lemonaid_gold` + 태그라인 |
| Login | `151:2` / `169:4` / `170:6` | 재방문 3변형 — 카카오/구글/Apple "최근 로그인" 툴팁 |
| Login 모션 | `166:4`, `218:19` | 모션/구현 노트 + 인터랙션 상태 참고 |
| Signup 0 | `206:17`, `255:20` | 약관 동의(바텀시트 모달) + 약관 상세 |
| Signup 1~9 | `191:9` Welcome / `197:9` Profile / `254:19` 생년월일 휠 / `198:10` Email / `199:11` Purpose / `200:12` Concerns / `201:13` Body / `202:14` Healthkit / `203:15` Review / `205:16` Dashboard 진입 |
| Email Edge | `264:21` 코드 오류 / `265:21` 재전송 타이머 / `266:22` 인증 완료 |
| 인증 복구 | `949:24` 비밀번호 찾기 / `949:45` 재설정 / `949:77` 변경 완료 / `949:88` **계정 충돌(이미 가입)** |
| 온보딩 | `911:24` ① 환영 / `911:41` ② 분석 / `911:58` ③ 루틴 |
| 프로토타입 | `272:9`~`272:422`(가입 인터랙션), 컴포넌트 `331:27` Checkbox / `335:27` Switch / `335:34` Chip / `335:41` SegmentItem / `343:28` CheckCircle / `343:33` SelectCard |

### 2.2 레이아웃 구조

- **약관 동의 바텀시트(206:17)**: 상단 그래버 → 타이틀 → "전체 동의" 마스터 체크(CheckCircle `343:28`) → 필수/선택 약관 행(체크 + "보기" 디스클로저 → 약관 상세 `255:20`) → 하단 고정 CTA "동의하고 시작하기"(필수 전체 체크 전 disabled).
- **가입 위저드**: 상단 프로그레스(단계 인디케이터) + 단계별 본문 + 하단 고정 Primary CTA. 생년월일은 휠 피커 바텀시트(254:19). Purpose/Concerns는 SelectCard(`343:33`)·Chip(`335:34`) 멀티선택.
- **로그인(151:2)**: 워드마크 → 소셜 버튼 3개 세로 스택(카카오→구글→Apple) → 이메일 로그인 텍스트 링크. "최근 로그인" 툴팁은 마지막 사용 수단 버튼 위에 말풍선.
- **온보딩 3장**: 풀스크린 일러스트 + 타이틀/설명 + 페이지 도트 + "건너뛰기"/"다음".

### 2.3 사용 토큰 (design_tokens_v2 — `mobile/lib/utils/design_tokens_v2.dart`)

| 용도 | 토큰 |
|---|---|
| 브랜드/CTA | `AppColor.brand`, 눌림 `AppColor.brandPressed`, 옅은 강조 `AppColor.brandSoft` |
| 소셜 버튼 | 카카오 `AppColor.kakao` (= `#FEE500`, 텍스트 `AppColor.ink`) / 구글 `AppColor.surface`+`AppColor.border` 아웃라인 / Apple `AppColor.appleBlack` (텍스트 `#FFFFFF` = `AppColor.bg`) |
| 텍스트 | 타이틀 `AppText.title`(24), 본문 `AppText.body`(15 — 시니어 최소), 보조 `AppText.caption`(13) |
| 상태색 | 오류 `AppColor.danger`, 완료 `AppColor.success`, 안내 `AppColor.info`, 쿨다운 보조 `AppColor.inkTertiary` |
| 간격/모서리 | 페이지 패딩 `AppSpace.page`(24), 카드 내부 `AppSpace.cardInside`(20), 버튼/시트 `AppRadius.md`(16)~`AppRadius.xl`(24) |
| 컴포넌트 | AppPrimaryButton(높이 52px+ — SoT 시니어 최소치), AppTextField(4상태), Checkbox/Chip/SelectCard(프로토타입 컴포넌트 준용) |

### 2.4 세부 인터랙션 스펙 (b 항목)

- **최근 로그인 툴팁**: 마지막 성공 로그인 수단을 `flutter_secure_storage`에 저장(`last_login_provider`) → 다음 진입 시 해당 버튼 위에 `AppColor.ink` 배경 말풍선("마지막으로 로그인했어요"). 3변형 = 카카오(151:2)/구글(169:4)/Apple(170:6).
- **이메일 인증코드 엣지**:
  - 코드 불일치(264:21): 입력 필드 `AppColor.danger` 보더 + 하단 캡션 "인증번호가 일치하지 않아요. 다시 확인해 주세요." + 필드 셰이크 모션(166:4 노트 준용).
  - 재전송 쿨다운(265:21): "재전송" 버튼 disabled + 카운트다운("00:58 후 다시 받을 수 있어요", `AppColor.inkTertiary`). 쿨다운 60초 권장.
  - 인증 완료(266:22): 필드 우측 `AppColor.success` 체크 아이콘 + "인증이 완료됐어요" 캡션, CTA 활성화.
- **계정 충돌(949:88)**: 이미 가입된 이메일로 다른 수단 시도 시 — 기존 가입 수단 안내 카드("이미 카카오로 가입된 계정이에요") + 해당 수단 로그인 CTA + "다른 계정으로 가입" 보조 링크. 백엔드 응답 `409 account_conflict`(P2 auth 계약에 포함) 기준.

---

## ③ 현재 코드 상태

| 영역 | 상태 | 파일 |
|---|---|---|
| 라우팅/redirect | **구현 완료(as-built)** — `/splash` 초기 진입, `TokenSessionController` `bootstrapped`/`canEnterShell` 기반 redirect(`/login` 게이트), 로그인 성공 시 `/shell/home` | `mobile/lib/app.dart` (64~235행 GoRouter, redirect 69~86행) |
| 토큰 세션 | **구현 완료** — `BearerTokenStore`(Secure/Memory), `devBypassActive`(릴리즈 외 무토큰 진입), `saveBearerToken`/`clearBearerToken` | `mobile/lib/features/auth/token_session.dart` |
| 로그인 화면 | **dev 전용** — JWT 붙여넣기 `_BearerTokenLoginScreen` + "로컬 dev bypass로 계속"(비릴리즈) | `mobile/lib/app.dart` 374~483행 |
| 동의 게이트 | **부분** — 카메라 브랜치 진입 시 `hasMinimumConsents` 미충족이면 표시. **영문 UI**("Required demo consents"), 시안과 무관한 데모 스타일 | `mobile/lib/features/consent/consent_gate_screen.dart`, 분기 `mobile/lib/app.dart` 330~332행 |
| 동의 모델 | **구현 완료** — `ConsentState.isGranted` | `mobile/lib/features/consent/consent_models.dart` |
| 403 동의 재시도 패턴 | **구현 완료(참조 표준)** — 403 `consent_required` → `POST /me/privacy/consents/sensitive_health_analysis`(201 기대) 1회 → 원요청 재시도 | `mobile/lib/features/chat/chat_repository.dart` 52~92행, `_isConsentRequired` 132~134행 |
| 스플래시 | **구현 완료** | `mobile/lib/screens/splash_screen.dart` |
| 상태 템플릿 | **구현 완료(P0 `547713b1`)** — `StatusStateVariant` 6종(emptyNew/syncFailed/permissionDenied/analysisFailed/notificationsEmpty/searchEmpty) + 모달 템플릿 | `mobile/lib/shared/widgets/status_state_view.dart`, `mobile/lib/widgets/common/app_modals.dart` |
| 온보딩 3장 / 소셜 로그인 / 가입 위저드 / 인증 복구 화면 | **없음** | 신규: `mobile/lib/features/onboarding/`, `mobile/lib/features/auth/` 하위 |
| 백엔드 `/auth/*` | **백엔드 공백** — 라우트 없음. `mobile/uiux/handoff/02_FRONTEND_GUIDE.md` §7에 계획 표만 존재(`/auth/signup·login·kakao·google·email/send-code·email/verify-code·refresh·logout`) | `backend/Nutrition-backend/src/api/v1/` (auth 모듈 부재 확인) |
| 팀원 레퍼런스 | 참고용 — 가입 위저드/auth_service 레퍼런스 구현(analyzer 제외됨, `d7014b58`) | `mobile/flutter_app/lib/`(레퍼런스), `mobile/uiux/handoff/02_FRONTEND_GUIDE.md` |

---

## ④ 구현 단계 (체크리스트)

### 1단계 — 약관 동의 바텀시트를 동의 게이트로 선적용 (P1 가능, 백엔드 불필요)

1. [ ] `mobile/lib/features/consent/consent_gate_sheet.dart` 신규 — 시안 206:17 레이아웃(전체 동의 마스터 체크 + 필수/선택 행 + 하단 CTA). 문구 전부 해요체 한국어.
2. [ ] 동의 항목 ↔ `ConsentType` 매핑 정의(`consent_models.dart` 확장):
   - 필수: `sensitive_health_analysis`(민감 건강 분석), `ocr_image_processing`(영양제 라벨 촬영), `food_image_processing`(음식 사진 분석)
   - 선택: `external_ocr_processing`(외부 OCR 전송), `data_retention`(기록 보관), `image_learning_dataset`(비식별 학습 활용 — 별도 opt-in)
3. [ ] `mobile/lib/features/consent/consent_policy_screen.dart` 신규 — 약관 상세(255:20). 정적 본문 + 동의 토글.
4. [ ] `mobile/lib/app.dart` `_SupplementCameraBranch`(330~332행)의 영문 `ConsentGateScreen` 호출을 신규 시트로 교체. 기존 화면은 위젯 테스트 호환 위해 deprecated 주석 후 단계 제거.
5. [ ] 동의 부여는 항목별 `POST /me/privacy/consents/{consent_type}`(201), 철회는 `DELETE`(설정 화면과 공유). 화면 진입 시 `GET /me/privacy/consents`로 현재 상태 프리필.
6. [ ] 위젯 테스트: 필수 미체크 시 CTA disabled / 전체 동의 토글 전파 / 영문 문구 부재.

### 2단계 — 가입 위저드 중 백엔드-가능 단계 (P1~P2 경계, auth 없이 동작)

7. [ ] `mobile/lib/features/auth/signup_wizard/` 신규 — 단계 모듈 구조(`signup_step.dart` 인터페이스 + 단계별 위젯). auth 도입 전에는 "프로필 보완 플로우"로 설정 화면에서 진입(`/shell/settings/profile-setup` 라우트).
8. [ ] Profile(197:9) + 생년월일 휠(254:19) + Body(201:13) → `POST /health/profile-snapshots` `{sex, birth_year, height_cm, weight_kg}` 1회 제출. 진입 시 `GET /health/profile-snapshots/latest` 프리필. 403 `consent_required` 시 chat_repository 패턴으로 `sensitive_health_analysis` 1회 동의 후 재시도.
9. [ ] Purpose(199:11)/Concerns(200:12) → **로컬 저장**(`shared_preferences` — P1-5에서 도입 예정인 의존성과 공유). 서버 보존용 프로필 필드는 **백엔드 공백**(profile-snapshots에 목적/관심사 필드 없음) — 추후 백엔드 협의 항목으로 명시, 날조 금지.
10. [ ] Healthkit/Health Connect 단계(202:14) → P1-6(Health Connect) 온보딩 화면으로 위임. 연동 선택 시 `health_device_data` 동의 부여, 미선택 시 스킵 가능.
11. [ ] Review(203:15) — 입력 요약 카드 + 수정 진입. Welcome(191:9)/완료(205:16)는 정적.
12. [ ] 온보딩 3장(911:24/41/58) — 첫 실행 플래그(로컬) 기준 `/splash` 직후 1회 노출, "건너뛰기" 제공. `mobile/lib/features/onboarding/onboarding_screen.dart` 신규 + app.dart 라우트/redirect에 `onboardingSeen` 분기 추가.

### 3단계 — auth 백엔드 결정 후 소셜/이메일 (P2)

13. [ ] **결정표** (팀 결정 필요 — 플랜 문서 R3):

| 기준 | Supabase Auth (권고 검토) | 자체 OIDC |
|---|---|---|
| 구현 비용 | 낮음 — 카카오(OIDC 커스텀)/구글/Apple/이메일 OTP 내장, 프로젝트에 supabase 의존 이미 존재 | 높음 — 토큰 발급/회전/이메일 발송 인프라 전부 자체 구축 |
| 백엔드 변경 | JWT 검증(JWKS)만 추가 — 현 resource-server 구조(`AUTH_MODE`) 유지 | `/auth/*` 라우트 9종 신규(`02_FRONTEND_GUIDE.md` §7 표) + 토큰 저장소 |
| 카카오 지원 | 커스텀 OIDC 공급자 등록 필요(검증 항목) | SDK 토큰 교환 직접 구현 |
| 데이터 주권/규제 | 사용자 계정이 외부 SaaS — 민감정보 분리 설계 필요 | 전부 자체 보유 |
| 모바일 영향 | `TokenSessionController`에 토큰 공급원만 교체(저장·redirect 로직 재사용) | 동일 |

14. [ ] 로그인 화면(151:2) — 소셜 3버튼 + 이메일 링크 + 최근 로그인 툴팁(2.4절 스펙). `mobile/lib/features/auth/login_screen.dart` 신규, app.dart `/login` 빌더 교체(`_BearerTokenLoginScreen`은 dev flavor 전용으로 강등·유지).
15. [ ] 이메일 인증코드 단계(198:10 + Edge 264:21/265:21/266:22) — send-code/verify-code 연동, 쿨다운 타이머·오류·완료 3상태.
16. [ ] 인증 복구 4화면(949:24/45/77/88) — 비밀번호 찾기/재설정/완료/계정 충돌.
17. [ ] iOS URL 스킴·Android 설정 적용 — ⑧ 플랫폼 노트 참조(`mobile/uiux/handoff/03_IOS_SETUP.md` 인용).

---

## ⑤ 엔드포인트 계약 표

ApiClient는 baseUrl에 `/api/v1`이 포함되므로 아래 경로는 **접두사 제거 형태**다.

### 실재 엔드포인트 (즉시 사용 가능 — `backend/Nutrition-backend/src/api/v1/privacy.py`, `health.py` 확인)

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| `GET /me/privacy/consents` | — | `consents[]`: `consent_type`, `policy_version`, `title`, `required`, `granted`, `occurred_at`, `revoked_at` | 인증만 |
| `POST /me/privacy/consents/{consent_type}` | path: `consent_type`(9종 enum) | `consent_type`, `policy_version`, `granted`, `occurred_at` (**201**) | 인증만 |
| `DELETE /me/privacy/consents/{consent_type}` | path: `consent_type` | 동일(`granted=false`) | 인증만 |
| `POST /health/profile-snapshots` | `sex`, `birth_year`(1900~2100), `height_cm`(30~260), `weight_kg`(1~500) — 최소 1개 필수 | 스냅샷 `id`, 입력 필드 에코, `created_at` | `sensitive_health_analysis` (없으면 403 `consent_required`) |
| `GET /health/profile-snapshots/latest` | — | 최신 스냅샷 또는 빈 응답(`EmptyLatestBodyProfileResponse`) | `sensitive_health_analysis` |
| `POST /me/data-deletion-requests` | (privacy.py 125행) | 접수 확인 | 인증만 — 탈퇴 플로우(가이드 04 설정 편과 공유) |

### 백엔드 공백 (날조 금지 — 3단계 결정 후 신규 개발 대상)

| METHOD 경로 (계획) | 비고 |
|---|---|
| `POST /auth/signup` / `POST /auth/login` | email/password — **현재 미존재** |
| `POST /auth/kakao` / `POST /auth/google` / (Apple 상당) | SDK 토큰 교환 — **미존재**. Apple은 handoff 표에도 없어 계약 신규 정의 필요 |
| `POST /auth/email/send-code` / `POST /auth/email/verify-code` | 인증코드 — **미존재** |
| `POST /auth/refresh` / `POST /auth/logout` | 토큰 회전/무효화 — **미존재** |

출처: `mobile/uiux/handoff/02_FRONTEND_GUIDE.md` §7 계획 표. Supabase Auth 채택 시 이 표 대부분은 Supabase SDK 호출로 대체되고 백엔드는 JWT 검증만 담당한다.

### 공통 호출 규칙

- 403 `consent_required` → 해당 `consent_type` 1회 동의(`POST /me/privacy/consents/{type}`, 201 기대) → 원요청 재시도. 구현 표준: `mobile/lib/features/chat/chat_repository.dart` `sendMessage`.
- 동의 그랜트는 멱등 아님을 가정하지 말 것 — 화면 진입 시 `GET`으로 상태 확인 후 미동의 항목만 `POST`.

---

## ⑥ 상태 / 에러 처리

`StatusStateView`(`mobile/lib/shared/widgets/status_state_view.dart`) + 모달 템플릿(`mobile/lib/widgets/common/app_modals.dart`) 활용.

| 상황 | 처리 |
|---|---|
| 프로필 스냅샷 로딩 | 단계 본문 스켈레톤 + 하단 CTA disabled |
| `GET .../latest` 빈 응답 | 빈 폼으로 시작(에러 아님 — `EmptyLatestBodyProfileResponse` 분기) |
| 네트워크 실패 (동의/스냅샷 제출) | `StatusStateVariant.syncFailed` 인라인 + "다시 시도" CTA. 위저드 입력값은 메모리 보존 |
| 403 `consent_required` | 1회 자동 동의 재시도(⑤ 공통 규칙). 재시도도 실패 시 동의 게이트 시트 재노출 |
| 401/토큰 만료 | `TokenSessionController.clearBearerToken()` → redirect가 `/login` 회수 (기존 as-built 동작) |
| 이메일 코드 불일치 | 264:21 — `AppColor.danger` 캡션 "인증번호가 일치하지 않아요. 다시 확인해 주세요." (5회 실패 시 재발송 유도) |
| 재전송 쿨다운 | 265:21 — 버튼 disabled + 남은 시간 표시. 서버 429 응답도 동일 UI로 흡수 |
| 계정 충돌 | 949:88 — 기존 수단 안내 + 해당 수단 로그인 CTA (P2) |
| 온보딩/약관 시트 이탈 | 필수 동의 미완료 시 보호 기능 진입 차단만 — 앱 자체는 사용 가능(소프트 게이트) |

워딩 규칙: 전부 해요체. 의료법 금칙어(진단/처방/치료/효능) 금지 — 온보딩 ②"분석" 장 카피도 "분석 결과를 참고 자료로 보여드려요" 수준 유지. 신뢰도 %는 본 영역에 노출 화면 없음(가드만 유지). 온보딩 ② 등 분석 기능을 소개하는 화면 하단에는 면책 푸터("건강 참고용이며 의료적 판단을 대신하지 않아요" — `mobile/lib/widgets/common/medical_disclaimer.dart`의 `MedicalDisclaimer`) 포함.

---

## ⑦ 테스트 계획

| 종류 | 항목 |
|---|---|
| 단위 | 동의 항목↔`ConsentType` 매핑 / 403 `consent_required` 1회 재시도(성공·재실패 케이스) / 쿨다운 타이머 상태 머신 / `TokenSessionController` 회귀(기존 테스트 유지) |
| 위젯 | 약관 시트: 필수 미체크 CTA disabled → 전체 동의 → 활성 / 위저드 각 단계 렌더+프리필 / 생년월일 휠 선택 반영 / 이메일 엣지 3상태 골든 / 최근 로그인 툴팁 3변형 / 온보딩 스킵 후 재노출 안 됨 |
| 라우팅 | `onboardingSeen` redirect 분기 / 미인증 → `/login` / dev bypass 비릴리즈 한정 유지 |
| 금칙어 가드 | 신규 사용자 문구 전수에 진단·처방·치료·효능 부재 assert (기존 가드 패턴 동반 — P0 회귀 규칙) |
| 보안 회귀 | `release_security_config_test` 통과 유지 / 토큰은 `flutter_secure_storage` 외 저장 금지 / 동의 전 보호 API 미호출 |
| 검증 게이트 | `flutter analyze` 0건 + `flutter test` 전체 통과(170개 기준선 이상) |

---

## ⑧ 플랫폼 노트

### iOS (iPhone 17 Pro · iOS 26.5)

- 카메라/사진 **한국어 권한 문구는 P0에서 적용 완료**(`784687ce`, `03_IOS_SETUP.md` §(B) 문구 — "저장된 사진을 불러와 분석하기 위해 권한이 필요해요" 등). 신규 권한 추가 시 동일 문서 준용.
- **P2 auth 진행 시** `mobile/uiux/handoff/03_IOS_SETUP.md` 그대로 적용: 카카오 URL 스킴(`kakao` + 네이티브 앱 키, 문서 §(A)), `LSApplicationQueriesSchemes`(`kakaokompassauth`, `kakaolink`), 구글 Reversed Client ID URL 스킴(문서 §구글 항목). 키 값은 문서에 기재된 우리 앱 키 사용 — 본 가이드에 재기재하지 않음.
- `UIUserInterfaceStyle=Light` 적용 완료(P0) — 인증 화면도 라이트 전용.
- Apple 로그인 채택 시 `Sign in with Apple` 엔타이틀먼트 추가 필요(handoff 미기재 — 신규 항목).

### Android (Pixel 10 Pro · Android 17 · targetSdk 36)

- dev HTTP(`10.0.2.2`)는 debug 전용 network_security_config 오버레이로 해결 완료(P0 `784687ce`) — auth 작업에서 main 설정에 cleartext 예외 추가 금지(보안 회귀 가드).
- P2 카카오 SDK 도입 시 `AndroidManifest.xml`에 카카오 redirect 액티비티/스킴 추가(키는 iOS와 동일 출처 문서·OAuth.md 참조), 구글은 `google-services` 구성 필요.
- 예측형 뒤로가기: 위저드 단계 이탈 시 입력 보존 확인(가입 9단계가 가장 긴 백스택).

---

## ⑨ 완료 기준 (DoD)

1. **1단계**: 카메라 진입 동의 게이트가 시안 206:17 한국어 바텀시트로 교체되고, 영문 `ConsentGateScreen` 노출 경로 0건. 동의 상태가 `GET /me/privacy/consents`와 일치.
2. **2단계**: 프로필/생년월일/신체 입력이 `/health/profile-snapshots`에 저장·프리필되고, 목적/관심사가 로컬 보존됨(서버 필드 공백은 문서·코드 TODO로 명시). 온보딩 3장이 첫 실행 1회만 노출.
3. **3단계**(auth 결정 후): 결정표 기반 ADR 1건 합의 → 소셜 3종+이메일 로그인/가입/복구/계정 충돌 화면이 시안 프레임과 일치하고, dev 토큰 화면은 dev flavor에서만 접근 가능.
4. 전 단계 공통: `flutter analyze` 0건 / `flutter test` 전체 통과 / 금칙어 가드·release 보안 테스트·면책 푸터 규칙 위반 0건 / 시니어 최소치(본문 15px+, 버튼 52px+, 터치 48px+) 충족.
5. 실기기 스모크: Pixel 10 Pro + iPhone 17 Pro에서 온보딩→동의→프로필 입력→홈 진입 풀 사이클 1회.

---

*근거: `mobile/uiux/2026-06-10-uiux-redesign-endpoint-integration-plan.md` §3.9 / `outputs/todo-list/2026-06-11/2026-06-11-uiux-p1-execution-todo.md` P2 / `backend/Nutrition-backend/src/api/v1/privacy.py`·`health.py` 실코드 / `mobile/lib/app.dart`·`features/consent/`·`features/auth/`·`features/chat/chat_repository.dart` 실코드 / `mobile/uiux/handoff/02_FRONTEND_GUIDE.md`·`03_IOS_SETUP.md`.*
