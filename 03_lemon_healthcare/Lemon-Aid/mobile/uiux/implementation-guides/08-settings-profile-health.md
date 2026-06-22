# 08. 설정 · 프로필 · 건강 연동 · 알림 구현 가이드

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

---

## ① 범위 / 목표

설정 탭(`/shell/settings`)과 그 하위 흐름 전체를 다룹니다.

| 영역 | 내용 | 우선순위 |
|---|---|---|
| (a) 프로필 편집 | 신체 정보 편집 → `POST /health/profile-snapshots` + `GET /health/profile-snapshots/latest` | P1 |
| (b) 건강 프로필 | 만성질환 칩 멀티선택 + 직접 입력 → `POST /medical-records` + `/confirm` | P1 |
| (c) 건강 데이터 연동 | Health Connect(Android 우선) → `POST /health/sync` + `GET /health/daily-summary` | P1 |
| (d) 복약 알림 | flutter_local_notifications + 시간 휠 바텀시트 + 요일 반복 (로컬 스케줄) | P1 |
| (e) 알림 센터 | 시간 그룹핑 / 읽음 점 / 빈 상태 — 로컬 이력 우선 | P1 |
| (f) 탈퇴 · 동의 관리 | `POST /me/data-deletion-requests` + `GET/POST/DELETE /me/privacy/consents` | P1 |
| (g) 테마 영속 | shared_preferences 도입으로 `TODO(persist)` 해소 | P1 |

범위 제외(다른 문서/단계):
- **복약(약) 등록·체크리스트 서버 동기화** — `user_medications` 라우트가 현재 백엔드에 미등록(**백엔드 공백**, 팀원 브랜치 `Lemon-Aid-KDT/Lemon-sin feat/ai-agent-backend-integration`에 구현 존재). P1-1 임포트 후 **문서 09**에서 다룸. 건강 프로필 화면의 '복약' 탭은 그때까지 안내 상태로 둠.
- **서버 알림(reminder_preferences / notifications API)** — 백엔드 `reminder_preferences` 테이블은 존재하나 라우트 미등록(**백엔드 공백**). 이번 단계는 로컬 알림만, 서버 동기화는 `notifications.py` 임포트 후.
- **iOS HealthKit** — SoT v1.1 스코프상 Apple Health는 v2 이후 보류. 이번 단계는 Android Health Connect만 실연동, iOS는 '준비 중' 상태 표기.
- 인증(로그인/가입) — P2, 문서 별도.
- 리워드 — 범위 외(백엔드 전무).

---

## ② 디자인 스펙

### 2.1 참조 프레임 (figma `tabLE08wPC1EQ0XdfgCwII` · `_frames_index.md`)

| 프레임 ID | 이름 | 용도 |
|---|---|---|
| `780:23` | S-13 Settings · 설정 | 설정 메인 (as-built 기준) |
| `957:24` | 프로필 편집 | (a) 프로필 편집 화면 |
| `767:24` | S · 건강 프로필 (05-⑦) | (b) 만성질환 칩 멀티선택 + 직접 입력 |
| `915:24` | S-10 건강 데이터(워치 연동) (10-①) | (c) 연결 상태 / 메트릭 4종 / 주간 차트 |
| `951:58` | 워치 미연결 (14-③) | (c) 미연동 상태 화면 |
| `916:76` | 복약 알림 설정 (10-④) | (d) 시간 목록 + 요일 반복 |
| `959:24` | 시간 선택 바텀시트 (16-①) | (d) 시간 휠 |
| `761:24` | S · 알림 (05-⑤) | (e) 알림 센터 |
| `951:24` | 알림 빈 | (e) 빈 상태 |
| `957:63` | 알림 설정 (15-②) | (d)(e) 알림 토글 5종 |
| `957:108` | 약관 · 개인정보 (15-③) | (f) 약관·정책 목록 |
| `957:143` | 회원 탈퇴 (15-④) | (f) 경고 카드 + 사유 수집 |
| `959:55` | 로그아웃 확인 (16-②) | 계정 액션 확인 다이얼로그 |
| `959:68` | 토스트 (저장됨) (16-③) | 저장 피드백 |

### 2.2 레이아웃 구조 (프레임 판독 요약)

