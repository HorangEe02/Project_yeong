# 05. 챗 레몬봇 (S-11) 구현 가이드

> 기준일 2026-06-12 · 디자인 소스: mobile/uiux/figma (DS v2.0 · SoT v1.1) · 브랜치 feat/ai-agent-chat-import

---

## ① 범위 / 목표

- **대상 화면**: 챗 탭 "레몬봇" — figma `03_UI_Design` 보드 05(부가 화면) 3번째 프레임 **S-11 Chat · 레몬봇 (`773:23`)**
- **P0 완료(as-built)**: mock 제거 → `POST /ai-agent/chat` 실연동 완료 (커밋 `10cbc199`). answerability 캡션, 출처 칩, CTA 칩, 분석 승인 카드, 동의 1회 재시도 모두 구현·테스트 통과 상태.
- **이 문서의 본론(잔여 작업)**:
  - (a) 응답의 `analysis_snapshot` / `today_analysis` / `smart_analysis` / `checklist_candidates` 블록 렌더 — **현재 파싱은 되지만 화면에 미표시**. 승인 루프 완료 후 분석 결과 카드를 채팅에 인라인 표시
  - (b) 출처 칩 탭 → 출처 상세 바텀시트
  - (c) 대화 영속화 현황 정리 (현 세션 메모리 — 서버 저장 라우트 없음)
  - (d) production fail-closed 운영 노트
  - (e) 분석결과 화면發 "챗으로 설명 보내기" 드래프트 흐름 as-built 문서화
- **비범위**: 오늘의 분석 탭 자체(S-09, 06 문서), 데일리 코칭 카드(홈, 03 문서), 음성 입력·이미지 첨부(시안에 없음).

---

## ② 디자인 스펙

### 프레임

| 프레임 | ID | 용도 |
|---|---|---|
| S-11 Chat · 레몬봇 | `773:23` | 챗 탭 본편 (헤더·말풍선·추천 질문·입력바) |
| 상태 · 분석 실패 | `913:60` | 응답 실패 시 상태 메시지 참조 |
| C · 분석결과 | `620:2` | (a) 인라인 분석 카드의 축약 레이아웃 참조 — 링/등급 칩·실천 항목 |
| S-09 분석 (오늘의 분석) | `800:23` | today_analysis 카드의 점수·실천 리스트 표현 참조 |

### 레이아웃 구조 (as-built가 시안과 일치)

```
Scaffold (배경 AppColor.section)
├─ _ChatHeader        — AppColor.brand 헤더 + 마스코트 원형 + "레몬봇" 타이틀/부제
├─ ListView (스크롤)
│   ├─ _IntroCard     — surface 카드 + hello-mascot + 인사
│   ├─ _SuggestionGrid — 추천 질문 칩 4개 (메시지 0건일 때만)
│   └─ 메시지 반복
│       ├─ _MessageBubble        — user: brand 우측 / bot: surface 좌측 / error: dangerSoft
│       ├─ _AnswerabilityCaption — answerability ≠ answerable 시 (AppColor.review)
│       ├─ _SourceChips          — "근거" 라벨 + 출처 칩 (section 배경)
│       ├─ _ApprovalCard         — 분석 승인 게이트 (infoSoft 카드 + 2버튼)
│       ├─ [신규] 분석 결과 인라인 카드  ← 잔여 (a)
│       └─ _CtaChips             — brandSoft 칩 ≤3 (탭 시 그 텍스트로 전송)
└─ _InputBar          — 둥근 입력 칩 + brand 그라디언트 원형 전송 버튼
```

### 사용 토큰/컴포넌트 (design_tokens_v2 참조만)

- 색: `AppColor.brand` / `brandSoft` / `brandTint` / `brandDeep` / `ink` / `inkSecondary` / `inkTertiary` / `surface` / `section` / `border` / `borderStrong` / `danger` / `dangerSoft` / `review` / `info` / `infoSoft`
- 간격·라운드: `AppSpace.page/lg/md/sm/xs/cardInside`, `AppRadius.lg/md/sm/full`
- as-built 예외 1건: 전송 버튼 그라디언트 상단색 `#FFD43A`(= AppColor.brand 의 밝은 변형, 토큰 미정의) — 신규 작업에서는 재사용하지 말고 `AppColor.brand` 단색 또는 토큰 추가 후 사용
- 신규 인라인 분석 카드: `AppCard(Outlined)` 구조 + 등급 칩(ConfidenceBadge 스타일) + 면책 푸터 (확신도 % 직접 노출 금지 — SoT §7)

