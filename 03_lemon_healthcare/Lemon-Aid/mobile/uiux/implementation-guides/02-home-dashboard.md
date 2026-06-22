# Lemon-Aid UI/UX 구현 가이드 — 02 홈 대시보드

> 기준일 2026-06-12 · 디자인 소스: `mobile/uiux/figma` (DS v2.0 · SoT v1.1) · 브랜치 `feat/ai-agent-chat-import`
> 공통 규약·권위 체계·완료 현황은 [00-overview-and-conventions.md](00-overview-and-conventions.md) 선행 숙지. 선행 백엔드 작업은 [09-backend-route-imports.md](09-backend-route-imports.md), 달력 월 펼침은 [07-records-calendar.md](07-records-calendar.md)와 연계.

---

## ① 범위 / 목표

- **범위**: 5탭 셸의 첫 번째 탭 — 홈(`/shell/home`). 노랑 브랜드 헤더, 건강 점수 히어로 카드, 오늘의 분석 요약 카드, 영양제 상호작용 카드(3상태), 식단 관리(끼니별), 영양제 체크리스트, 면책 푸터, 그리고 홈에 붙는 잔여 기능(복약 관리 카드, 달력 월 펼침 진입, 소모/잔여 kcal, 체크 영속).
- **상태**: P0 배치 A(`4fab30d6`)로 **핵심 카드 전부 실데이터 연동 완료(as-built)**. 이 문서는 as-built를 참조 수준으로 요약하고, **잔여 5건(a~e)을 구현 가능 수준으로 상세화**한다.
  - (a) 복약 관리 카드 — `user_medications` 라우트 임포트(문서 09) 후 GET/POST 연동
  - (b) 달력 위젯 A안(소프트 셀) → 월 펼침 전환(문서 07 연계)
  - (c) 소모 kcal·잔여 kcal — Health Connect 연동 전 잠금 상태 표기
  - (d) '오늘의 분석' 요약 카드 ↔ 분석 탭(S-09) 딥링크
  - (e) 영양제 체크 상태 영속화 — `shared_preferences` 도입 시점(P1-5)과 함께

---

## ② 디자인 스펙

### 참조 프레임 (`figma/_frames_index.md`, 페이지 `03_UI_Design`)

| 프레임 ID | 이름 | 용도 |
|---|---|---|
| `268:24` | S-07 Main (홈) | 홈 전체 레이아웃 기준 |
| `580:29` | 상호작용 · 상태 변형 | 상호작용 카드 3상태(주의 N건 / 안심 / 약 미등록) |
| `356:25` / `357:24` / `358:24` | 달력 A / B / C | 주간 위젯 비교 — **A안(소프트 셀) 채택**(플랜 §3.1) |
| `364:24` | 전체 달력 (펼침) | 월 그리드 펼침 — 문서 07의 캘린더 화면 |
| `800:23` | S-09 분석 (오늘의 분석) | (d) 딥링크 목적지 |
| `763:24` | S · 캘린더 | 캘린더 진입 아이콘 동선 |
| `916:76` | 복약 알림 설정 | 복약 카드의 후속 동선(문서 08) |
| `951:58` | 워치 미연결 | (c) 소모 kcal 잠금 상태 문구 톤 |

### 레이아웃 구조 (S-07 `268:24` 기준, as-built 일치)

```
┌ 노랑 브랜드 헤더 (AppColor.brand, status bar 포함)
│   워드마크 '레몬·에이드' + 우측 아이콘 3 (캘린더/알림/프로필)
│   ※ 기록 모드(과거 날짜)일 때만 주간 날짜 스트립 노출 — 달력 A안 소프트 셀
├ 본문 (AppColor.bg, 상단 28r 라운드로 헤더 위에 겹침)
│   1. HealthHeroCard — 날짜 네비 캡슐 + 점수 반원 게이지 + kcal/매크로 3종 바
│   2. 오늘의 분석 요약 카드 (health_score.message)        ← (d) 딥링크 추가
│   3. 영양제 상호작용 카드 (3상태)                        ← (a) 후 '약 미등록' 분기 갱신
│   4. 식단 관리 카드 (아침/점심/저녁/간식 슬롯)
│   5. 영양제 체크리스트 카드 (n/m 완료)                   ← (e) 체크 영속
│   6. [신규] 복약 관리 카드                               ← (a)
│   7. 면책 푸터 (_MedicalDisclaimer)
└ 하단 탭바 (+FAB)
```

