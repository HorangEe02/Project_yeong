# 04 — 분석 결과 화면 구현 가이드 (C 채택안 · 영양제 최종/저장 완료 · 성분 상세)

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

---

## ① 범위/목표

이 문서는 **분석 결과 표면 전체**를 다룬다.

| 영역 | figma | 상태 |
|---|---|---|
| 식단(음식) 분석 결과 — C 하이브리드 채택안 | 04 보드 `620:2` (참고: A `616:2`, B `617:2`) | **P0 완료 — as-built 참조** |
| 음식 상세 (D) | 04 보드 `718:23` | P0 완료 — as-built 참조 |
| 영양제 최종 결과 | 07 보드 ④ `856:23` | 부분 구현 — 개인화 코멘트 잔여 |
| 영양제 저장 완료 | 07 보드 ⑤ `857:23` | **미구현 — 본 문서 (b)** |
| 성분 상세 | 12 보드 ④ `947:49` | **미구현 — 본 문서 (a)** |
| 저장→홈 기록 반영 흐름 | 03 Main `268:24` 연계 | 부분 — 본 문서 (c) |
| '챗으로 설명 보내기' | S-11 `773:23` 연계 | P0 완료 — as-built 참조 (d) |

목표: P0에서 완성된 C 레이아웃·5카드·소프트블록 위에, **성분 상세 / 저장 완료 / 홈 반영**의 잔여 3개 표면을 같은 토큰·계약으로 마저 붙인다. 연산은 전부 백엔드 책임 — 모바일은 표시·매핑만 한다(mobile/CLAUDE.md).

---

## ② 디자인 스펙

### 2.1 프레임 인용 (file key `tabLE08wPC1EQ0XdfgCwII`, 03_UI_Design 페이지 `0:1`)

| 프레임 | ID | 핵심 레이아웃 |
|---|---|---|
| C · 분석결과 (채택) | `620:2` | 링게이지 점수 → 주의 성분 → 부족/과다 2열 그리드 → 목적별(만성질환) 카드 → 면책 → 하단 고정 [저장] |
| D · 식단(음식) 결과 | `718:23` | 음식 항목 리스트 + 영양 합산 + AI 설명 문단 |
| S-04 영양제 분석 결과(최종) | `856:23` | 핵심 성분 기준치% 바 + 기대 작용/주의 리스트 + 개인화 코멘트 카드 |
| S-05 영양제 저장 완료 | `857:23` | 축하 헤더 + 요약 그리드(제품/성분 수/복용 일정) + **[복용 알림 설정하기] CTA** + [홈으로] |
| 성분 상세 (12-④) | `947:49` | 함량 헤더 → 권장량 100%·상한(예: 2000mg) 게이지 카드 → 도움 정보 리스트 → 질환 조건부 주의 배너 → 함유 식품 칩 |
| 상호작용 경고 모달 | `921:24` | 소프트 블록(“그래도 저장할게요” / “안전 정보 자세히 보기”) |
| 저장 완료 축하 모달 | `921:53` | 컨페티 + 1차 CTA |
| 분석 신뢰도 낮음 | `951:76` | 저신뢰 배너 + 직접 입력/재촬영 폴백 |
| 토스트 (저장됨) | `959:68` | 실행취소 토스트 |

디자인 모순 결정(플랜 §1.8) 적용: **D1** 과다=review 앰버(주의=danger 레드), **D2** 신뢰도는 % 비노출·등급 칩 기본.

### 2.2 토큰/컴포넌트 (design_tokens_v2 단일 출처)