- **설정 메인(`780:23`)**: 노랑 헤더(브랜드 컬러 `AppColor.brand`) + 프로필 아바타/이름/가입 경과일 + 편집 버튼 → 아래 라운드 시트(`AppColor.section`, 상단 radius 28)에 섹션 카드 리스트. 섹션: 내 건강(만성질환·복약 / 관심 목적 / 신체 정보) → 알림 → 계정(내 정보 / 동의 관리) → 안내 → 테마 색상 4스와치. 현재 코드 구조와 일치(아래 ③).
- **프로필 편집(`957:24`)**: 풀스크린 폼 — 이름(닉네임), 생년월일(휠 시트 재사용), 성별 세그먼트, 키/몸무게 숫자 필드, 하단 고정 [저장하기] 52px 버튼.
- **건강 프로필(`767:24`)**: 상단 탭(만성질환 | 복약) → 만성질환 탭: 질환 칩 그리드 멀티선택(당뇨, 고혈압, 고지혈증, 신장 질환 등) + "직접 입력" 칩(텍스트 필드 노출) + 하단 [저장하기]. 선택 칩은 `AppColor.brand` 채움 + 체크, 미선택은 `AppColor.surface` + `AppColor.border` 외곽선.
- **건강 데이터(`915:24`)**: 연결 상태 카드(기기명 + 상태 칩) → 메트릭 4종 타일 2×2(걸음 수 / 심박수 / 체중 / 활동 에너지 — `HealthDailyAggregate` 필드와 1:1) → 주간 바 차트 → [동기화하기]. 미연결 시 `951:58` 레이아웃(마스코트 + "워치가 아직 연결되지 않았어요" + [연동하기] CTA).
- **복약 알림(`916:76`)**: 알림 시간 행 목록(시간 + 토글) + [시간 추가] → 시간 휠 바텀시트(`959:24`: 오전/오후 + 시/분 3열 휠, [확인] 버튼) + 요일 반복 칩 7개(월~일 멀티선택).
- **알림 센터(`761:24`)**: 시간 그룹 헤더("오늘", "어제", "이번 주") + 알림 행(아이콘 + 제목 + 본문 + 상대시각 + **읽지 않음 점**(`AppColor.brand` 8px 원)). 빈 상태는 `951:24`.
- **회원 탈퇴(`957:143`)**: 경고 카드(danger soft 배경, 삭제 항목 불릿) → 사유 선택 라디오(로컬 수집) → 확인 체크박스 → [탈퇴하기] (`AppColor.danger`) — 최종 확인 다이얼로그 1회 더.

### 2.3 사용 토큰 / 컴포넌트 (design_tokens_v2 단일 출처)

- 색: `AppColor.brand` / `brandSoft` / `brandDeep` / `brandTint`, `AppColor.section` / `surface` / `sunken` / `border`, `AppColor.ink` / `inkSecondary` / `inkTertiary`, `AppColor.success(Soft)` / `warning(Soft)` / `danger(Soft)`. hex 직접 기재 금지 — 예: `#FFC700`(= `AppColor.brand`).
- 타이포: `AppText.subtitle`(행 타이틀 16), `AppText.body`(본문 15, 시니어 최소), `AppText.caption`(13), `AppText.micro`(11).
- 간격/곡률: `AppSpace.page/lg/md/sm/xs/cardInside`, `AppRadius.md/lg/xl`.
- 기존 컴포넌트 재사용: `_SettingsCard`/`_SettingsRow`/`_SectionLabel`(settings_screen.dart 내 — 서브화면에서 쓰도록 공용 위젯으로 승격), `StatusStateView`(6변형), `showAppDialog` / `showAppBottomSheet` / `showDeleteConfirmDialog` / `showUndoToast`(`lib/widgets/common/app_modals.dart`), `MedicalDisclaimer`(면책 푸터).
- 접근성: 버튼 높이 52px+, 터치 타깃 48px+, 색+아이콘+텍스트 병행.

---

## ③ 현재 코드 상태