### 사용 토큰/컴포넌트 (design_tokens_v2 단일 출처)

- 색: `AppColor.brand`(헤더)·`brandDeep`(강조)·`brandSoft`(아이콘 배지)·`bg/surface/sunken/border`·`ink/inkSecondary/inkTertiary`·`success`(안심)·`warning`(주의)
- 타이포: `AppText.subtitle`(카드 제목)·`body`(본문 15px, 시니어 최소)·`bodyLg`·`caption`·`micro`
- 간격/라운드: `AppSpace.page/xl/lg/md/sm/xs/cardInside`, `AppRadius.lg`(메인 카드)·`sm`·`full`(칩)
- 카드 데코: `dashboard_screen.dart`의 `_mainCardDeco()`(surface + soft shadow) — 신규 복약 카드도 동일 데코 사용
- 상태 템플릿: `shared/widgets/status_state_view.dart`(`syncFailed`/`emptyNew` 변형 사용 중)
- 매크로 3색 포인트는 `health_hero_card.dart` 상수(`_kCarb/_kProtein/_kFat`) — DS v2.0 시맨틱 외 보조색, 변경 시 토큰 승격 검토

---

## ③ 현재 코드 상태

### 구현 완료 (as-built — 변경 금지 영역, 참조만)

| 영역 | 파일 | 비고 |
|---|---|---|
| 홈 화면 본체 | `mobile/lib/screens/dashboard_screen.dart` (1,285줄) | 헤더/히어로/오늘의분석/상호작용 3상태/식단/영양제 체크리스트/면책. 날짜 스와이프·페이드 전환·당겨서 새로고침 포함 |
| 히어로 카드 | `mobile/lib/widgets/dashboard/health_hero_card.dart` | 점수 게이지(`scoreReady` 분기), `targetKcal=null`이면 '기록 합계' 모드(목표 하드코딩 금지), `_hasTarget`일 때만 소모/잔여 행 노출 |
| 홈 모델 | `mobile/lib/features/dashboard/home_models.dart` | `DashboardHealthScore`(not_ready 수렴 null-safe), `HomeMeal*`, `HomeSupplement*` |
| 데이터 로딩 | `mobile/lib/app_controller.dart` | `bootstrap()`/`refreshDashboard()`/`_loadHomeData()` — meals·supplements·impact 3블록 병렬 + 블록별 실패 플래그(`homeMealsFailed` 등), `mealsForDay()` 클라이언트 필터(최근 7일 윈도) |
| API 경로 | `mobile/lib/features/supplements/supplement_repository.dart` | `/dashboard/summary`, `/meals`, `/supplements`, `/supplements/recommendations/latest` (ApiClient baseUrl에 `/api/v1` 포함 — 접두사 없음) |
| 테스트 | `mobile/test/widget/dashboard_screen_test.dart`, `mobile/test/unit/home_models_test.dart`, `mobile/test/unit/app_controller_test.dart` | 170개 스위트에 포함 |

### 부분 구현 (잔여 작업 대상)

- **영양제 체크 상태**: `dashboard_screen.dart:50` `_checkedSupplementIds` — 세션 메모리, `// TODO(persist): SharedPreferences 연동.` 주석 존재 → (e)
- **상호작용 카드 ③상태**: 현재 '등록된 영양제가 없어요'로만 분기(`_InteractionCard`) — 복약 라우트 부재로 약 기준 점검 미구현 → (a)
- **소모/잔여 kcal**: 히어로 카드가 지원하나 홈에서 `targetKcal: null`로 호출(`dashboard_screen.dart:178`) — '오늘 먹은 음식 합계예요' 폴백만 노출 → (c)
- **오늘의 분석 카드**: `_TodayAnalysisCard`는 표시 전용(탭 액션 없음) → (d)
- **캘린더 진입**: `mobile/lib/app.dart`의 `/shell/home/calendar`가 `_NeutralBranch` placeholder → (b), 화면 자체는 문서 07

### 미구현 (없음 상태)

- 복약 관리 카드 위젯·모델·repository 메서드 전부 없음 → (a)
- 로컬 영속 계층(`shared_preferences`) 미도입 — pubspec에 의존성 없음 → (e)

### 백엔드 상태