---

## ③ 현재 코드 상태

### 구현 완료 (as-built — 참조만, 재작업 금지)

| 파일 | 내용 |
|---|---|
| `mobile/lib/features/chat/chat_models.dart` | `ChatTurn`, `ChatbotResponse`(응답 **전 필드** null-safe 파싱: sources, ctas, requiresUserApproval, analysisSnapshot, todayAnalysis, smartAnalysis, checklistCandidates, approvalPreview), `ChatbotChecklistCandidate`, `ChatbotApprovalPreview`, `ChatbotSource` |
| `mobile/lib/features/chat/chat_repository.dart` | `sendMessage()` — 메시지 trim·4000자 캡, conversation 최근 24턴 컷, `request_id` 자동 생성(`mobile-chat-{micros}-{hex}`), `user_id: 'mobile-client'` 플레이스홀더(서버가 인증 주체로 덮어씀), **403 `consent_required` → `POST /me/privacy/consents/sensitive_health_analysis`(201) 후 정확히 1회 재시도** |
| `mobile/lib/screens/chat_screen.dart` | 화면 전체 + `_buildMessageExtras()`: answerability 캡션 / 출처 칩 / 승인 카드(`approval_state == 'approval_required'` 시) / CTA 칩. 승인 시 동일 메시지를 `context.analysis_run_approval = {approved: true, analysis_kind}` 로 재전송(`_approveAnalysis`) |
| `mobile/lib/app_controller.dart` | `ChatExplanationDraft`(L136), `queueSupplementExplanationForChat()`(L825 부근), `markChatExplanationDraftDelivered()`(L844) — 잔여 (e)의 as-built |
| `mobile/lib/screens/analysis_result_screen.dart` | L1533 "챗으로 설명 보내기" CTA → 드래프트 큐잉 |
| `mobile/test/chat_repository_test.dart`, `mobile/test/widget/chat_screen_test.dart` | 저장소 단위 테스트 + 드래프트 소비 위젯 테스트 |
| `backend/Nutrition-backend/src/api/v1/ai_agent.py` | `POST /ai-agent/chat`(L316~) + `POST /ai-agent/daily-coaching`. 요청/응답 스키마 `ChatbotApiRequest`/`ChatbotApiResponse` 이 파일에 정의 |
| `backend/Nutrition-backend/src/services/app_health_analysis.py` | `build_analysis_response_contract()` — 분석 블록 4종의 단일 출처 |

### 부분 구현 / 미구현 (이 문서의 작업 대상)

| 항목 | 상태 |
|---|---|
| (a) 분석 블록 인라인 렌더 | **미표시.** `ChatbotResponse` 에 파싱은 완료, `_buildMessageExtras()` 가 todayAnalysis/smartAnalysis/checklistCandidates 를 전혀 사용하지 않음 |
| (b) 출처 상세 | `_SourceChips` 는 라벨만 표시 — 탭 핸들러·`sourceUrl` 미사용 |
| (c) 대화 영속화 | `_ChatScreenState._messages`/`_history` 위젯 state 메모리. go_router `StatefulShellBranch` 라 탭 전환 간엔 유지, **앱 재시작 시 소실. 서버 대화 저장/조회 라우트 없음(백엔드 공백)** |
| 챗 화면 면책 푸터 | 챗 탭 자체엔 없음 — (a) 인라인 분석 카드에 면책 푸터 필수 부착 |
| checklist_candidates 승인 실행 | 서버에 `add_today_practice` 실행 라우트 없음 — **백엔드 공백** (아래 ⑤) |

---

## ④ 구현 단계 (잔여 작업 체크리스트)

### (a) 분석 블록 인라인 렌더 — 승인 루프 후 결과 카드

