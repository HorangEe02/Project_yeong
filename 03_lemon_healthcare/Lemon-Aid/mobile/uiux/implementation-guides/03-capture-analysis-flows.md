# Lemon-Aid UI/UX 구현 가이드 — 03 카메라·검출·분석 플로우

> 기준일 2026-06-12 · 디자인 소스: `mobile/uiux/figma` (DS v2.0 · SoT v1.1) · 브랜치 `feat/ai-agent-chat-import`
> 공통 규약·권위 체계·플랫폼 매트릭스는 [00-overview-and-conventions](00-overview-and-conventions.md) 참조. 결과 화면(5카드·영양제 최종)은 [04-analysis-results](04-analysis-results.md) 담당 — 이 문서는 **촬영 → 검출 → 후보 확인 직전**까지.

---

## ① 범위 / 목표

| 구분 | 내용 |
|---|---|
| 담당 화면 | S-08 카메라(촬영/권한/미리보기/오류/가이드 모달), 음식 분석 중·후보 선택(06 보드), 영양제 분석 중(07 보드 ①), 검출 오버레이·다중 촬영(12 보드), 섭취량 바텀시트(16-④) |
| 핵심 사실 | 이 플로우는 **백엔드 실연동이 이미 완성**된 영역(멀티샷 6장 · OCR 4-프로바이더 레이스 · analysis-sessions). 이번 작업의 본질은 **시안 UI 보강**이지 배선 신설이 아님 |
| 목표 | (a) 모드 세그먼트 정합 확인 (b) 촬영 가이드 모달+다시 보지 않기 (c) 미리보기 품질 체크 2종 (d) 다중 촬영 2슬롯 UI (e) 음식 후보 선택 화면(등급 칩·섭취량·폴백) (f) 검출 오버레이 (g) 분석 중 3단계 체크리스트 |
| 우선순위 | (e)(g) = P1-7 체크리스트 항목, (b)(c)(d)(f) = P1~P2 보강, (a) = as-built 검증만 |

## ② 디자인 스펙

### 2.1 figma 프레임 (`figma/_frames_index.md`, 보드 `03_UI_Design` page `0:1`)

| 프레임 ID | 이름 | 적용 대상 |
|---|---|---|
| `782:23` | S-08 Camera · 촬영 | 카메라 본 화면 (세그먼트·가이드 프레임·셔터) |
| `912:23` | S-08 카메라 권한 요청 | 권한 거부 상태 |
| `912:46` | S-08 촬영 미리보기 | 품질 체크 2종 UI |
| `912:69` | S-08 카메라 오류 | 초기화 실패 상태 |
| `920:23` | S-08 촬영 가이드 (모달) | 가이드 모달 + 다시 보지 않기 |
| `851:24` | F-01 음식 분석 중 | 3단계 체크리스트 (검출→분류→후보) |
| `852:23` | F-02 음식 인식 결과(후보) | 후보 선택 리스트 + 예상 영양소 |
| `853:24` | S-01 영양제 분석 중 | 3단계 체크리스트 (검출→OCR→LLM) |
| `946:24` | 음식 영역 검출 | 바운딩박스 오버레이 — **백엔드 공백, §⑤ 참조** |
| `946:50` | 영양제 라벨 검출(OCR) | `detected_product_regions[]` 오버레이 |
| `947:23` | 다중 촬영 (앞면+성분표) | 2슬롯 UI |
| `959:80` | 섭취량 조절 바텀시트 | 후보 선택의 섭취량 칩/스테퍼 (16-④) |
| `916:23` | 직접 입력 (검색) | 후보 0건/저신뢰 폴백 |
| `951:36` / `951:76` | 검색 0건 / 분석 신뢰도 낮음 | 상태 변형 |

### 2.2 레이아웃 구조 (시안 판독 요약)

- **카메라(782:23)**: 검정 풀스크린 + 가이드 프레임(코너 마커) + 하단 컨트롤(갤러리·셔터·렌즈전환) + **영양제/식단 슬라이딩 세그먼트**(노랑 알약). 떠 있는 컨트롤은 반투명 검정 surface — 코드의 `_CamTone` 톤 체계가 이미 이 규칙을 구현.
- **음식 후보(852:23)**: 사진 썸네일 → 후보 카드 리스트(이름 + **일치 등급 칩** — D2 결정: % 비노출) → 선택 시 섭취량 칩(0.5/1/1.5인분)·스테퍼 → 예상 영양소(kcal·탄단지) → [이 음식이 맞아요] CTA. 후보 0건이면 직접 입력 검색으로 전환.
- **분석 중(851:24/853:24)**: 마스코트 + 3단계 체크리스트(음식: 검출→분류→후보 정리 / 영양제: 검출→OCR→AI 해석) + **[메인으로 이동]** 보조 버튼(백그라운드 계속).
- **다중 촬영(947:23)**: 상단 2슬롯 썸네일(앞면 / 성분표) + 슬롯별 재촬영, 둘 다 차면 [분석하기] 활성.