| 구분 | 파일 | 상태 |
|---|---|---|
| 설정 메인 | `mobile/lib/screens/settings_screen.dart` (732줄) | **부분 구현**. 동의 상태 카드(`_ConsentStatusCard` — grant/reload 실연동), JWT 토큰 관리(`_TokenAccessCard`), 테마 4색 스와치(`_ThemeSwatchRow` → `brandThemeProvider`) = **as-built**. 프로필 헤더(`_ProfileHeader`)는 '태동님' 정적 하드코딩 + 편집 버튼 no-op. '내 건강/알림/안내' 섹션 행 전부 정적(탭해도 이동 없음, `_SettingsRow`에 onTap 자체가 없음) |
| 테마 컨트롤러 | `mobile/lib/shared/theme/brand_theme_controller.dart` (110줄) | **부분 구현**. `BrandThemeNotifier`(in-memory) + `buildThemedLemonAidTheme`. `TODO(persist)`: shared_preferences 미도입으로 앱 재시작 시 yellow로 초기화 |
| 상태 템플릿 | `mobile/lib/shared/widgets/status_state_view.dart` | **완료(as-built)**. `StatusStateVariant` 6종: emptyNew / syncFailed / permissionDenied / analysisFailed / **notificationsEmpty** / searchEmpty |
| 모달 템플릿 | `mobile/lib/widgets/common/app_modals.dart` | **완료(as-built)**. `showAppDialog` / `showAppBottomSheet` / `showDeleteConfirmDialog` / `showInteractionWarningDialog` / `showUndoToast` 등 |
| API 클라이언트 | `mobile/lib/core/api/api_client.dart` | **완료(as-built)**. baseUrl이 `/api/v1`로 끝남 → **호출 경로는 접두사 제거 형태**(예: `/health/sync`). 403 처리 참조 패턴: `mobile/lib/features/chat/chat_repository.dart`(`consent_required` → 동의 1회 grant 후 재시도) |
| 라우팅 | `mobile/lib/app.dart` | `/shell/settings` 등록됨. 서브 라우트 없음 — 전부 신규 |
| 의존성 | `mobile/pubspec.yaml` | `shared_preferences` / `flutter_local_notifications` / `health` **전부 없음** — 신규 추가 필요 |
| Android 매니페스트 | `mobile/android/app/src/main/AndroidManifest.xml` | CAMERA / INTERNET / 미디어 읽기만. `POST_NOTIFICATIONS` · Health Connect 권한 **없음** |
| 프로필 리포지토리 | — | **없음**. `features/profile/` 신규 |
| 의료기록 리포지토리 | — | **없음**. `features/medical/` 신규 |
| 건강 동기화 | — | **없음**. `features/health_sync/` 신규 |
| 로컬 알림 서비스 | — | **없음**. `shared/services/` 신규 |
| 알림 센터 화면 | — | **없음** (플랜 §2.2 "캘린더/알림: 명시적 placeholder") |

백엔드(실재 확인 — `backend/Nutrition-backend/src/api/v1/`):
- `health.py`: `POST /health/sync`, `POST /health/profile-snapshots`, `GET /health/profile-snapshots/latest`, `POST /health/metric-samples`, `GET /health/daily-summary` ✅
- `medical_records.py`: `POST/GET /medical-records`, `POST /medical-records/{id}/confirm` ✅
- `privacy.py`: `GET/POST/DELETE /me/privacy/consents*`, `POST/GET /me/data-deletion-requests*` ✅
- `user_medications` / `notifications`(reminder_preferences) 라우트: **백엔드 공백** (라우트 파일 자체가 미등록 — 날조 금지 원칙에 따라 본 문서 범위에서 서버 동기화 제외)
- **프로필 '이름(닉네임)' 필드**: `BodyProfileSnapshotCreate`에 이름 필드가 없음 → **백엔드 공백**. 이름은 로컬(shared_preferences) 저장으로 처리하고 헤더에 표시.

---

## ④ 구현 단계 (파일 단위 체크리스트)

### 0단계 — 공통 기반 (선행)

1. [ ] `mobile/pubspec.yaml` — `shared_preferences`, `flutter_local_notifications`, `health`, `timezone`(스케줄 계산용) 추가 → `flutter pub get`
2. [ ] `mobile/lib/app.dart` — `/shell/settings` 하위 라우트 추가: `profile-edit`, `health-profile`, `health-data`, `medication-reminders`, `notification-settings`, `policies`, `withdraw` + `/shell/home/notifications`(알림 센터)
3. [ ] `mobile/lib/screens/settings_screen.dart` — `_SettingsRow`에 `onTap` 파라미터 추가, 각 행을 위 라우트로 배선. `_SettingsCard`/`_SettingsRow`/`_SectionLabel`을 `mobile/lib/widgets/settings/settings_widgets.dart`로 승격(서브화면 공용)

### (g) 테마 영속 — 가장 작은 단위, 먼저