1. [ ] `mobile/lib/features/chat/chat_analysis_models.dart` 신규 — opaque map 을 typed 모델로:
   - `ChatTodayAnalysis` ← `today_analysis` (status / score(int?) / scoreName / strengths / priorityAdjustments / recommendedFoods / checklistActions / missingRecords / stale)
   - `ChatSmartAnalysis` ← `smart_analysis` (readinessLevel / coverage 4축 / nutrientPriorities / recommendedFoods / checklistActions)
   - 모든 fromJson null-safe (chat_models.dart 의 `_stringList`/`_objectMap` 헬퍼 재사용)
2. [ ] `mobile/lib/features/chat/widgets/chat_analysis_card.dart` 신규 — figma C(`620:2`)·S-09(`800:23`) 축약 레이아웃:
   - 점수: `score == null` 또는 `status == 'analysis_pending'` → 점수 날조 금지, "기록을 조금 더 채우면 분석할 수 있어요" + `missing_records` 안내 (StatusStateView 스타일 축소판)
   - 점수 있음 → 등급 칩(좋음/보통/확인 필요 — % 비노출) + 강점/우선 보완 리스트(각 ≤3줄)
   - `checklist_candidates` → "오늘 실천 후보" 칩 ≤3. `approval_state == 'approval_required'` 이고 서버 실행 라우트가 없으므로 **표시 전용 + 탭 시 해당 문구로 챗 전송**(CTA 칩과 동일 패턴). 서버 라우트 임포트(P1) 전까지 로컬 토글 저장 금지
   - 하단 면책 푸터 고정: "건강 참고용이며 의료 행위를 대신하지 않아요." (금칙어 사용 금지)
3. [ ] `chat_screen.dart` `_buildMessageExtras()` 확장:
   - 표시 조건: `response.approvalPreview.approvalState == 'approved'` (승인 루프 완료 응답) **또는** `used_tools` 에 `app_health_analysis` 포함 시 → `todayAnalysis`(analysis_kind 가 today) 혹은 `smartAnalysis` 카드 1장 렌더
   - 일반 응답의 분석 블록(매 응답에 실려 옴)은 렌더하지 않음 — 노이즈 방지, 승인 결과에만 표시
4. [ ] 위젯 테스트: 승인 → 재전송 → 카드 표시 / `analysis_pending` 폴백 / 금칙어 부재 assert

### (b) 출처 상세 시트

5. [ ] `_SourceChips` 칩에 `onTap` 추가 → `showModalBottomSheet`:
   - 내용: `title`(타이틀) / `sourceFamily`(칩) / `sourceId`(캡션) / `sourceUrl`(있을 때만, 선택·복사 가능 텍스트)
   - 외부 브라우저 열기는 `url_launcher` 의존성이 **현재 pubspec 에 없음** — P1 의존성 추가 합의 전엔 "URL 복사" (`Clipboard.setData`)만 제공
   - 하단 캡션: "검수된 출처 기반 안내예요. 참고용으로 봐주세요."
6. [ ] 위젯 테스트: 칩 탭 → 시트 표출, URL 없는 출처는 URL 행 미표시

### (c) 대화 영속화 (현황 명시 + 점진)

7. [ ] 코드 주석·본 문서에 현황 고정: **클라이언트 세션 메모리만** (StatefulShellBranch 로 탭 전환 유지, 앱 종료 시 소실). 서버는 대화 원문을 저장하지 않음 — 저장되는 것은 ① 감사 이벤트(`record_sensitive_audit_event`) ② `agent_memory`(서버측 데일리 코칭 요약 메모리 — `load_agent_memory_context`/`upsert_daily_coaching_memory`) ③ 승인된 분석 snapshot(`analysis_results`, algorithm_version `app-health-analysis-v1.0.0`) ④ 미답변 백로그(`record_unknown_knowledge_event`)
8. [ ] (P1-5 의 shared_preferences 도입 시) 마지막 N턴 로컬 캐시 복원 — 민감 대화이므로 도입 시 `flutter_secure_storage` 우선 검토, 기본은 **저장 안 함 유지**
9. [ ] 서버측 대화 저장/조회가 제품 요구가 되면 "백엔드 공백"으로 별도 발의 (`GET /ai-agent/conversations` 류 — 현재 없음, 날조 금지)

### (d) production fail-closed 운영 노트

