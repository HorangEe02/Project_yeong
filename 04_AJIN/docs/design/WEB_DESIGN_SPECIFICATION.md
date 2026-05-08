# AJIN AI ASSISTANT — 웹 디자인 설명서 (Web Design Specification)

> **버전**: v3.5
> **작성일**: 2026-04-26
> **대상**: 제3회 KNU SILLI 경진대회 본선 진출 — Streamlit → React 마이그레이션 기준 자료
> **목적**: 현재 구현된 웹 UI의 디자인 시스템·컴포넌트·레이아웃·페이지 사양을 React 재구현이 가능한 수준으로 문서화

---

## 목차

1. [디자인 철학 및 컨셉](#1-디자인-철학-및-컨셉)
2. [컬러 시스템 (60-30-10)](#2-컬러-시스템-60-30-10)
3. [타이포그래피](#3-타이포그래피)
4. [레이아웃 시스템 (3-Column HUD)](#4-레이아웃-시스템-3-column-hud)
5. [디자인 토큰 (Design Tokens)](#5-디자인-토큰-design-tokens)
6. [공통 컴포넌트 카탈로그](#6-공통-컴포넌트-카탈로그)
7. [아이콘 시스템 (SVG)](#7-아이콘-시스템-svg)
8. [테마 시스템 (Light / Dark / Auto)](#8-테마-시스템-light--dark--auto)
9. [페이지별 상세 디자인 사양](#9-페이지별-상세-디자인-사양)
10. [상태 표시 및 배지](#10-상태-표시-및-배지)
11. [데이터 시각화 (Plotly)](#11-데이터-시각화-plotly)
12. [반응형 디자인](#12-반응형-디자인)
13. [접근성 (WCAG)](#13-접근성-wcag)
14. [애니메이션 / 인터랙션](#14-애니메이션--인터랙션)
15. [React 마이그레이션 매핑 가이드](#15-react-마이그레이션-매핑-가이드)

---

## 1. 디자인 철학 및 컨셉

### 1-1. 컨셉
**"HUD Command Center Dashboard"** — 군사용/항공용 헤드업 디스플레이(HUD)에서 영감을 받은 정보 집약형 커맨드 센터 인터페이스

### 1-2. 핵심 원칙
| # | 원칙 | 적용 |
|---|---|---|
| 1 | **정보 밀도 우선 (Information-Dense)** | 한 화면에 핵심 메트릭/상태/액션을 동시 노출, 불필요한 여백 최소화 |
| 2 | **모노톤 + 골드 강조 (Monochrome + Gold Accent)** | 베이지/그레이 베이스 + `#C88A00` 아진 골드를 CTA·활성 상태에만 사용 |
| 3 | **터미널/엔지니어링 미학** | 영문+한글 병기 (`CORE MODULES (핵심 모듈)`), 모노스페이스 라벨, 점선·각진 모서리 |
| 4 | **거의 직각 모서리 (Sharp Corners)** | `border-radius: 2px` — 산업용 UI 인상 강조 |
| 5 | **상태 즉시성 (Realtime Status)** | 모든 시스템 컴포넌트(LLM/DB/RBAC) 상태를 상단 고정 바에 24/7 표시 |
| 6 | **부서·권한 컨텍스트 가시화** | 사용자 RBAC 레벨·소속 부서를 UI 곳곳에 노출 |

### 1-3. 디자인 인상 (Design Mood)
- **레퍼런스**: 우주관제센터 콘솔 / Bloomberg Terminal / Iron Man HUD / Figma HUD Infographic Pack
- **사용자 인지**: "전문 분석가/엔지니어를 위한 도구"
- **분위기**: 견고함(Solid), 신뢰성(Reliable), 즉각성(Realtime), 산업성(Industrial)

---

## 2. 컬러 시스템 (60-30-10)

### 2-1. 60-30-10 분배 원칙
색상은 **60% 베이스 / 30% 보조 / 10% 강조** 비율로 사용한다.

### 2-2. 라이트 모드 (Default)
| 비율 | 역할 | 토큰 | HEX | 용도 |
|:--:|---|---|---|---|
| **60%** | bg_primary | `--hud-bg` | `#FAF8F5` | 전체 배경 (베이지 화이트) |
| | bg_card | `--hud-surface` | `#FFFFFF` | 카드/패널 배경 |
| | text_primary | `--hud-text` | `#2C241A` | 본문 텍스트 (다크 브라운) |
| | text_mono | — | `#1A1A1A` | 모노스페이스 텍스트 |
| **30%** | bg_sidebar | — | `#F0EBE3` | 사이드바·좌측 패널 |
| | border | `--hud-border` | `#D6CFC3` | 일반 보더 |
| | border_light | — | `#E8E3DA` | 얇은 구분선 |
| | text_secondary | `--hud-text-dim` | `#5C4E3C` ~ `#7A6E5E` | 보조 텍스트·라벨 |
| | text_muted | — | `#A09686` | 비활성 텍스트 |
| **10%** | accent (메인) | `--hud-primary` | `#C88A00` | CTA 버튼·활성 항목 (아진 골드) |
| | accent_bright | — | `#F9A70D` | 활성 탭 밑줄·하이라이트 |
| | accent_dim | — | `#D4A84420` | 반투명 골드 배경 |

### 2-3. 다크 모드 (HUD Mode)
| 토큰 | HEX | 용도 |
|---|---|---|
| `--hud-bg` | `#0A0E14` | 전체 배경 (딥 네이비) |
| `--hud-surface` | `#111820` | 카드 배경 |
| (surface2) | `#1A2030` / `#1c2636` | 인풋·선택자 배경 |
| `--hud-border` | `#2A2520` | 보더 |
| `--hud-primary` | `#F9A70D` | 강조 골드 (라이트보다 한 톤 밝게) |
| `--hud-primary-dim` | `#F9A70D33` | 반투명 골드 |
| `--hud-primary-glow` | `0 0 10px #F9A70D44, 0 0 20px #F9A70D22` | 골드 글로우 (그림자) |
| `--hud-text` | `#E8E1D5` | 본문 (웜 화이트) |
| `--hud-text-dim` | `#D5CFC5` | **v3.4 갱신** — 명암비 8.5:1 (WCAG AAA) |

### 2-4. Semantic 색상 (라이트/다크 공통)
| 의미 | 토큰 | HEX | 사용처 |
|---|---|---|---|
| 정상/완료 | `--hud-green` | `#2D8A4E` | LLM 연결 ON, 상태 정상, 검증 통과 |
| 경고 | `--hud-orange` | `#E8A317` | 주의 필요, 임계치 근접 |
| 위험/실패 | `--hud-red` | `#C0392B` | 에러, 실패, 임계치 초과 |
| 정보 | `--hud-blue` | `#2980B9` | 정보 안내, 중립 메시지 |
| 비활성 | (text_dim) | `#D5CFC5` | 비활성·OFF |

### 2-5. CSS 변수 정의 (실제 적용)
```css
:root {
    /* Dark Mode (기본) */
    --hud-bg: #0A0E14;
    --hud-surface: #111820;
    --hud-border: #2A2520;
    --hud-primary: #F9A70D;
    --hud-primary-dim: #F9A70D33;
    --hud-primary-glow: 0 0 10px #F9A70D44, 0 0 20px #F9A70D22;
    --hud-primary-light: #FFC84D;
    --hud-red: #C0392B;
    --hud-orange: #E8A317;
    --hud-green: #2D8A4E;
    --hud-yellow: #F9A70D;
    --hud-blue: #2980B9;
    --hud-text: #E8E1D5;
    --hud-text-dim: #D5CFC5;       /* v3.4: WCAG AAA */
    --hud-font: 'Pretendard', 'Noto Sans KR', sans-serif;
}
```

---

## 3. 타이포그래피

### 3-1. 폰트 패밀리
| 용도 | 패밀리 | 적용 |
|---|---|---|
| **모노/디스플레이/본문 통합** | `'Pretendard', 'Noto Sans KR', sans-serif` | 전체 UI 단일 패밀리 사용 |
| **한글 fallback** | `'Noto Sans KR', sans-serif` | Pretendard 미적재 시 |
| **머티리얼 아이콘** | `'Material Symbols Rounded', 'Material Icons'` | 일부 아이콘 |

> **이유**: Pretendard는 한국어와 영어를 같은 골격감으로 묶어주는 변형 산세리프. HUD의 영문 라벨(`CORE MODULES`)과 한글 보조(`핵심 모듈`)를 동시에 자연스럽게 표현.

### 3-2. 폰트 크기 스케일 (v3.4 +2px 증가)
| 토큰 | 크기 | 용도 |
|---|---|---|
| `xs` | **12px** | 작은 라벨, 보조 메타 (이전 10px) |
| `sm` | **13px** | 패널 헤더, 보조 텍스트 (이전 11px) |
| `base` | **15px** | 본문 (이전 13px) |
| `md` | **16px** | 카드 타이틀, 강조 본문 (이전 14px) |
| `lg` | **18px** | 섹션 타이틀 |
| `xl` | **20px** | 페이지 서브 타이틀 |
| `2xl` | **28px** | 페이지 메인 타이틀 |
| `3xl` | **36px** | 메트릭 값(Hero Number) |

### 3-3. 자간(Letter-spacing) — HUD 특유의 키워드
| 컨텍스트 | letter-spacing |
|---|---|
| 영문 라벨 (`CORE MODULES`, `SYSTEM REGISTRY`) | `0.08em` ~ `0.1em` |
| 메트릭 라벨 | `0.1em` |
| 본문 한글 | 기본값 (자간 미적용) |
| 사이드바 버전 표기 (`v3.5 // KNU SILLI 2026`) | `2px` (절대값) |

### 3-4. 굵기(Weight)
| Weight | 용도 |
|---|---|
| 400 | 본문, 보조 텍스트 |
| 600 | 패널 헤더, 카운트 |
| 700 | 메트릭 값, 페이지 타이틀, 활성 강조 |

### 3-5. 영한 병기 패턴
HUD의 시그니처 — 모든 주요 라벨은 **영문 대문자 + 한글 부제** 형식.
```
CORE MODULES         핵심 모듈
SYSTEM REGISTRY      시스템 등록 현황
SECURITY LOG         보안 로그
QUERY RESULTS        검색 결과
```
구현: `<span class="hud-panel-title">` + `<span class="hud-ko-sub">`

---

## 4. 레이아웃 시스템 (3-Column HUD)

### 4-1. 전체 레이아웃 구조
```
┌─────────────────────────────────────────────────────────────────────┐
│  ◼ 아진산업 AI v3.5 │ 환경:ON-PREMISE · 인증:JWT_ACTIVE │ LLM:QWEN3.5 ●│ ← Top Bar (52px, sticky)
├──────────────┬──────────────────────────────────────┬───────────────┤
│              │                                      │               │
│  [LOGO]      │                                      │ SYSTEM        │
│  v3.5 KNU    │                                      │ ANALYTICS     │
│              │                                      │ ─────────     │
│  USER INFO   │                                      │ ╭──────╮      │
│  [PROFILE]   │       CENTER PANEL                   │ │ 42%  │      │
│  [LOGOUT]    │       (Page Content)                 │ │ GPU  │      │
│              │                                      │ ╰──────╯      │
│  THEME ▼     │       - Dashboard / Search /         │ 지연시간:124ms │
│              │         Draft / Onboarding /         │ QPS: 8.4k     │
│  CORE        │         Compliance / Admin /         │               │
│  MODULES     │         Equipment / Profile          │ DATA          │
│  ▣ 인원검색  │                                      │ INGESTION     │
│  ▢ 문서작성  │                                      │ ━━━━━━ 100%   │
│  ▢ AI도우미  │                                      │ 에러코드 201/201│
│  ▢ 법규모니터│                                      │ 금형     25/25 │
│  ▢ 인사관리  │                                      │ SPC     5/5    │
│  ▢ 설비AI    │                                      │ ...           │
│              │                                      │               │
│  SYSTEM      │                                      │               │
│  REGISTRY    │                                      │ [HIDE/SYS]    │
│  29 부서  ●  │                                      │ 토글버튼      │
│              │                                      │               │
│  SECURITY    │                                      │               │
│  LOG         │                                      │               │
│  [AUTH] OK   │                                      │               │
│  [RBAC] L6   │                                      │               │
│              │                                      │               │
└──────────────┴──────────────────────────────────────┴───────────────┘
   240~400px         flex-grow (4)               280px (0.8 ratio)
   Left Sidebar      Center Panel                Right Panel
```

### 4-2. 레이아웃 토큰
| 영역 | 토큰 | 값 |
|---|---|---|
| 상단 바 높이 | `top_bar_height` | `52px` |
| 좌측 패널 폭 | `left_panel_width` | `240px` (최대 `400px`) |
| 우측 패널 폭 | `right_panel_width` | `280px` |
| 카드 모서리 | `card_radius` | `2px` (거의 직각) |
| 카드 패딩 | `card_padding` | `16px` |
| 섹션 간격 | `section_gap` | `20px` |
| 메인 컬럼 비율 (우측 패널 ON) | `main_col_ratio` | `[4, 0.8]` |
| 메인 컬럼 비율 (우측 패널 OFF) | `main_col_full` | `[1]` (전체 폭) |

### 4-3. 좌측 사이드바 구성 (수직 흐름)
| 순서 | 섹션 | 콘텐츠 |
|:--:|---|---|
| ① | **로고** | AJIN 로고 SVG (테마별 전환) + `AI ASSISTANT` + `v3.5 // KNU SILLI 2026` |
| ② | **유저 카드** | 이름 + 직급, [PROFILE] [LOGOUT] 버튼 (2열) |
| ③ | **DASHBOARD 버튼** | 아이콘 + 라벨, 단독 |
| ④ | **THEME 셀렉터** | LIGHT / DARK / AUTO (AUTO 시 현재 모드 캡션) |
| ⑤ | **CORE MODULES** | 6개 모듈 네비 (RBAC·부서별 필터) |
| ⑥ | **SYSTEM REGISTRY** | 등록 부서 카운트 + 정상 표시 ● |
| ⑦ | **SECURITY LOG** | 4줄 로그 (`[AUTH]`, `[RBAC]`, `[SYNC]`, `[LLM]`) |
| ⑧ | **푸터** | `AJIN INDUSTRY // ON-PREMISE AI` + 스택 정보 |

### 4-4. 우측 패널 (System Analytics)
| 순서 | 섹션 | 콘텐츠 |
|:--:|---|---|
| ① | 헤더 | `SYSTEM ANALYTICS` + `REALTIME ●` |
| ② | GPU 게이지 | 80×80 원형 SVG, 골드 stroke, % + GPU 라벨 |
| ③ | 메트릭 행 | 지연시간(ms) / QPS — 1행 가로 배치 |
| ④ | DATA INGESTION | 5종 (에러코드/금형/SPC/도면/검사) — 라벨 + 카운트 + 3px 진행 바 |

토글 가능 (`HIDE` / `SYS` 버튼). 숨김 시 중앙 패널 100% 폭으로 확장.

---

## 5. 디자인 토큰 (Design Tokens)

### 5-1. Token Map (코드 ↔ React용)
```ts
// React/CSS-in-JS 권장 매핑
export const tokens = {
  color: {
    light: {
      bgPrimary:    '#FAF8F5',
      bgCard:       '#FFFFFF',
      bgSidebar:    '#F0EBE3',
      textPrimary:  '#2C241A',
      textSecondary:'#5C4E3C',
      textMuted:    '#7A6E5E',
      border:       '#D6CFC3',
      borderLight:  '#E8E3DA',
      accent:       '#C88A00',
      accentBright: '#F9A70D',
      accentDim:    'rgba(212,168,68,0.13)', // #D4A84420
    },
    dark: {
      bgPrimary:    '#0A0E14',
      bgCard:       '#111820',
      bgSurface2:   '#1A2030',
      textPrimary:  '#E8E1D5',
      textSecondary:'#D5CFC5',
      border:       '#2A2520',
      accent:       '#F9A70D',
      accentDim:    'rgba(249,167,13,0.20)',
    },
    semantic: {
      success: '#2D8A4E',
      warning: '#E8A317',
      danger:  '#C0392B',
      info:    '#2980B9',
    },
  },
  font: {
    family: "'Pretendard', 'Noto Sans KR', sans-serif",
    size: { xs:12, sm:13, base:15, md:16, lg:18, xl:20, '2xl':28, '3xl':36 },
    weight: { regular:400, semibold:600, bold:700 },
    letterSpacing: { wide:'0.08em', wider:'0.1em' },
  },
  layout: {
    topBarHeight:    52,
    leftPanelWidth:  240,
    rightPanelWidth: 280,
    cardRadius:      2,
    cardPadding:     16,
    sectionGap:      20,
  },
  shadow: {
    glow: '0 0 10px rgba(249,167,13,0.27), 0 0 20px rgba(249,167,13,0.13)',
  },
};
```

---

## 6. 공통 컴포넌트 카탈로그

### 6-1. 패널 박스 (`.hud-panel-box`)
모든 사이드 섹션의 기본 컨테이너.
```css
.hud-panel-box {
    border: 1px solid var(--hud-border);
    padding: 16px;
    margin-bottom: 12px;
    background: var(--hud-surface);
}
.hud-panel-header {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 13px; font-weight: 600;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--hud-text-dim);
    margin-bottom: 12px; padding-bottom: 8px;
    border-bottom: 1px solid var(--hud-border);
}
.hud-panel-header .hud-badge {
    font-size: 12px;
    color: var(--hud-text-dim);
}
```

### 6-2. 메트릭 카드 (`hud_metric_card`)
큰 숫자 + 라벨(영) + 라벨(한) + 서브 텍스트 — 라이트 모드에서 골드 값(`#C88A00`).
- value: `36px` / `bold` / accent 색상
- label_en: `14px` / 영문 letter-spacing 0.1em
- label_ko: `13px` / 한글 보조
- sub: `13px` / dim

### 6-3. 쿼리 결과 카드 (`render_query_result_card`)
검색 결과 1건 — 출처 / 신뢰도 / 타이틀 / 설명 (하이라이트).
```
┌─────────────────────────────────────────────┐
│  출처: ChromaDB        신뢰도: 87%          │
│                                             │
│  품질관리 SOP — 8D 보고서 작성 가이드       │ ← 골드, 16px bold
│                                             │
│  본문 텍스트 ... 키워드 하이라이트 ...      │ ← 14px, line-height 1.6
└─────────────────────────────────────────────┘
   border 1px solid var(--hud-border)
```

### 6-4. 상태 배지 (`.hud-badge-*`)
```
●  hud-badge-ok    (#2D8A4E)   정상
●  hud-badge-warn  (#E8A317)   경고
●  hud-badge-fail  (#C0392B)   실패
●  hud-badge-info  (#2980B9)   정보
○  hud-badge-off   (#D5CFC5)   비활성
```
모두 `::before` content `●`/`○` + `font-weight:700`.

### 6-5. 점선 구분선 (`hud_dotted_separator`)
```css
.hud-dotted-line {
    border-top: 1px dashed var(--hud-border);
    margin: 12px 0;
}
```
세션 메모리 영역, 페이지 구역 분리에 사용.

### 6-6. 코너 마커 (`.hud-corner-tl`, `.hud-corner-br`)
HUD 특유의 모서리 강조 — 좌상/우하 코너에 작은 골드 ㄱ자 마커.

### 6-7. 버튼 (Streamlit 오버라이드 → React `<Button>`)
| 종류 | 라이트 모드 | 다크 모드 |
|---|---|---|
| **Primary (활성)** | bg `#C88A00`, text 흰색 | bg `#F9A70D`, text `#0A0E14` |
| **Secondary/Tertiary** | border `#D6CFC3`, text `#2C241A` | border `#2A2520`, text `#E8E1D5` |
| **Hover** | border `#C88A00`, text `#C88A00` | bg `#E09E10` |
| **Disabled** | opacity 0.5, cursor not-allowed | 동일 |
| **글꼴** | Pretendard, `13px` | 동일 |

```css
.stApp .stButton > button {
    font-family: var(--hud-font) !important;
    font-size: 13px !important;
    border: 1px solid var(--hud-border);
    background: var(--hud-surface2);
    color: var(--hud-text);
    /* radius 2px (사실상 직각) */
}
.stApp .stButton > button[kind="primary"] {
    background: var(--hud-primary) !important;
    color: #0A0E14 !important;
    border-color: var(--hud-primary) !important;
}
```

### 6-8. 입력 필드 (`text_input`, `selectbox`)
- 폰트 `15px` Pretendard
- border `1px solid var(--hud-border)`
- background `var(--hud-bg)` (다크) / `#FFFFFF` (라이트)
- focus 시 border `var(--hud-primary)` + 골드 outline
- placeholder 색상 `var(--hud-text-dim)`

### 6-9. SQL 입력 바 (`render_sql_input_bar`)
중앙 패널의 시그니처 컴포넌트.
```
> FTS5/SQL:  [SELECT processes FROM SPC WHERE anor...]    [실행]
   13px dim    placeholder dim                              primary btn
```

### 6-10. 검색 결과 헤더 (`render_query_results_header`)
```
검색 결과                                              일치: 12건
─────────────────────────────────────────────────────────────────
13px / dim / uppercase / letter-spacing 0.08em / border-bottom
```

### 6-11. AI 세션 메모리 박스 (`render_session_memory`)
하단 점선 박스 — 토큰 카운트 + 요약 텍스트.
```
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
AI 세션 메모리 요약                          토큰: 420
SYS_MEM: 사용자가 8D 보고서 생성을 요청...
```

---

## 7. 아이콘 시스템 (SVG)

### 7-1. 아이콘 명세
- **viewBox**: `0 0 24 24` (전부)
- **타입**: stroke 기반 (`fill="none"`, `stroke-width="1.5"`)
- **색상**: `currentColor` (텍스트 색상 자동 상속)
- **모서리**: `stroke-linecap="round"`
- **정의 파일**: [icons.py](../../ui/icons.py)

### 7-2. 아이콘 카탈로그 (16종)
| 키 | 용도 | 형태 |
|---|---|---|
| `dashboard` | 메인 대시보드 | 4분할 그리드 |
| `employee` | 인원 검색 (기능 A) | 사람 + 검색 + 표식 |
| `documents` | 문서 검색/작성 (기능 B) | 문서 + 줄 |
| `onboarding` | AI 업무 도우미 (기능 C) | 챗 버블 |
| `compliance` | 법규 모니터링 (기능 D) | 방패 + 체크 |
| `admin` | 인사 관리 (기능 E) | 톱니바퀴 |
| `equipment` | 설비/공정 AI (기능 F) | 3중 다이아몬드 |
| `internal`, `external` | 기능 B 내부/외부 탭 | 그리드 / 지구 |
| `login`, `password` | 로그인 페이지 | 자물쇠 / 키 |
| `email`, `report`, `search`, `download` | 공통 액션 | 봉투 / 보고서 / 돋보기 / 다운로드 |
| `chart`, `analytics` | 차트/분석 | 바 차트 / 라인 |
| `toggle_panel` | 우측 패널 토글 | 사이드 패널 |

### 7-3. 사용 패턴
**3가지 변형 함수**:
1. `hud_icon(name, size, color)` → `<span style="display:inline-flex...">SVG</span>`
2. `hud_icon_label(name, text, size, color)` → 아이콘 + 텍스트 라벨
3. `get_svg_data_uri(name, color)` → CSS `background-image`용 data URI (URL 인코딩됨)

### 7-4. React 마이그레이션 권장
- **방법 A**: 그대로 인라인 SVG 컴포넌트로 변환 (`<Icon name="employee" size={16} />`)
- **방법 B**: Heroicons / Lucide-react 매핑 — viewBox·stroke 스타일 호환 (1.5 stroke)

---

## 8. 테마 시스템 (Light / Dark / Auto)

### 8-1. 3가지 모드
| 모드 | 동작 |
|---|---|
| **LIGHT** | 항상 라이트 모드 (60-30-10 베이지 계열) |
| **DARK** | 항상 다크 모드 (HUD 네이비 계열) |
| **AUTO** | 시간 기반 자동 전환 — **06:00~18:00 라이트, 18:00~06:00 다크** |

### 8-2. AUTO 모드 표시
사이드바 캡션에 `AUTO: 현재 라이트 모드 (06~18시 라이트)` 형태로 현재 적용 모드 노출.

### 8-3. 테마 전환 메커니즘
- `st.session_state["theme_preference"]` 에 저장 (`light` / `dark` / `auto`)
- `get_current_theme()` → 선호도가 `auto`면 시간 기반으로 결정
- `inject_hud_style()` 에서 `:root` CSS 변수 주입 시 현재 테마에 맞는 값 사용

### 8-4. 테마별 자산 전환
| 자산 | 라이트 | 다크 |
|---|---|---|
| 로고 SVG | [ajin_logo_light.svg](../../ui/assets/ajin_logo_light.svg) (텍스트 `#2C241A`) | `ajin_logo.svg` (텍스트 `#fff`) |
| Plotly 폰트 색 | `#2C241A` | `#E8E1D5` |
| Plotly 호버 bg | `#FFFFFF` | `#1c2636` |
| 호버 보더 색 | `#C88A00` | `#f9a70d` |

### 8-5. 라이트/다크 모두 강제되는 규칙
- `.stMarkdown strong` → 항상 골드 (`#C88A00`)
- `.stMarkdown a` → 항상 골드
- 코드 블록 — 모노스페이스 + 골드 보더

---

## 9. 페이지별 상세 디자인 사양

### 9-1. 로그인 페이지 ([page_login.py](../../ui/page_login.py), 610줄)
```
┌──────────────────────────────────────┐
│                                      │
│           [AJIN LOGO]                │ ← 테마별 SVG 자동 전환
│           AI ASSISTANT               │
│           v3.5 // KNU SILLI 2026     │
│                                      │
│    ┌──────────────────────────┐      │
│    │ 사원번호                 │      │
│    │ [_____________________]  │      │ 입력 필드 (15px)
│    │                          │      │
│    │ 비밀번호                 │      │
│    │ [_____________________]  │      │
│    │                          │      │
│    │ [        로그인        ] │      │ Primary 버튼 (full width)
│    │                          │      │
│    │ 비밀번호 변경 필요 시:    │      │
│    │ - 현재 비밀번호           │      │
│    │ - 새 비밀번호             │      │
│    │ - 비밀번호 강도 표시 (6조건) │   │ 실시간 검증
│    └──────────────────────────┘      │
│                                      │
└──────────────────────────────────────┘
```
- **비밀번호 정책 표시 (v3.3)**: 8자+/대소문자/숫자/특수문자/연속3회 금지 → 6개 체크박스 실시간 점등
- **계정 잠금**: 5회 실패 → 30분 잠금 안내
- **테마**: 전체 사이트 테마 동일 적용 (테마별 로고 전환)

### 9-2. 대시보드 ([page_dashboard.py](../../ui/page_dashboard.py), 266줄)
```
┌─────────────────────────────────────────────────────────────┐
│  대시보드                                          v3.5     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │   329   │  │   201   │  │   29    │  │   33    │         │ 메트릭 카드 (3xl)
│  │EMPLOYEES│  │ ERRORS  │  │ DEPTS   │  │ ACCOUNTS│         │ - 메트릭 값: 36px bold
│  │  사원   │  │ 에러코드│  │  부서   │  │테스트계정│         │ - 라벨: 14px / 0.1em letter-spacing
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ A. 인원 검색    │  │ B. 문서 작성    │                   │ 모듈 카드 (6개, 2x3)
│  │ • FTS5+ChromaDB │  │ • Few-shot RAG  │                   │ - border + 16px padding
│  │ • 시맨틱 하이브리│  │ • 품질평가 5기준 │                   │ - 호버: 골드 글로우
│  │ • ML 의도분류   │  │ • 7포맷 다운로드 │                   │
│  └─────────────────┘  └─────────────────┘                   │
│  ... (C, D, E, F)                                           │
│                                                             │
│  시스템 정보                                                │
│  • LLM: 5개 패밀리 (Qwen3.5/EXAONE/Gemma4/GPT-OSS/Nemotron) │
│  • 비전: Gemma 4 멀티모달                                   │
│  • ML/DL: 7모델                                             │
│  • RBAC: 6단계 + 28개 세부 권한                             │
└─────────────────────────────────────────────────────────────┘
```

### 9-3. A. 인원 검색 ([page_search.py](../../ui/page_search.py), 690줄)
- **상단**: 시맨틱 검색 입력 바 (FTS5/SQL 라벨 형식)
- **검색 이력**: 최근 5건 바로가기 칩 (`#abc123` 클릭 시 재검색)
- **5종 정렬 셀렉터**: 관련도순/이름/부서/직급/사업장
- **결과**: 카드 그리드 (1행 3개) — 사진(이니셜)/이름/부서/직급/이메일(가시성 마스킹)/연락처
- **하단**: 조직도 (HTML/CSS 카드형, 부서별 트리)
- **권한**: 타부서 email은 `***@***` 마스킹 (3-Tier 가시성)

### 9-4. B. 문서 검색/작성 ([page_draft.py](../../ui/page_draft.py), 940줄)
3탭 구조: 내부용 / 외부용 / 문서 이력
- **탭 바**: 영문+한글 (`INTERNAL 내부용` / `EXTERNAL 외부용`) + 골드 밑줄 (활성)
- **입력**: 자유 텍스트 + 어조(공식적/친근한/긴급) + 문서유형 셀렉터
- **결과**: 마크다운 렌더링 + **7개 다운로드 버튼** (DOCX/ODT/PDF/XLSX/CSV/TXT/복사)
- **품질 평가 카드**: 5기준 100점 채점 (구조/길이/전문성/완성도/톤) + 개선 포인트
- **버전 비교 diff**: 유사도% + 추가/삭제/변경 줄 수 + HTML 하이라이트
- **CC 추천 박스**: 필수/권장/선택 3색상

### 9-5. C. AI 업무 도우미 ([page_onboarding.py](../../ui/page_onboarding.py), 1896줄) — **최대 페이지**
ChatGPT 스타일 챗 인터페이스 + HUD 테마.
```
┌─────────────────────────────────────────────────┐
│  AI 업무 도우미 (AI WORK ASSISTANT)             │
│  부서: 품질보증팀 ▼   모드: [교육] [업무]       │ ← 부서 자동 + 듀얼 모드 토글
├─────────────────────────────────────────────────┤
│                                                 │
│  [질문 1: 8D 보고서 작성 절차?]      ← 우측 정렬 │
│                                                 │
│  AI 답변 (스트리밍 토큰)             ← 좌측 정렬 │
│  스트리밍 진행 중... 0.8초/200토큰              │
│  📥 DOCX  📥 XLSX  📥 CSV  📥 TXT              │ ← 영구 다운로드 버튼
│  👍 도움됨   👎 아쉬움                          │ ← 피드백 이모지
│                                                 │
│  [질문 2: ...]                                  │
│  ...                                            │
│                                                 │
│  ─ ─ ─ ─ ─ ─ AI 세션 메모리 ─ ─ ─ ─ ─ ─        │
│  토큰: 420 / 컨텍스트: 6턴                      │
│                                                 │
├─────────────────────────────────────────────────┤
│  [📎 파일] [질문을 입력하세요...]      [전송] ↑ │ ← 입력 바 (sticky bottom)
└─────────────────────────────────────────────────┘
```
- **스트리밍**: SSE 토큰 단위 출력 + 응답 메타데이터 (model, latency)
- **파일 업로드**: 20+ 확장자 (PDF/DOCX/XLSX/CSV/이미지)
- **이미지 분석**: 비전 모델 (Gemma 4) 자동 호출
- **퀴즈 / SOP**: 시스템 메시지 형태로 단계별 카드 출력
- **스트리밍 중 네비게이션 차단**: 사이드바 모듈 버튼 disabled (`(응답 생성 중...)` 표시)

### 9-6. D. 법규 모니터링 ([page_compliance.py](../../ui/page_compliance.py), 2144줄)
**4탭 구조 (v3.5)**:
1. 법규 모니터 (6서브탭)
2. **법규 업데이트** (메인 탭으로 승격) — 시나리오 TOP-3 + 변경 감지 + CSV 내보내기
3. 사업장
4. 법규 문서

- **시나리오 카드**: 리스크 점수 100점 (재무 40 + 가능성 30 + 긴급도 30)
- **타임라인**: Plotly 간트차트 — D-day별 색상 (CRITICAL `#C0392B` / HIGH `#E8A317` / MEDIUM / LOW)
- **관세 시뮬레이터**: 슬라이더 0~50% → 6품목 실시간 원가 영향 (25%=400억원)
- **영향 네트워크**: Plotly Network — 규제 → 시설 → 부서/제품 노드 그래프
- **사업장 지도**: Folium + OpenStreetMap (19개소 마커)

### 9-7. E. 인사 관리 ([page_admin.py](../../ui/page_admin.py), 1314줄)
**6탭 (Tier 4) / 4탭 (Tier 3)** — v3.5에서 이력→보안 통합
1. 사용자 (인라인 편집 7항목)
2. 생성 (3단계 위저드)
3. **보안** (감사 + 상세 이력 + 다운로드)
4. 분석 (AI 활용 분석 + 부서별 히트맵)
5. 인사 통계 (7종 Plotly 차트)
6. 도구

- **로그인 이력 다운로드**: CSV/XLSX (날짜 필터 + 타임스탬프+사번+부서+IP+UA)
- **보안 감사**: 무차별 대입 / 야간 접근 / 비활성 계정 탐지 — 위험 카드 색상 코딩
- **인력 통계**: 본부별/직급별/성별/사업장별/근속연수 — 7종 Plotly 차트 + 히트맵

### 9-8. F. 설비/공정 AI ([page_equipment.py](../../ui/page_equipment.py), 1628줄)
**3탭 구조 (v3.3)**: OVERVIEW / 매뉴얼 검색 / 점검 이력
- **OVERVIEW 6서브탭**: 종합 현황 / SPC 분석 / 에러 검색 / 금형 / 점검 / 수리 이력
- **SPC 분석**: Nelson 8 Rules 위반 하이라이트 + Plotly 관리도 + Annotation
- **5공정 건강 대시보드**: 카드 그리드 (CCH/OBC/범퍼빔/도어/볼시트)
- **금형 XGBoost**: 잔여수명 게이지 + 교체일 + 리스크 레벨 카드
- **에러 검색**: TF-IDF 증상→에러코드 매칭 + 이력 DB 685건 + Markov 통합
- **데이터 관리**: 통계적 데이터 생성기 + CSV 업로드 인터페이스 (Expander 내부)

### 9-9. 프로필 페이지 ([page_profile.py](../../ui/page_profile.py), 199줄)
사용자 정보 카드 — 사진/이름/사번/부서/직급/이메일/입사일/마지막 로그인.

---

## 10. 상태 표시 및 배지

### 10-1. 시스템 상태 점 (Status Dot)
```
●  hud-dot-on    (#2D8A4E) — LLM 연결됨, ChromaDB UP
●  hud-dot-off   (#C0392B) — 오프라인, 연결 실패
```
상단 바 LLM/벡터 DB 표시기에 사용 (`QWEN 3.5 ●`).

### 10-2. 텍스트 상태 (`.hud-st-*`)
```
.hud-st-ok    → 녹색 (정상)
.hud-st-warn  → 주황 (경고)
.hud-st-fail  → 빨강 (실패)
.hud-st-info  → 파랑 (정보)
.hud-st-off   → 디밍 (비활성)
.hud-st-on    → 녹색 (활성)
```
모두 `font-weight: 700`.

### 10-3. 배지 (`.hud-badge-*`)
박스 형태 — 점 + 텍스트.
```
●  ON-LINE     녹색 박스, 녹색 보더
●  WARNING     주황 박스, 주황 보더
●  CRITICAL    빨강 박스, 빨강 보더
○  OFFLINE     디밍, 보더 없음
```

### 10-4. 진행 바 (Ingestion Progress)
- 높이 3px (콤팩트) / 8px (일반)
- 배경: `var(--hud-border)` / 진행: `var(--hud-primary)`
- 카운트가 totalsegmentat 미달 → 카운트 색상 빨강

---

## 11. 데이터 시각화 (Plotly)

### 11-1. 공통 테마 ([plotly_theme.py](../../ui/plotly_theme.py))
모든 Plotly 차트는 `apply_theme(fig)` 호출 — 테마 자동 전환.
```python
{
  "paper_bgcolor": "rgba(0,0,0,0)",  # 투명 (HUD 배경 노출)
  "plot_bgcolor":  "rgba(0,0,0,0)",
  "font": {"color": "#2C241A | #E8E1D5", "family": "Noto Sans KR, sans-serif"},
  "hoverlabel": {
    "bgcolor":     "#FFFFFF | #1c2636",
    "bordercolor": "#C88A00 | #f9a70d",
  }
}
```

### 11-2. 차트 종류
| 차트 | 페이지 | 용도 |
|---|---|---|
| Bar | 인사 통계, AI 활용 분석 | 부서별/직급별 인원 |
| Pie | 인사 통계 | 성별/사업장 분포 |
| Heatmap | 부서별 활용 | 부서 × 기능 사용 빈도 |
| Scatter | SPC 산점도 | 공정 데이터 분포 |
| Timeline / Gantt | 법규 데드라인 | 시나리오 D-day |
| Radar | 법규 리스크 | 5축 (재무/가능성/긴급도/...) |
| Network | 영향 네트워크 | 규제 → 시설 → 부서 |
| 관리도 (Control Chart) | SPC | Nelson 8 Rules + UCL/LCL |
| 게이지 (커스텀 SVG) | 우측 패널 | GPU 사용률 |

### 11-3. 차트 색상 팔레트
- **메인**: 골드 `#C88A00` / `#F9A70D`
- **보조**: 그린 `#2D8A4E`, 블루 `#2980B9`, 오렌지 `#E8A317`, 레드 `#C0392B`
- **그라디언트**: 단일 골드 → 디밍 (`#C88A00` → `#C88A0040`)

---

## 12. 반응형 디자인

### 12-1. 브레이크포인트
| 화면폭 | 동작 |
|---|---|
| `> 768px` (Desktop) | 3-Column 풀 레이아웃 |
| `≤ 768px` (Tablet) | 사이드바 자동 접힘, 우측 패널 숨김 |
| `≤ 480px` (Mobile) | 메트릭 카드 1열, 폰트 -1px, 패딩 축소 |

### 12-2. 모바일 최적화
- Streamlit `[server] enableWebsocketCompression = false`
- `[server] maxUploadSize = 200` (200MB까지 파일 업로드)
- 사이드바 토글 버튼으로 수동 제어

### 12-3. 우측 패널 토글
- 헤더 우측 `[HIDE]` / `[SYS]` 버튼
- `st.session_state["show_right_panel"]` 으로 상태 관리
- ON: 메인 비율 `[4, 0.8]` / OFF: `[1]` (전체 폭)

---

## 13. 접근성 (WCAG)

### 13-1. 명암비
| 모드 | 토큰 | 대비 | 등급 |
|---|---|---|---|
| **다크 모드 보조 텍스트** (v3.4) | `#D5CFC5` on `#0A0E14` | **8.5:1** | **WCAG AAA** |
| 다크 모드 본문 | `#E8E1D5` on `#0A0E14` | 13.2:1 | AAA |
| 라이트 모드 본문 | `#2C241A` on `#FAF8F5` | 12.7:1 | AAA |
| 라이트 모드 보조 | `#5C4E3C` on `#FAF8F5` | 7.5:1 | AAA |

### 13-2. 한글 가독성 (v3.4)
- 폰트 크기 전체 +2px (10→12, 11→13, 13→15...)
- letter-spacing은 영문 라벨에만 적용 (한글은 기본값 유지)

### 13-3. 키보드/포커스
- Streamlit 기본 포커스 링 → 골드 outline으로 오버라이드
- `Tab` 순서: 사이드바 → 중앙 → 우측 패널

### 13-4. 시각적 계층
- 페이지 타이틀 28px → 섹션 타이틀 18px → 카드 타이틀 16px → 본문 15px
- 골드는 강조 / 액션에만 사용 (남용 금지)

---

## 14. 애니메이션 / 인터랙션

### 14-1. Hover 효과
| 요소 | 효과 |
|---|---|
| 사이드바 로고 영역 | 배경 `rgba(200,138,0,0.05)` 페이드인 (200ms) |
| 버튼 (Secondary) | border 골드 + 텍스트 골드 |
| 버튼 (Primary) | bg `#E09E10` (다크) / 약간 어둡게 |
| 카드 | 골드 그림자 글로우 (다크 모드만) |
| 메트릭 카드 | scale 1.0 → 1.02, transition 300ms |

### 14-2. 글로우 효과 (다크 모드 전용)
```css
--hud-primary-glow: 0 0 10px #F9A70D44, 0 0 20px #F9A70D22;
```
주요 액션 버튼·활성 모듈 카드에 적용.

### 14-3. 스트리밍 인디케이터
- AI 응답 생성 중 사이드바 모듈 라벨에 `(응답 생성 중...)` 골드 텍스트
- 모든 네비게이션 버튼 `disabled=true` (사용자 의도치 않은 페이지 이동 방지)
- 입력 바 placeholder 변경 (`AI가 응답을 생성하고 있습니다...`)

### 14-4. 페이지 전환
- Streamlit `st.rerun()` 기반 — 부드러운 전환은 없음 (즉시 재렌더)
- React 마이그레이션 시 `<Suspense>` + 페이드 트랜지션 권장 (200ms)

---

## 15. React 마이그레이션 매핑 가이드

### 15-1. Streamlit → React 컴포넌트 매핑
| Streamlit | React 권장 |
|---|---|
| `st.columns([4, 0.8])` | CSS Grid `grid-template-columns: 4fr 0.8fr` |
| `st.sidebar` | `<aside class="sidebar">` (고정 폭) |
| `st.button(type="primary")` | `<Button variant="primary">` |
| `st.text_input` | `<input className="hud-input">` |
| `st.markdown(unsafe_allow_html=True)` | `<div dangerouslySetInnerHTML>` 또는 react-markdown |
| `st.session_state["x"]` | Zustand / Jotai / React Context |
| `st.rerun()` | React 자동 리렌더 (state 변경) |
| `st.write_stream()` | `EventSource` + `useState` 누적 |
| `st.expander` | `<Disclosure>` (Headless UI) |
| `st.tabs` | `<Tabs>` (Radix UI) |
| `st.selectbox` | `<Select>` (Radix UI / shadcn) |
| `st.file_uploader` | `<input type="file">` + react-dropzone |
| `st.plotly_chart` | `<Plot>` (react-plotly.js) |
| `st.dataframe` | `<DataGrid>` (TanStack Table / AG Grid) |

### 15-2. 권장 라이브러리 스택
| 카테고리 | 추천 |
|---|---|
| **프레임워크** | **Vite + React 18** (또는 Next.js 14 App Router) |
| **상태 관리** | Zustand (단순) / Jotai (atomic) |
| **스타일** | Tailwind CSS + CSS Variables (HUD 토큰 그대로 이식) |
| **컴포넌트 베이스** | shadcn/ui (Radix UI 기반) — 커스터마이징 자유도 높음 |
| **차트** | Plotly.js (react-plotly.js) — 기존 차트 코드 재사용 가능 |
| **폼** | React Hook Form + Zod |
| **인증** | JWT는 그대로 + axios interceptor (auto refresh) |
| **SSE 스트리밍** | `@microsoft/fetch-event-source` (POST 지원) |
| **아이콘** | 기존 SVG 인라인 컴포넌트로 변환 (또는 Lucide-react) |
| **마크다운** | `react-markdown` + `remark-gfm` (테이블 지원) |
| **다국어** | `react-i18next` (영한 병기 시) |

### 15-3. 디자인 토큰 → Tailwind config
```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        hud: {
          bg:        'var(--hud-bg)',
          surface:   'var(--hud-surface)',
          border:    'var(--hud-border)',
          primary:   'var(--hud-primary)',
          text:      'var(--hud-text)',
          'text-dim':'var(--hud-text-dim)',
          green:     '#2D8A4E',
          orange:    '#E8A317',
          red:       '#C0392B',
          blue:      '#2980B9',
        },
      },
      fontFamily: {
        hud: ['Pretendard', 'Noto Sans KR', 'sans-serif'],
      },
      fontSize: {
        xs: '12px', sm: '13px', base: '15px', md: '16px',
        lg: '18px', xl: '20px', '2xl': '28px', '3xl': '36px',
      },
      borderRadius: {
        hud: '2px',  // HUD 거의 직각
      },
      letterSpacing: {
        hud: '0.08em',
        'hud-wide': '0.1em',
      },
      boxShadow: {
        glow: '0 0 10px rgba(249,167,13,0.27), 0 0 20px rgba(249,167,13,0.13)',
      },
    },
  },
};
```

### 15-4. 라우팅 구조 권장
```
/                       → Dashboard
/login                  → Login Page
/search                 → 기능 A (인원 검색)
/draft                  → 기능 B (문서 검색/작성)
/draft/internal         → 기능 B 내부 탭
/draft/external         → 기능 B 외부 탭
/onboarding             → 기능 C (AI 도우미)
/compliance             → 기능 D (법규 모니터링)
/compliance/updates     → 법규 업데이트 탭
/admin                  → 기능 E (인사 관리)
/admin/security         → 보안 탭
/equipment              → 기능 F (설비/공정)
/equipment/spc          → SPC 분석
/profile                → 프로필
```

### 15-5. 마이그레이션 우선순위
| Phase | 범위 | 예상 공수 |
|:---:|---|:---:|
| **1** | 디자인 토큰 + Tailwind config + 기본 컴포넌트 (Button/Input/Card/Badge) | 1주 |
| **2** | 레이아웃 (TopBar / Sidebar / RightPanel) + 라우터 + 인증 흐름 (JWT) | 1주 |
| **3** | 페이지 A (인원 검색) — 검색·정렬·조직도 | 2주 |
| **4** | 페이지 B (문서 작성) — 7포맷 다운로드·품질평가·diff | 2주 |
| **5** | 페이지 C (AI 도우미) — SSE 스트리밍·파일업로드·비전 | 2~3주 |
| **6** | 페이지 D (법규) — Plotly 차트·관세 시뮬·네트워크 | 2주 |
| **7** | 페이지 E (인사) — 다탭·CSV 내보내기·통계 | 2주 |
| **8** | 페이지 F (설비) — Nelson SPC·Plotly·CSV 업로드 | 2주 |
| **9** | Firebase Hosting 배포 + Cloud Run 백엔드 + Ollama 외부 호스팅 | 1주 |
| **합계** | | **15~17주** |

### 15-6. Firebase 배포 시 주의사항
| 컴포넌트 | 배포 대상 |
|---|---|
| **React 빌드 결과 (dist/)** | Firebase Hosting ✅ |
| **FastAPI 백엔드** | Cloud Run (또는 사내 서버 + nginx + SSL) |
| **Ollama LLM 엔진** | GPU 인스턴스 (Cloud Run with GPU / 사내 GPU 서버) |
| **ChromaDB** | Cloud Run + Persistent Volume 또는 GCS 마운트 |
| **SQLite (auth.db, audit.db 등)** | Cloud SQL (PostgreSQL 마이그레이션 권장) 또는 Persistent Disk |
| **CORS 설정** | `backend/config.py CORS_ORIGINS`에 `https://<your-app>.web.app` 추가 필수 |
| **세션 쿠키** | `secure: true; samesite: none` (HTTPS 필수) |

---

## 부록 A. UI 파일 라인 수 통계

| 파일 | 라인 | 역할 |
|---|---:|---|
| [hud_style.py](../../ui/hud_style.py) | **1,421** | 메인 CSS 인젝션 + 테마 함수 |
| [page_compliance.py](../../ui/page_compliance.py) | **2,144** | 법규 페이지 (4탭, 9 크롤러) |
| [page_onboarding.py](../../ui/page_onboarding.py) | **1,896** | AI 도우미 (스트리밍, 비전, SOP) |
| [page_equipment.py](../../ui/page_equipment.py) | **1,628** | 설비/공정 (SPC, 에러 검색) |
| [page_admin.py](../../ui/page_admin.py) | **1,314** | 인사 관리 (6탭) |
| [page_draft.py](../../ui/page_draft.py) | **940** | 문서 작성 (3탭, 7포맷) |
| [page_search.py](../../ui/page_search.py) | **690** | 인원 검색 (시맨틱) |
| [page_login.py](../../ui/page_login.py) | **610** | 로그인 + 비밀번호 변경 |
| [doc_search_panel.py](../../ui/doc_search_panel.py) | **608** | 문서 검색 패널 |
| [page_dashboard.py](../../ui/page_dashboard.py) | **266** | 대시보드 |
| [page_profile.py](../../ui/page_profile.py) | **199** | 프로필 |
| [hud_left_panel.py](../../ui/hud_left_panel.py) | **186** | 좌측 사이드바 |
| [hud_right_panel.py](../../ui/hud_right_panel.py) | **153** | 우측 시스템 분석 |
| [components.py](../../ui/components.py) | **127** | 공통 헬퍼 |
| [hud_layout.py](../../ui/hud_layout.py) | **104** | 레이아웃 매니저 |
| [hud_top_bar.py](../../ui/hud_top_bar.py) | **96** | 상단 상태 바 |
| [hud_center_panel.py](../../ui/hud_center_panel.py) | **92** | 중앙 패널 헬퍼 |
| [icons.py](../../ui/icons.py) | **84** | SVG 아이콘 16종 |
| [hud_tokens.py](../../ui/hud_tokens.py) | **77** | 디자인 토큰 정의 |
| [plotly_theme.py](../../ui/plotly_theme.py) | **44** | Plotly 테마 적용 |
| **합계** | **12,679** | |

## 부록 B. 디자인 시스템 핵심 자산 위치

| 자산 | 경로 |
|---|---|
| 디자인 토큰 (Python) | [ui/hud_tokens.py](../../ui/hud_tokens.py) |
| 메인 CSS 함수 | [ui/hud_style.py](../../ui/hud_style.py) |
| 로고 (다크) | [ui/assets/ajin_logo.svg](../../ui/assets/ajin_logo.svg) |
| 로고 (라이트) | [ui/assets/ajin_logo_light.svg](../../ui/assets/ajin_logo_light.svg) |
| 아이콘 정의 | [ui/icons.py](../../ui/icons.py) |
| Plotly 테마 | [ui/plotly_theme.py](../../ui/plotly_theme.py) |
| 레이아웃 매니저 | [ui/hud_layout.py](../../ui/hud_layout.py) |

## 부록 C. 영문 + 한글 라벨 사전

| 영문 | 한글 | 위치 |
|---|---|---|
| `CORE MODULES` | 핵심 모듈 | 사이드바 헤더 |
| `SYSTEM REGISTRY` | 시스템 등록 현황 | 사이드바 |
| `SECURITY LOG` | 보안 로그 | 사이드바 |
| `SYSTEM ANALYTICS` | 시스템 분석 | 우측 패널 |
| `DATA INGESTION` | 데이터 수집 | 우측 패널 |
| `QUERY RESULTS` | 검색 결과 | 중앙 패널 |
| `MATCHES` | 일치 (건) | 결과 헤더 |
| `AI SESSION MEMORY` | AI 세션 메모리 요약 | 중앙 하단 |
| `LLM ENGINE` | LLM 엔진 | 상단 바 |
| `VECTOR DB` | 벡터 DB | 상단 바 |
| `RBAC LEVEL` | 접근 권한 | 상단 바 |
| `JWT_ACTIVE` | 인증 활성 | 상단 바 |
| `ON-PREMISE` | 환경 | 상단 바 |
| `REALTIME` | 실시간 | 우측 패널 |

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-26 | 초안 작성 — Streamlit v3.5 기준 전면 문서화 |

---

**문서 작성**: Claude (Anthropic)
**검수 필요 항목**: React 마이그레이션 매핑(15-1, 15-2)은 권장안이며, 팀 정책에 따라 조정 필요
**다음 단계**: 본 문서를 기반으로 React 컴포넌트 라이브러리 (Storybook) 구축 → 페이지별 마이그레이션 시작