4. [ ] `mobile/lib/shared/theme/brand_theme_controller.dart` — `BrandThemeNotifier`에 `SharedPreferences` 주입: 생성 시 `brand_theme` 키 로드, `select()`에서 저장. `TODO(persist)` 주석 제거
5. [ ] `mobile/lib/main.dart`(또는 `app_providers.dart`) — `SharedPreferences.getInstance()`를 부트스트랩에서 1회 획득해 ProviderScope override로 주입(비동기 빌드 회피)
6. [ ] 테스트: 저장→재생성 시 테마 복원 단위 테스트

### (a) 프로필 편집

7. [ ] `mobile/lib/features/profile/profile_models.dart` — `BodyProfileSnapshot`(sex/birth_year/height_cm/weight_kg/waist_cm/activity_level/effective_at) fromJson/toJson. `GET latest`의 `{"status":"not_ready"}` 응답을 null 매핑
8. [ ] `mobile/lib/features/profile/profile_repository.dart` — `fetchLatest()` = `GET /health/profile-snapshots/latest`, `save()` = `POST /health/profile-snapshots`(source는 `"manual"` 고정). chat_repository와 동일한 **403 `consent_required` → `POST /me/privacy/consents/sensitive_health_analysis` 1회 → 재시도** 패턴
9. [ ] `mobile/lib/screens/settings/profile_edit_screen.dart` — figma `957:24` 폼. 이름은 shared_preferences `profile_display_name` 키(서버 공백 명시 주석), 생년월일 휠(기존 바텀시트 패턴), 성별 세그먼트(`male`/`female`), 키/몸무게 숫자 입력(스키마 범위 검증: 키 30~260, 몸무게 1~500). 저장 성공 시 `showUndoToast` 대신 일반 토스트("저장했어요") + pop
10. [ ] `settings_screen.dart` `_ProfileHeader` — 정적 '태동님' 제거 → 로컬 이름 + `fetchLatest()` 결과 요약("키 172cm · 68kg" 식) 표시, 편집 버튼 → `profile-edit` 라우트

### (b) 건강 프로필 (만성질환)

11. [ ] `mobile/lib/features/medical/medical_models.dart` — `MedicalRecord`(id/record_type/status/conditions[]/medications[]), `PatientCondition`(condition_text/clinical_status/onset_date_text)
12. [ ] `mobile/lib/features/medical/medical_records_repository.dart` — `list()` = `GET /medical-records`, `addCondition(String text)` = `POST /medical-records` `{record_type:"condition", source:"user_manual", condition:{condition_text, clinical_status:"active", source:"user_confirmed"}, user_confirmed:true}` → 201 후 `POST /medical-records/{id}/confirm` `{user_confirmed:true, status:"active"}`, `archive(id)` = confirm에 `status:"archived"`. 403 동의 재시도 패턴 동일
13. [ ] `mobile/lib/screens/settings/health_profile_screen.dart` — figma `767:24`. 진입 시 `list()`로 기존 condition 레코드 → 선택 상태 복원. 프리셋 칩(당뇨/고혈압/고지혈증/신장 질환/간 질환/위장 질환 등) + '직접 입력' 칩 → 텍스트 필드(180자 제한 = 스키마 max). 저장 시: 신규 선택 → addCondition, 해제 → archive. **복약 탭**: `user_medications` 라우트 임포트 전까지 "복약 정보는 곧 연결돼요" 안내 패널(문서 09 연계)
14. [ ] 하단 면책 푸터: "입력하신 정보는 건강 참고용이며 진단·처방이 아닙니다" (`MedicalDisclaimer` 또는 동일 문구 고정 푸터)

### (c) Health Connect 연동 (Android 우선)

15. [ ] `mobile/android/app/src/main/AndroidManifest.xml` — Health Connect 읽기 권한 4종: `android.permission.health.READ_STEPS` / `READ_HEART_RATE` / `READ_WEIGHT` / `READ_ACTIVE_CALORIES_BURNED` + 권한 사용 근거 액티비티 인텐트 필터(`androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE`)
16. [ ] `mobile/lib/features/health_sync/health_connect_service.dart` — `health` 패키지 래퍼: 가용성 확인(미설치 → 설치 안내), 권한 요청, 최근 7일 일자별 집계(steps/restingHeartRate/weight/activeEnergy) 수집. **iOS에서는 항상 unavailable 반환**(HealthKit v2 보류 명시 주석)
17. [ ] `mobile/lib/features/health_sync/health_sync_repository.dart` — `sync(records)` = `POST /health/sync` `{client_batch_id: <uuid>, records:[{measured_date, source_platform:"android_health_connect", steps, weight_kg, resting_heart_rate_bpm, active_energy_kcal}]}` (403 → `health_device_data` 동의 grant 1회 → 재시도, **409 idempotency_conflict는 '이미 반영됨'으로 정상 처리**), `weekly()` = `GET /health/daily-summary?start_date&end_date&limit=7`
18. [ ] `mobile/lib/screens/settings/health_data_screen.dart` — figma `915:24`. 상태 분기: 미연동 → `951:58` 레이아웃(`StatusStateView` 신규 변형 `watchDisconnected` 추가 또는 permissionDenied 변형 커스텀) / 연동 → 메트릭 4종 타일 + 주간 바 차트(`daily-summary` 기반) + [동기화하기]. 동기화 결과 토스트: "걸음 수 등 N일치를 가져왔어요"
19. [ ] `settings_screen.dart` — '내 건강' 섹션에 '건강 데이터 연동' 행 추가(연결 상태 칩: 연동됨 `AppColor.success` / 미연동 `AppColor.inkTertiary`)

