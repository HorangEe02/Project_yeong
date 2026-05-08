# Day 5++ — C 도우미 HUD Command Center 폴리싱 (디자인 시스템 v2 적용)

> **작성일**: 2026-04-27 (Day 5+ Firebase Auth 통합 완료 직후)
> **선행**: Day 4 채팅 UI + Day 5 Phase 1~5 + Firebase Auth 통합 (현재 Firestore/RTDB/Storage 동작)
> **대상**: 첨부 시안 그대로의 **HUD Command Center 레이아웃** + v2 디자인 시스템 적용
> **목표 시간**: 1.5~2시간
> **본선까지**: 13 작업일 남음

---

## 목차

1. [목적 + 요구사항](#1-목적--요구사항)
2. [v2 디자인 시스템 분석](#2-v2-디자인-시스템-분석)
3. [첨부 시안 컴포넌트 트리 분해](#3-첨부-시안-컴포넌트-트리-분해)
4. [3-Panel 레이아웃 사양](#4-3-panel-레이아웃-사양)
5. [SOPSidePanel 3-탭 갱신](#5-sopsidepanel-3-탭-갱신)
6. [AI 메시지 헤더 + 메타 footer](#6-ai-메시지-헤더--메타-footer)
7. [세션 ID + LIVE 배지](#7-세션-id--live-배지)
8. [RightPanel SYSTEM ANALYTICS + DATA INGESTION](#8-rightpanel-system-analytics--data-ingestion)
9. [v2 토큰 통합 (colors_and_type.css)](#9-v2-토큰-통합-colors_and_typecss)
10. [i18n 신규 키](#10-i18n-신규-키)
11. [파일 구조](#11-파일-구조)
12. [단계 분할 — Phase 1~3](#12-단계-분할--phase-13)
13. [검증 체크리스트](#13-검증-체크리스트)
14. [위험 + 완화](#14-위험--완화)
15. [Day 5++ 비스코프](#15-day-5-비스코프)
16. [시간 분배표](#16-시간-분배표)
17. [사용자 결정 대기](#17-사용자-결정-대기)

---

## 1. 목적 + 요구사항

### 1-1. 목표
첨부 시안의 **HUD Command Center Dashboard** 디자인을 `/chat` 라우트에 그대로 구현. v2 디자인 시스템(`uiux/AJIN AI Assistant Design System_v2/`)의 토큰·패턴·Liquid Glass 사양을 React 컴포넌트로 매핑.

### 1-2. 비즈니스 요구사항

| # | 요구사항 | 근거 |
|:--:|---|---|
| 1 | 3-Panel HUD 셸 (좌 SOP·중 CHAT·우 ANALYTICS) | v2 README L98 + 시안 |
| 2 | 좌측 SOP 8 / 협업 5 / 퀴즈 3-탭 | 시안 + C-2-3,4,5 사양 |
| 3 | 세션 ID `#A47-2026` + ● LIVE 배지 | 시안 + v2 글리프 정책 |
| 4 | AI 메시지 헤더 — `AI [SOP_GUIDE] 신뢰도 ─ Xms HH:MM` | 시안 + v2 `[AUTH] OK` 패턴 |
| 5 | 메시지 footer 메타 — `토큰 X/Y · 컨텍스트 N턴 · 모델 M · 의도 분류 Xms` | 시안 |
| 6 | 우측 SYSTEM ANALYTICS — GPU 게이지 + LATENCY/QPS 카드 + DATA INGESTION 5종 | 시안 + v2 메트릭 패턴 |
| 7 | v2 디자인 토큰 (colors_and_type.css) 통합 검증 + 갱신 | v2 단일 진실 출처 |
| 8 | 이중 언어 라벨 강화 (`SYSTEM REGISTRY · 시스템 등록 현황`) | v2 README L62-64 |

### 1-3. 비기능 요구사항

| 항목 | 목표 |
|---|---|
| 첫 paint (FCP) | <500ms — 좌·우 패널 lazy mount 또는 즉시 |
| GPU 게이지 / DATA INGESTION 갱신 주기 | 5초 (mock) — 본선 시연 시 살아있는 느낌 |
| TS strict | 0 오류 |
| 모바일 < 768px | 우측 패널 자동 숨김 ([SYS] 토글), 좌측 SOP는 Drawer로 |
| 라이트/다크/AUTO 테마 | v2 토큰 기준 모두 정상 |

### 1-4. 비범위
- ❌ 퀴즈 탭 본격 콘텐츠 (단순 placeholder만 — C-2-5 본격은 Day 13)
- ❌ TF-IDF intent 분류기 실 동작 (mock `의도 분류 5ms` 표시만 — Day 13)
- ❌ DATA INGESTION 실 백엔드 카운트 (mock — Day 6/10/13에 실연동)
- ❌ GPU 실 측정 (mock — Day 6 F 설비 ML 엔진과 통합 시 실 데이터)
- ❌ 부서 라우터 31종 UI (Day 11)
- ❌ 용어집 매처 297항목 UI 하이라이트 (Day 12)

---

## 2. v2 디자인 시스템 분석

### 2-1. 핵심 사양 (uiux/.../v2/README.md 정독 결과)

| 영역 | 사양 |
|---|---|
| 컬러 | 60/30/10 — 베이지 60% (`#FAF8F5`) + 뉴트럴 30% (`#F0EBE3`) + AJIN 골드 10% (`#D89400` 라이트, `#FCB132` 다크) |
| 타이포 | Pretendard + Noto Sans KR 폴백 (단일 패밀리), 12→36 2px 스텝, weight 400/600/700 |
| Letter-spacing | 영문 라벨에만 0.08~0.1em, 한글 0 |
| 코너 | 2px 모든 곳 (8/12px 절대 X) |
| 보더 | 1px 헤어라인, 점선은 메모리/구분 zone |
| 그림자 | 라이트 모드 X, 다크 모드만 골드 글로우 (CTA/active만) |
| Liquid Glass | 상단 / 우측 패널 / 모달 / chat composer 한정 |
| 글리프 | `●` ON/OK, `○` OFF, `▣` active module, `▢` inactive, `─ ─` 구분 |
| 이모지 | 절대 X (피드백 👍/👎는 functional이라 v2 검토 필요 — `▲▼` 또는 `+/-` 대체 권장) |
| 라벨 패턴 | `ENGLISH UPPERCASE` + `한글 부제` 페어 |

### 2-2. 시안 ↔ v2 매칭 (15건 모두 ✅)

| 시안 요소 | v2 사양 | 평가 |
|---|---|:--:|
| 3-Column 셸 | README L98 | ✅ |
| AJIN INDUSTRY + AI ASSISTANT | EN+KO 페어 | ✅ |
| 60/30/10 컬러 | README L88-93 | ✅ |
| 2px 코너 + 1px 보더 | README L102-104 | ✅ |
| Liquid Glass (상단/우측/composer) | README L112-124 | ✅ |
| ● LIVE 배지 | 글리프 정책 | ✅ |
| 세션 ID `#A47-2026` | versioning 패턴 (v3.5 // KNU) | ✅ |
| `[SOP_GUIDE]` AI 라벨 | `[AUTH] OK` 패턴 | ✅ |
| 메트릭 카드 | README L67 (`지연시간 124ms`, `QPS 8.4k`) | ✅ |
| Letter-spacing 영문 | README L64 | ✅ |
| 공백 sub-text 패턴 | README L62-64 | ✅ |
| 점선 구분 zone | `─ ─ ─` 글리프 | ✅ |
| GPU 42% 게이지 | README L67 (`42% GPU`) | ✅ |
| 다운로드 ↓ 화살표 글리프 | 영문 라벨 | ✅ |
| `LIVE` / `JWT_ACTIVE` 상태 키워드 | README L68 | ✅ |

**결론**: v2가 시안의 모든 시각 요소를 사양으로 보유. 100% 토큰 기반 구현 가능.

### 2-3. 이모지 정책 충돌 — 👍/👎

v2의 "No emoji anywhere" 정책 vs 현재 Day 5의 FeedbackActions (👍/👎). 시안에도 `👍 👎` 사용. **결정안**: 시안이 골격이므로 v2 정책 부분 예외 — `👍/👎`만 유지 (functional, button 안에서만). Bug fix는 `▲/▼` 또는 `↑/↓` 글리프로 대체할 수도. **권장**: 시안 그대로 유지(사용자 결정 항목 #2).

---

## 3. 첨부 시안 컴포넌트 트리 분해

```
<HUDChatPage>                              /* /chat 라우트 */
├── <TopBar />                            아진산업 AIv3.5 | 환경 ON-PREMISE | JWT_ACTIVE | LLM QWEN 3.5 ●
│                                         RBAC L6·ADMIN [HIDE] [LOGOUT]
│
├── <LeftSidebar>                         240px
│   ├── <BrandHeader />                   AJIN INDUSTRY / AI ASSISTANT / v3.5 // KNU SILLI 2026
│   ├── <UserCard />                      김아진 / KIM A.J. / 품질보증팀·L6 ADMIN [PROFILE][LOGOUT]
│   ├── <NavItem code="DASHBOARD" />      대시보드
│   ├── <ThemeSelector />                 [LIGHT][DARK][AUTO]
│   ├── <CoreModulesGroup>                CORE MODULES · 핵심 모듈
│   │   ├── A. 인원검색
│   │   ├── B. 문서 작성
│   │   ├── C. AI 도우미        ← active (▣ + 골드 인디케이터)
│   │   ├── D. 법규 모니터
│   │   ├── E. 인사 관리
│   │   └── F. 설비 AI
│   └── <SystemRegistry>                  SYSTEM REGISTRY · 시스템 등록
│       ├── [DEPT] 29/29 ●
│       └── [ACCT] 33/33 ●
│
├── <CenterContent>                       flex
│   ├── <SOPSidePanel>                   320px (시안 좌측 카드)
│   │   ├── <Tabs>                       [SOP 8][협업 5][퀴즈]
│   │   ├── <SOPHeader />                SOP · 프레스 트라이 / Step 1/7 (진행률 바)
│   │   ├── <SOPStepCard />              Step 1 — 금형 점검 / 체크리스트 / 주의 (▲)
│   │   ├── <StepNav />                  ◀이전 [다음▶] [퀴즈]
│   │   └── <SOPList />                  SOP 8종 (01~08)
│   │
│   └── <ChatStream>                     flex (시안 중앙 큰 카드)
│       ├── <ChatHeader />               CHAT · 생산기술팀-교육 / 세션 #A47-2026 [● LIVE]
│       ├── <MessageList>
│       │   ├── <UserMessage />          "프레스 트라이 SOP 알려줘" (golden bubble)
│       │   └── <AIMessage>
│       │       ├── <AILabel />          AI [SOP_GUIDE] 신뢰도 ─ Xms HH:MM
│       │       ├── <Markdown />         프레스 트라이 SOP를 단계별로 안내합니다...
│       │       ├── <DownloadActions />  ↓DOCX ↓XLSX ↓CSV ↓TXT
│       │       └── <FeedbackActions />  👍 👎
│       ├── <MessageMetaFooter />        토큰 420/3,000 · 컨텍스트 6턴 · 모델 QWEN-3.5 · 의도 분류 5ms
│       └── <InputComposer />            [📎] 질문을 입력하세요... (PDF/...) [전송 ↑]
│
└── <RightPanel>                          280px (Liquid Glass)
    ├── <Header />                       SYSTEM ANALYTICS · 시스템 분석 · REALTIME ●
    ├── <GPUGauge />                     원형 게이지 42% · GPU UTILIZATION
    ├── <MetricCardGroup>
    │   ├── LATENCY 124ms
    │   └── QPS 8.4k
    └── <DataIngestion>                  DATA INGESTION · 데이터 수집
        ├── ERROR_CODES   201/201
        ├── MOLD_ASSETS    25/25
        ├── SPC_PROCESS     5/5
        ├── DRAWINGS     418/418
        └── INSPECTIONS   64/72
```

---

## 4. 3-Panel 레이아웃 사양

### 4-1. 그리드 (CSS Grid)

> **사용자 정책 갱신 (v1.1)**: 좌측 컬럼(`sop` area)을 **상하 50/50 분할** — 상단 SOPSidePanel + 하단 QuickPrompts. 중앙 채팅 영역이 자연스럽게 두드러지도록 좌측 컬럼은 **300px** 로 약간 줄임.

```css
.hud-chat {
  display: grid;
  grid-template-columns: 240px 300px minmax(0, 1fr) 280px;
  grid-template-rows: 52px 1fr;
  grid-template-areas:
    "topbar topbar topbar topbar"
    "sidebar sop chat analytics";
  height: 100vh;
}

/* 좌측 컬럼 내부 — 상하 50/50 분할 */
.hud-chat__sop-column {
  grid-area: sop;
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 12px;
  min-height: 0;  /* overflow 허용 */
}
.hud-chat__sop-column > * { min-height: 0; overflow: auto; }

@media (max-width: 1280px) {
  .hud-chat { grid-template-columns: 240px 280px 1fr; }
  .hud-chat .right-panel { display: none; }  /* [SYS] 토글로 표시 */
}

@media (max-width: 1024px) {
  .hud-chat { grid-template-columns: 240px 1fr; }
  .hud-chat .sop-panel { /* Drawer로 변환 */ }
}

@media (max-width: 768px) {
  .hud-chat { grid-template-columns: 1fr; }
  /* 모든 사이드 패널 Drawer/오버레이 */
}
```

### 4-2. 패널 토글 (사용자 정책)

- 우측 ANALYTICS 패널: TopBar `[HIDE]` 클릭 → `useUIStore.rightPanelVisible` 토글
- 좌측 SOP 패널: SOP 첫 항목 카드의 `[펼침/접힘]` 토글 (시안 패턴) — 또는 항상 표시 (시안 기본)
- TopBar 의 `[HIDE]` 는 시안 그대로 우측만 적용

### 4-3. CSS 클래스 명명 (BEM-lite)

- `.hud-chat`, `.hud-chat__topbar`, `.hud-chat__sidebar`, `.hud-chat__sop`, `.hud-chat__chat`, `.hud-chat__analytics`
- 또는 기존 Day 1 셸 (`page`, `page-h`, `metric-card`)과 호환되도록 alias

---

## 5. SOPSidePanel 3-탭 갱신

### 5-1. 탭 사양

```tsx
<Tabs activeId={tab} onChange={setTab}>
  <Tab id="sop" label="SOP 8" badge="8" />
  <Tab id="collab" label="협업 5" badge="5" />
  <Tab id="quiz" label="퀴즈" badge={quizCount || 0} />
</Tabs>
```

기존 Day 5 의 SOPSidePanel(80줄) → 3-탭 갱신 (~120줄로).

### 5-2. SOP 탭 (Day 5 자산 재사용 + 시안 패턴 일치)

- `SOPHeader`: `SOP · {currentSopTitle}` + Step Indicator (`Step 1/7` + 진행률 바)
- `SOPStepCard`: 현재 단계 본문 + 체크리스트 + 주의(▲ 글리프) — Day 5 SOPStepDrawer 의 Step 카드 분리
- `StepNav`: `◀이전`, `다음▶`(골드 CTA), `퀴즈` 인라인
- `SOPList`: 01~08 8종 목록 — 클릭 시 currentSopId 변경

기존 Day 5 의 `SOPStepDrawer` 는 Drawer 패턴으로 모달이었지만, 시안은 **inline 패널**. 전환 필요. Drawer 컴포넌트는 그대로 두되 SOP 진입은 inline 으로 변경.

### 5-3. 협업 5 탭

`features/onboarding/collaboration_guide.py` 의 5종 시나리오 메타 카드:
- 카드 5개: 8D Report / ECN / SPC / PPAP / 안전점검
- 카드 클릭 → "이 시나리오로 챗 시작" → InputComposer 자동 입력 → 시나리오 매처 발동 (Day 5 Phase 2 기능)

신규 `<ScenarioPanel />` (~80줄) — Day 5의 ScenarioCard 컴포넌트 재사용.

### 5-4. 퀴즈 탭 (placeholder)

- 시안 그대로 탭 자체는 표시
- 콘텐츠는 `<EmptyState>` — "SOP 학습을 마치면 자동으로 출제됩니다 / Quiz auto-generated after SOP completion"
- 본격 구현은 Day 13 (C-2-5 본 작업)

---

## 5-bis. QuickPrompts 패널 (좌측 컬럼 하단 50%)

### 5-bis-1. 목적
SOPSidePanel(상단) 과 별개로 **자주 쓰는 질문 chip 모음** 을 좌측 하단에 노출. 사용자가 챗 창을 봐도 즉시 시작점이 보임 → 시연 시 흐름 자연스러움 + 본선 평가 #1(시나리오 매처) 부각.

### 5-bis-2. 컴포넌트 사양 — `<QuickPrompts />`

```tsx
interface QuickPrompt {
  id: string;
  label: string;          // chip 본문 (한글)
  category: 'scenario' | 'action' | 'sop' | 'general';
  promptText: string;     // 입력창에 채워질 실제 텍스트
  autoSend?: boolean;     // 즉시 전송 vs 입력만 (기본: true — 시연 가속)
}
```

기본 chips (~7개, 협업 시나리오 + 액션 라우터 대표):
| label | category | promptText |
|---|---|---|
| 8D Report 양식 어디? | scenario | 품질팀에서 8D 올려달라는데? |
| ECN 발행 절차 | scenario | 설계 변경 요청 왔어 |
| SPC Cpk 떨어짐 시정 | scenario | Cpk 1.0 떨어졌어 |
| 신차 PPAP 절차 | scenario | 현대 신차 양산 시작 |
| 안전 점검 체크리스트 | scenario | 안전 점검 어떻게 해? |
| REACH 규제 현황 | action | REACH 규제 현황? |
| 에러코드 E001 | action | 에러코드 E001 |

### 5-bis-3. UI 사양 (시안 패턴)

```
┌──────────────────────────────────┐
│ QUICK · 빠른 질문                 │
│ ───                                │
│ ┌─────────────────┐ ┌──────────┐ │
│ │ 8D Report 양식  │ │ ECN 발행 │ │
│ └─────────────────┘ └──────────┘ │
│ ┌─────────────────────┐          │
│ │ SPC Cpk 떨어짐 시정 │          │
│ └─────────────────────┘          │
│ ...                                │
└──────────────────────────────────┘
```

- 헤더: `QUICK · 빠른 질문` (EN+KO 페어)
- chip: GlassPanel + 2px radius + 골드 hover
- flex-wrap, gap 8px
- 클릭 → `useChatStore.sendMessage(promptText)` 자동 호출 (시나리오 매처 → LLM 0회 즉시 응답 시연)

### 5-bis-4. 콘텐츠 출처

- 기본 7 chips 는 **하드코딩 (frontend/src/types/chat.ts 의 `DEFAULT_QUICK_PROMPTS` 상수)**
- 향후 사용자별 자주 쓰는 prompt 는 Day 11 또는 Day 12 에서 Firestore 영구화 (비스코프)

### 5-bis-5. 빈 상태 처리

- chips 항상 표시 (시연용)
- 사용자 정의 prompt 추가 기능은 Day 12 비스코프

---

## 6. AI 메시지 헤더 + 메타 footer

### 6-1. AI 메시지 헤더 사양

```tsx
<div className="ai-message-header">
  <span className="label-en">AI</span>
  <span className="badge bracket">[SOP_GUIDE]</span>
  <span className="dim">신뢰도</span>
  <span className="separator">─</span>
  <span className="dim">{ttftMs}ms</span>
  <span className="dim">{HH}:{MM}</span>
</div>
```

CSS:
```css
.ai-message-header {
  display: flex; gap: 8px; align-items: center;
  font-size: 12px; letter-spacing: 0.06em;
}
.badge.bracket { color: var(--hud-primary); font-weight: 600; }
```

`badge` 종류:
- `[SOP_GUIDE]` — SOP 응답
- `[CHAT]` — 일반 챗
- `[SCENARIO]` — 시나리오 카드
- `[ACTION]` — 액션 응답
- `[VISION]` — 비전 응답

`message.meta` 에 `category` 필드 추가 (현재 `provider`, `model` 만).

### 6-2. 메시지 footer 메타

```tsx
<div className="message-meta-footer">
  <span>토큰 {tokens}/{tokenBudget}</span>
  <span>·</span>
  <span>컨텍스트 {historyTurns}턴</span>
  <span>·</span>
  <span>모델 {modelLabel}</span>
  <span>·</span>
  <span>의도 분류 {intentMs}ms</span>
</div>
```

데이터 출처:
- `tokens` — Gemini SDK `usage_metadata.total_token_count` 또는 mock
- `tokenBudget` — `mode === 'education' ? 3000 : 2000`
- `historyTurns` — `useChatStore.messages.length / 2`
- `modelLabel` — `useChatStore.lastMeta.model` (예: `QWEN-3.5`, `GEMINI-2.5-PRO`)
- `intentMs` — mock 5ms 표시 (Day 13에 실 TF-IDF 분류기 연결)

### 6-3. v2 라벨 패턴 일관성

- 영문 라벨: `LATENCY`, `QPS`, `GPU UTILIZATION`, `LIVE`, `SOP_GUIDE` — letter-spacing 0.08em
- 한글 부제: `· 시스템 분석`, `· 데이터 수집`, `· 핵심 모듈` — letter-spacing 0
- 페어 패턴: `<span class="label-en">SYSTEM ANALYTICS</span> <span class="label-ko">시스템 분석</span>`

---

## 7. 세션 ID + LIVE 배지

### 7-1. 세션 ID 생성

```typescript
function generateSessionId(): string {
  const year = new Date().getFullYear();
  const seq = Math.floor(Math.random() * 999) + 1;  // 1~999
  const padded = String(seq).padStart(2, '0');
  return `#A${padded}-${year}`;  // #A47-2026
}
```

`useChatStore.sessionId` 필드 추가 — 페이지 진입 시 1회 생성, 리프레시 시 새 세션.

### 7-2. LIVE 배지

```tsx
<div className="session-badge">
  <span className="dot dot-pulse" />
  <span>LIVE</span>
</div>
```

CSS:
```css
.dot-pulse {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--success);
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

스트리밍 중에만 LIVE, idle 시 `IDLE` (회색).

---

## 8. RightPanel SYSTEM ANALYTICS + DATA INGESTION

### 8-1. 기존 RightPanel 활용 vs 신규

`frontend/src/components/shell/RightPanel.tsx` Day 1에 작성. 현재 dashboard.tsx 에서 사용 중. 시안의 chat 페이지 우측 패널은 같은 컴포넌트 + 콘텐츠 모드 분기.

### 8-2. 콘텐츠 모드

```typescript
type RightPanelMode = 'analytics' | 'minimal' | 'chat-context';

<RightPanel mode="analytics" />  // 시안 그대로
```

`analytics` 모드 컴포넌트:
- `<GPUGauge value={42} />` — 원형 progress (SVG circle)
- `<MetricCard label="LATENCY" value="124ms" />` (Day 1~3 메트릭 카드 재사용)
- `<MetricCard label="QPS" value="8.4k" />`
- `<DataIngestionList items={[...]} />`

### 8-3. mock 데이터 출처

신규 `frontend/src/api/analytics.ts` (~60줄) — mock 우선:
```typescript
export interface SystemAnalytics {
  gpu_pct: number;
  latency_ms: number;
  qps: number;
  ingestion: { label: string; current: number; total: number }[];
}

export async function fetchSystemAnalytics(): Promise<SystemAnalytics> {
  // 1차: 백엔드 /api/system/analytics (없으면 fallback)
  // 2차: mock — Day 2 시드 + 살짝 흔들리는 값 (시각 효과)
  return {
    gpu_pct: 38 + Math.random() * 8,           // 38~46
    latency_ms: 100 + Math.random() * 50,      // 100~150
    qps: 7000 + Math.random() * 3000,          // 7~10k
    ingestion: [
      { label: 'ERROR_CODES', current: 201, total: 201 },
      { label: 'MOLD_ASSETS', current: 25, total: 25 },
      { label: 'SPC_PROCESS', current: 5, total: 5 },
      { label: 'DRAWINGS', current: 418, total: 418 },
      { label: 'INSPECTIONS', current: 64, total: 72 },
    ],
  };
}
```

5초 폴링 (`setInterval`) + AbortController 으로 unmount 시 정리. `useEffect` + `useState` 또는 `useSWR`-like 단순 패턴.

### 8-4. GPU Gauge SVG

```tsx
function GPUGauge({ value }: { value: number }) {
  const C = 2 * Math.PI * 56;
  const offset = C * (1 - value / 100);
  return (
    <svg width="160" height="160" viewBox="0 0 160 160">
      <circle cx="80" cy="80" r="56" fill="none" stroke="var(--hud-border)" strokeWidth="8" />
      <circle
        cx="80" cy="80" r="56" fill="none"
        stroke="var(--hud-primary)" strokeWidth="8"
        strokeDasharray={C} strokeDashoffset={offset}
        transform="rotate(-90 80 80)"
        style={{ transition: 'stroke-dashoffset 0.5s ease-out' }}
      />
      <text x="80" y="80" textAnchor="middle" dominantBaseline="central" fontSize="32" fontWeight="700">
        {Math.round(value)}%
      </text>
      <text x="80" y="110" textAnchor="middle" fontSize="10" letterSpacing="0.1em" fill="var(--hud-text-dim)">
        GPU · UTILIZATION
      </text>
    </svg>
  );
}
```

---

## 9. v2 토큰 통합 (colors_and_type.css)

### 9-1. 비교

기존 Day 1: `frontend/src/styles/tokens.css` (246줄) — Day 1 빠르게 이식.
v2: `uiux/AJIN AI Assistant Design System_v2/colors_and_type.css` — 단일 진실 출처.

Phase 1에서 두 파일 직접 비교 후 차이점만 반영. 절대 v2 전체를 그대로 덮어쓰기 X (Day 1~5 의 다른 컴포넌트 의존성 깨짐 위험).

### 9-2. 우선순위
- 컬러 변수 (`--hud-primary`, `--hud-bg`, `--hud-border` 등) — 일관성 검증 + v2 기준으로 갱신
- Glass 변수 (`backdrop-filter`, `mix-blend`) — v2 의 Liquid Glass 레시피 적용
- letter-spacing 변수 추가 (`--ls-en: 0.08em`)
- glow 변수 (다크 모드) — `--hud-primary-glow`

### 9-3. 신규 변수

```css
/* tokens.css 추가 */
--ls-en: 0.08em;       /* 영문 라벨 letter-spacing */
--ls-en-tight: 0.06em; /* 작은 영문 (메타 라인) */
--hud-primary-glow: 0 0 10px #FCB13244, 0 0 20px #FCB13222;
--glass-blur: blur(24px) saturate(140%);
--glass-bg: color-mix(in oklab, var(--hud-surface) 55%, transparent);
--glass-border: 1px solid color-mix(in oklab, var(--hud-border) 65%, transparent);
```

---

## 10. i18n 신규 키

| Key | 한 | 영 |
|---|---|---|
| `chat.session.live` | LIVE | LIVE |
| `chat.session.idle` | IDLE | IDLE |
| `chat.session.id` | 세션 #{{id}} | Session #{{id}} |
| `chat.tabs.sop` | SOP {{n}} | SOP {{n}} |
| `chat.tabs.collab` | 협업 {{n}} | Collab {{n}} |
| `chat.tabs.quiz` | 퀴즈 | Quiz |
| `chat.tabs.quiz.empty` | SOP 학습을 마치면 자동으로 출제됩니다 | Auto-generated after SOP completion |
| `chat.meta.tokens` | 토큰 {{n}}/{{max}} | Tokens {{n}}/{{max}} |
| `chat.meta.context` | 컨텍스트 {{n}}턴 | Context {{n}} turns |
| `chat.meta.model` | 모델 {{name}} | Model {{name}} |
| `chat.meta.intent` | 의도 분류 {{n}}ms | Intent {{n}}ms |
| `chat.ai.label.sop` | SOP_GUIDE | SOP_GUIDE |
| `chat.ai.label.scenario` | SCENARIO | SCENARIO |
| `chat.ai.label.action` | ACTION | ACTION |
| `chat.ai.label.chat` | CHAT | CHAT |
| `chat.ai.label.vision` | VISION | VISION |
| `chat.ai.confidence` | 신뢰도 | Confidence |
| `analytics.title` | SYSTEM ANALYTICS | SYSTEM ANALYTICS |
| `analytics.subtitle` | 시스템 분석 | System Analytics |
| `analytics.realtime` | REALTIME | REALTIME |
| `analytics.gpu` | GPU · UTILIZATION | GPU · UTILIZATION |
| `analytics.latency` | LATENCY | LATENCY |
| `analytics.qps` | QPS | QPS |
| `analytics.ingestion.title` | DATA INGESTION | DATA INGESTION |
| `analytics.ingestion.subtitle` | 데이터 수집 | Data Ingestion |
| `sidebar.registry.title` | SYSTEM REGISTRY | SYSTEM REGISTRY |
| `sidebar.registry.subtitle` | 시스템 등록 | System Registry |

총 ~26 키 × 2 언어 = ~52 줄 추가.

---

## 11. 파일 구조

### 11-1. 신규/갱신 파일

```
frontend/src/
├── routes/
│   └── chat.tsx                          ⭐ 갱신 (278줄 → ~350)
├── components/
│   ├── chat/
│   │   ├── AIMessageHeader.tsx           ⭐ 신규 (~50)
│   │   ├── MessageMetaFooter.tsx         ⭐ 신규 (~40)
│   │   ├── SessionBadge.tsx              ⭐ 신규 (~30)
│   │   ├── QuickPrompts.tsx              ⭐ 신규 (~80, v1.1)
│   │   └── (Day 4-5 기존 11개 + MessageBubble 갱신)
│   ├── sop/
│   │   ├── SOPSidePanel.tsx              갱신 (3-탭, 80→150)
│   │   ├── ScenarioPanel.tsx             ⭐ 신규 (~80)
│   │   ├── QuizPanelEmpty.tsx            ⭐ 신규 (~30)
│   │   ├── SOPHeader.tsx                 ⭐ 신규 (~40)
│   │   ├── SOPStepCard.tsx               ⭐ 신규 (~80, Drawer 콘텐츠 분리)
│   │   ├── StepNav.tsx                   ⭐ 신규 (~50)
│   │   └── SOPList.tsx                   ⭐ 신규 (~50)
│   ├── analytics/                        ⭐ 신규 디렉토리
│   │   ├── GPUGauge.tsx                  ⭐ ~60
│   │   ├── MetricCard.tsx                재사용 (Day 3 또는 신규 spec-light)
│   │   ├── DataIngestionList.tsx         ⭐ ~50
│   │   └── SystemAnalyticsPanel.tsx      ⭐ ~80
│   └── shell/
│       └── RightPanel.tsx                갱신 (mode prop)
├── hooks/
│   └── useSystemAnalytics.ts             ⭐ 신규 (~50, 5s 폴링)
├── api/
│   └── analytics.ts                      ⭐ 신규 (~60, mock)
├── store/
│   ├── chat.ts                           갱신 (+sessionId, +intentMs)
│   └── ui.ts                             갱신 (+rightPanelVisible toggle)
├── types/
│   └── chat.ts                           갱신 (+category in meta)
├── styles/
│   ├── tokens.css                        갱신 (+v2 letter-spacing, glass, glow)
│   └── components.css                    갱신 (+hud-chat 그리드, AI label, footer meta)
└── i18n/
    ├── ko/common.json                    갱신 (+~26 키)
    └── en/common.json                    갱신 (+~26 키)
```

### 11-2. 줄 수 합계

| 카테고리 | 신규 | 갱신 |
|---|---:|---:|
| Components/chat | ~120 | +30 (MessageBubble) |
| Components/sop | ~330 | +70 |
| Components/analytics | ~190 | — |
| Components/shell | — | +30 |
| hooks/api | ~110 | — |
| store/types | — | +50 |
| styles | — | +120 |
| i18n | — | +52 |
| chat.tsx | — | +72 |
| **합계** | **~750** | **~424** |

총 **~1,174줄** (신규 750 + 갱신 424).

---

## 12. 단계 분할 — Phase 1~3

### Phase 1 — 토큰 + 레이아웃 + 분석 패널 (~45분)
- [ ] `tokens.css` v2 비교 + 갱신 (letter-spacing, glass, glow 변수)
- [ ] `components.css` 신규 클래스 (`.hud-chat` 그리드, `.ai-message-header`, `.message-meta-footer`, `.session-badge`)
- [ ] `frontend/src/api/analytics.ts` mock + `hooks/useSystemAnalytics.ts` 5초 폴링
- [ ] `components/analytics/{GPUGauge,DataIngestionList,SystemAnalyticsPanel}.tsx`
- [ ] `components/shell/RightPanel.tsx` mode prop + analytics 모드 통합
- [ ] `routes/chat.tsx` 그리드 레이아웃 갱신 — 3-Panel 구조

검증: `npm run build` 0 오류 + `/chat` 진입 시 우측 SYSTEM ANALYTICS 표시 + 5초 폴링 동작

### Phase 2 — SOP 3-탭 + 메시지 헤더/footer (~45분)
- [ ] `components/sop/SOPSidePanel.tsx` 3-탭 (Day 5 갱신)
- [ ] `components/sop/{SOPHeader,SOPStepCard,StepNav,SOPList}.tsx` 분리
- [ ] `components/sop/{ScenarioPanel,QuizPanelEmpty}.tsx` 신규
- [ ] `components/chat/{AIMessageHeader,MessageMetaFooter,SessionBadge}.tsx`
- [ ] `MessageBubble.tsx` 갱신 — AI 헤더 + footer 통합
- [ ] `useChatStore` 갱신 — `sessionId`, `intentMs`, meta `category` 필드
- [ ] i18n 한·영 키 26개 추가

검증: SOP 클릭 → inline Step 1/N 표시 + AI 응답 시 `[SOP_GUIDE] 신뢰도 ─ Xms HH:MM` 헤더 + footer 메타

### Phase 3 — 통합 검증 + 시연 시나리오 (~20분)
- [ ] 라이트/다크/AUTO 테마 모두 정상
- [ ] 모바일 768/1024 반응형 (RightPanel/SOP Drawer 변환)
- [ ] 본선 시연 6 시나리오 흐름 — DAY5_PLAN Section 16-4 그대로 동작
- [ ] 시안 ↔ 실 화면 비교 (시각 fidelity)

---

## 13. 검증 체크리스트

### 13-1. 코드
- [ ] TS strict (`tsc -b`) 0 오류
- [ ] ESLint 0 경고
- [ ] pytest `test_llm_router.py` 30/30 PASS 유지
- [ ] 외부 npm 추가 0
- [ ] Day 1~5 의 다른 라우트 (`/dashboard`, `/search`, `/dev/components`) 손상 0

### 13-2. 시각 fidelity
- [ ] 3-Panel 그리드 (240+320+flex+280) 정확
- [ ] AJIN INDUSTRY + AI ASSISTANT 헤더 폰트/스타일 v2
- [ ] SOP Step 진행률 + 다음 버튼 골드 CTA
- [ ] AI 헤더 `[SOP_GUIDE]` 골드 + letter-spacing
- [ ] 메시지 footer 메타 dim 톤 + 점선 구분
- [ ] 우측 GPU 게이지 + LATENCY/QPS 카드 + DATA INGESTION 5종 모두 표시
- [ ] LIVE 배지 ● 골드 펄스
- [ ] 라이트/다크 모드 모두 정상

### 13-3. 동작
- [ ] 페이지 진입 시 세션 ID 자동 생성
- [ ] SOP 탭 클릭 → 3-탭 전환 정상
- [ ] 협업 탭 → 5종 카드 → 클릭 시 챗 자동 전송 → 시나리오 매처
- [ ] 퀴즈 탭 → empty state 표시
- [ ] 우측 SYSTEM ANALYTICS 5초 갱신 (살짝 흔들리는 값)
- [ ] 모바일 768 → 우측 패널 자동 숨김 + SOP 패널 Drawer 변환
- [ ] [HIDE] 토글 → 우측 패널 토글
- [ ] AI 응답 시 헤더 카테고리 (`[SOP_GUIDE]` / `[CHAT]` / `[SCENARIO]`) 정확

---

## 14. 위험 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | tokens.css 갱신 시 다른 라우트 컴포넌트 의존성 깨짐 | 🔴 | v2 전체 덮어쓰기 X — 추가 변수만 도입, 기존 변수 이름 유지 |
| 2 | SOPSidePanel 3-탭 갱신 시 Day 5 Phase 2~3 통합 깨짐 | 🟡 | 기존 prop 시그니처 유지, 내부만 갱신 |
| 3 | RightPanel mode prop 추가 시 dashboard.tsx 깨짐 | 🟡 | 기본값 `default`(=현재 동작), `analytics`만 신규 |
| 4 | GPU 게이지 mock 5초 폴링 메모리 누수 | 🟢 | useEffect cleanup + AbortController |
| 5 | 세션 ID `#A47-2026` 의 47이 충돌 또는 의미 없음 | 🟢 | 1~999 랜덤 — 시연 시각 효과만 |
| 6 | 메시지 footer 메타 데이터 출처 미확정 | 🟡 | tokens/intent 는 mock 가능, model/context 실제 |
| 7 | 모바일 < 768 의 SOP Drawer 전환 | 🟡 | useWindowSize 훅 + 조건 렌더링 |
| 8 | 이중 언어 라벨 letter-spacing 깨짐 | 🟢 | `.label-en` / `.label-ko` 클래스 일관 사용 |
| 9 | DATA INGESTION 5종 카운터 데이터 없음 | 🟢 | mock 그대로 — Day 6/10/13 에서 실 연동 |
| 10 | v2 의 No-emoji vs 👍/👎 충돌 | 🟢 | 사용자 결정 (#17-2) — 시안 그대로 유지 권장 |

---

## 15. Day 5++ 비스코프

| # | 항목 | 일정 |
|:--:|---|---|
| 1 | 퀴즈 탭 본격 콘텐츠 (4지선다 자동 생성) | Day 13 (C-2-5) |
| 2 | TF-IDF intent 분류기 실 동작 | Day 13 |
| 3 | DATA INGESTION 5종 실 백엔드 카운트 | Day 6 / 10 / 13 |
| 4 | GPU 실 측정 | Day 6 또는 비범위 |
| 5 | 부서 라우터 31종 UI | Day 11 |
| 6 | 용어집 매처 297항목 UI 하이라이트 | Day 12 |
| 7 | RightPanel mode 다양화 (chat-context, monitoring 등) | Day 12 |
| 8 | 신뢰도 % — 백엔드 응답에 confidence 필드 추가 | Day 13 |
| 9 | session id 영구화 (Firestore) | 비범위 |
| 10 | TopBar `[SYS]` 토글 (RightPanel 강제 숨김 해제) | Day 12 |

---

## 16. 시간 분배표 (총 1.5~2h)

| 시간대 | 작업 |
|:--:|---|
| 00:00 ~ 00:10 | uiux/AJIN AI Assistant Design System_v2/colors_and_type.css 정독 + tokens.css 비교 |
| 00:10 ~ 00:55 | Phase 1 — 토큰/레이아웃/분석 패널 + 5초 폴링 |
| 00:55 ~ 01:00 | Phase 1 검증 (TS strict + 시각 검수) |
| 01:00 ~ 01:45 | Phase 2 — SOP 3-탭 + 메시지 헤더/footer + 세션 ID |
| 01:45 ~ 01:50 | Phase 2 검증 |
| 01:50 ~ 02:10 | Phase 3 — 통합 검증 + 시안 fidelity 비교 + 시연 시나리오 흐름 |

---

## 17. 사용자 결정 대기

| # | 결정 | 권장 |
|:--:|---|---|
| 1 | **위임 방식** | `executor` (opus) 백그라운드 |
| 2 | **이모지 정책 충돌** (👍/👎 vs v2 no-emoji) | 시안 그대로 유지 (functional, 작은 버튼) |
| 3 | **GPU/DATA INGESTION** mock vs 백엔드 신규 엔드포인트 | mock — Day 6/10/13에 실 연동 |
| 4 | **세션 ID** 영구화 여부 | 미영구화 (페이지 리프레시 시 새 세션) |
| 5 | **RightPanel** chat 페이지에서 dashboard 와 다른 mode? | mode='analytics' 신규, dashboard는 default 그대로 |
| 6 | **퀴즈 탭** placeholder vs 비활성 | placeholder (탭은 표시, 콘텐츠는 empty state) |

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 17 섹션 / 신규 ~750 + 갱신 ~424 / Phase 3분할 / 검증 26건 |

---

**관련 문서**:
- [DAY5_PLAN.md](DAY5_PLAN.md) — Day 5 Phase 1~5 (완료)
- [DAY4_PLAN.md](DAY4_PLAN.md) — Day 4 채팅 UI (완료)
- [LLM_ROUTER_PLAN.md](LLM_ROUTER_PLAN.md) — 백엔드 LLM 라우터 (완료)
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — 17일 일정
- `uiux/AJIN AI Assistant Design System_v2/README.md` — v2 디자인 시스템 단일 진실 출처
- `uiux/AJIN AI Assistant Design System_v2/colors_and_type.css` — v2 토큰 사양
