# Hospital Chatbot 설계 (R3)

> **작성일**: 2026-04-24 (R3 착수 직전)
> **범위**: 삭제된 `triageSymptoms` (F19) 기능을 **범용 병원 안내 챗봇**으로 확장 재구현
> **백엔드**: Google AI Studio (Gemini 2.5 Flash) MVP; Ollama 로컬 LLM은 **추후 작업 예정**

---

## 1. 스코프 재정의 — F19 → Hospital Chatbot

| 축 | 기존 F19 (삭제됨) | 신규 Hospital Chatbot |
|---|---|---|
| 대화 형태 | 1-shot 증상 텍스트 | 멀티턴 대화 (대화 히스토리) |
| 기능 범위 | 진료과 추천만 | 병원 정보 Q&A + 증상 triage + 예약 안내 + 오시는 길 + 일반 대화 |
| 상태 | Stateless | RTDB `chat_sessions` 영속 |
| 컨텍스트 | 하드코드 진료과 매핑 | `/hospitals/{hid}/profile·departments·features` 동적 주입 |
| 백엔드 | OpenAI·Anthropic·Gemini 선택 | Gemini (기본) + Ollama (향후) |

## 2. 아키텍처

```
┌────────────────────────────────────────────────────────────┐
│   Patient Browser (/h/{hid}/patient/home?tab=chatbot)      │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ ChatbotWidget.tsx — 말풍선 리스트 + 입력 폼           │ │
│   │ + Quick Replies + Disclaimer 배너                    │ │
│   └──────────────────────────────────────────────────────┘ │
└─────────────────────────────┬──────────────────────────────┘
                              │ httpsCallable('hospitalChatbot')
                              ▼
┌────────────────────────────────────────────────────────────┐
│   Cloud Function: hospitalChatbot (asia-northeast3)        │
│                                                             │
│   1) Auth check (auth.uid 필수)                             │
│   2) Rate limit check (/chatbot_usage/{uid}/{hour})        │
│   3) Safety pre-check (자해/응급 키워드 + PII)               │
│   4) Context 빌드 (hospitals/{hid}/profile·departments·    │
│      features → system prompt)                             │
│   5) Intent classify (간단 규칙 → Gemini fallback)          │
│   6) Gemini API 호출 (systemInstruction + history + user)  │
│   7) Safety post-check + disclaimer 삽입                   │
│   8) chat_sessions에 messages 저장 + usage 카운트 업데이트   │
│   9) Response 반환                                          │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────┐
         │ Google AI Studio Gemini API        │
         │ https://generativelanguage.googleapis.com │
         └────────────────────────────────────┘
```

## 3. 데이터 모델 (RTDB)

```
/chat_sessions/{hospitalId}/{uid}/{chatId}
  startedAt: number
  lastActivityAt: number
  messageCount: number
  resolved: boolean
  summary: string (선택 — 추후 LLM 생성 요약)

/chat_sessions/{hospitalId}/{uid}/{chatId}/messages/{msgId}
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  meta:
    intent: 'triage' | 'hospital_info' | 'appointment_help' | 'direction' | 'general' | 'escalate'
    recommendedDepartments?: string[]  // triage intent 시
    tokensIn?: number
    tokensOut?: number
    disclaimerApplied?: boolean

/chatbot_usage/{uid}/{yyyy-mm-dd}
  hourly: { "08": 3, "09": 5, ... }
  dailyTotal: number
  lastMessageAt: number
  tokensUsedToday: number
```

## 4. Intent 분류 (7종)

| Intent | 감지 트리거 (간단 규칙) | LLM 동작 |
|---|---|---|
| `triage` | "증상", "아파요", "통증", "기침" 등 키워드 | 진료과 3개 + 신뢰도 + "진단 아님" disclaimer |
| `hospital_info` | "오시는 길", "주소", "진료 시간", "주차" | hospital profile + features 기반 답변 |
| `department_info` | "{진료과} 진료", "의사 선생님" | departments 리스트 조회 |
| `appointment_help` | "예약", "접수" | "외래 탭으로 이동해 주세요" + 링크 |
| `direction` | "응급실 어디", "화장실 위치" | pois 참조 (추후 RAG) |
| `general` | 인사·잡담 | 친절한 안내 + 도움 유도 |
| `escalate` | 자해·응급 위험 신호 (자살·가슴통증·호흡곤란) | 119 + 응급실 + 1393 고정 응답, LLM 미사용 |

## 5. Cloud Function 파일 구조