### (d) 복약 알림 (로컬)

20. [ ] `mobile/lib/shared/services/local_notification_service.dart` — flutter_local_notifications 초기화(Android 채널 '복약 알림', iOS Darwin 설정), 권한 요청(Android 13+ `POST_NOTIFICATIONS`, iOS alert/sound/badge), `zonedSchedule` 요일×시간 반복 등록/해제, 발송 시 로컬 이력 기록((e)와 공유)
21. [ ] `mobile/android/app/src/main/AndroidManifest.xml` — `POST_NOTIFICATIONS`, `SCHEDULE_EXACT_ALARM`(또는 inexact 폴백), `RECEIVE_BOOT_COMPLETED`(재부팅 후 재등록)
22. [ ] `mobile/lib/widgets/common/time_wheel_sheet.dart` — figma `959:24` 시간 휠 바텀시트: `CupertinoPicker` 3열(오전·오후/시/분) + [확인] 52px. `showAppBottomSheet` 셸 재사용
23. [ ] `mobile/lib/features/reminders/medication_reminder_store.dart` — shared_preferences에 `medication_reminders` JSON(시간 목록 + 요일 set + 활성 토글). **서버 reminder_preferences 동기화는 백엔드 공백 — notifications 라우트 임포트 후 추가** 주석
24. [ ] `mobile/lib/screens/settings/medication_reminder_screen.dart` — figma `916:76`: 시간 행(토글) 목록 + [시간 추가] → 시간 휠 + 요일 칩 7개. 저장 시 스케줄 재등록 + "알림을 설정했어요" 토스트. 영양제 저장 완료 화면(문서 07 흐름)의 "복용 알림 설정하기" CTA가 이 라우트로 딥링크
25. [ ] `mobile/lib/screens/settings/notification_settings_screen.dart` — figma `957:63` 토글 5종(복약 시간 / 분석 완료 / 리포트 / 마케팅 / 야간 무음): 로컬 설정 키로 저장, 복약 토글 off 시 스케줄 일괄 해제

### (e) 알림 센터

26. [ ] `mobile/lib/features/notifications/notification_history_store.dart` — 로컬 이력(shared_preferences JSON: id/제목/본문/타입/발생시각/읽음). 발송 콜백 + 주요 앱 이벤트(분석 완료 등)에서 append. **서버 푸시 이력은 P2(백엔드 공백)**
27. [ ] `mobile/lib/screens/notification_center_screen.dart` — figma `761:24`: "오늘/어제/이번 주" 그룹 헤더 + 행(읽지 않음 점 `AppColor.brand`), 탭 시 읽음 처리, 비어 있으면 `StatusStateView(variant: notificationsEmpty)`. 홈/설정 헤더의 종 아이콘에서 진입 + 미읽음 배지

### (f) 탈퇴 · 동의 관리