### 2.3 사용할 토큰·컴포넌트 (`lib/utils/design_tokens_v2.dart`)

- 색: `AppColor.brand`(세그먼트 알약·CTA), `AppColor.ink/inkSecondary`, `AppColor.success/warning/review` + 각 `Soft`(등급 칩), `AppColor.danger`(오류). 카메라 화면 한정 `_CamTone`(반투명 검정 surface — 검정 배경 위 전용, 신규 컨트롤도 이 톤 재사용)
- 타이포: `AppText.title`(분석 중 헤드라인), `AppText.body`(15px, 시니어 최소), `AppText.caption`(체크리스트 보조)
- 간격/모서리: `AppSpace.page/lg/md/sm`, `AppRadius.full`(세그먼트·셔터), `AppRadius.md`(카드), 버튼 높이 52px+·터치 48px+
- 공용 위젯: `ConfidenceGradeChip`(높음≥0.85/보통≥0.6/직접 확인 — % 비노출), `LowConfidenceBanner`, `StatusStateView`(permissionDenied/analysisFailed/searchEmpty), `showAppBottomSheet`·`showAppDialog`(`widgets/common/app_modals.dart`)

## ③ 현재 코드 상태

| 항목 | 상태 | 실제 파일 |
|---|---|---|
| 카메라 화면 (실연동) | ✅ 완료 (as-built) | `mobile/lib/screens/camera_screen.dart` (2,631줄) — 라이브 프리뷰·셔터·갤러리·렌즈 전환·에뮬 폴백(Mac 카메라 브리지/picker)·Android lost-data 복구 |
| (a) 영양제/식단 세그먼트 토글 | ✅ **이미 구현** | `camera_screen.dart` `_ModeSegment`(L2283) — 노랑 슬라이딩 알약, `/shell/camera?mode=&role=` 쿼리로 초기 모드 주입(`mobile/lib/app.dart` L172). FAB 퀵 액션 팔레트(`widgets/common/quick_action_palette.dart`)는 진입 경로로 공존 |
| 멀티샷 + role | ✅ 완료 | `_CapturedSupplementImage`(role) + `_SupplementBatchStrip`, 최대 6장(`_maxSupplementGalleryImages`), role 5종 `unknown/front_label/supplement_facts/intake_method/precautions`(L1366), analysis-sessions 연동 `features/supplements/supplement_repository.dart` L322~374 |
| OCR 4-프로바이더 레이스 | ✅ 완료 | `mobile/lib/app_controller.dart` `_analyzeSupplementImageAutomatically`(L1011~) — `ocrProvider: 'configured'` 위임 |
| 분석 중 화면 + 메인으로 이동 | 🔶 부분 | `screens/analysis_result_screen.dart` `_AnalysisInProgressScreen`(L2549) — 마스코트+단일 문구+[메인으로 이동] 구현. **3단계 체크리스트 없음**. 백그라운드 상태는 `app_controller.dart` `AnalysisJobSnapshot`(L29, running→completed/failed + 미읽음 알림) as-built |
| (b) 촬영 가이드 모달 | ❌ 없음 | 신규. `shared_preferences` 미도입(pubspec 부재) — P1-5에서 도입 예정 |
| (c) 미리보기 품질 체크 | 🔶 부분 | 미리보기 자체는 `_buildPreview`(L1243) 구현. 품질 체크 UI 없음. 백엔드 사후 리포트 모델은 존재: `SupplementImageQualityReport`(status/issues/retake_reasons, `supplement_models.dart` L990) |
| (d) 다중 촬영 2슬롯 | 🔶 부분 | 6장 자유 배치 스트립은 있으나 시안 947:23의 "앞면+성분표" 2슬롯 고정 UI 없음. API는 재사용으로 충분 |
| (e) 음식 후보 선택 | 🔶 부분 | 모델·배선 완료: `MealImageAnalysisPreview.foodCandidates[]`(`supplement_models.dart` L197, display_name/confidence/portion/영양추정). 결과 화면은 **첫 후보만 시드**해 수정 필드에 채움(`analysis_result_screen.dart` `_seedMealCorrectionFields` L1494) — 후보 리스트 선택 UI·섭취량 바텀시트·검색 폴백 없음. **repository에 `GET /meals/foods` 검색 메서드도 없음** |
| (f) 검출 오버레이 | ❌ 없음 | 영양제: `SupplementDetectedProductRegion`(x/y/w/h/confidence/selected, `supplement_models.dart` L1115) 모델만 존재, 렌더 없음. 음식: 백엔드 미노출(§⑤) |
| 권한/오류 상태 | 🔶 부분 | `features/supplements/camera_readiness.dart`(permissionDenied/unavailable/error 분류) + `_ErrorBox`(L2016). `StatusStateView` 변형으로 시안 정합 교체 잔여 |