```
functions/src/chatbot/
├── hospitalChatbot.ts       — onCall 진입점
├── providers/
│   ├── gemini.ts            — Google AI Studio REST 클라이언트
│   └── shared.ts            — 공통 타입 (Message, Response)
├── intent.ts                — 규칙 기반 감지 + LLM fallback
├── context.ts               — hospital RTDB → system prompt 빌더
├── safety.ts                — 응급/자해/PII 감지 + disclaimer 주입
├── rateLimit.ts             — /chatbot_usage 체크·증가
└── __tests__/
    ├── intent.test.ts
    ├── safety.test.ts
    ├── context.test.ts
    └── hospitalChatbot.test.ts
```

## 6. API 계약

### Request (frontend → `hospitalChatbot`)
```typescript
{
  chatId?: string;   // 새 대화면 미전송 → 서버가 생성
  hospitalId: string; // 현재 context 병원
  userText: string;   // 사용자 입력 (최대 1000자)
}
```

### Response
```typescript
{
  chatId: string;          // 신규/기존 대화 식별자
  messageId: string;       // assistant 응답 메시지 ID
  reply: string;           // 본문
  intent: IntentKind;
  recommendedDepartments?: string[];
  disclaimer: string;      // 항상 포함
  rateLimit: {
    remainingHour: number;
    remainingDay: number;
  };
}
```

## 7. Rate Limit 정책

| 레이어 | 한도 | 메시지 |
|---|---|---|
| 유저 × 시간 | 20 messages | `resource-exhausted` — "잠시 후 다시 시도해 주세요" |
| 유저 × 일 | 100 messages | `resource-exhausted` — "오늘은 이용 한도를 초과했어요" |
| 입력 길이 | 1,000자 | `invalid-argument` — "질문이 너무 깁니다" |
| 출력 토큰 | 512 tokens (Gemini config) | 응답 잘림 경고 추가 |
| 월 예상 비용 | 1K 유저 × 100회 × 200토큰 = 20M tokens ≈ **$1.5/월** | (Gemini 2.5 Flash 기준) |

## 8. Safety 가드레일

### 8.1 응급 키워드 즉시 응답 (LLM 미사용)
```
가슴통증 | 호흡곤란 | 의식저하 | 대량출혈 | 자살 | 자해 | 숨을 못 쉬
→ "🚨 응급 증상이 의심됩니다. 즉시 119에 전화하거나 응급실로 오세요.
    정신건강 위기 상담: 1393 (24시간)
    본 대화는 의학적 진단이 아닙니다."
```

### 8.2 모든 assistant 응답에 Disclaimer 강제 삽입
```
본 답변은 진단이 아니며 최종 판단은 의료진이 합니다.
```

### 8.3 PII 거부 패턴
- 주민등록번호 (13자리 숫자·하이픈), 전화번호, 본인확인번호 요청 → 거부

### 8.4 법무 게이트
- 확정 진단·약물 용량·처방 문의 → "의료진 상담 필요" 안내
- 원격진료 경계 (의사법) → 진료 행위로 간주되지 않도록 "안내" 범주 유지

## 9. Gemini Prompt 템플릿

### System Instruction (컨텍스트 주입)
```
당신은 "{hospitalName}" 안내 챗봇입니다.
본 병원 정보를 근거로 친절하게 답변하되, 아래 제약을 엄수하세요.

[병원 프로필]
- 이름: {profile.name}
- 주소: {profile.address ?? '미등록'}
- 연락처: {profile.phone ?? '미등록'}
- 활성 기능: {Object.keys(features).filter(k => features[k]).join(', ')}

[진료과]
{departments.map(d => `- ${d.name} (${d.code})`).join('\n')}

[답변 스타일]
- 한국어, 존댓말, 3~5문장 이내
- 증상 질문엔 진료과 3개 추천 + 신뢰도 + disclaimer 필수
- 진단·처방·약물 용량은 답변 금지 → "의료진 상담" 안내
- 예약 요청: "외래 탭에서 직접 예약해 주세요" 유도
- 응급 의심 증상은 즉시 119·응급실 안내

[금지]
- 주민번호·계좌 등 개인정보 요청 X
- 환자 특정 이름·병명 추측 X
- 다른 병원 추천 X
```

### History 형식 (Gemini contents)
```typescript
contents: [
  { role: 'user', parts: [{ text: '내과 진료 시간 알려줘' }] },
  { role: 'model', parts: [{ text: '저희 내과 진료 시간은...' }] },
  ...최근 10개 turn
  { role: 'user', parts: [{ text: <userText 현재 입력> }] },
]
```

## 10. Frontend UI 컴포넌트 (R3.4)