28. [ ] `mobile/lib/features/privacy/privacy_repository.dart` — `consents()` = `GET /me/privacy/consents`, `grant/revoke(type)` = `POST/DELETE /me/privacy/consents/{consent_type}`, `requestDeletion()` = `POST /me/data-deletion-requests` `{request_type:"all_user_data"}`(202), `deletionStatus(id)` = `GET /me/data-deletion-requests/{id}` (기존 app_controller 동의 로직과 중복되지 않게 위임/통합)
29. [ ] `mobile/lib/screens/settings/withdraw_screen.dart` — figma `957:143`: dangerSoft 경고 카드(삭제되는 항목 불릿) → 사유 라디오(**로컬 수집만** — 서버 필드 없음) → 확인 체크 → [탈퇴하기] → `showDeleteConfirmDialog` 최종 확인 → `requestDeletion()` 성공(202) 시 로컬 토큰/스토리지 정리 + 완료 화면("요청을 접수했어요. 그동안 함께해 주셔서 감사해요")
30. [ ] `mobile/lib/screens/settings/policies_screen.dart` — figma `957:108`: 약관·개인정보 처리방침 정적 목록(로컬 문서/웹뷰), 동의 관리 행 → 기존 `_ConsentStatusCard` 확장(9종 ConsentType 중 사용자가 다룰 5종: sensitive_health_analysis / health_device_data / ocr_image_processing / food_image_processing / data_retention 토글 — revoke는 DELETE 호출)

---

## ⑤ 엔드포인트 계약 표

> ApiClient 경로 표기 = `/api/v1` 접두사 제거 형태(baseUrl에 포함됨). 모든 호출 Bearer 인증 필수. 403 `{"detail":{"code":"consent_required","required_consents":[...]}}` 수신 시 해당 동의 `POST /me/privacy/consents/{type}` 1회 후 재시도(chat_repository 패턴).

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의 / 스코프 |
|---|---|---|---|
| `POST /health/profile-snapshots` | `source:"manual"`, `sex?`, `birth_year?`(1900~2100), `height_cm?`(30~260), `weight_kg?`(1~500), `waist_cm?`, `activity_level?`, `effective_at?` | 201: `id`, `effective_at`, `sex`, `birth_year`, `height_cm`, `weight_kg`, `waist_cm`, `activity_level`, `created_at` | sensitive_health_analysis / health:write |
| `GET /health/profile-snapshots/latest` | — | 스냅샷 동일 필드 **또는** `{"status":"not_ready"}` | sensitive_health_analysis / health:read |
| `POST /health/sync` | `client_batch_id?`, `records[1..366]`: `{measured_date, source_platform:"android_health_connect", steps?(0~200000), weight_kg?(20~300), resting_heart_rate_bpm?(20~240), active_energy_kcal?(0~20000), source_record_hash?}` | 202: `batch_id`, `accepted_count`, `rejected_count`, `synced_at` · 409 `idempotency_conflict` | health_device_data / health:write |
| `GET /health/daily-summary?start_date&end_date&limit(≤366)` | 쿼리만 | `summaries[]`: `measured_date`, `source_platform`, `steps`, `weight_kg`, `resting_heart_rate_bpm`, `active_energy_kcal`, `synced_at` | health_device_data / health:read |
| `POST /medical-records` | `record_type:"condition"`, `source:"user_manual"`, `condition:{condition_text(≤180), clinical_status:"active", onset_date_text?}`, `user_confirmed:true` | 201: `id`, `record_type`, `status`, `conditions[]{id, condition_text, clinical_status}`, `created_at` | sensitive_health_analysis / medical:write |
| `GET /medical-records?include_archived&limit(≤100)` | 쿼리만 | `records[]`(위 응답 배열) | sensitive_health_analysis / medical:read |
| `POST /medical-records/{record_id}/confirm` | `user_confirmed:true`, `status:"active"｜"archived"` | 200: 확정된 레코드 · 404 `medical_record_not_found` · 409 `medical_record_not_confirmable` | sensitive_health_analysis / medical:write |
| `GET /me/privacy/consents` | — | `consents[]`(타입별 granted 상태) | — / privacy:read |
| `POST /me/privacy/consents/{consent_type}` | path: ConsentType 9종 | 201: 동의 grant 이벤트 | — / privacy:write |
| `DELETE /me/privacy/consents/{consent_type}` | path | 동의 revoke 이벤트 | — / privacy:write |
| `POST /me/data-deletion-requests` | `request_type:"all_user_data"`(그 외 422) | 202: 삭제 요청(즉시 처리) | — / privacy:delete |
| `GET /me/data-deletion-requests/{id}` | path | 요청 상태(`completed`/`failed` 등) | — / privacy:read |

**백엔드 공백 (날조 금지 — 라우트 미존재 명시)**

