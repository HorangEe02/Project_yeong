# 07. 기록·캘린더 구현 가이드 — 캘린더 / 오늘의 기록 / 직접 입력 검색 / 삭제

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

---

## ① 범위 / 목표

P1-3 "캘린더 + 오늘의 기록"(`outputs/todo-list/2026-06-11/2026-06-11-uiux-p1-execution-todo.md`)을 구현 가능한 수준으로 구체화합니다.

| 영역 | 내용 | 우선순위 |
|---|---|---|
| (a) 캘린더 화면 | 월 그리드 + 일자별 기록 점 + 일자 상세 카드 | P1 |
| (b) 오늘의 기록 화면 | 끼니·영양제 타임라인 병합 + 합계 카드 + 일자 이동 | P1 |
| (c) 직접 입력 검색 | 음식 카탈로그 검색 + 분류 필터 + 수동 confirm 합류 | P1 (일부 백엔드 공백) |
| (d) 삭제 | 삭제 확인 모달 + 실행취소 토스트 (영양제·분석결과) | P1 |

목표: `lib/app.dart`의 캘린더 placeholder 라우트(`/shell/home/calendar`)를 실화면으로 교체하고, 홈 주간 스트립(as-built)과 동일한 데이터 소스(`GET /meals` + `GET /supplements`)를 월 단위로 확장합니다. 연산은 모두 백엔드, 모바일은 표시·합산만 합니다(mobile/CLAUDE.md 원칙).

비범위: 복약(user_medications) 기록 — P1-1 라우트 임포트 이후 별도 가이드. 알림 센터(05-⑤) — P2.

---

## ② 디자인 스펙

### 참조 프레임 (figma `tabLE08wPC1EQ0XdfgCwII` · `_frames_index.md`)

| 프레임 ID | 이름 | 용도 |
|---|---|---|
| `763:24` | S · 캘린더 (05 보드 ⑥) | 캘린더 메인 화면 |
| `364:24` | 전체 달력 (펼침) | 월 그리드 펼침 레이아웃 |
| `356:25` / `357:24` / `358:24` | 달력 A / B / C | 주간 위젯 비교 — **A(소프트 셀) 채택** (플랜 §3.1) |
| `947:108` | 오늘의 기록 (일일) (12 보드 ⑤) | 일일 타임라인 화면 |
| `916:23` | 직접 입력 (검색) (10 보드 ③) | 음식 검색 화면 |
| `951:36` | 검색 0건 (14 보드 ②) | 검색 빈 상태 |
| `921:40` | 삭제 확인 (모달) (11 보드 ②) | 삭제 컨펌 다이얼로그 |
| `959:68` | 토스트 (저장됨) (16 보드 ③) | 실행취소 토스트 |

### 레이아웃 구조

**캘린더(763:24 + 364:24)**
```
AppBar(타이틀 "캘린더", 뒤로가기)
├─ 월 헤더: ◀ 2026년 6월 ▶ (AppText.subtitle)
├─ 요일 행: 일 월 화 수 목 금 토 (AppText.caption)
├─ 월 그리드 7×5~6: 일자 셀
│   ├─ 오늘: brand 원형 배경 (= AppColor.brand) + 흰 숫자
│   ├─ 선택일: brandSoft 원형 배경 (= AppColor.brandSoft)
│   └─ 기록 점: 셀 하단 — 식단 점(brand), 영양제 점(info) 최대 2개
├─ 일자 상세 카드(선택일): "6월 12일 기록 N건이에요"
│   └─ 기록 행 리스트 (끼니 아이콘 + 이름 + kcal / 영양제 아이콘 + 이름)
│       행 탭 → 기록 상세 (오늘의 기록 화면으로 해당 일자 진입)
└─ 하단 면책 푸터 (disclaimer_list)
```
- 요일 색 규칙: **일요일 = danger 계열(= AppColor.danger), 토요일 = info 계열(= AppColor.info), 평일 = ink2(= AppColor.ink2)**. 색만으로 구분하지 않도록 요일 텍스트를 함께 표기(SoT 색+텍스트 병행 원칙). 정확한 시안 색은 프레임 `763:24` 렌더로 최종 대조.
- 시니어 최소치: 일자 셀 터치 영역 48px+, 본문 15px+(AppText.body).