## ④ 구현 단계 (파일 단위 체크리스트)

권장 순서: 1→2(P1-7 핵심) → 3→4 → 5→6 → 7.

1. **음식 후보 선택 화면 (e) — P1-7**
   - [ ] `lib/features/supplements/supplement_repository.dart` — `searchFoodCatalog({String? q, int limit})` 추가: `GET '/meals/foods'` + `FoodCatalogItem` 모델(`supplement_models.dart`에 fromJson, 단위 테스트 동반)
   - [ ] `lib/widgets/common/food_candidate_list.dart` (신규) — 후보 카드: `displayName` + `ConfidenceGradeChip(confidence)`(% 비노출) + 예상 영양 요약(kcal·탄단지, null 필드는 숨김). 단일 선택 라디오 동작
   - [ ] `lib/widgets/common/portion_sheet.dart` (신규, figma 959:80) — `showAppBottomSheet` 기반 섭취량 칩(0.5/1/1.5/2인분) + 스테퍼(0.25 단위). 결과는 `portionAmount/portionUnit`
   - [ ] `lib/screens/analysis_result_screen.dart` — `_mealCards`(L307)의 정보 카드 나열을 후보 선택 리스트로 교체. 선택 후보 → `MealFoodItemInput.fromCandidate` + 섭취량 반영 → 기존 `confirmMealImagePreview` payload(`food_items[].portion_amount/portion_unit`) 그대로
   - [ ] 폴백: `foodCandidates.isEmpty || pipelineMetadata.requiresManualEntry || 최고 confidence < 0.6` → `LowConfidenceBanner` + 직접 입력 검색 패널(916:23, `searchFoodCatalog`, 0건 시 `StatusStateView(variant: searchEmpty, query:)` + 수동 입력 필드 유지)
2. **분석 중 3단계 체크리스트 (g)**
   - [ ] `lib/screens/analysis_result_screen.dart` `_AnalysisInProgressScreen` — 단일 문구를 3단계 체크리스트로 교체. 음식: 검출→분류→후보 정리 / 영양제: 검출→OCR 추출→AI 해석. ⚠️ **백엔드는 동기 202 단일 응답이고 진행률 스트림/폴링 라우트가 없음** → 단계 전환은 시간 기반 연출로 명시(주석 필수), 완료 후 `pipeline_metadata`(`detector_used/classifier_used`, `ocr_status/vision_status/llm_status`)로 실제 수행 여부를 결과 화면에서 검증 표기
   - [ ] [메인으로 이동] 버튼·`AnalysisJobSnapshot` 백그라운드 패턴은 **as-built 유지** — 변경 금지(완료 시 미읽음 알림 → `resultRoute` 복귀 동작 기존 그대로)
3. **촬영 가이드 모달 (b) — figma 920:23**
   - [ ] `lib/widgets/common/capture_guide_modal.dart` (신규) — `showAppDialog` 기반: 일러스트 + 수칙 3줄(프레임 안에 / 흔들림 없이 / 글자가 보이게) + [다시 보지 않기] 체크 + [촬영 시작]
   - [ ] `lib/app_controller.dart` — `captureGuideDismissed` 플래그(세션 메모리, `TODO(persist)` 주석 — P1-5 `shared_preferences` 도입 시 일괄 영속). `camera_screen.dart` `initState` 후 첫 진입 시 모드별 1회 표출