10. [ ] 운영 문서화(본 문서 ⑥ 참조): `environment == "production"` 이고 reviewed source governance DB 미시드면 챗은 **결정론적 보수 답변**으로 폴백 (`_production_medical_source_gate`) — `answerability = unknown_no_reviewed_source`, `used_tools = ["medical_source_readiness"]`. 클라이언트는 추가 분기 불필요(기존 answerability 캡션이 그대로 동작). **데모는 dev 환경 사용** (플랜 R5)

### (e) 분석결과 → 챗 드래프트 (as-built — 변경 없음, 회귀 가드만)

11. [ ] 흐름 고정: 영양제 저장 완료 후 "챗으로 설명 보내기"(analysis_result_screen L1533) → `AppController.queueSupplementExplanationForChat()` 가 **사용자 확인 필드만**으로 `ChatExplanationDraft{id, title, userPrompt, assistantMessage}` 생성(원시 OCR·프로바이더 페이로드 제외) → 챗 탭 진입 시 `_schedulePendingDraft()` 가 1회 소비: 말풍선 2개 렌더 + `_history` 에 시드 → **다음 실 질문에 이 턴이 conversation 으로 동봉**되어 백엔드 컨텍스트로 합류 → `markChatExplanationDraftDelivered(id)` 로 소거
12. [ ] 회귀 가드: 기존 `chat_screen_test.dart` 의 드래프트 소비 테스트 유지 + (a) 카드 추가 후에도 드래프트 메시지엔 분석 카드가 붙지 않음을 assert (`_Message.text` 는 response 없음)

---

## ⑤ 엔드포인트 계약 표

> ApiClient 경로 표기: `/api/v1` 접두사 제거 (baseUrl 에 포함됨). 요청 스키마는 `extra="forbid"` — 정의 외 필드 전송 시 422.

| METHOD 경로 | 요청 핵심 필드 | 응답 핵심 필드 | 필요 동의/스코프 |
|---|---|---|---|
| `POST /ai-agent/chat` | 아래 상세 | 아래 상세 | scope `analysis:write` (`require_analysis_write`) · consent `sensitive_health_analysis` (403 `consent_required` → 동의 후 1회 재시도) |
| `POST /me/privacy/consents/sensitive_health_analysis` | (빈 바디) | 201 Created | 인증만 |
| `POST /ai-agent/daily-coaching` | `AgentInput` (06 문서 담당) | `AgentOutput` | 동일 scope/consent — 챗에서는 직접 호출하지 않음(오늘의 분석 탭 담당) |

### POST /ai-agent/chat — 요청 전체

| 필드 | 제약 | 비고 |
|---|---|---|
| `request_id` | string 1~120 | 클라이언트 생성 (`mobile-chat-{micros}-{hex}`) |
| `user_id` | string 1~120 | **서버가 인증 주체로 덮어씀** — `'mobile-client'` 고정 전송 |
| `message` | string 1~4000 | trim 후 캡 (repository 처리) |
| `conversation[]` | **≤24 턴** | `{role: 'user'\|'assistant', content: 1~4000, created_at: ISO8601 string ≤80}` |
| `context` | object | 기본 `{}`. 승인 재전송 시 `analysis_run_approval: {approved: true, analysis_kind: 'today_analysis'\|'health_analysis'}` |

### POST /ai-agent/chat — 응답 전체 (`ChatbotApiResponse`)

