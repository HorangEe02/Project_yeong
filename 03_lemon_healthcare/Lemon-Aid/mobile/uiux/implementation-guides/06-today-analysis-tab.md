# 06 — 분석 탭 '오늘의 분석' 구현 가이드 (figma S-09)

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

---

## ① 범위/목표

- **대상 화면**: 하단 탭 4번째 '분석' = **오늘의 분석** (라우트 `/shell/score`, figma S-09).
- **P0 완료(as-built)**: 점수 탭 → 오늘의 분석 전환(`88c3ef4b`), `GET /dashboard/summary`의 `health_score` 링/등급/코멘트 표시, `POST /ai-agent/daily-coaching` 실천 리스트 + 일자 캐시 + 승인 안내, 레몬봇 딥링크, 면책 푸터. 본 문서에서는 **간결한 참조로만** 다룬다.
- **이번 가이드의 본편(잔여 작업)**:
  - **(a)** 4주 추이 차트 잠금 해제 — 점수 영속 백엔드 작업 명세(보류 결정 #7, [근거](../../../outputs/todo-list/2026-06-11/2026-06-11-daily-health-score-decisions.md))
  - **(b)** 실천 리스트 체크 영속화 (현재 세션 메모리)
  - **(c)** 날짜 칩 과거 일자 조회 (점수는 당일 재계산 한계 명시)
  - **(d)** 등급별 링/칩 색상 규칙 (label → success/warning/danger 토큰)
- **비범위**: 홈 점수 카드(가이드 02), 챗 화면 자체(가이드 05), 점수 산식 변경(백엔드 결정 문서 소관).

---

## ② 디자인 스펙

### 2.1 figma 프레임

| 보드 | 프레임 ID | 용도 |
|---|---|---|
| 03_UI_Design (page `0:1`) | **`800:23` S-09 분석 (오늘의 분석)** | 본 화면 기준 시안 |
| 03_UI_Design | `773:23` S-11 Chat · 레몬봇 | '레몬봇에게 물어보기' CTA 딥링크 대상 |
| 03_UI_Design | `913:60` 상태 · 분석 실패 / `913:24` 상태 · 빈 (신규) | 상태 템플릿 레이아웃 참조 |
| 01_Design_System (page `5:4`) | `37:2` DesignSystem_v2.0 | 토큰·SummaryRing·등급 칩 정의 |

### 2.2 레이아웃 구조 (S-09, 위→아래)

1. **헤더**: '오늘의 분석' 타이틀(좌) + **날짜 칩**(우, `brandSoft` 배경 pill) — 잔여 (c)에서 탭 가능한 일자 선택으로 확장
2. **카드 1 — 오늘의 종합 분석**: 도넛 링 148px(점수/100, strokeWidth 12) + 등급 칩 + 종합 코멘트(서버 `message` 그대로) + 연노랑 '🍋 레몬봇에게 물어보기 ›' CTA
3. **카드 2 — 실천 리스트** '오늘 챙기면 좋은 N가지': 체크 원형(24px) + 제목/보조설명, 최대 5개
4. **카드 3 — 스마트 분석 · 지난 4주 추이**: 라인 차트 — 현재 잠금 placeholder, 잔여 (a)에서 해제
5. **면책 푸터** (고정): "이 분석은 건강 관리를 돕는 참고 정보예요. 의사·약사·영양사의 진단을 대신하진 않아요."

### 2.3 사용 토큰 (design_tokens_v2 — `mobile/lib/utils/design_tokens_v2.dart`)

- 배경/카드: `AppColor.bg`, `AppColor.surface`, `AppColor.sunken`(잠금 영역), `AppColor.border`
- 브랜드: `AppColor.brand` (= `#FFC700`), `AppColor.brandSoft` (= `#FFF6CC`, 날짜 칩·CTA 배경), `AppColor.brandDeep` (= `#C99100`, on-yellow 텍스트)
- 시맨틱(잔여 d): `AppColor.success`/`successSoft` (= `#22B07D`/`#E6F5EE`), `AppColor.warning`/`warningSoft` (= `#FF9500`/`#FFEACC`), `AppColor.danger`/`dangerSoft` (= `#EF4452`/`#FDE7E9`)
- 타이포: `AppText.title`(헤더) / `AppText.subtitle`(카드 제목) / `AppText.body`(본문 15px — 시니어 최소) / `AppText.caption`(칩·보조)
- 간격/모서리: `AppSpace.page`/`lg`/`md`/`sm`, `AppRadius.lg`(카드)/`md`(CTA·잠금)/`full`(칩)

### 2.4 등급별 링·칩 색상 규칙 — 잔여 (d) 확정안

서버 `health_score.label` 5단계를 시맨틱 3토큰으로 매핑한다. **색+텍스트 병행**(등급 한국어 `label_text`를 칩에 항상 표기 — SoT 시니어 접근성 원칙).

| label (점수 구간) | label_text | 링·칩 전경 | 칩 배경 |
|---|---|---|---|
| `excellent` (≥90) / `good` (≥75) | 좋아요 / 양호 | `AppColor.success` | `AppColor.successSoft` |
| `moderate` (≥55) | 보통 | `AppColor.warning` | `AppColor.warningSoft` |
| `warning` (≥35) / `needs_attention` (<35) | 주의 / 참고 | `AppColor.danger` | `AppColor.dangerSoft` |

- 링 트랙(배경)은 현행 유지, 진행 색만 위 규칙 적용. 도넛 중앙 숫자는 `AppColor.ink` 유지.
- `label`이 null/미지(서버 신규 값)일 때 폴백: `AppColor.brand` (현행 색).
- 점수 산식·라벨 경계는 백엔드 단일 소유([daily-health-score-decisions.md](../../../outputs/todo-list/2026-06-11/2026-06-11-daily-health-score-decisions.md) §확정 산식 — `final = round(0.6×활동 + 0.4×영양)`, 0~100 clamp, 한 축 결손 시 가중치 재정규화, 둘 다 결손 시 `not_ready`). **모바일은 label 문자열만 소비하고 점수→색 재계산 금지.**

---

## ③ 현재 코드 상태

### 구현 완료 (as-built — 변경 없이 참조)

| 파일 | 내용 |
|---|---|
| `mobile/lib/screens/score_screen.dart` (775줄) | S-09 전환 완료. 헤더+날짜 칩(정적), 종합 분석 카드(링/등급/코멘트/not_ready 분기), 실천 리스트 카드(로딩/실패/승인 안내/빈 상태), 추이 잠금 카드, 면책 푸터 |
| `mobile/lib/features/ai_coaching/ai_coaching_models.dart` | `DailyCoachingRequest`(AgentInput 직렬화) · `DailyCoachingResult`(AgentOutput null-safe 파싱, recommendations+actions 병합 → priority 정렬 → 5개 절단) |
| `mobile/lib/features/ai_coaching/ai_coaching_repository.dart` | `/ai-agent/daily-coaching` 호출 캡슐화. **403 `consent_required` → 동의 1회 부여 후 재시도** (chat_repository 동일 패턴) |
| `mobile/lib/features/dashboard/home_models.dart` | `DashboardHealthScore` — `health_score` 블록 파싱 (`data_status`/`score`/`label`/`label_text`/`message`) |
| `mobile/lib/shared/widgets/status_state_view.dart` | 전역 상태 템플릿 6변형 (`547713b1`) |
| 백엔드 `src/api/v1/ai_agent.py` | `POST /api/v1/ai-agent/daily-coaching` (AgentOutput, 동의 게이트 + 감사 로그 + 코칭 메모리 upsert) |
| 백엔드 `src/services/daily_health_score.py` | 점수 산식 v1.0.0 + 5단계 라벨 + 금칙어-안전 메시지 |
| 테스트 | `mobile/test/widget/score_screen_test.dart`, `mobile/test/ai_coaching_repository_test.dart` |

### 부분 구현 (이번 가이드로 완성)

- **실천 체크 상태**: `score_screen.dart`의 `_checkedItemIndexes` — 세션 메모리, `// TODO(persist): SharedPreferences 연동` 주석 존재 → (b)
- **링/칩 색상**: `_ScoreRing`은 `AppColor.brand` 고정, `_GradeChip`은 `successSoft/success` 고정 — '주의' 등급도 초록 칩으로 보이는 상태 → (d)
- **날짜 칩**: 오늘 고정 표시 전용, 탭 불가 → (c)
- **`safety_warnings`**: 모델은 파싱하나 화면 미표시 → (b) 단계에서 함께 노출

### 구현 없음 (공백)

- **4주 추이 실데이터**: `_TrendLockedCard` placeholder뿐 → (a)
- **점수 영속**: `AnalysisType`(백엔드 `src/models/schemas/analysis_result.py`)은 `activity_score`/`weight_prediction`/`nutrition_analysis` 3종뿐 — **`DAILY_HEALTH_SCORE` 없음. 점수 저장/이력 라우트도 없음 → 백엔드 공백** (아래 4.1에 명세, 날조 금지)
- **의존성**: `mobile/pubspec.yaml`에 `shared_preferences`·차트 라이브러리 없음 (현재 앱은 최소 의존 원칙 — http/go_router/riverpod 수준)

---

## ④ 구현 단계

### 4.1 (a) 4주 추이 차트 잠금 해제 — 선행: 점수 영속 [백엔드 공백 명세]

보류 결정 #7 채택을 전제로 한 백엔드 작업. **아래 라우트/enum은 현재 존재하지 않으며 신규 개발이 필요하다.**

**백엔드 (Nutrition-backend)**

1. [ ] `src/models/schemas/analysis_result.py` — `AnalysisType.DAILY_HEALTH_SCORE = "daily_health_score"` 추가 (StrEnum 멤버 1줄 + docstring)
2. [ ] 저장 방식 결정 — 2안 중 택1:
   - **A안(권고): 서버 측 자동 영속.** `GET /dashboard/summary` 처리 중 `build_daily_health_score()`가 `data_status="ready"`를 반환하면 `(user_id, measured_date)` 기준 **1일 1행 upsert**로 `analysis_results`에 저장. `result_snapshot`에는 health_score 블록 전체(`score`/`label`/`label_text`/`message`/`measured_date`/`algorithm_version`/`source_citations`) 보존. 클라이언트 변경 0, 홈만 열어도 이력이 쌓임. 멱등성(같은 날 재호출 시 갱신) 테스트 필수.
   - **B안: `POST /analysis-results/daily-health-score` 신설.** 기존 `POST /analysis-results/activity-score`(`src/api/v1/analysis_results.py`) 패턴 복제 — 동의 게이트 + `store_*` 서비스(`src/services/analysis_results.py`) + 감사 이벤트. 모바일이 점수 수신 후 명시 호출해야 하므로 중복 저장 방지 로직이 클라이언트로 새는 단점.
3. [ ] **시계열 조회 보강 [백엔드 공백 ②]**: 기존 `GET /analysis-results?analysis_type=...`의 목록 응답(`AnalysisResultSummary`)에는 `result_snapshot`이 없어 **점수 값이 내려오지 않는다**. 4주 추이를 28회 상세 조회 없이 그리려면 택1:
   - Summary에 옵셔널 요약 필드(`score: int | null`, `measured_date: str | null`) 추가 — 스냅샷에서 추출, 타 타입은 null (하위호환·권고)
   - 또는 `include_snapshot=true` 쿼리 파라미터
4. [ ] `DASHBOARD_ALGORITHM_VERSION` bump 검토 (보류 결정 #9 관례) + pytest: enum 추가/upsert 멱등/목록 score 필드/RLS 소유자 격리

**모바일 (mobile/lib)**

5. [ ] `features/analysis_trend/analysis_trend_models.dart` 신설 — `ScoreTrendPoint{date, score, label}` + 목록 JSON null-safe 파싱
6. [ ] `features/analysis_trend/analysis_trend_repository.dart` 신설 — `ApiClient.getJson('/analysis-results?analysis_type=daily_health_score&limit=28')` (403 동의 재시도 패턴은 ai_coaching_repository와 동일하게 적용 — 조회도 sensitive 스코프)
7. [ ] `screens/score_screen.dart` — `_TrendLockedCard` → `_TrendChartCard` 교체: 데이터 7일치 미만이면 현행 잠금 유지("기록이 쌓이면 추이를 보여드려요"), 이상이면 28일 라인 차트. **차트는 `CustomPainter` 자체 구현 권고**(점 최대 28개 — 외부 차트 의존성 추가 불필요; `fl_chart` 도입은 팀 합의 시 대안)
8. [ ] 차트 색: 라인 `AppColor.brand`, 포인트는 2.4 등급 매핑 색, 축 라벨 `AppText.micro`+`AppColor.inkTertiary`. **y축에 점수 숫자 표기는 가능(건강 점수), 신뢰도 %는 어떤 형태로도 금지**

### 4.2 (b) 실천 리스트 체크 영속화 — ✅ 구현 완료 (2026-06-12)

1. [x] `pubspec.yaml` — `shared_preferences` (P1 배치에서 선반영돼 있었음)
2. [x] `features/ai_coaching/coaching_check_store.dart` 신설 — key `coaching_checked:{YYYY-MM-DD}`, value = **체크된 항목의 제목 기반 키 목록**(`coach:{title}` / `custom:{title}` — 재호출로 항목 순서가 바뀌어도 체크 유지). 초안의 `item.title` 해시는 Dart `String.hashCode`가 런타임 버전 간 안정성이 보장되지 않아 **제목 원문 키로 확정**(의도적 편차). 보관 기한(7일) 지난 키는 로드 시 정리. as-built 확장: 직접 추가 실천(figma 800:23 CTA — P1 as-built)의 제목 목록도 `coaching_custom:{YYYY-MM-DD}` 키로 함께 영속(화면 TODO 주석이 약속한 범위). 같은 제목 중복 추가는 키 충돌(동시 토글)을 막기 위해 추가 시 차단
3. [x] `score_screen.dart` — `_checkedItemIndexes`(Set\<int\>) → `Set<String>` 전환, `initState` 복원 / `_toggleItem` 저장, `// TODO(persist)` 주석 제거
4. [x] 같은 단계에서 `safety_warnings` 노출 추가: 실천 리스트 카드 하단에 `warningSoft` 배경 안내 행 (문구는 서버 그대로 — 프론트 가공 금지)

### 4.3 (c) 날짜 칩 — 과거 일자 조회 — ✅ 구현 완료 (2026-06-12)

1. [x] `score_screen.dart` `_Header` — 날짜 칩을 `Pressable`로 감싸 탭 시 데이트 피커(범위: 오늘−27일 ~ 오늘, ko 로케일) 표시. 선택일 `_selectedDay` 상태 추가. 구현 노트: ko 로케일은 앱 전역(`MaterialApp.localizationsDelegates` + `locale: ko`, `flutter_localizations`)으로 적용 · 자정 경과로 선택일이 새 범위 밖이 되는 경우 대비 `initialDate` 클램프 · 칩 히트 영역은 시니어 최소 48px 확보(시각 크기 유지)
2. [x] 과거 일자 선택 시:
   - **실천 리스트**: `runDailyCoaching(day: _selectedDay, meals: _controller.mealsForDay(_selectedDay), ...)` — payload `date`에 과거일이 들어가며 일자 캐시는 선택일별 결과 맵(`_coachingCache[YYYY-MM-DD]`)으로 동작 — 같은 날짜 재진입(오늘 복귀 포함) 시 재호출하지 않아 생성형 재실행으로 제목이 바뀌어 체크 표시가 탈락하는 것을 막는다. 과거일은 체크 토글 **읽기 전용** 처리 + 추가 CTA 숨김
   - **종합 점수**: `health_score`는 `GET /dashboard/summary`가 **호출 시점의 '당일'만 재계산**한다 — 과거 일자의 점수는 서버에 없으므로, (a) 영속 적용 **전**에는 점수 카드 대신 안내를 표시한다: "지난 날짜의 점수는 준비 중이에요. 실천 기록만 보여드려요." (a) 적용 **후**에는 `analysis-results` 이력(추이 조회 결과)에서 해당 일자 스냅샷을 찾아 표시 — 이력에 없는 날짜는 위 안내 유지
3. [x] **한계 문서화(코드 주석 + 화면)**: 당일 점수도 재조회 시점의 기록 상태로 재계산되므로, 과거에 본 점수와 이력 저장값이 다를 수 있다. 이력 카드에는 `measured_date` 기준임을 캡션으로 표기 ("기록 당시 기준이에요")
4. [x] 오늘로 복귀하는 '오늘' 칩 제공 (과거 보기 상태에서만 노출)

### 4.4 (d) 등급별 링/칩 색상 규칙 — ✅ 구현 완료 (2026-06-12)

1. [x] 헬퍼는 처음부터 공유 위치로 — `shared/score_label_colors.dart`의 `scoreLabelColor(String?)` / `scoreLabelSoftColor(String?)` (2.4 매핑 표 그대로, 미지 값 → `AppColor.brand`/`brandSoft` 폴백)
2. [x] `_GradeChip`에 `labelCode` 전달 → 전경/배경 색 적용 (`label_text`는 현행대로 그대로 표기)
3. [x] `_ScoreRing`에 `color` 파라미터 추가 → `valueColor`에 매핑 색 적용 (추이 차트 포인트 색도 동일 헬퍼로 통합)
4. [x] 홈 점수 카드(`widgets/dashboard/health_hero_card.dart`)와 동일 매핑 공유 — `scoreLabel`(코드값) 전달 시 라벨 캡션에 매핑 색 적용, 위젯 테스트로 회귀 가드 (보류 결정 #5 "홈 카드·오늘의 분석 링 = 같은 score" 정합)

---

## ⑤ 엔드포인트 계약 표

> ApiClient 경로 표기: `/api/v1` 접두사 제거 형태 (baseUrl에 포함됨). 403 `consent_required` 수신 시 `POST /me/privacy/consents/sensitive_health_analysis`(201) 1회 후 원요청 재시도 — `ai_coaching_repository.dart` 구현 완료 패턴.

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| `POST /ai-agent/daily-coaching` | AgentInput: `request_id`(멱등 키), `user_id`(서버가 인증 주체로 덮어씀 — placeholder 가능), `payload{date, sources[], foods[], supplements[], health_trends[]}`, `context{profile{goals[]}}` | AgentOutput: `status`(preview/completed/failed), `approval_status`, `requires_user_approval`, `message`, `findings[]`, `recommendations[]`, `actions[]`, `safety_warnings[]`, `provider` | analysis write 스코프 + `sensitive_health_analysis` |
| `GET /dashboard/summary` | (없음 — 당일 기준 서버 계산) | `health_score{data_status(ready/not_ready), score(0~100/null), label, label_text, message, measured_date, algorithm_version, disclaimers[], source_citations[]}` | `sensitive_health_analysis` |
| `GET /meals?from_eaten_at=&to_eaten_at=` | 날짜 범위 쿼리 | 식사 목록(`food_items[]`, `nutrition_summary`) — (c) 과거일 payload 구성용 | 인증 |
| `GET /supplements` | — | 등록 영양제 목록(`intake_schedule`) — supplements payload 구성용 | 인증 |
| `POST /me/privacy/consents/sensitive_health_analysis` | (빈 본문) | 201 Created | 인증 |
| `GET /analysis-results?analysis_type=daily_health_score&limit=28&offset=0` | 쿼리: `analysis_type`, `limit`(1~100, 기본 20), `offset` | `results[]{id, analysis_type, algorithm_version, created_at}` — **현재 Summary에 점수 값 없음** | analysis read 스코프 + `sensitive_health_analysis` |
| ~~`POST /analysis-results/daily-health-score`~~ 또는 dashboard 자동 upsert | (4.1 명세) | `AnalysisResultResponse{id, analysis_type, result_snapshot, created_at}` | analysis write 스코프 + `sensitive_health_analysis` |

마지막 2행 비고: `analysis_type=daily_health_score` 필터와 저장 경로는 **백엔드 공백** — 4.1의 enum 신설·영속·Summary 점수 필드 작업 완료 후에만 유효하다. 그 전에 모바일에서 호출 금지(422).

**AgentInput payload 항목 형태 (as-built, `ai_coaching_models.dart`/`ai_coaching_repository.dart` 기준)**

```jsonc
// foods[] 항목 (당일 확정 식사 → 음식 단위 평탄화)
{ "display_name": "현미밥", "kcal": 310, "carb_g": 68, "protein_g": 6, "fat_g": 1,
  "sodium_mg": 0, "user_confirmed": true, "source": "user_confirmed" }

// supplements[] 항목 (등록 영양제)
{ "product_name": "비타민D 2000IU", "ingredients": [], "times_per_day": 1, "user_confirmed": true }
```

**AgentOutput 하위 객체 (백엔드 `ai_agent_chat/src/lemon_ai_agent/adapters/app.py` 기준)**

| 배열 | 필드 |
|---|---|
| `findings[]` | `nutrient`, `total_amount`, `unit`, `ratio_to_target?`, `level`(low/high/ok), `message` |
| `recommendations[]` | `category`, `title`, `rationale`, `priority`(int), `requires_professional_consult` |
| `actions[]` | `action_type`, `title`, `payload{}`, `requires_user_approval`(기본 true) |

모바일 소비 규칙(as-built): recommendations+actions 병합 → `priority` 오름차순(actions 무priority는 100으로 뒤) → 최대 5개. `message`/`label_text`는 서버가 금칙어 처리 완료 — **프론트 가공 금지**. `source_citations[].source_path` 사용자 노출 금지(title만).

---

## ⑥ 상태/에러 처리

| 상태 | 처리 (위젯/문구는 해요체) |
|---|---|
| 점수 `not_ready` | 점수·링 미표시(날조 금지). "기록을 추가하면 점수를 보여드려요." + '촬영하기' CTA (as-built `_NotReadyBody`) |
| 실천 리스트 로딩 | 카드 내 인라인 스피너 (as-built) — 전체 화면 블로킹 금지 |
| 실천 리스트 실패 | 카드 내 가벼운 오류 + '다시 시도' (as-built `_ChecklistError`). 화면 전체 실패 시에만 `StatusStateView`(`shared/widgets/status_state_view.dart`) 동기화 실패 변형 사용 |
| `requires_user_approval=true` + 항목 0 | "기록을 확정하면 맞춤 제안을 드려요." (as-built) |
| 항목 0 (승인 불요) | "오늘 끼니와 영양제를 기록하면 실천 항목을 만들어 드려요." (as-built) |
| `safety_warnings[]` 존재 | (4.2-4 신규) `warningSoft` 안내 행 — 서버 문구 그대로, 상담 권고형 유지 |
| 403 `consent_required` | 동의 1회 부여 후 재시도, 재차 403이면 오류 상태로 강하 (as-built repository) |
| 추이 데이터 7일 미만 / 백엔드 공백 미해소 | 잠금 카드 유지: "기록이 쌓이면 추이를 보여드려요" |
| 과거 일자 + 점수 이력 없음 | "지난 날짜의 점수는 준비 중이에요. 실천 기록만 보여드려요." (4.3-2) |
| 저신뢰 | 본 화면은 확신도 개념이 없는 서버 확정 점수/코칭만 표시 — 신뢰도 % 노출 금지 원칙상 추가 처리 불요. findings `level`은 문구로만 표현 |
| 면책 푸터 | 모든 상태에서 하단 고정 (as-built `_Disclaimer`) |

---

## ⑦ 테스트 계획

**기존 (회귀 유지)**: `mobile/test/widget/score_screen_test.dart`, `mobile/test/ai_coaching_repository_test.dart`, `mobile/test/widget/status_state_view_test.dart` — `flutter analyze` 0건 + `flutter test` 전체(170개 기준) 통과 유지.

**신규 — 모바일**

- [ ] 단위: `coaching_check_store` — 날짜 키 저장/복원/7일 정리, 제목 기반 키가 항목 순서 변경에 견디는지
- [ ] 단위: `_labelColor` 매핑 — 5개 label→3토큰 + 미지 값 폴백 (홈 카드와 동일 헬퍼 공유 검증)
- [ ] 단위: `ScoreTrendPoint` 파싱 — score 필드 누락(구버전 Summary) 시 안전 강하
- [ ] 위젯: 추이 카드 — 7일 미만 잠금 / 28일 데이터 렌더 / 과거 일자 선택 시 읽기 전용 체크 + 안내 문구
- [ ] **금칙어 가드**: 신규 사용자 문구(4.3 안내 2종, 추이 캡션)에 진단·처방·치료·효능 부재 assert (기존 가드 테스트 패턴 동반)
- [ ] 신뢰도 % 미노출 가드: 추이 차트 위젯 텍스트에 `%` 부재 assert (점수 숫자는 허용)

**신규 — 백엔드** (`backend/.venv/bin/python -m pytest Nutrition-backend/tests -q -o addopts=""`)

- [ ] `AnalysisType.DAILY_HEALTH_SCORE` 직렬화/필터
- [ ] 영속 멱등성: 같은 `measured_date` 재계산 시 1행 유지(upsert)
- [ ] Summary 점수 필드: daily_health_score 타입만 값, 타 타입 null (하위호환)
- [ ] 소유자 격리(RLS): 타 사용자 이력 조회 불가
- [ ] `result_snapshot` 내 금칙어 부재 (daily_health_score.py 기존 가드 연장)

---

## ⑧ 플랫폼 노트

**Pixel 10 Pro · Android 17 (targetSdk 36)**
- dev API `http://10.0.2.2:8000/api/v1` — debug 전용 cleartext 오버레이 적용 완료(`784687ce`). `release_security_config_test` 통과 유지(메인 설정에 예외 추가 금지)
- 데이트 피커(4.3): Material 3 기본 + ko 로케일 확인, 예측형 뒤로가기에서 피커 닫힘 동작 점검
- CustomPainter 28점 라인 차트는 성능 이슈 없음. 엣지투엣지에서 하단 면책 푸터의 SafeArea(bottom: false) + 패딩 80 유지 확인

**iPhone 17 Pro · iOS 26.5 (deployment target 15.0)**
- dev API `http://127.0.0.1:8000/api/v1` (ATS `NSAllowsLocalNetworking=true` 확인됨)
- `UIUserInterfaceStyle=Light` 고정 적용 완료 — 등급 색 매핑은 라이트 팔레트 기준만 검증하면 됨
- 검증 빌드: `flutter build ios --no-codesign`, 시뮬레이터 `iPhone 17 Pro`

**공통 dev 스택**
- 백엔드: `uvicorn src.main:app --port 8000` (PYTHONPATH에 `ai_agent_chat/src`), 최초 1회 `alembic upgrade head`(0030~0041 미적용 상태 — P0 잔여 E2E 항목)
- LLM 미기동 시 daily-coaching은 결정론적 응답(`provider: "deterministic"`)으로 동작 — 데모 가능

---

## ⑨ 완료 기준 (DoD)

- [x] (d) 등급 5단계가 success/warning/danger 토큰으로 링·칩에 반영되고, 홈 점수 카드와 동일 매핑을 공유한다 (2026-06-12)
- [x] (b) 실천 체크가 앱 재시작 후에도 당일 내 유지되고, 날짜가 바뀌면 초기화된다. `safety_warnings`가 화면에 노출된다 (2026-06-12)
- [x] (c) 날짜 칩으로 최근 28일 조회 가능 — 과거일 실천 리스트 표시 + 점수 한계 안내 문구 + '오늘' 복귀 칩 (2026-06-12 — iOS 26.5 시뮬레이터 실화면 검증 포함)
- [x] (a) 백엔드: `AnalysisType.DAILY_HEALTH_SCORE` + 1일 1행 영속 + 목록 응답 점수 필드 — pytest 통과(멱등/격리/금칙어). 모바일: 7일치 이상이면 추이 차트, 미만이면 잠금 (f8e1c07d)
- [x] `flutter analyze` 0건 + `flutter test` 전체 통과 (2026-06-12 기준 370+), 백엔드 unit suite 통과(허용 실패 = 사용자 WIP 2건뿐)
- [x] 회귀 가드 4종 충족: 금칙어 부재(표준 면책 문장은 정확 일치 화이트리스트) / release_security_config_test / 신뢰도 % 미노출 / 면책 푸터 상시 표시
- [ ] 양 플랫폼 스모크: 기록 → 홈 점수 → 오늘의 분석(점수·실천·추이) → 레몬봇 딥링크 E2E — Android 풀사이클·iOS 인터랙티브(b/c/d) 완료, 7일치 누적 후 추이 차트 실데이터 렌더만 잔여