4. **미리보기 품질 체크 2종 (c) — figma 912:46**
   - [ ] `lib/features/supplements/image_quality_probe.dart` (신규) — 업로드 전 클라이언트 체크 2종: ① 선명도(라플라시안 분산 블러 추정) ② 밝기(평균 휘도 저조도). 결과 2행 체크 UI(통과 ✓ success / 미달 ⚠ review + "다시 찍기" 권고 — 색+아이콘+텍스트 병행). **차단 아님, 소프트 안내만**(분석하기 버튼 유지)
   - [ ] `camera_screen.dart` `_buildPreview` — 체크 행 2개 삽입. 업로드 후에는 응답의 `image_quality_report.retake_reasons[]` → 결과 화면에서 재촬영 유도(기존 retake 딥링크 `/shell/camera?mode=supplement&role=` 재사용)
5. **다중 촬영 2슬롯 (d) — figma 947:23**
   - [ ] `camera_screen.dart` — 영양제 모드에 "간단(2슬롯)" 레이어 추가: 슬롯1=`front_label`, 슬롯2=`supplement_facts` 고정, 슬롯 탭→해당 role로 촬영, 2장 충족 시 [분석하기]. 기존 6장 자유 배치 스트립은 "추가 촬영"으로 유지(슈퍼셋 보존). API는 기존 `createSupplementAnalysisSession`→`uploadSupplementAnalysisSessionImage(image_role)`→`finalize` 그대로 — **신규 배선 없음**
6. **검출 오버레이 (f) — figma 946:50**
   - [ ] `lib/widgets/common/detection_overlay.dart` (신규) — `CustomPainter`로 `detectedProductRegions[]` 박스 렌더(선택 영역 `selected=true`는 brand 테두리, 라벨은 등급 칩으로 — % 비노출). 좌표는 입력 이미지 픽셀 기준 → 위젯 스케일 변환
   - [ ] 음식 영역 박스(946:24)는 **백엔드 공백** — `MealImageAnalysisPreview`에 영역 좌표 필드 없음(플랜 R4). 구현 보류, 백엔드 노출 시 같은 오버레이 재사용
7. **권한/오류 상태 정합**
   - [ ] `camera_screen.dart` — `CameraReadinessKind.permissionDenied` → `StatusStateView(variant: permissionDenied)`(설정 열기 CTA), 초기화 실패 → `StatusStateView(variant: analysisFailed)` 톤으로 `_ErrorBox` 교체(912:23/912:69)

## ⑤ 엔드포인트 계약 표

ApiClient 경로는 `/api/v1` 접두사 제거 형태(baseUrl 포함됨). 403 `consent_required` 응답 시 해당 동의 1회 POST 후 재시도(패턴: `lib/features/chat/chat_repository.dart`).

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| POST `/meals/analyze-image` | multipart: `image`, `client_request_id`, `meal_type`, `eaten_at?` | 202 `MealImageAnalysisPreview`: `analysis_id`, `meal_id`, `food_candidates[]{display_name, confidence, portion_amount?, kcal?, carb_g?, protein_g?, fat_g?, sodium_mg?}`, `warning_codes[]`, `pipeline_metadata{detector_used, classifier_used, requires_manual_entry}` | meal:write + `food_image_processing` |
| POST `/meals/{meal_id}/confirm` | `analysis_id`, `food_items[]{display_name, portion_amount, portion_unit, …}`, `meal_type?`, `eaten_at?`, `user_confirmed: true` | 200 `MealRecordResponse`(food_items·nutrition_summary) | meal:write (동의 없음) |
| GET `/meals/foods` | query: `q?`, `cuisine_code?`, `course_code?`, `limit≤100`, `offset` | `FoodCatalogItemListResponse.items[]` | meal:read (동의 없음) |
| POST `/meals/{meal_id}/explain` | path: 확정 meal id | `MealExplainResponse`(분석 문단·출처) | meal:read (동의 없음) |
| POST `/supplements/analyze` | multipart: `image`, `client_request_id`, `ocr_provider` | 202 `SupplementAnalysisPreview`: `ingredient_candidates[]`, `image_quality_report{status, retake_reasons[]}`, `detected_product_regions[]{region_id, x, y, width, height, confidence, selected}`, `low_confidence_fields[]`, `pipeline_metadata{ocr_status, vision_status, llm_status}` | supplement:write + `ocr_image_processing` (외부 OCR 시 `external_ocr_processing` 조건부) |
| POST `/supplements/analysis-sessions` | (빈 바디) | `analysis_group_id`, `expires_at` | supplement:write + `ocr_image_processing` |
| POST `/supplements/analysis-sessions/{analysis_group_id}/images` | multipart: `image`, `client_request_id`, `ocr_provider`, `image_role`(front_label/supplement_facts/intake_method/precautions/unknown) | 202 `SupplementMultiImageAnalysisPreview`: `previews[]`, `merged_preview?`, `missing_required_sections[]`, `action_required` | 동상 |
| POST `/supplements/analysis-sessions/{analysis_group_id}/finalize` | path만 | 동상 (merged 확정) | 동상 |
| POST `/supplements/analyze-multi` | multipart 복수 이미지 일괄 | `SupplementMultiImageAnalysisPreview` | 동상 |