**오늘의 기록(947:108)**
```
AppBar(타이틀 "오늘의 기록")
├─ 일자 내비: ◀ 6월 12일 (목) ▶  — 미래 일자로는 ▶ 비활성
├─ 합계 카드: 총 kcal | 끼니 N회 | 영양제 N개 (AppCard, 3분할)
├─ 타임라인 (시간 오름차순 병합):
│   ├─ [08:10] 아침 — 현미밥 외 2 · 520kcal   (끼니 행)
│   ├─ [09:00] 오메가3 — 등록된 영양제        (영양제 행)
│   └─ ...
├─ '저녁 기록 추가' 점선 버튼 (border: AppColor.border 점선, 라벨 brand)
│   → 탭 시 카메라(/shell/camera) 이동
└─ 하단 면책 푸터
```
- 행 탭 → 기록 상세(끼니: food_items 펼침, 영양제: 영양제 상세). 행 우측 ⋯ → 삭제 진입(섹션 (d)).

**직접 입력 검색(916:23 + 951:36)**
```
AppBar(타이틀 "직접 입력")
├─ AppTextField(검색): placeholder "음식 이름을 검색해 보세요"
├─ 분류 필터 칩 가로 스크롤: 전체 | 한식 | 중식 | ... (GET /meals/cuisines)
├─ 결과 리스트: canonical_name_ko + cuisine/course 라벨 + 우측 ⊕ 버튼
│   ⊕ 탭 → 수동 food_item 행으로 담기 (하단 '담은 항목 N개' 바)
├─ 0건: StatusStateView(variant: searchEmpty, query: 검색어)
└─ 하단 '기록에 추가하기' AppPrimaryButton (52px+)
```

### 사용 컴포넌트 / 토큰

- 토큰: `lib/utils/design_tokens_v2.dart`의 `AppColor` / `AppText` / `AppSpace` / `AppRadius`만 참조. hex 직접 기재 금지(병기 형식: `#FFC700`(= AppColor.brand)).
- 기존 위젯 재사용: `AppCard`·`AppPrimaryButton`·`AppTextField`(design_tokens_v2 내), `LemonChip`(`widgets/common/lemon_chip.dart`), `Pressable`, `StatusStateView`(`shared/widgets/status_state_view.dart`), `showDeleteConfirmDialog`/`showUndoToast`(`widgets/common/app_modals.dart`), 면책 푸터(`shared/widgets/disclaimer_list.dart`).
- 사용자 문구는 전부 해요체. 의료법 금칙어(진단/처방/치료/효능) 사용 금지.

---

## ③ 현재 코드 상태

| 항목 | 상태 | 파일 |
|---|---|---|
| 캘린더 라우트 | **placeholder** — `_NeutralBranch` 안내문만 표시 | `mobile/lib/app.dart` (`/shell/home` 하위 `calendar`, 약 126행) |
| 홈 주간 스트립 | **as-built 완료** — AppController가 최근 7일(`오늘-6일`) `GET /meals`를 로드해 날짜별 기록 점을 클라이언트 필터로 표시 | `mobile/lib/app_controller.dart`(`_loadHomeData`), `mobile/lib/screens/dashboard_screen.dart` |
| 과거 기록 조회 모드 | **부분 구현** — `DashboardScreen(recordDate:)`가 비-null이면 풀스크린 '과거 기록 조회' 페이지로 동작 | `mobile/lib/screens/dashboard_screen.dart` |
| meals/supplements 응답 모델 | **구현 완료(재사용)** — `HomeMealsResult`/`HomeMeal`/`HomeFoodItem`/`HomeMealNutrition`, `HomeSupplementsResult`/`HomeSupplement`/`HomeSupplementSchedule` 파서 존재 | `mobile/lib/features/dashboard/home_models.dart` |
| 오늘의 기록 화면 | **없음** | (신규) |
| 직접 입력 검색 화면 | **없음** | (신규) |
| 삭제 모달·실행취소 토스트 | **위젯 완료(P0 배치 D)** — `showDeleteConfirmDialog`(Future\<bool\>), `showUndoToast`(message+onUndo, 4초 SnackBar) | `mobile/lib/widgets/common/app_modals.dart` |
| 상태 템플릿 | **완료** — `StatusStateVariant.{emptyNew, syncFailed, permissionDenied, analysisFailed, notificationsEmpty, searchEmpty}` | `mobile/lib/shared/widgets/status_state_view.dart` |
| ApiClient | `getJson`/`postJson`/`postMultipart`/`postMultipartFiles`만 존재 — **DELETE 메서드 없음(추가 필요)** | `mobile/lib/core/api/api_client.dart` |
| 동의 재시도 패턴 | **as-built 참조** — 403 `consent_required` → 동의 1회 부여 후 재시도 | `mobile/lib/features/chat/chat_repository.dart` |