- 색: `AppColor.brand`(#FFC700 = AppColor.brand), `AppColor.success`/`successSoft`(충분·높음), `AppColor.warning`/`warningSoft`(보통), `AppColor.review`/`reviewSoft`(과다·직접확인), `AppColor.danger`/`dangerSoft`(주의 성분 high), `AppColor.inkStrong/ink/inkLight`, `AppColor.surfaceSunken`
- 타이포: `AppText.title`(점수 헤더), `AppText.subtitle`(카드 제목), `AppText.body`(15px — 시니어 최소), `AppText.caption`(보조)
- 간격/라운드: `AppSpace.page/lg/md/sm`, `AppRadius.lg/full`
- 기존 컴포넌트 재사용: `AppCard`, `AppPrimaryButton`(높이 52px+), `ConfidenceGradeChip`, `LowConfidenceBanner`, `DietScoreHeaderCard`, `CautionaryComponentCard`, `NutrientInsightGrid`, `PurposeTargetCard`, `StatusStateView`, `showInteractionWarningDialog`, `showCelebrationDialog`, `showUndoToast`, `MedicalDisclaimer`/`_MedicalNote`(면책 푸터)
- 성분 상세 게이지(신규): 권장량 100% 기준 채움 바 + 상한(UL) 마커. 100% 이하 `AppColor.success`, 100~UL `AppColor.review`, UL 초과 `AppColor.danger` + 아이콘·텍스트 병행(색 단독 금지)

---

## ③ 현재 코드 상태

### 구현 완료 (as-built — 변경 금지, 참조만)

| 파일 | 내용 |
|---|---|
| `mobile/lib/screens/analysis_result_screen.dart` | 결과 화면 본체(식단/영양제 겸용). `_dietComprehensiveCards()`가 C 순서(점수 링 → 저신뢰 배너 → 주의 성분 → 부족/과다 그리드 → 목적별)로 조립. comprehensive 미가용 시 카드 생략하고 기존 레이아웃 폴백(빈 화면 없음). 저장 직전 `_confirmInteractionSoftBlock()` → `showInteractionWarningDialog`(impact preview의 high severity 시). 등록 후 1차 버튼이 '챗으로 설명 보내기'로 전환 |
| `mobile/lib/widgets/common/diet_result_cards.dart` | `DietScoreHeaderCard`(+`_ScoreRing`), `CautionaryComponentCard`, `NutrientInsightGrid`(부족/과다 2열), `PurposeTargetCard` |
| `mobile/lib/widgets/common/confidence_grade_chip.dart` | `ConfidenceGrade.fromConfidence` — 높음 ≥0.85 / 보통 ≥0.6 / 직접 확인 필요. % 숫자 비노출 |
| `mobile/lib/features/supplements/comprehensive_analysis_models.dart` | `ComprehensiveDietAnalysis` 응답 파서(5카드 + `chronicDiseaseIndications` + `warnings`) |
| `mobile/lib/features/supplements/supplement_repository.dart` | `analyzeComprehensive()` → `POST /supplements/analyze/comprehensive` (현재 `user_profile`은 null 전달), `registerSupplement()` → `POST /supplements` |
| `mobile/lib/app_controller.dart` | `_refreshComprehensiveDietAnalysis()`(meal preview 영양 합산 → ingredients 변환, 실패 시 점수영역 숨김), `queueSupplementExplanationForChat()`/`markChatExplanationDraftDelivered()`(챗 드래프트 큐) |
| `mobile/lib/widgets/common/app_modals.dart` | `showInteractionWarningDialog`(소프트블록), `showCelebrationDialog`, `showDeleteConfirmDialog`, `showUndoToast` |
| `mobile/lib/shared/widgets/status_state_view.dart` | `StatusStateVariant` 6종(emptyNew/syncFailed/permissionDenied/analysisFailed/notificationsEmpty/searchEmpty) |

### 부분 구현

- **영양제 최종 결과(07-④)**: 성분 표(`_ingredientInfoTable`) + `_AnalysisExplanationCard`(`POST /supplements/analyses/{id}/explain`의 `explanation_bullets`/`source_citations`) + `_ImpactPreviewCard`는 동작. **개인화 코멘트 카드 없음** — `analyzeComprehensive`에 `user_profile`을 안 보내서 `purpose_targets`/`chronic_disease_indications`가 항상 빈 배열. 기준치% 바도 `SupplementIngredientCandidate.dailyValuePercent`(모델 존재)를 표가 아닌 게이지로 승격 필요
- **저장→홈 반영(c)**: 식단은 confirm 후 `context.go('/shell/home')` + 홈의 `refreshDashboard`(pull-to-refresh)로 반영. 영양제는 등록 후 챗으로 이동하는 경로라 홈 복귀 시 자동 재조회 보장이 약함

### 구현 없음

- **성분 상세 화면(12-④)** — 라우트·화면 파일 자체가 없음
- **저장 완료 화면(07-⑤)** — 등록 후 같은 화면에 머무름(요약 그리드·복용 알림 CTA 없음)
- KDRIs 조회용 모바일 repository 메서드(`GET /nutrition/kdris`) 없음

---

## ④ 구현 단계

### (a) 성분 상세 화면 — 12-④ `947:49`

1. [ ] `mobile/lib/features/nutrition/kdri_models.dart` 신규 — `KdriReference`(nutrient_code, nutrient_name_ko, reference_type, reference_amount, reference_unit, ul_amount, ul_unit, dataset_status) 파서. 백엔드 `src/models/schemas/nutrition.py`의 `KDRIReference`/`KDRILookupResponse` 필드만 사용(없는 필드 날조 금지)
2. [ ] `mobile/lib/features/supplements/supplement_repository.dart` — `lookupKdris({required int age, required String sex, String pregnancyStatus = 'none'})` 추가, `GET /nutrition/kdris?age=&sex=&pregnancy_status=` (공개 라우트 — 동의 불필요)
3. [ ] `mobile/lib/screens/ingredient_detail_screen.dart` 신규 — 진입 인자: `SupplementIngredientCandidate`(분석 결과의 성분 행) + `ComprehensiveDietAnalysis?`(주의 배너용)
   - 함량 헤더: `displayName` + `amount`/`unit` + `ConfidenceGradeChip(confidence: candidate.confidence)`
   - 권장량 게이지 카드: `dailyValuePercent` 우선, 없으면 KDRIs `reference_amount` 대비 클라이언트 표시 계산(단위 일치 시에만 — 단위 불일치면 "직접 확인 필요" 처리, 환산 날조 금지). 상한 마커: `ul_amount`(예: 비타민C 상한 2000mg) — `ul_amount` null이면 마커 생략
   - 도움 정보 리스트: `POST /supplements/analyses/{analysis_id}/explain`의 `explanation_bullets` + `source_citations` 출처 칩. ⚠️ figma 라벨 "효능"은 의료법 금칙어 — UI 문구는 **"이런 점에 도움을 줄 수 있어요"** 로 대체
   - 질환 조건부 주의 배너: `cautionary_components` 중 해당 성분(`component` 매칭) + `chronic_disease_indications` 보유 시에만 표시. severity high → `AppColor.danger` 계열, "복용 전 의료진과 상담해 보세요" 상담 권고형 워딩
   - 함유 식품 칩: **백엔드 공백** — KDRIs/comprehensive 응답에 식품 출처 데이터 없음. 라우트 신설 전까지 섹션 비표시(또는 백엔드 협의 후 P2). 임의 정적 사전 금지
   - 하단 면책 푸터 필수
4. [ ] 라우팅 — `mobile/lib/app.dart`(GoRouter 정의 위치)에 결과 화면에서 `Navigator.push`형 상세 진입 또는 `/shell/analysis/ingredient` 서브라우트 추가. `showInteractionWarningDialog`의 "안전 정보 자세히 보기" 액션을 이 화면으로 연결
5. [ ] `analysis_result_screen.dart` — `_ingredientInfoTable` 각 행에 onTap → 성분 상세 진입(이 파일은 행 탭 핸들러 추가만, 레이아웃 변경 없음)

### (b) 저장 완료 화면 — 07-⑤ `857:23`

1. [ ] `mobile/lib/screens/supplement_save_complete_screen.dart` 신규 — 입력: `UserSupplementResponse`(등록 응답)
   - 축하 헤더(마스코트 + "영양제를 저장했어요") — `showCelebrationDialog` 모티프를 풀스크린으로
   - 요약 그리드 2×2: 제품명/제조사 · 성분 N개 · 복용 일정(`intake_schedule` 있을 때만) · 등록일
   - **[복용 알림 설정하기] CTA** → 복약 알림 설정 화면(figma `916:76`, 시간 휠 `959:24`) — **08-settings 문서 연계**(P1-5에서 구현, 그 전까지 CTA는 비활성 또는 숨김. 가짜 화면 금지)
   - [챗으로 설명 보내기] 보조 버튼 — as-built `queueSupplementExplanationForChat()` 재사용
   - [홈으로 돌아가기] → `/shell/home`
2. [ ] `analysis_result_screen.dart::_handlePrimaryAction` — `registerSupplement` 성공 분기에서 챗 즉시 이동 대신 저장 완료 화면으로 push (챗 이동은 저장 완료 화면의 보조 버튼으로 이동)
3. [ ] 면책 푸터 + 해요체 검수

### (c) 저장 → 홈 기록 반영 흐름

1. [ ] `app_controller.dart` — `registerSupplement`/`confirmMealImagePreview` 성공 시 홈 데이터 stale 플래그 set (또는 등록 응답을 홈 목록 캐시에 즉시 병합)
2. [ ] `mobile/lib/screens/dashboard_screen.dart` — 탭 복귀(visibility) 시 stale이면 `refreshDashboard()` 자동 호출 — 반영 경로: `GET /dashboard/summary`(health_score) + `GET /meals`(끼니 섹션) + `GET /supplements`(영양제 체크리스트·주간 스트립 기록 점)
3. [ ] 위젯 테스트: 등록 → 홈 진입 시 새 기록 행 렌더 확인

### (d) '챗으로 설명 보내기' — as-built 참조 (작업 없음)

등록 완료 상태에서 1차 버튼 '챗으로 설명 보내기' → `queueSupplementExplanationForChat()`가 사용자 확인 필드·안전 요약만 담은 `ChatExplanationDraft` 생성(원본 OCR/프로바이더 payload 미포함) → `/shell/chat` 이동 → 챗 화면이 드래프트를 컨텍스트로 소비 후 `markChatExplanationDraftDelivered()`. (b) 적용 후에도 동일 메서드를 그대로 재사용한다.

---

## ⑤ 엔드포인트 계약 표

> ApiClient 경로 표기는 `/api/v1` 접두사 제거 형태(baseUrl에 포함). 모든 라우트는 `backend/Nutrition-backend/src/api/v1/`에 실재 확인됨.

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| `POST /supplements/analyze/comprehensive` | `analysis_id?`, `ingredients[]{display_name(필수), nutrient_code?, amount?, unit?}`(≤80개), `user_profile{age 1~120, sex male\|female, chronic_conditions[]≤8, is_pregnant, smoking_status, audit_kr_score?, medications[]≤20}`, `persona "A"\|"B"(기본 B)` | `deficient_nutrients[]{nutrient_code, display_name, current_intake, recommended_intake, unit, deficit_ratio 0~1}` · `excessive_nutrients[]{…, upper_limit, excess_ratio ≥1}` · `cautionary_components[]{component, reason, severity low\|medium\|high, message}` · `diet_score 0~100(int)`, `diet_score_label excellent\|good\|moderate\|warning\|critical`, `diet_score_message` · `purpose_targets[]{condition, relevance_score 0~1, evidence_level strong\|moderate\|weak\|insufficient, message}` · `wellness_goal_targets[]`, `chronic_disease_indications[]`, `algorithm_version`, `warnings[]` | 인증만 |
| `GET /nutrition/kdris` | query: `age`(1~120), `sex`, `pregnancy_status=none` | `references[]{nutrient_code, nutrient_name_ko, reference_type(RDA/AI/…), reference_amount, reference_unit, ul_amount?, ul_unit?, review_status}`, `dataset_status`, `dataset_version`, `note`(안전 문구) | 공개(동의 불필요) |
| `POST /supplements/analyses/{analysis_id}/explain` | path: analysis_id (`use_local_llm` 옵션) | `explanation_bullets[]`, `source_citations[]`(로컬 WIKI 근거 — 응답에 있을 때만 표기, 날조 금지) | ocr_image_processing + sensitive_health_analysis |
| `POST /supplements` | `analysis_id?`, `display_name`, `manufacturer?`, `ingredients[]{display_name, amount?, unit?, daily_value_percent?}`, `serving`, `intake_schedule?`, `precaution_snapshot[]`, `evidence_refs[]` | `UserSupplementResponse`(등록 id·확정 성분·등록일) | 인증만 |
| `GET /supplements` / `GET /supplements/{id}` / `DELETE /supplements/{id}` | — | 목록/상세/삭제 결과 | 인증만 |
| `POST /meals/{meal_id}/confirm` | 사용자 확정 음식명·`portion_amount` | `MealRecordResponse{food_items[], nutrition_summary}` | meal:write (동의 없음 — 동의는 analyze-image 단계에서 처리됨) |
| `POST /meals/{meal_id}/explain` | path: meal_id | AI 영양 설명 문단 + `source_citations` | meal:read (동의 없음) |
| `GET /dashboard/summary` | — | `health_score` 블록 등 홈 요약 | sensitive_health_analysis |

**백엔드 공백**: ① 성분별 **함유 식품** 데이터 라우트 없음(12-④ 함유식품 칩 — 신설 협의 전 비표시) ② 복용 알림 서버 동기화(`notifications` 라우트 미등록 — 팀원 브랜치 P1-1 임포트 대상).

403 `consent_required` 공통 처리: 응답 detail의 `required_consents`로 `POST /me/privacy/consents/{type}` 1회 동의 후 원요청 재시도(chat_repository as-built 패턴 재사용).

---

## ⑥ 상태/에러 처리

| 상황 | 처리 (as-built 템플릿 활용) |
|---|---|
| comprehensive 호출 실패/빈 응답 | 점수·5카드 영역 숨김, 기존 음식/영양제 정보로 폴백 — 빈 화면 금지 (`_dietComprehensiveCards` as-built) |
| `diet_score_confidence` 저신뢰(<0.6) | 점수 링 아래 `LowConfidenceBanner` + 등급 칩 '직접 확인 필요' (% 비노출) |
| 분석 실패 | `StatusStateView(variant: analysisFailed)` + 재촬영/직접 입력 CTA |
| KDRIs 조회 실패(성분 상세) | 게이지 카드 대신 "기준 정보를 불러오지 못했어요" 안내 + 함량만 표시 (화면 자체는 유지) |
| KDRIs `dataset_status` 비공식/`review_status` 미검수 | 카드에 "참고용 기준값이에요" 캡션 병기 (응답 `note` 활용) |
| 단위 불일치로 % 산출 불가 | 게이지 생략 + '직접 확인 필요' 칩 (환산 날조 금지) |
| impact preview high severity | 저장 직전 `showInteractionWarningDialog` 소프트블록 — "그래도 저장할게요" / "안전 정보 자세히 보기"(→ 성분 상세) |
| 403 consent_required | 동의 시트 1회 → 재시도, 거부 시 해당 카드만 비표시 |
| 네트워크 오류 | `StatusStateView(variant: syncFailed)` + 재시도 |
| 모든 분석 표면 공통 | 하단 고정 면책 푸터("건강 참고용이며 진단·처방이 아닙니다" — SoT 고정 문구) + 해요체 |

---

## ⑦ 테스트 계획

- **단위**: `kdri_models` 파싱(널 필드/ul 없음), 게이지 % 산출·클램프(0/100/UL 초과), 단위 불일치 시 게이지 생략 분기, stale 플래그 set/clear
- **위젯**: 성분 상세 — 질환 보유 시에만 주의 배너 렌더 / KDRIs 실패 폴백 / 등급 칩 키(`confidence-grade-*`)로 % 텍스트 부재 assert · 저장 완료 — 요약 그리드 + intake_schedule 없을 때 셀 생략 + 알림 CTA 게이팅 · 결과→홈 반영 — 등록 후 홈에 새 행
- **금칙어 가드**: 신규 문구 전수에 진단/처방/치료/**효능** 부재 assert(기존 패턴 동일 — 백엔드는 `b43b9bfd` 테스트 선례), "효능" 대신 "도움" 계열 워딩 확인
- **회귀**: 기존 170개 테스트 통과 유지, `flutter analyze` 0건, 면책 푸터 존재 assert(성분 상세·저장 완료 추가분)

---

## ⑧ 플랫폼 노트

**Pixel 10 Pro · Android 17 (targetSdk 36)**
- dev API `http://10.0.2.2:8000` — debug 전용 cleartext 오버레이 적용됨(`784687ce`), release 차단 유지(release_security_config_test 회귀 금지)
- 성분 상세/저장 완료는 push 라우트 — 예측형 뒤로가기 제스처에서 pop 애니메이션 확인, 엣지투엣지에서 하단 고정 CTA SafeArea 점검

**iPhone 17 Pro · iOS 26.5 (deployment target 15.0)**
- `UIUserInterfaceStyle=Light` 고정·한국어 권한 문구 적용됨(P0) — 신규 화면은 추가 권한 불필요
- dev API `http://127.0.0.1:8000`(ATS LocalNetworking 허용 확인됨)
- 저장 완료 축하 컨페티 — 저전력 모드에서 애니메이션 축소(접근성 motion 설정 존중)

---

## ⑨ 완료 기준 (DoD)

- [ ] 성분 상세 화면: 함량/권장량·상한 게이지 + 도움 정보(출처 칩) + 질환 조건부 배너가 실데이터(KDRIs + comprehensive)로 렌더, 함유식품 섹션은 백엔드 공백으로 비표시 처리됨
- [ ] 저장 완료 화면: 등록 성공 → 요약 그리드 표시, 복용 알림 CTA는 08-settings 구현 연계(미구현 시 게이팅), 챗 보내기/홈 복귀 동작
- [ ] comprehensive에 `user_profile` 전달 시 목적별 카드·개인화 코멘트 표시(프로필 없으면 카드 생략 — 날조 없음)
- [ ] 저장 후 홈 복귀 시 새 기록(끼니/영양제)이 재조회로 반영
- [ ] 신뢰도 % 직접 노출 0건(등급 칩만), 금칙어 0건, 전 표면 면책 푸터, 본문 15px+/버튼 52px+
- [ ] `flutter analyze` 0건 + `flutter test` 전체 통과(170개 기준 + 신규), 양 플랫폼 스모크(촬영→분석→성분 상세→저장→저장 완료→홈 반영→챗)