**백엔드 공백 (날조 금지 — 필요 시 백엔드 이슈로)**
1. **음식 영역 바운딩박스 미노출**: `/meals/analyze-image` 응답에 검출 영역 좌표 없음(`food_candidates`에 bbox 없음) → figma 946:24 오버레이는 보류 (플랜 R4)
2. **분석 진행률 스트림/폴링 라우트 없음**: analyze 계열은 동기 202 단일 응답 → 3단계 체크리스트는 클라이언트 연출 + 사후 `pipeline_metadata` 검증 표기로 구현 (§④-2)

## ⑥ 상태 / 에러 처리

| 상황 | 처리 | 위젯/패턴 |
|---|---|---|
| 카메라 권한 거부 (912:23) | 설명 + [설정 열기] CTA, 갤러리 폴백 유지 | `StatusStateView(variant: permissionDenied)` |
| 카메라 초기화 실패 (912:69) | 재시도 + 갤러리 폴백 | `StatusStateView(variant: analysisFailed)` 톤 |
| 분석 중 | 3단계 체크리스트 + [메인으로 이동] (백그라운드 = `AnalysisJobSnapshot.running`) | `_AnalysisInProgressScreen` 확장 |
| 분석 실패 | `AnalysisJobSnapshot.failed` 메시지 + 재촬영/갤러리 CTA | `StatusStateView(variant: analysisFailed)` |
| 후보 0건 / `requires_manual_entry` | 직접 입력 검색 폴백 (916:23) | 검색 패널 + 수동 입력 필드 |
| 저신뢰 (최고 confidence < 0.6, 951:76) | "AI가 확실하지 않아요" 배너 + 직접 확인/재촬영 유도. **% 숫자 비노출, 등급 칩만** | `LowConfidenceBanner` + `ConfidenceGradeChip` |
| 검색 0건 (951:36) | 검색어 표시 + 수동 입력 유지 | `StatusStateView(variant: searchEmpty, query:)` |
| 403 `consent_required` | 해당 동의(`food_image_processing`/`ocr_image_processing`) 1회 POST 후 동일 요청 재시도 | `chat_repository.dart` 패턴 |
| 409 (client_request_id 충돌 / preview 상태 불가) | 새 request id로 재생성 안내, confirm 409는 "이미 처리된 분석이에요" 후 기록으로 이동 | 스낵바 + 라우팅 |
| 413/415 (용량/형식) | "사진 용량(형식)을 확인해주세요" + 재선택 | 스낵바 |
| 빈 파일/소실 (Android picker) | 기존 as-built: 빈 파일 가드(`_analyze` L1066)·lost-data 복구(`_recoverLostGalleryPick`) 유지 | 변경 금지 |

모든 안내 문구는 해요체. 후보·검출 화면 하단에도 면책 푸터(`MedicalDisclaimer`) 고정 — "건강 참고용이며 진단·처방이 아닙니다" 프레임 유지.

## ⑦ 테스트 계획

기존 통과 기준 유지: `flutter analyze` 0건 + `flutter test` 170개 전부 통과(추가분 포함 전체 green).