| 필요 기능 | 상태 |
|---|---|
| 복약(약) 목록/체크 `user_medications` | 라우트 미등록 — 팀원 브랜치에 구현 존재, P1-1 임포트 후 문서 09 |
| 복약 알림 서버 동기화 `reminder_preferences`(notifications) | 테이블만 존재, 라우트 미등록 — 임포트 후 로컬 스케줄에 동기화 레이어 추가 |
| 프로필 이름·닉네임 서버 저장 | `BodyProfileSnapshotCreate`에 필드 없음 — 로컬 저장으로 대체 |
| 서버 푸시 알림 이력 | 전무 — P2 |
| 탈퇴 사유 서버 수집 | `DeletionRequestCreate`에 사유 필드 없음 — 로컬 수집만 |

---

## ⑥ 상태 / 에러 처리

| 상황 | 처리 (사용자 문구는 해요체) |
|---|---|
| 프로필 latest `{"status":"not_ready"}` | 폼을 빈값으로 열고 헤더에 "신체 정보를 입력하면 분석이 더 정확해져요" 안내 |
| 만성질환 기록 0건 | 칩 전부 미선택 상태로 표시(별도 빈 화면 불필요) |
| 워치 미연동 / Health Connect 미설치 | figma `951:58` 레이아웃 — "워치가 아직 연결되지 않았어요" + [연동하기] / 미설치 시 Play 스토어 이동 CTA |
| Health Connect 권한 거부 | `StatusStateView(variant: permissionDenied)` + 시스템 설정 이동 CTA — SoT §8 'HC거부' 메시지 매핑 |
| `POST /health/sync` 409 idempotency_conflict | 오류로 띄우지 않음 — "이미 최신 상태예요" 토스트 |
| 네트워크 실패(ApiClient 공통) | `StatusStateView(variant: syncFailed)` + [다시 시도] (기존 메시지 "서버에 연결하지 못했어요…" 재사용) |
| 403 consent_required | 동의 1회 grant 후 자동 재시도(chat_repository 패턴). 재시도도 403이면 동의 안내 패널 노출 |
| medical-records confirm 404/409 | "정보를 다시 불러올게요" 후 목록 재조회(낙관적 UI 롤백) |
| 알림 권한 거부(POST_NOTIFICATIONS/iOS) | 시간 추가는 허용하되 상단 배너 "알림 권한을 허용해야 시간에 맞춰 알려드릴 수 있어요" + 설정 이동 |
| 알림 센터 빈 상태 | `StatusStateView(variant: notificationsEmpty)` |
| 탈퇴 최종 확인 | `showDeleteConfirmDialog` — 파괴적 액션 공통 모달(figma `921:40` 계열), 처리 중 버튼 비활성 |
| 신뢰도 표기 | 본 영역 해당 시(건강 데이터 품질 등) % 직접 노출 금지 — 등급 칩만 |
| 면책 푸터 | 건강 프로필·건강 데이터 화면 하단 고정: "건강 참고용이며 진단·처방이 아닙니다" |

---

## ⑦ 테스트 계획

검증 기준선: `flutter analyze` 0건 + `flutter test` 전체 통과(현재 170개 기준, 신규 추가분 포함).

**단위 테스트**
- [ ] `profile_repository_test.dart` — latest not_ready→null 매핑, POST 직렬화(Decimal 문자열), 403→동의 grant→재시도 1회(mock http)
- [ ] `medical_records_repository_test.dart` — addCondition 2단계(create→confirm) 호출 순서, archive payload, 404/409 예외 매핑
- [ ] `health_sync_repository_test.dart` — records 직렬화(`measured_date` ISO date, `source_platform` 값), 409→정상 처리 분기, `client_batch_id` 부여
- [ ] `brand_theme_controller_test.dart` — shared_preferences 저장/복원(기존 테스트 확장)
- [ ] `medication_reminder_store_test.dart` — JSON 라운드트립, 요일 반복 다음 발화 시각 계산
- [ ] `notification_history_store_test.dart` — 시간 그룹핑(오늘/어제/이번 주), 읽음 처리

**위젯 테스트**
- [ ] `profile_edit_screen_test.dart` — not_ready 빈 폼 / 기존 값 프리필 / 범위 밖 입력 검증 문구
- [ ] `health_profile_screen_test.dart` — 칩 선택 토글, 직접 입력 칩→필드 노출, 기존 레코드 복원, 면책 푸터 존재
- [ ] `health_data_screen_test.dart` — 미연동(`951:58`)/연동 분기, 동기화 버튼→repository 호출
- [ ] `medication_reminder_screen_test.dart` — 시간 휠 확인→행 추가, 요일 칩 멀티선택, 토글 off
- [ ] `notification_center_screen_test.dart` — 그룹 헤더, 미읽음 점, 빈 상태 변형
- [ ] `withdraw_screen_test.dart` — 확인 체크 전 버튼 비활성, 최종 다이얼로그 경유