- `GET /dashboard/summary`의 `health_score` 블록 **배포 완료**(`b43b9bfd`, `src/services/daily_health_score.py`, `daily-health-score-v1.0.0`) — 산식·보류 결정 10건은 `outputs/todo-list/2026-06-11/2026-06-11-daily-health-score-decisions.md`
- `user_medications` 서비스(`backend/Nutrition-backend/src/services/user_medications.py`)는 로컬에 존재하나 **API 라우트 파일(`src/api/v1/user_medications.py`)은 미임포트** — 팀원 워크트리 `external/Lemon-sin-ai-agent-branch/backend/Nutrition-backend/src/api/v1/user_medications.py`(prefix `/me/medications`)에 구현 존재 → 문서 09에서 임포트
- ⚠️ `alembic upgrade head` 라이브 DB 1회 실행 미수행 — 잔여 작업 스모크 전 선행(00 문서 §4)

---

## ④ 구현 단계 (잔여 — 순서 있는 체크리스트)

### (a) 복약 관리 카드 — 선행: 문서 09의 라우트 임포트 완료

1. [ ] **백엔드 선행 확인** — 문서 09 완료 후 `GET /api/v1/me/medications` 200 응답 스모크 (`router.py` 등록 + alembic 적용 포함)
2. [ ] `mobile/lib/features/dashboard/home_models.dart` — `HomeMedication` 모델 추가: `id`, `displayName`, `medicationClass?`, `conditionTags`, `isActive`. 기존 패턴대로 null-safe `fromJson` + `HomeMedicationsResult`(items 배열 — 응답 키는 `items`, meals/supplements의 `results`와 다름에 주의)
3. [ ] `mobile/lib/features/supplements/supplement_repository.dart` — `fetchMedications()`(GET `/me/medications`), `createMedication(...)`(POST `/me/medications`), `deactivateMedication(id)`(POST `/me/medications/{id}/deactivate`) 추가. 403 `consent_required` → sensitive 동의 1회 후 재시도(chat_repository 패턴)
4. [ ] `mobile/lib/app_controller.dart` — `_loadHomeData()`의 `Future.wait`에 `_loadMedicationsBlock()` 추가(블록 독립 실패 플래그 `homeMedicationsFailed` 동일 패턴), getter 노출
5. [ ] `mobile/lib/screens/dashboard_screen.dart` — `_MedicationCard` 신규(`_mainCardDeco()` 톤 통일): 활성 약 목록 행(이름 + medication_class 한국어 라벨), 비어 있으면 `StatusStateView`류 안내 + [약 추가하기] → 약 이름 직접 입력 시트(POST). 하단 각주 "약 변경은 의사·약사와 상담해주세요." (금칙어 금지 — '복용 지도/처방' 표현 불가)
6. [ ] `_InteractionCard` 분기 갱신 — ③'미등록' 상태를 "영양제·약 모두 미등록"일 때로 좁히고, 약이 등록되면 카드 부제에 "등록한 약 N개 기준으로 함께 살펴봐요" 추가(시안 `580:29` ③상태 문구 톤)
7. [ ] **복용 체크 서버 동기화 — 백엔드 공백 명시**: 팀원 라우트에는 약/영양제의 **일별 섭취 체크(intake log) 엔드포인트가 없다**(있는 것은 GET/POST/PATCH `/me/medications*`와 deactivate뿐). 체크 상태는 (e)의 로컬 영속으로 처리하고, 서버 동기화는 `POST /me/medications/{id}/intake-logs`류 신규 라우트 협의 후 별도 P2 — **날조 금지, 이 문서 범위에서 서버 동기화 구현하지 않음**

### (b) 달력 A안 → 월 펼침 전환

8. [ ] 주간 스트립(A안 소프트 셀)은 as-built(`_BrandHeader`의 `_DateBubble` — 선택=흰 원, 오늘=brandDeep 점, 기록=ink 점) — 변경 없음
9. [ ] `mobile/lib/app.dart` — `/shell/home/calendar`의 `_NeutralBranch`를 문서 07의 `CalendarScreen`(월 그리드 `364:24`)으로 교체. 헤더 캘린더 아이콘과 히어로 카드 날짜 텍스트(`onTapDate`) 두 진입점 모두 동일 라우트 유지
10. [ ] 월 화면에서 날짜 탭 → 기존 기록 모드 재사용: `DashboardScreen(recordDate: picked)` push (이미 구현된 '지난 기록' 페이지) — 신규 화면 만들지 않음
11. [ ] 기록 점 데이터: 현재 `_recordDots()`는 최근 7일 meals 윈도만 — 월 범위는 문서 07에서 `GET /meals?from_eaten_at=&to_eaten_at=`(월 단위) + `GET /supplements` 집계로 별도 로딩(홈 컨트롤러 윈도 확장 금지 — 홈 성능 유지)