### 10.1 Widget 구조
```
<ChatbotWidget>
  <ChatbotHeader title="{hospitalName} 안내 챗봇" onClose={...} />
  <DisclaimerBadge>
    본 대화는 진단이 아닙니다. 응급 시 119.
  </DisclaimerBadge>
  <MessageList>
    {messages.map(m => <Message role={m.role} content={m.content} />)}
  </MessageList>
  <QuickReplies options={['진료과 추천', '오시는 길', '예약 방법']} />
  <InputForm maxLength={1000} onSubmit={sendMessage} />
</ChatbotWidget>
```

### 10.2 진입점
- HomePage 플로팅 버튼 (우하단)
- 더보기 탭 → "챗봇 상담"
- 고령자 모드: 큰 버튼·폰트 확대

### 10.3 UX 규칙
- Optimistic UI (user 메시지 즉시 표시 + loading skeleton)
- 500자 넘으면 경고 표시
- Rate limit 초과 시 remainingTime 배너
- 응급 intent 응답 시 빨간 테마로 전환 + 119 버튼

## 11. 배포 단계

### R3.1 — Gemini MVP Backend (1일)
- `providers/gemini.ts` — Gemini API 호출
- `hospitalChatbot.ts` onCall — stateless 버전 (context, history X)
- 하드코드 system prompt로 시작
- `functions/.env` 에 `GEMINI_API_KEY` 추가
- 단순 frontend에서 호출 테스트

### R3.2 — Hospital Context 주입 (0.5일)
- `context.ts` — hospital profile/departments 읽어 system prompt 동적 생성
- Cache (같은 hospitalId 5분 memoize)

### R3.3 — 멀티턴 영속성 (1일)
- `chat_sessions/{hid}/{uid}/{chatId}` 스키마 구현
- 히스토리 주입 (최근 10 turn)
- Rules 추가: chat_sessions 본인만 R/W, platformAdmin R
- chat 삭제 플로우 (userSoftDelete 연동)

### R3.4 — Frontend Widget (1~2일)
- `ChatbotWidget` + `MessageList` + `QuickReplies`
- Zustand chatStore
- Error handling + retry
- 모바일 반응형

### R3.5 — Safety + Rate Limit (0.5일)
- `safety.ts` — 응급·자해·PII 감지
- `rateLimit.ts` — `/chatbot_usage` 카운트
- Audit log 통합

### R3.6 — 테스트 + 배포
- Vitest: intent, safety, rateLimit, chatbot handler
- E2E: `public/e2e-chatbot.html`
- `firebase deploy --only functions:hospitalChatbot`

## 12. Rules (R3 시 추가)

```json
"chat_sessions": {
  "$hospitalId": {
    "$uid": {
      ".read": "auth != null && (auth.uid === $uid || auth.token.role === 'platformAdmin')",
      ".write": "auth != null && (auth.uid === $uid || auth.token.role === 'platformAdmin')"
    }
  }
},
"chatbot_usage": {
  "$uid": {
    ".read": "auth != null && (auth.uid === $uid || auth.token.role === 'platformAdmin')",
    ".write": "auth != null && auth.uid === $uid"
  }
}
```

## 13. 향후 확장 (R3.7+)

| 항목 | 설명 | 시점 |
|---|---|---|
| RAG | 병원 FAQ·규정 임베딩 + 검색 | P3 후반 |
| Streaming | Gemini SSE 스트리밍 응답 → 체감 지연 ↓ | R3.4 후 |
| Ollama 로컬 | `providers/ollama.ts` — 환경변수 switch | 사용자 요청 시 |
| Voice I/O | STT (Web Speech API) + TTS — 고령자용 | P4 TTS와 병행 |
| 예약 실행 | Chatbot → `/hospitals/{hid}/appointments` 직접 write | 권한·흐름 검토 후 |

## 14. 결정 완료 / 보류

### 결정됨
- ✅ Gemini 2.5 Flash 기본 백엔드
- ✅ `.env`에 `GEMINI_API_KEY` 직접 입력 (MVP)
- ✅ Ollama 추후 작업
- ✅ 대화 영속 `/chat_sessions/{hid}/{uid}/{chatId}`
- ✅ 한국어 존댓말, disclaimer 필수

### 보류
- Intent 분류: 규칙 우선 vs LLM 분류 일원화 → R3.1에서 규칙 우선으로 착수, 정확도 낮으면 R3.2에서 LLM 보조
- 대화 보존 기간: PIPA 고려해 기본 30일 + 유저 요청 시 즉시 삭제 (R3.3 실장 시 확정)
- 고령자 모드 특화 (큰 버튼·음성) → R3.4 확장으로 분리