### 백엔드 실재 확인 (`backend/Nutrition-backend/src/api/v1/`)

- `meals.py`: `POST /meals/analyze-image`, `GET /meals/cuisines`, `GET /meals/foods`, `GET /meals`(from_eaten_at/to_eaten_at 지원), `POST /meals/{meal_id}/explain`, `POST /meals/{meal_id}/confirm` — **전부 실재**.
- `supplements.py`: `GET /supplements`(limit/offset/category/q), `GET /supplements/{id}`, `DELETE /supplements/{id}`(**soft-delete** — `soft_delete_user_supplement`, `src/services/supplement_registration.py`) — 실재.
- `analysis_results.py`: `GET /analysis-results`, `DELETE /analysis-results/{result_id}`(204) — 실재.
- **백엔드 공백 1 — 이미지 없는 수동 끼니 생성**: `POST /meals/{meal_id}/confirm`은 `analyze-image`가 만든 preview의 `meal_id`만 받습니다(없으면 404 `meal_preview_not_found`). 이미지 업로드 없이 meal 레코드를 새로 만드는 라우트(`POST /meals` 류)는 **존재하지 않습니다**. 팀원 브랜치(`external/Lemon-sin-ai-agent-branch`)의 `food_records.py` 임포트 또는 신규 라우트 협의 필요(플랜 §4 공백 #2).
- **백엔드 공백 2 — 끼니 기록 삭제**: `DELETE /meals/{id}` 라우트 없음. 타임라인의 끼니 행 삭제는 라우트 추가 전까지 비노출.
- **백엔드 공백 3 — 삭제 복구**: soft-delete이지만 restore 라우트가 없어 실행취소는 클라이언트 지연 실행으로 구현(섹션 (d)).

---

## ④ 구현 단계 (파일 단위 체크리스트)

> 공통 전제: `GET /supplements`에는 날짜 범위 파라미터가 없으므로 영양제 점·타임라인은 `created_at`/`user_confirmed_at`(등록일) 기준 클라이언트 집계입니다(플랜 §3.7 "등록일 기준"과 동일).

1. [ ] **`mobile/lib/core/api/api_client.dart`** — `Future<void> delete(String path, {Set<int> expectedStatusCodes = const {204}})` 추가. 기존 `_baseUrl`(이미 `/api/v1`로 끝남)·타임아웃·에러 매핑(`ApiError`) 재사용.
2. [ ] **`mobile/lib/features/records/records_models.dart`** (신규) — `MonthRecords`(yyyy-MM 키, 일자→`DayRecords{meals, supplements}` 맵), `DayRecords.totalKcal`(각 meal `nutrition_summary` kcal 합산), 타임라인 병합 정렬 항목 `RecordTimelineEntry{time, kind(meal|supplement), …}`. 끼니 시각 = `eaten_at`(로컬 변환), 영양제 시각 = `intake_schedule` 시각이 있으면 그 시각, 없으면 `user_confirmed_at`. 파싱은 `home_models.dart`의 `HomeMeal`/`HomeSupplement` 재사용.
3. [ ] **`mobile/lib/features/records/records_repository.dart`** (신규) —
   - `fetchMonth(DateTime month)`: `GET /meals?from_eaten_at={월초 00:00 로컬→UTC ISO8601}&to_eaten_at={월말 23:59:59}&limit=100` + `results.length == limit`이면 `offset` 증분 반복(끼니 3회×31일=93건이라 보통 1페이지지만 가드 필수). `GET /supplements?limit=100`도 동일 페이지네이션 후 등록일로 분배.
   - **월 단위 1회 로드 캐시**: `Map<String, MonthRecords>` — 같은 달 재진입 시 네트워크 생략. 끼니 confirm·영양제 저장·삭제 성공 시 해당 월 키 무효화(또는 `invalidateAll()`).
   - `searchFoods({String? q, String? cuisineCode, int offset})` → `GET /meals/foods`, `fetchCuisines()` → `GET /meals/cuisines`.
   - `deleteSupplement(id)` / `deleteAnalysisResult(id)` — 1단계의 `delete` 사용.
4. [ ] **`mobile/lib/features/records/deferred_delete_queue.dart`** (신규) — 실행취소용 지연 실행 큐: `schedule(id, Future<void> Function() commit)` → 4초 타이머, `undo(id)` → 타이머 취소. 화면 dispose 시 `flush()`로 보류분 즉시 커밋(삭제 유실 방지).
5. [ ] **`mobile/lib/screens/calendar_screen.dart`** (신규) — ② 캘린더 레이아웃. 월 전환 ◀▶ 시 `fetchMonth` 호출(캐시 히트 시 즉시), 로딩 동안 그리드 스켈레톤. 일자 셀 탭 → 하단 일자 상세 카드 갱신, 상세 행 탭 → `context.push('/shell/home/records?date=2026-06-12')`.
6. [ ] **`mobile/lib/screens/daily_records_screen.dart`** (신규) — ② 오늘의 기록 레이아웃. `date` 쿼리 파라미터(기본 오늘). ◀▶로 일자 이동(월 경계 넘어가면 인접 월 `fetchMonth`). '저녁 기록 추가' 점선 버튼 → `context.go('/shell/camera')` (촬영→분석→confirm 후 돌아오면 월 캐시 무효화로 자동 반영). 합계 카드 문구 예: "오늘 1,840kcal를 기록했어요".
7. [ ] **`mobile/lib/screens/food_search_screen.dart`** (신규) — ② 검색 레이아웃. 검색어 debounce 300ms → `searchFoods`. 칩 = `fetchCuisines().display_name_ko`. ⊕ 탭 → 담은 항목(이름·`food_catalog_item_id`·`source: 'database_match'`) 누적. **진입 경로는 카메라 분석 폴백 한정**(후보 0건·저신뢰·`pipeline_metadata.requires_manual_entry=true`): preview가 발급한 `meal_id`로 `POST /meals/{meal_id}/confirm` payload에 담은 항목을 `food_items[]`로 합류. 독립 진입(이미지 없는 기록)은 백엔드 공백 1 해소 후 활성화 — 그 전까지 캘린더/오늘의 기록에서 이 화면으로 가는 CTA는 만들지 않습니다.
8. [ ] **`mobile/lib/app.dart`** — `calendar` placeholder를 `CalendarScreen`으로 교체 + `/shell/home` 하위 `records` 라우트 추가(`date` 쿼리). `_NeutralBranch` 캘린더 분기 제거.
9. [ ] **삭제 배선** — 오늘의 기록 영양제 행 ⋯ / 영양제 관리(홈) 행: `showDeleteConfirmDialog` true → 리스트에서 낙관적 제거 + `showUndoToast(message: '영양제를 삭제했어요', onUndo: …)` + `deferred_delete_queue.schedule`. 실행취소 시 행 복원. (상세는 섹션 (d))
10. [ ] **테스트 추가** — ⑦ 참조. `flutter analyze` 0건 + `flutter test` 전체 통과(170개+) 확인.

---

## ⑤ 엔드포인트 계약 표

> ApiClient 경로 표기: `/api/v1` 접두사 제거(클라이언트 baseUrl에 포함). 날짜는 ISO8601(UTC 변환 후 전송).

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| GET `/meals` | query: `from_eaten_at`, `to_eaten_at`, `cuisine_code?`, `course_code?`, `food_catalog_item_id?`, `limit`(≤100, 기본 20), `offset` | `results[]{id, status, meal_type, eaten_at, food_items[], nutrition_summary{}, confirmed_at, created_at}`, `limit`, `offset` | scope MEAL_READ (동의 불요) |
| GET `/supplements` | query: `limit`(≤100, 기본 20), `offset`, `category_key?`, `category_id?`, `q?` — **날짜 필터 없음** | `results[]{id, display_name, manufacturer, ingredients[], serving, intake_schedule?, user_confirmed_at, created_at}` | scope SUPPLEMENT_READ (동의 불요) |
| GET `/meals/cuisines` | (없음) | `results[]{id, cuisine_code, display_name_ko, display_name_en, sort_order, courses[]}` | scope MEAL_READ |
| GET `/meals/foods` | query: `q?`(≤120자), `cuisine_code?`, `course_code?`, `limit`(≤100, 기본 50), `offset` | `results[]{id, cuisine_code, course_code, canonical_name_ko, canonical_name_en?, source}`, `limit`, `offset` | scope MEAL_READ |
| POST `/meals/{meal_id}/confirm` | `analysis_id?`, `food_items[1..40]{display_name, portion_amount?, portion_unit?, kcal?, carb_g?, protein_g?, fat_g?, sodium_mg?, food_catalog_item_id?, confidence?, source: manual\|vision\|database_match}`, `meal_type?`, `eaten_at?`, `user_confirmed: true` | `MealRecordResponse` (위 GET /meals 항목과 동일) · 404 `meal_preview_not_found` / 409 `meal_preview_not_confirmable` / 422 `meal_confirmation_invalid` | scope MEAL_WRITE — **meal_id는 analyze-image preview 발급분만 유효** |
| POST `/meals/analyze-image` | multipart 이미지 + `meal_type?`, `eaten_at?` | 202 `MealImageAnalysisPreview{analysis_id, meal_id, food_candidates[], pipeline_metadata{requires_manual_entry}, warning_codes[]}` | consent food_image_processing — 수동 confirm 진입의 유일한 meal_id 공급원(as-built, 카메라 플로우) |
| DELETE `/supplements/{supplement_id}` | path id | 204 (soft-delete) · 404 `supplement_not_found` | scope SUPPLEMENT_DELETE |
| DELETE `/analysis-results/{result_id}` | path id | 204 · 404 | scope ANALYSIS_DELETE 계열(`require_analysis_delete`) |
| *(공백)* POST `/meals` 수동 생성 | — | — | **백엔드 공백** — 이미지 없는 수동 기록 생성 불가. 팀원 `food_records.py` 임포트/신규 라우트 협의 필요 |
| *(공백)* DELETE `/meals/{id}` | — | — | **백엔드 공백** — 끼니 삭제 UI 비노출 |
| *(공백)* POST 복구(undo) | — | — | **백엔드 공백** — restore 라우트 없음 → 클라이언트 지연 실행으로 대체 |

403 `consent_required` 발생 시(이 표의 기록 조회 라우트는 동의 불요지만, 향후 동의가 추가될 가능성 대비) `chat_repository.dart`의 패턴을 따릅니다: 해당 동의 `POST /me/privacy/consents/{type}`(201 기대) 1회 → 원요청 1회 재시도.

---

## ⑥ 상태 / 에러 처리

| 상황 | 처리 (StatusStateView·모달 템플릿 활용) |
|---|---|
| 월 로딩 중 | 그리드 스켈레톤(점 비표시) + 일자 상세 카드 자리 placeholder. 합계 카드는 "불러오는 중이에요" |
| 해당 월 기록 0건 | 그리드는 정상 표시, 일자 상세 카드 영역에 `StatusStateVariant.emptyNew`(축약형) — CTA "기록 시작하기" → 카메라 |
| 오늘의 기록 0건 | `StatusStateVariant.emptyNew` + '저녁 기록 추가' 점선 버튼 유지 |
| 네트워크/서버 실패 | `StatusStateVariant.syncFailed` — CTA "다시 시도하기" → 해당 월 캐시 무효화 후 재호출 |
| 검색 0건 | `StatusStateVariant.searchEmpty`(query 전달, 프레임 `951:36`) — CTA "다른 검색어로 찾아보기" |
| 검색 결과 저신뢰/추정치 | 카탈로그 검색은 신뢰도 개념 없음. 카메라 폴백 합류 시 confirm 전 화면의 저신뢰 배너(`shared/widgets/low_confidence_banner.dart`)·등급 칩 규칙(% 직접 노출 금지) 그대로 따름 |
| 삭제 404 | 이미 삭제된 항목 — 토스트 "이미 삭제된 항목이에요" + 목록 새로고침 |
| 삭제 실패(5xx) | 낙관적 제거 롤백 + `StatusStateVariant.syncFailed` 토스트 변형("잠시 후 다시 시도해 주세요") |
| 미래 일자 이동 | ▶ 비활성 (오늘까지만) |

면책 푸터: 캘린더·오늘의 기록 화면 하단에 고정 면책 푸터("건강 참고용이며 의학적 판단을 대신하지 않아요" — `disclaimer_list.dart` 표준 문구 사용)를 포함합니다. 합계 카드는 기록 합산 표시일 뿐 해석 문구를 덧붙이지 않습니다.

---

## ⑦ 테스트 계획

**단위 (`mobile/test/unit/`)**
- [ ] `records_models_test.dart` — 월 경계 집계(말일 23:59 포함), kcal 합산(`nutrition_summary` 누락 키 0 처리), 타임라인 병합 정렬(동시각 끼니 우선), 영양제 등록일 분배.
- [ ] `records_repository_test.dart` — `from_eaten_at`/`to_eaten_at` UTC 변환 쿼리 생성, `results.length == limit` 시 offset 페이지네이션 반복, 월 캐시 히트/무효화, DELETE 204/404 분기.
- [ ] `deferred_delete_queue_test.dart` — 4초 후 commit 호출, undo 시 미호출, dispose flush.

**위젯 (`mobile/test/widget/`)**
- [ ] 캘린더: 기록 점 렌더(식단/영양제 색 구분), 일/토 요일 색, 오늘 셀 brand 강조, 일자 탭 → 상세 카드 갱신, 행 탭 → records 라우트 push.
- [ ] 오늘의 기록: 합계 카드 수치, ◀▶ 이동, 미래 ▶ 비활성, 점선 버튼 → 카메라 라우트.
- [ ] 검색: debounce 후 결과 렌더, 칩 필터 쿼리 반영, 0건 → `searchEmpty` + query 노출.
- [ ] 삭제: `showDeleteConfirmDialog` 취소 시 무변화 / 확인 시 행 제거 + `showUndoToast` 노출 + 실행취소 시 행 복원.

**금칙어 가드 (회귀 가드 공통)**
- [ ] 신규 사용자 문구 전체에 진단/처방/치료/효능 **부재 assert** (기존 P0 테스트 패턴 동일).
- [ ] 신뢰도 % 직접 노출 없음 assert (검색·기록 화면 — SoT §7).
- [ ] 면책 푸터 존재 assert (캘린더·오늘의 기록).

완료 기준: `flutter analyze` 0건, `flutter test` 전체 통과(현재 170개 + 신규).

---

## ⑧ 플랫폼 노트

**Android — Pixel 10 Pro · Android 17 (targetSdk 36)**
- 예측형 뒤로가기: 캘린더 → 일자 상세 카드(인페이지 상태)는 pop 대상이 아님 — `PopScope`로 화면 단위만 처리.
- 엣지투엣지: 월 그리드 하단·면책 푸터에 `SafeArea`/시스템 인셋 패딩.
- dev API: `http://10.0.2.2:8000/api/v1` — debug 전용 cleartext 오버레이 적용 완료(P0 `784687ce`), release 차단 유지(`release_security_config_test` 통과 필수).

**iOS — iPhone 17 Pro · iOS 26.5 (deployment target 15.0)**
- `UIUserInterfaceStyle=Light` 고정 적용 완료 — 다크 모드 분기 불필요.
- 일자 이동 ◀▶와 스와이프 백 제스처 충돌 없도록 타임라인은 수직 스크롤만 사용.
- 시뮬레이터 dev API: `http://127.0.0.1:8000/api/v1` (ATS LocalNetworking 허용 확인됨).

**공통**
- 날짜 처리: `eaten_at`은 서버 UTC — 화면 표기·일자 버킷팅은 로컬 타임존 변환 후 수행. 월 범위 쿼리는 로컬 월초/월말을 UTC로 변환해 전송(경계일 누락 방지).
- 한국어 로케일: 요일·월 표기는 `intl` `ko_KR` 포맷 사용.

---

## ⑨ 완료 기준 (DoD)

- [ ] `/shell/home/calendar` placeholder 제거 — 월 그리드 + 기록 점 + 일자 상세 카드 실데이터 동작 (월 단위 1회 로드 + 캐시).
- [ ] `/shell/home/records?date=` 오늘의 기록 — 타임라인 병합·합계 카드·일자 이동·카메라 딥링크 동작.
- [ ] 직접 입력 검색 — 카메라 폴백 경로에서 카탈로그 검색→⊕→confirm 합류 동작. 독립 수동 기록은 "백엔드 공백 1"로 문서화·CTA 비노출.
- [ ] 영양제 삭제 — 확인 모달 → 낙관적 제거 → 실행취소 토스트(4초 지연 실행) → 미취소 시 DELETE 204 확인.
- [ ] 기록 변경(confirm/저장/삭제) 시 월 캐시 무효화로 캘린더·홈 주간 스트립 정합 유지.
- [ ] `flutter analyze` 0건 / `flutter test` 전체 통과 / 금칙어·% 노출·면책 푸터 가드 테스트 포함.
- [ ] 일/토 색 규칙·시니어 최소치(본문 15px+, 터치 48px+, 버튼 52px+)·해요체 문구 — 시안 `763:24`·`947:108` 대조 확인.
- [ ] 백엔드 공백 3건(수동 끼니 생성 / 끼니 삭제 / 삭제 복구)이 백엔드 트래커에 이슈로 등록됨.