| 종류 | 파일 | 검증 내용 |
|---|---|---|
| 위젯 (기존 확장) | `test/widget/source_camera_screen_test.dart` | 세그먼트 토글 모드 전환, 가이드 모달 1회 표출 + 다시 보지 않기 후 미표출, 미리보기 품질 체크 2행 렌더 |
| 위젯 (기존 확장) | `test/widget/supplement_capture_test.dart` | 2슬롯: role 고정(front_label/supplement_facts) 업로드 호출 검증, 2장 충족 시 CTA 활성 |
| 위젯 (기존 확장) | `test/widget/analysis_result_screen_test.dart` | 후보 리스트 선택 → confirm payload `portion_amount` 반영, 0건 → 검색 폴백 + searchEmpty, 저신뢰 → `LowConfidenceBanner`, 3단계 체크리스트 + [메인으로 이동] |
| 단위 (신규) | `test/unit/image_quality_probe_test.dart` | 블러/저조도 판정 경계값 (결정론적 픽스처 이미지) |
| 단위 (기존 확장) | `test/unit/supplement_repository_test.dart` | `searchFoodCatalog` 쿼리 직렬화 + `FoodCatalogItem.fromJson` null-safe |
| 단위 (기존) | `test/unit/confidence_grade_test.dart` | 등급 경계(0.85/0.6) 회귀 유지 |
| 금칙어 가드 | 신규 문구가 있는 각 테스트 | "진단/처방/치료/효능" 부재 assert 동반 (회귀 가드 공통 규칙) — % 텍스트(`%` + 숫자) 비노출 assert 포함 |
| 보안 회귀 | `test/unit/release_security_config_test.dart` | cleartext 예외 debug 오버레이 한정 유지 (변경 금지) |

## ⑧ 플랫폼 노트

**Android — Pixel 10 Pro (Android 17, targetSdk 36)**
- dev API `http://10.0.2.2:8000/api/v1` — debug 전용 cleartext 오버레이 적용 완료(P0). release 차단 유지
- Photo Picker lost-data 복구(`_recoverLostGalleryPick`)와 debug 샘플 이미지 경로(`LEMON_DEBUG_SUPPLEMENT_IMAGE_PATH`)는 에뮬 한정 — 신규 UI가 이 폴백 분기를 가리지 않는지 확인
- 예측형 뒤로가기: 분석 중 화면에서 뒤로가기 = [메인으로 이동]과 동일 동작(작업은 백그라운드 유지)으로 일관 처리
- 카메라 풀스크린의 시스템 바 스타일은 `AnnotatedRegion` as-built — 신규 모달/시트가 다크 아이콘으로 덮지 않게 주의

**iOS — iPhone 17 Pro (iOS 26.5, deployment target 15.0)**
- 한국어 카메라/사진 권한 문구 + Light 고정 적용 완료(P0)
- 시뮬레이터는 실카메라 없음 → Mac 카메라 브리지(`LEMON_MAC_CAMERA_BRIDGE_URL`)/갤러리 폴백 as-built — 품질 체크 2종은 브리지 프레임에도 동일 적용
- dev API `http://127.0.0.1:8000/api/v1` (ATS LocalNetworking 허용 확인됨)
- 햅틱: 셔터/분석 시작의 `HapticFeedback.mediumImpact` 유지, 신규 바텀시트 선택에는 `selectionClick` 권장

## ⑨ 완료 기준 (DoD)

- [ ] 음식 촬영 → 후보 선택(등급 칩, % 비노출) → 섭취량 조정 → confirm payload에 `portion_amount/portion_unit` 반영 → 기록 저장까지 실기기 E2E 통과 (양 플랫폼)
- [ ] 후보 0건·저신뢰 경로에서 직접 입력 검색(`GET /meals/foods`)으로 막힘 없이 저장 가능
- [ ] 분석 중 화면: 3단계 체크리스트 표출 + [메인으로 이동] 후 다른 탭 사용 → 완료 알림으로 결과 복귀 (AnalysisJobSnapshot 회귀 없음)
- [ ] 촬영 가이드 모달 모드별 1회 + 다시 보지 않기 동작 (영속화는 P1-5 도입 시 — `TODO(persist)` 추적)
- [ ] 영양제 2슬롯(앞면+성분표) → analysis-sessions 재사용으로 merged preview 도달, 기존 6장 자유 배치 회귀 없음
- [ ] 영양제 검출 오버레이가 `detected_product_regions[]` 좌표를 올바른 스케일로 렌더, 음식 박스는 "백엔드 공백" 주석으로 보류 명시
- [ ] `flutter analyze` 0건 / `flutter test` 전체 통과(기존 170개 + 신규) / 금칙어·% 비노출·면책 푸터·cleartext 회귀 가드 4종 green
- [ ] 신규 사용자 문구 전부 해요체 + 본문 15px 이상 + 버튼 52px 이상 (SoT 시니어 최소치)