| 필드 | 타입 | 렌더 상태 |
|---|---|---|
| `request_id` / `message` / `provider` | string | message 말풍선 ✅ |
| `used_tools[]` / `safety_warnings[]` / `source_families[]` | string[] | 미표시(디버그성) — `used_tools` 는 (a) 표시 조건 판정에 사용 |
| `answerability` | `answerable` \| `needs_more_info` \| `unknown_no_reviewed_source` | 캡션 ✅ |
| `sources[]` | `{title, source_id, source_family, source_url}` | 칩 ✅ / 상세 시트 ← (b) |
| `requires_user_approval` | bool | 승인 카드 게이트 ✅ |
| `ctas[]` | string ≤3 | 칩 ✅ |
| `analysis_snapshot` | `{today_analysis, smart_analysis}` (아래 둘의 묶음) | **미표시** ← (a) |
| `today_analysis` | `today-analysis-snapshot-v1`: `status('analysis_pending'\|'ready_for_analysis')`, `score(int\|null)`, `score_name`, `minimum_conditions{food_records, supplement_check_required, supplement_check}`, `missing_records[]`, `stale`, `stale_reasons[]`, `strengths[]`, `priority_adjustments[]`, `recommended_foods[]`, `checklist_actions[]`, `ctas[]` | **미표시** ← (a) |
| `smart_analysis` | `health-analysis-snapshot-v1`: `readiness_level`, `coverage{food, supplement, checklist, chat_signals}`, `strengths[]`, `nutrient_priorities[]`, `recommended_foods[]`, `checklist_actions[]`, `chat_signal_stages[]`, `ctas[]` | **미표시** ← (a) |
| `checklist_candidates[]` | ≤3 × `{candidate_id, kind: 'today_practice', title, source, approval_state: 'approval_required', side_effect: 'none', deferred_action: 'add_today_practice'}` | **미표시** ← (a) |
| `approval_preview` | `approval-preview-v1`: `required`, `approval_state('approval_required'\|'approved'\|'not_required')`, `analysis_kind?`, `requested_action?`, `snapshot_preview?`, `will_persist`, `side_effects[]`, `actions[]` | 승인 카드 ✅ / `approved` + `side_effects=['analysis_result_persisted']` 분기 ← (a) |

### 승인 루프 서버 동작 (ai_agent.py `_maybe_handle_chat_analysis_run`)

1. `detect_analysis_run_intent(message)`: "분석/실행/run/analy" + "오늘/today" → `today_analysis`, + "건강/health" → `health_analysis` (둘 다 없으면 일반 챗)
2. 미승인 → `requires_user_approval=true`, `approval_preview.approval_state='approval_required'`, `snapshot_preview` 동봉, **저장 없음**
3. `context.analysis_run_approval` 승인 일치 → `analysis_results` 에 snapshot 영속(`NUTRITION_ANALYSIS` / `app-health-analysis-v1.0.0`), 응답 `approval_state='approved'`, `side_effects=['analysis_result_persisted']`, `ctas=['ask_about_this_result']`

### 백엔드 공백 (날조 금지 — 필요 시 별도 발의)

- **대화 저장/조회 라우트 없음** (예: `GET /ai-agent/conversations`) — (c)
- **`add_today_practice` 실행 라우트 없음** — checklist_candidates 는 preview-only 계약(Day 05). 후보 승인→실천 리스트 반영은 P1 `notifications.py`/체크리스트 라우트 임포트 결정 후

---

## ⑥ 상태 / 에러 처리

| 상황 | 처리 (as-built ✅ / 신규) |
|---|---|
| 빈 대화 | ✅ 인사 카드 + 추천 질문 칩 4개 (전용 StatusStateView 불필요 — 시안 동일) |
| 전송 중 | ✅ `_TypingBubble` 점 3개 + 입력바 비활성 |
| 403 `consent_required` | ✅ repository 가 동의 1회 부여 후 재시도 — 화면 분기 없음. 동의 부여 자체가 실패하면 ApiError 버블 |
| 네트워크 실패 | ✅ `dangerSoft` 에러 버블 "인터넷 연결을 확인한 뒤 다시 시도해주세요." (상태 프레임 `913:60` 워딩 결) |
| `needs_more_info` | ✅ 캡션 "조금 더 알려주시면 더 정확히 안내할 수 있어요." |
| `unknown_no_reviewed_source` (저신뢰/무근거) | ✅ 캡션 "아직 확인된 근거가 부족한 내용이에요. 참고용으로만 봐주세요." — **% 비노출 원칙 준수** |
| production 의료 소스 미시드 (fail-closed) | 서버가 결정론 보수 답변 반환(긴급 시 119·전문가 확인 안내 포함) — 클라이언트 추가 처리 불필요. **운영 노트: production 시드 전 데모는 dev 환경** |
| 분석 `analysis_pending` (점수 null) | 신규 (a): 점수 미표기 + `missing_records` 기반 "기록 보완" 안내 — 점수 날조 금지 |
| 인라인 분석 카드 | 신규 (a): 하단 면책 푸터 필수 |

---

## ⑦ 테스트 계획