### (c) 소모 kcal · 잔여 kcal — Health Connect 전 잠금 표기

12. [ ] `health_hero_card.dart` — `_hasTarget == false` 폴백 행을 잠금 안내로 강화: 현재 "오늘 먹은 음식 합계예요" 유지 + 자물쇠/워치 아이콘과 "워치 연동 후 소모·잔여 칼로리를 보여드려요" 캡션(시안 `951:58` 워치 미연결 톤, 색+아이콘+텍스트 병행). **추정치 표시 금지**(점수 날조 금지 원칙과 동일)
13. [x] 목표 kcal(P1, Health Connect와 독립): `GET /health/profile-snapshots/latest` + `GET /nutrition/kdris` 기반 목표를 백엔드 값으로 주입 — 클라이언트 계산 금지(연산은 백엔드 원칙). 값 확보 시 `targetKcal` 전달 → 히어로가 자동으로 '소비/목표' 모드 전환 ✅ 2026-06-13 구현: `dashboard_screen._loadTargetKcal()` — 스냅샷 sex/birth_year 보유 시에만 `energy_kcal`(EER) 값을 그대로 사용, 미확보·실패 시 합계 모드 유지(추정치 날조 금지). 같은 작업에서 위젯 기본 소모 200kcal 추정치 노출을 제거(`burnedKcal` nullable — 소모는 14번 HC 주입 시에만). 라이브 확인: dev 백엔드 2020-sample 데이터셋(19~64세) 기준 0/2000 kcal 모드 캡처. **dev 컨테이너가 승인된 2025 데이터셋 대신 2020-sample을 쓰는 설정(KDRIS_DATA_VERSION)은 팀 결정 필요**
14. [ ] 소모 kcal(P1-6, 문서 08): Health Connect `POST /health/sync` → `GET /health/daily-summary`의 소모 kcal을 `burnedKcal`로 주입. 연동 전에는 12번 잠금 상태 고정

### (d) '오늘의 분석' 카드 ↔ 분석 탭 딥링크

15. [ ] `dashboard_screen.dart`의 `_TodayAnalysisCard` — 카드 전체를 `Pressable`로 감싸고 우측 `chevron_right` 추가, 탭 시 `context.go('/shell/score')` (분석 탭 = '오늘의 분석' S-09 `800:23`, 점수 분기는 P0 배치 C `88c3ef4b`에서 교체 완료)
16. [ ] 메시지 본문은 계속 `health_score.message`만 사용 — daily-coaching 본문 캐시 공유는 문서 06 소관(이중 호출 금지: 홈에서 `POST /ai-agent/daily-coaching` 호출하지 않음)
17. [ ] not_ready 시 기존 기록 유도 문구 유지 + 탭 시에도 분석 탭으로 이동(분석 탭의 not_ready 처리 재사용)

### (e) 영양제(·복약) 체크 상태 영속화 — P1-5와 동시 도입

18. [ ] `pubspec.yaml`에 `shared_preferences` 추가(P1-5 복약 알림·테마 영속과 같은 커밋으로 — `TODO(persist)` 일괄 해소)
19. [ ] 저장 키 설계: `home.supplement.checked.<yyyy-MM-dd>` → 체크된 supplement id 리스트(날짜별 — 자정 지나면 자동으로 빈 체크). 복약 카드 도입 시 `home.medication.checked.<yyyy-MM-dd>` 동일 패턴
20. [ ] `dashboard_screen.dart` — `_checkedSupplementIds`를 initState 로드 + 토글 시 저장으로 교체. 컨트롤러가 아닌 화면 로컬 유지(서버 데이터 아님 — 컨트롤러 오염 방지). 단위 테스트는 `SharedPreferences.setMockInitialValues` 사용
21. [ ] 서버 동기화는 7번 항목과 동일 — **백엔드 공백, 이번 범위 제외**

---

## ⑤ 엔드포인트 계약 표