**금칙어 가드 (회귀 공통)**
- [ ] 신규 사용자 문구 전체에 의료법 금칙어(진단/처방/치료/효능) 부재 assert — 기존 금칙어 테스트 패턴에 신규 화면 문자열 등록
- [ ] release_security_config_test 통과 유지(매니페스트 변경이 cleartext 예외를 건드리지 않는지)
- [ ] 신뢰도 % 직접 노출 부재 assert

---

## ⑧ 플랫폼 노트

**Android — Pixel 10 Pro · Android 17 (targetSdk 36)**
- Health Connect는 시스템 통합(Android 14+) — Pixel 10 Pro에서는 별도 앱 설치 불필요. 권한 4종 + rationale 인텐트 필터 필수, 미선언 시 권한 시트가 아예 뜨지 않음
- `POST_NOTIFICATIONS` 런타임 권한(Android 13+) — 복약 알림 첫 설정 시 요청, 요청 전 한국어 목적 설명 다이얼로그 선행(심사·UX 규칙)
- 정확 알람: `SCHEDULE_EXACT_ALARM`은 Android 14+에서 기본 거부 가능 → `androidScheduleMode: inexactAllowWhileIdle` 폴백 권장(복약 알림은 ±수분 허용)
- 재부팅 후 스케줄 소실 → `RECEIVE_BOOT_COMPLETED` 리시버로 재등록
- 빌드: `flutter build apk --debug --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` (debug cleartext 오버레이는 P0 반영 완료 — release 차단 유지)

**iOS — iPhone 17 Pro · iOS 26.5 (deployment target 15.0)**
- **HealthKit은 SoT v1.1상 v2 이후 보류** — 엔타이틀먼트/Info.plist 추가 금지. 건강 데이터 화면은 iOS에서 "iPhone 건강 연동은 준비 중이에요" 상태로 분기
- 로컬 알림: `flutter_local_notifications` Darwin 초기화 + alert/sound/badge 권한 — 권한 문구는 P0에서 적용한 한국어 문구 톤과 일치시킬 것
- 라이트 모드 고정(`UIUserInterfaceStyle=Light`, P0 반영 완료) 전제로 색 토큰 그대로 사용
- 빌드 검증: `flutter build ios --no-codesign`, 시뮬레이터 dev API `http://127.0.0.1:8000/api/v1`(ATS LocalNetworking 허용 확인됨). 단, 시뮬레이터는 로컬 알림 발화 확인 제한 → 실기기 스모크 권장

---

## ⑨ 완료 기준 (DoD)

- [ ] 설정 메인의 모든 행이 실제 서브화면으로 이동(no-op 행 0개), 프로필 헤더가 실데이터(로컬 이름 + 최신 스냅샷) 표시
- [ ] 프로필 편집 저장 → `POST /health/profile-snapshots` 201 → 재진입 시 `GET latest`로 프리필 (수동 검증 + 위젯 테스트)
- [ ] 건강 프로필에서 만성질환 추가/해제가 `medical-records` create→confirm/archive로 반영되고 재진입 시 복원
- [ ] Android 실기기/에뮬에서 Health Connect 권한 승인 → 동기화 → `POST /health/sync` 202 → 주간 차트에 `daily-summary` 값 표시; iOS는 보류 상태 화면 정상
- [ ] 복약 알림: 시간 휠로 등록한 요일×시간에 로컬 알림 발화(Android 실기기), 토글 off 시 미발화, 발화 내역이 알림 센터에 적재
- [ ] 알림 센터: 그룹핑·읽음 점·빈 상태 3종 동작
- [ ] 탈퇴: `POST /me/data-deletion-requests` 202 수신 → 로컬 세션 정리 → 완료 화면; 동의 토글 grant/revoke 왕복 동작
- [ ] 테마 4색 선택이 앱 재시작 후에도 유지(`TODO(persist)` 주석 제거 확인)
- [ ] `flutter analyze` 0건 · `flutter test` 전체 통과(기존 170 + 신규) · 금칙어/% 비노출/면책 푸터 가드 테스트 포함
- [ ] 백엔드 공백 항목(user_medications·notifications 라우트, 프로필 이름 필드)이 코드 주석과 문서 09 백로그에 명시되어 있고, 존재하지 않는 라우트 호출이 코드에 없음