| 종류 | 파일 | 내용 |
|---|---|---|
| 단위 (기존 유지) | `mobile/test/chat_repository_test.dart` | 24턴 컷·4000자 캡·403 동의 재시도 1회·request_id 유일성 |
| 단위 (신규) | `mobile/test/unit/chat_analysis_models_test.dart` | snapshot 모델 fromJson null-safe (필드 누락/타입 불일치 시 빈 값) |
| 위젯 (기존 유지) | `mobile/test/widget/chat_screen_test.dart` | 드래프트 소비 → 말풍선 2개 + history 시드 |
| 위젯 (신규) | 〃 확장 | ① 승인 카드 → 승인 → `approved` 응답 → 분석 카드 인라인 표시 ② `analysis_pending` 폴백 ③ 출처 칩 탭 → 상세 시트 ④ 일반 응답에선 분석 카드 미표시 |
| 금칙어 가드 | 모든 신규 문구 | "진단/처방/치료/효능" 부재 assert 동반 (회귀 가드 규칙) — 점수 카드·면책 푸터·시트 문구 포함 |
| % 비노출 가드 | 위젯 테스트 | 분석 카드에 `%` 문자열 부재 assert (등급 칩만) |
| 수동 E2E | — | dev 스택(uvicorn + alembic 0030~0041)에서 "오늘 분석해줘" → 승인 카드 → 실행 → 인라인 카드 → 오늘의 분석 탭에서 동일 snapshot 확인 |

검증 기준: `flutter analyze` 0건 + `flutter test` 전체 통과(170개 기준선 이상).

---

## ⑧ 플랫폼 노트

**Android (Pixel 10 Pro · Android 17, targetSdk 36)**
- dev API `http://10.0.2.2:8000` — debug 전용 cleartext 오버레이 적용 완료(`784687ce`). `release_security_config_test` 통과 유지 필수
- 입력바: 엣지투엣지 환경에서 `SafeArea(top:false)` + IME inset 동작 확인(현 구조 OK), 예측형 뒤로가기로 탭 이탈 시 StatefulShellBranch 가 대화 state 유지하는지 스모크
- 분석 카드 추가 후 긴 메시지 + 카드 조합의 ListView 성능(프레임 드랍) 확인

**iOS (iPhone 17 Pro · iOS 26.5, deployment target 15.0)**
- dev API `http://127.0.0.1:8000` (ATS `NSAllowsLocalNetworking` 확인 완료), 한국어 권한 문구·Light 고정 적용 완료(`784687ce`)
- 키보드 dismiss 인터랙티브 드래그 + 입력바 SafeArea 하단 인셋 확인
- (b) 출처 시트: 시트 내 텍스트 선택·복사 동작 iOS에서 확인 (`SelectableText` 권장)

**공통 dev 스택**: `alembic upgrade head` 1회(0030~0041) → `uvicorn src.main:app --port 8000` (PYTHONPATH 에 `ai_agent_chat/src`). LLM 미기동 시에도 결정론 답변으로 챗 데모 가능.

---

## ⑨ 완료 기준 (DoD)

- [ ] 챗에서 "오늘 분석해줘" → 승인 카드 → "분석 실행하기" → **분석 결과 카드가 채팅 인라인에 표시**되고, 같은 snapshot 이 분석 탭(`analysis_results`)에 영속됨
- [ ] 인라인 분석 카드: 점수 null 시 점수 미표기(기록 보완 안내), 등급 칩만(% 비노출), 하단 면책 푸터 존재
- [ ] checklist_candidates ≤3 표시(표시 전용 — 서버 실행 라우트 공백 문서화 유지)
- [ ] 출처 칩 탭 → 상세 시트(title/family/id/URL 복사) 동작
- [ ] 대화 영속화 현황이 코드 주석 + 본 문서에 명시(세션 메모리 / 서버 무저장 / agent_memory 는 서버측)
- [ ] 드래프트 흐름 회귀 없음: "챗으로 설명 보내기" → 챗 진입 시 1회 소비 + history 시드
- [ ] `flutter analyze` 0건 · `flutter test` 전체 통과 · 금칙어/% 비노출/면책 푸터 가드 테스트 동반
- [ ] release 네트워크 보안 테스트 통과 유지 (debug 오버레이 외 cleartext 예외 없음)