> ApiClient 경로 표기 — baseUrl이 `/api/v1`을 포함하므로 접두사 제거 형태. 모든 호출 Bearer 인증.

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| GET `/dashboard/summary` | `as_of?`(date), `days`(1~365, 기본 30) | `health_score{data_status(ready·not_ready), score(0~100·null), label(excellent~needs_attention), label_text, message, components{activity·nutrition: subscore·weight}, source_citations[]{title·source_path·heading·excerpt·score}, disclaimers[], algorithm_version, measured_date}` + `nutrition`/`activity`/`weight`/`supplements` 블록 | `dashboard:read` + `sensitive_health_analysis` |
| GET `/meals` | `from_eaten_at?`, `to_eaten_at?`, `limit`(≤100, 기본 20), `offset`, (`cuisine_code?`·`course_code?`·`food_catalog_item_id?`) | `results[]{id, status, meal_type, eaten_at, food_items[]{display_name·kcal·carb_g·protein_g·fat_g}, nutrition_summary}`, `limit`, `offset` | `meal:read` (동의 불요) |
| GET `/supplements` | `limit`, `offset` | `results[]{id, display_name, manufacturer, intake_schedule{frequency·time_of_day·times_per_day}}`, `limit`, `offset` | `supplement:read` |
| GET `/supplements/recommendations/latest` | — | `excess_or_duplicate_risks[]{nutrient_code·nutrient_name·user_message·action}`, 안전 요약 메시지 | `sensitive_health_analysis` |
| GET `/me/medications` *(문서 09 임포트 후)* | — | `items[]{id, display_name, medication_class, condition_tags[], is_active}` | `analysis:read` + `sensitive_health_analysis` |
| POST `/me/medications` *(〃)* | `display_name`(필수 ≤160), `normalized_name?`, `medication_class?`(허용 목록 검증), `condition_tags`(≤8, 허용 태그만), `is_active` | `UserMedicationResponse`(단건) | `analysis:write` + `sensitive_health_analysis` |
| PATCH `/me/medications/{id}` *(〃)* | 위 필드 부분 갱신 | `UserMedicationResponse` | `analysis:write` + `sensitive_health_analysis` |
| POST `/me/medications/{id}/deactivate` *(〃)* | — | `UserMedicationResponse`(`is_active=false`) | `analysis:write` + `sensitive_health_analysis` |
| GET `/health/profile-snapshots/latest` *(P1, 목표 kcal)* | — | 신체 프로필 스냅샷 | `sensitive_health_analysis` |
| GET `/nutrition/kdris` *(P1, 목표 kcal)* | 프로필 파라미터 | KDRIs 기준치 | 공개(인증만) |
| **백엔드 공백** — 복용 체크(intake log) 동기화 | — | — | 라우트 없음 → 로컬 영속(e)로 대체, 신규 라우트는 백엔드 협의 후 P2 |

---

## ⑥ 상태 / 에러 처리

| 상황 | 처리 (as-built 패턴 유지) |
|---|---|
| 점수 `not_ready` | 히어로 카드 숫자/게이지 숨김(`scoreReady=false`) + 기록 유도, 탭 시 카메라(`/shell/camera?mode=meal`) — **점수 표시·추정 금지** (점수 결정 문서 재확인 사항) |
| meals/supplements/impact/medications 블록 실패 | 블록별 독립 플래그 → 카드 단위 `StatusStateView(syncFailed)` + 당겨서 새로고침 안내. 홈 전체를 실패시키지 않음 |
| 영양제 0건 | 체크리스트 카드 `StatusStateView(emptyNew)` + [등록하기] → 카메라 영양제 모드 |
| 약 0건 (a 이후) | 복약 카드 빈 상태 + [약 추가하기] 시트. 상호작용 카드는 ③상태 문구 |
| 403 `consent_required` | bootstrap의 `hasMinimumConsents` 게이트 + 동의 1회 부여 후 재시도(`grantMinimumConsents`) — 복약 GET/POST도 동일 패턴 적용 |
| 상호작용 위험 검출 | warning 톤 행(최대 3건) + "확인이 필요하면 의사·약사와 상담해주세요." 각주 — 저지/차단 아님(소프트 안내) |
| 소모/잔여 kcal 미연동 | (c) 잠금 캡션 — 색+아이콘+텍스트 병행, 추정치 노출 금지 |
| 신뢰도 표기 | 홈에는 % 노출 지점 없음 — 점수 `label_text` 칩만(서버 가공값 그대로, 프론트 재가공 금지) |
| 면책 푸터 | `_MedicalDisclaimer` 최하단 고정 — 카드 추가 시에도 항상 마지막 |

---

## ⑦ 테스트 계획

- **단위** (`mobile/test/unit/`)
  - `home_models_test.dart` 확장: `HomeMedication.fromJson` null-safe(필드 누락·타입 변형), `items` 키 파싱
  - `app_controller_test.dart` 확장: `_loadMedicationsBlock` 실패 시 `homeMedicationsFailed=true`이고 다른 블록 비오염, 403 → 동의 → 재시도 경로
  - (e) 체크 영속: `SharedPreferences.setMockInitialValues`로 날짜 키 롤오버(어제 체크가 오늘 미반영) 검증
- **위젯** (`mobile/test/widget/dashboard_screen_test.dart` 확장)
  - 복약 카드 3상태(목록/빈/실패) 렌더, 상호작용 카드 ③상태 분기 갱신(약 등록 시 문구 변경)
  - `_TodayAnalysisCard` 탭 → `/shell/score` 라우팅(go_router 테스트 하네스)
  - 히어로 잠금 캡션: `targetKcal=null`일 때 소모/잔여 미노출 + 잠금 문구 노출
- **금칙어 가드**: 신규 사용자 문구(복약 카드·잠금 캡션·시트)에 진단/처방/치료/효능 부재 assert 동반(기존 가드 테스트 패턴) — 해요체 확인
- **회귀 기준**: `flutter analyze` 0건 + `flutter test` 전체 통과(170개 + 신규). 백엔드는 `backend/.venv/bin/python -m pytest Nutrition-backend/tests -q -o addopts=""`(허용 실패 = 사용자 WIP 2건)

---

## ⑧ 플랫폼 노트

**Android (Pixel 10 Pro · Android 17, targetSdk 36)**
- dev API `http://10.0.2.2:8000/api/v1` — debug 전용 cleartext loopback 오버레이 적용 완료(`784687ce`). `release_security_config_test` 통과 유지(메인 설정에 예외 추가 금지)
- 노랑 헤더가 status bar까지 채움 — 엣지투엣지에서 아이콘 대비 확인(ink 아이콘은 노랑 위 가독 OK), 예측형 뒤로가기에서 기록 모드 pop 동작 점검
- Health Connect(소모 kcal 해제)는 Android 먼저 — 문서 08 P1-6

**iOS (iPhone 17 Pro · iOS 26.5, deployment target 15.0)**
- `UIUserInterfaceStyle=Light` 고정·한국어 권한 문구 적용 완료(`784687ce`)
- dev API `http://127.0.0.1:8000/api/v1` (ATS LocalNetworking 허용 확인됨)
- HealthKit은 SoT상 v2 이후 — iOS의 소모 kcal은 (c) 잠금 상태가 정식 사양(미지원 안내, SoT 상태 매트릭스 'AppleHealth 미지원')
- 날짜 스와이프 제스처와 시스템 엣지 백 스와이프 충돌 여부 실기기 확인(본문 내부 horizontal drag라 일반적으로 무충돌)

---

## ⑨ 완료 기준 (DoD)

- [ ] (a) 복약 카드: 라이브 백엔드에서 약 등록→홈 목록 표시→비활성화까지 E2E 동작, 상호작용 카드 ③상태 문구 갱신
- [ ] (b) 헤더 캘린더 아이콘·히어로 날짜 탭 → 월 펼침(문서 07 화면) → 날짜 탭 → 기록 모드 진입 동선 완성, placeholder `_NeutralBranch` 제거
- [ ] (c) 미연동 상태에서 소모/잔여 kcal 추정치가 어디에도 노출되지 않고 잠금 캡션 노출, 목표 kcal은 백엔드 값 주입 시에만 '소비/목표' 모드
- [ ] (d) 오늘의 분석 카드 탭 → 분석 탭 이동, 홈에서 daily-coaching 추가 호출 0회 확인
- [ ] (e) 앱 재시작 후 당일 체크 상태 유지·자정 롤오버 동작, `TODO(persist)` 주석 제거
- [ ] 모든 신규 문구: 해요체 + 금칙어 부재 테스트 동반, 면책 푸터 위치 불변, 신뢰도 % 미노출
- [ ] `flutter analyze` 0건 / `flutter test` 전체 통과 / 백엔드 스위트 기준 충족, 양 플랫폼 스모크(홈 로드→점수→복약→캘린더→분석 탭 딥링크)
- [ ] 복용 체크 서버 동기화는 "백엔드 공백 — P2 협의"로 기록만 남기고 미구현(범위 준수)
