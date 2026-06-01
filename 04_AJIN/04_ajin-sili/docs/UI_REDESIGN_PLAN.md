# AJIN UI 재설계 구현 계획 — Design System v3.5 + Neural Expressive 통합

**작성일**: 2026-05-27
**대상 본선**: 2026-06-10~11 (KNU SILLI 2026) — D-15
**근거 자료**: `uiux/AJIN AI Assistant Design System/` (v3.5, 2026-04-26)
**시연 범위**: 웹(데스크탑 1280+) + 태블릿(641-1024) + 모바일(≤640) 3-tier 반응형

---

## 0. Executive Summary

### 도입 결정 사항

| 항목 | 결정 |
|---|---|
| Visual Identity | **HUD Command Center** (Bloomberg + Iron Man HUD + Apple Liquid Glass) |
| Color | 60/30/10 — beige base + neutral border + **AJIN gold** (`#D89400` light / `#FCB132` dark) |
| Corners | **2px** (HUD industrial) — Neural overlay 활성 시 일부 pill (9999px) |
| Typography | AJIN Sans (브랜드 폰트) → Pretendard → Noto Sans KR fallback |
| Bilingual | EN uppercase + KO subtitle (`CORE MODULES / 핵심 모듈`) |
| No emoji | 상태는 `●○▣▢` glyph + 색상으로 표현 |
| Liquid Glass 적용 | top bar / right panel / modals / chat composer (제한적) |
| Neural Expressive | `data-neural="on"` 토글 — 향상된 카드/orb/pill (선택 활성) |

### 현재 적용 진척률 (추정)

| 영역 | 진척 | 보강 필요 |
|---|---|---|
| tokens.css (v3.5 base) | 95% | weight ladder 100-900 확장 (현재 400-700) |
| theme.css | 85% | Neural overlay 미통합 |
| lg-theme.css (Liquid Glass) | 80% | top bar/right panel 일관성 검증 |
| components.css | 70% | 카드/buttons/inputs 표준화 |
| breakpoints.css v4.4 | 90% | 태블릿(641-1024) slim sidebar 미구현 |
| responsive-overrides.css | 60% | 모바일 drawer + bottom nav 추가 필요 |
| Neural Expressive overlay | 30% | `ui_kits/neural-expressive.css` (683 lines) 통합 미완료 |

### 핵심 작업 5 Phase

1. **Phase 1** (P0, D-7): 디자인 토큰 일치 검증 + weight ladder 확장 + Neural overlay 통합
2. **Phase 2** (P0, D-5): 모바일 (≤640px) — Drawer + Bottom Nav + responsive overrides
3. **Phase 3** (P1, D-3): 태블릿 (641-1024px) — Slim sidebar + Right panel toggle
4. **Phase 4** (P1, D-3): 페이지별 컴포넌트 마이그레이션 (login/chat/dashboard/search 우선)
5. **Phase 5** (P2, 본선 후): Neural Expressive 적용 페이지 확장 + 시각 회귀 테스트

---

## 1. 현재 상태 정밀 분석

### 1.1 styles/ 구조 (7,897 lines 총합)

| 파일 | 줄수 | 역할 |
|---|---|---|
| `tokens.css` | 243 | v3.5 tokens (color/type/spacing/glass) |
| `breakpoints.css` | 65 | v4.4 4단계 break (480/640/1024/1280) |
| `theme.css` | 1,898 | 페이지/모듈별 핵심 스타일 |
| `components.css` | 3,462 | 카드/buttons/inputs 컴포넌트 클래스 |
| `lg-theme.css` | 1,976 | Liquid Glass 효과 |
| `responsive-overrides.css` | 216 | 모바일/태블릿 override |
| `animations.css` | 37 | streaming-pulse / fade-in / scale-on-hover |

### 1.2 라우트 페이지 18개 (frontend/src/routes/)

| 페이지 | 역할 | HUD 적용 | Glass | Neural |
|---|---|---|---|---|
| `_shell.tsx` | 3-column shell | ✅ | ✅ TopBar | 부분 |
| `login.tsx` | 로그인 splash | ✅ | ✅ | ❌ |
| `dashboard.tsx` | 위젯 + 알람 | ✅ | ✅ | 부분 |
| `chat.tsx` | AI 챗 (Module C) | ✅ | ✅ composer | 부분 |
| `draft.tsx` | 문서 작성 (Module B) | ✅ | 부분 | ❌ |
| `search.tsx` | 사람/문서 검색 (Module A) | ✅ | 부분 | ❌ |
| `compliance.tsx` + 3 sub | 법규 (Module D) | ✅ | ✅ | ❌ |
| `equipment.tsx` + 1 sub | 설비/SPC (Module F) | ✅ | ✅ | ❌ |
| `admin.tsx` / `management.tsx` | 관리 (Module E) | ✅ | 부분 | ❌ |
| `profile.tsx` / `profile-llm` / `profile-notifications` | 프로필 | ✅ | ❌ | ❌ |
| `onboarding.tsx` | 신입 가이드 | ✅ | 부분 | ❌ |

### 1.3 핵심 컴포넌트 디렉토리 (frontend/src/components/)

- `chat/` — ModelSelect, CRAGVerdictBanner, ...
- `employee/` — DigitalEmployeeBadge, EmployeeDetailDrawer, ProfilePhotoUploadModal
- `equipment/` — EquipmentLineVisual (701 lines), EquipmentHoverCard, EquipmentDetailDrawer
- `dashboard/` — WidgetGrid + personas
- `common/`, `ui/`, `chart/`, `compliance/`

---

## 2. 디자인 시스템 핵심 원칙 (uiux/ → frontend/ 매핑)

### 2.1 Color (60/30/10)

| 토큰 | dark (HUD default) | light | 현재 frontend |
|---|---|---|---|
| `--hud-bg` (60%) | `#0A0E14` | `#FAF8F5` | ✅ 동일 |
| `--hud-surface` (60%) | `#111820` | `#FFFFFF` | ✅ |
| `--hud-border` (30%) | `#2A2520` | `#D6CFC3` | ✅ |
| `--hud-text` (30%) | `#E8E1D5` | `#2C241A` | ✅ |
| `--hud-text-dim` | `#D5CFC5` (WCAG AAA 8.5:1) | `#5C4E3C` | ✅ |
| **`--hud-primary` (10% gold)** | **`#FCB132`** | **`#D89400`** | ✅ |
| `--hud-primary-glow` | gold glow (dark only) | — | ✅ |

→ tokens.css 의 색상 토큰은 디자인 시스템과 **완전 일치**. 변경 불필요.

### 2.2 Typography

| 토큰 | 값 | 적용 위치 |
|---|---|---|
| `--hud-font` | `AJIN Sans` → Pretendard → Noto Sans KR | 본문 + 헤딩 |
| `--hud-font-mono` | 동일 family (letter-spacing 으로 mono 느낌) | code, version line |
| `--fs-xs ~ --fs-3xl` | 12 / 13 / 15 / 16 / 18 / 20 / 28 / 36px | ✅ |
| `--ls-wide / wider / widest` | `0.08 / 0.10 / 2px` (EN labels only) | ✅ |
| weight ladder | **100-900** (현재 frontend: 400-700) | ⚠️ **확장 필요** |

### 2.3 Spacing & Layout

| 토큰 | 값 | 현재 |
|---|---|---|
| `--top-bar-height` | 52px (desktop) / 56px (mobile) | ✅ |
| `--left-panel-width` | 240px (desktop) / 0 (mobile drawer) | ✅ |
| `--right-panel-width` | 280px (desktop) / 0 (mobile) | ✅ |
| `--card-radius` | **2px** (HUD industrial) | ✅ |
| `--radius-pill` | 9999px (Neural pill) | ⚠️ Neural 활성 시만 |
| `--card-padding` | 16px → 14px (mobile) | ✅ |
| `--section-gap` | 20px → 14px (mobile) | ✅ |
| `--bottom-nav-h` | 60px (mobile) | ⚠️ 컴포넌트 미구현 |

### 2.4 Liquid Glass Recipe

```css
.glass {
  background: color-mix(in oklab, var(--hud-surface) 55%, transparent);
  backdrop-filter: blur(24px) saturate(140%);
  -webkit-backdrop-filter: blur(24px) saturate(140%);
  border: 1px solid color-mix(in oklab, var(--hud-border) 65%, transparent);
  box-shadow:
    inset 0 1px 0 color-mix(in oklab, white 18%, transparent),
    0 1px 0 color-mix(in oklab, black 8%, transparent);
}
```

→ **적용 위치 한정 (디자인 룰)**:
- ✅ Top bar (`_shell.tsx` 상단)
- ✅ Right panel (system analytics)
- ✅ Modals (login splash, photo upload, employee detail drawer)
- ✅ Chat composer (`chat.tsx` 하단 입력)
- ❌ **나머지 surface 는 flat 유지** (industrial 미학 보존)

### 2.5 Neural Expressive (선택 활성)

`[data-neural="on"]` root attribute 토글로 활성. 주요 컴포넌트:

| 클래스 | 용도 |
|---|---|
| `.ne-pill` | 64px height pill composer (chat 입력) |
| `.ne-card` | 22px radius generative response card (chat 답변) |
| `.ne-card.spectrum` | 상단 3px gold gradient bar |
| `.ne-card.user` | 사용자 메시지 (light gold bg) |
| `.ne-keyfact` | 26px ombre key-fact (사원증 KPI 등) |
| `.ne-chip` | 38px height suggestion chip |
| `.ne-orb` | Gemini-style 56px brand orb (브랜드 마크) |
| `.ne-brief-grid` | 12-col dashboard tile grid |
| `.ne-thinking-dots` | LLM 대기 중 3-dot bounce |

→ Phase 5 에서 **chat, dashboard 만** 우선 활성. 나머지 페이지는 v3.5 HUD 유지.

---

## 3. Phase 별 작업 (5 Phase)

### Phase 1 (P0, D-7 = 2026-06-04 마감) — 토큰 + Neural overlay 통합

**목표**: 디자인 시스템 파일들을 frontend/src/styles/ 와 정합 + Neural overlay 통합.

| Task | 파일 | 변경 |
|---|---|---|
| 1.1 weight ladder 확장 | `tokens.css` | 100-900 모두 `@font-face` 등록 |
| 1.2 Neural overlay 통합 | 신규 `styles/neural.css` | `ui_kits/neural-expressive.css` 683 lines 복사 + 경로 보정 |
| 1.3 import wiring | `index.css` | `import './styles/neural.css'` 추가 |
| 1.4 root toggle | `App.tsx` | URL `?neural=1` 또는 settings store 로 `<html data-neural="on">` |
| 1.5 검증 | DevTools | `[data-neural="on"]` 적용 시 chat 의 ne-pill 동작 확인 |

**예상 PR**: `feat/ui-design-tokens-neural` (~+800 / -50)

### Phase 2 (P0, D-5 = 2026-06-06 마감) — 모바일 (≤640px)

**목표**: iOS/Android 브라우저에서 HUD 미학 유지 + Drawer + Bottom Nav.

| Task | 파일 | 변경 |
|---|---|---|
| 2.1 Drawer 컴포넌트 | `components/shell/MobileDrawer.tsx` 신규 | 좌측 메뉴 off-canvas, swipe 닫기 |
| 2.2 Bottom Nav | `components/shell/MobileBottomNav.tsx` 신규 | 5 탭 (Dashboard/Chat/Search/Compliance/Profile), 60px height, Liquid Glass |
| 2.3 Top bar 축소 | `_shell.tsx` | 모바일은 56px (safe-area) + 햄버거 아이콘 |
| 2.4 Right panel 강제 숨김 | `responsive-overrides.css` | `--right-panel-width: 0` (이미 적용됨) |
| 2.5 fluid type | `tokens.css` | `clamp()` 적용 — 본문 15→16px (+1px bump) |
| 2.6 Touch target ≥44px | components | 버튼/링크 min-height 44px 강제 |

**예상 PR**: `feat/ui-mobile-shell` (~+500 / -100)

### Phase 3 (P1, D-3 = 2026-06-08 마감) — 태블릿 (641-1024px)

**목표**: iPad 가로/세로 + Surface Pro 에서 균형있는 3-column.

| Task | 파일 | 변경 |
|---|---|---|
| 3.1 Slim sidebar | `responsive-overrides.css` | left panel 64px (icon-only) + hover expand |
| 3.2 Right panel toggle | `_shell.tsx` | `[HIDE]/[SYS]` 버튼 활성, default off |
| 3.3 Tablet break | `breakpoints.css` | `@media (min-width: 641px) and (max-width: 1024px)` 블록 채움 |
| 3.4 grid reflow | `dashboard.tsx` | 12-col → 6-col (tablet) → 1-col (mobile) |

**예상 PR**: `feat/ui-tablet-layout` (~+300 / -80)

### Phase 4 (P1, D-3 = 2026-06-08 마감) — 페이지별 마이그레이션

**목표**: 4개 핵심 페이지에 v3.5 HUD + Liquid Glass 일관 적용.

| 페이지 | 우선순위 | 작업 |
|---|---|---|
| `login.tsx` | P0 | splash glass card + AJIN orb 적용 |
| `chat.tsx` | P0 | Neural pill composer + ne-card 응답 (선택 활성 시) |
| `dashboard.tsx` | P0 | 위젯 그리드 12-col + glass right panel |
| `search.tsx` | P1 | 결과 카드 2px radius + CRAGVerdictBanner |
| `compliance.tsx` | P1 | 알람 카드 + Gantt glass |
| `equipment.tsx` | P2 | LineVisual 유지, Drawer 만 글래스 |
| `profile.tsx` | P2 | 사원증 + LLM/notifications 탭 |

**예상 PR**: `feat/ui-page-migration-core` (~+1200 / -400)

### Phase 5 (P2, 본선 후 D+7) — Neural 확장 + 회귀 테스트

**목표**: Neural 활성화 시 시연 데모 강화 + 시각 회귀 자동화.

| Task | 도구 | 변경 |
|---|---|---|
| 5.1 Neural 토글 UI | settings 페이지 | `data-neural="on"` checkbox |
| 5.2 chat ne-pill 활성 | chat.tsx | composer 만 Neural 변형 |
| 5.3 dashboard ne-brief | dashboard.tsx | 위젯 grid 변형 |
| 5.4 Playwright 회귀 | `scripts/visual_regression.spec.ts` | 18 페이지 screenshot 비교 |
| 5.5 WCAG AAA contrast | axe-playwright | dim text 8.5:1 검증 |

---

## 4. 모바일/태블릿 Break Point 전략

```css
/* tokens.css 의 4단계 break (이미 적용됨) */
--bp-sm:  480px;
--bp-md:  640px;
--bp-lg: 1024px;
--bp-xl: 1280px;
```

| Break | 적용 |
|---|---|
| `≤480px` | 모바일 small (iPhone SE) — 16px safe-area, 14px card padding |
| `≤640px` | 모바일 (iPhone Pro) — Drawer + Bottom Nav 활성 |
| `641-1024px` | 태블릿 (iPad, Galaxy Tab) — Slim 64px sidebar + right toggle |
| `1025-1280px` | 데스크탑 narrow — 3-column 표준 |
| `>1280px` | 데스크탑 wide — 3-column + max-width 1440px 제한 |

### 모바일 추가 컴포넌트 (Phase 2 신규)

```
frontend/src/components/shell/
├── MobileDrawer.tsx       (좌측 메뉴 off-canvas)
├── MobileBottomNav.tsx    (5 탭 bottom nav, 60px, glass)
└── MobileTopBar.tsx       (56px, 햄버거 + 검색 아이콘 + AJIN orb)
```

---

## 5. Neural Expressive 활성 정책

### 5.1 토글 위치
- URL query: `?neural=1`
- localStorage: `ajin-ui-neural=on`
- Settings 페이지: 사용자 토글 (Phase 5)

### 5.2 적용 우선순위

| 페이지 | 활성 추천 | 비고 |
|---|---|---|
| `chat.tsx` | ✅ 활성 | ne-pill composer + ne-card 응답 카드 (LLM 차단 시 ambiguous 표시도 ne-card 적용) |
| `dashboard.tsx` | ✅ 활성 | ne-brief tile grid + ne-orb 브랜드 마크 |
| `search.tsx` | ⚠️ 부분 | ne-chip 으로 검색 필터 (결과 카드는 HUD 유지) |
| `login.tsx` | ⚠️ 부분 | ne-orb 만 (splash 글래스는 HUD) |
| `compliance.tsx` | ❌ 미활성 | 산업 데이터 — HUD 유지 |
| `equipment.tsx` | ❌ 미활성 | SPC 산업 데이터 — HUD 유지 |
| `admin.tsx` | ❌ 미활성 | 관리 화면 — HUD 유지 |
| `profile.tsx` | ⚠️ 부분 | ne-orb 만 (사원증은 v3.5 카드) |

### 5.3 시연 데모 시나리오 (본선)

본선에서 **Neural 활성** 상태로 시연 시:
- `/chat` 첫 진입 → 큰 `ne-greet` ("안녕하세요, 김아진님") + ombre highlight
- pill composer 에 검색어 입력 → glow ring 활성 + send 버튼 amber 강조
- AI 응답이 `ne-card` 형식 — spectrum 상단 + key-fact + 인용 출처 cards
- D 알람 발생 시 ne-card 위에 CRAGVerdictBanner 충돌 검증 필요

---

## 6. 컴포넌트 마이그레이션 매핑 표

### 6.1 page → 적용 컴포넌트

| 페이지 | HUD 카드 | Liquid Glass | Neural | 비고 |
|---|---|---|---|---|
| `login.tsx` | login-card (2px radius) | splash-bg | ne-orb | login splash 글래스 |
| `_shell.tsx` (TopBar) | — | ✅ glass | ne-orb (옵션) | sticky top |
| `_shell.tsx` (LeftSidebar) | sidebar-item | — | — | flat (industrial) |
| `_shell.tsx` (RightPanel) | metric-card | ✅ glass | — | system analytics |
| `dashboard.tsx` (위젯) | widget-card | — | ne-brief (옵션) | 12-col grid |
| `dashboard.tsx` (알람) | alarm-card | — | ne-card.spectrum (옵션) | severity 색상 |
| `chat.tsx` (composer) | — | ✅ glass | ne-pill (옵션) | sticky bottom |
| `chat.tsx` (messages) | message-card | — | ne-card (옵션) | user/ai 분기 |
| `search.tsx` (결과) | result-card (2px) | — | — | partial 표시 |
| `compliance.tsx` (알람) | compliance-card | — | — | grade 색상 |
| `equipment.tsx` (시뮬레이션) | EquipmentLineVisual | — | — | 기존 유지 |
| `profile.tsx` (사원증) | DigitalEmployeeBadge | — | — | 3D flip 유지 |

### 6.2 신규 vs 기존 컴포넌트 매핑

| 디자인 시스템 클래스 | 현재 frontend 컴포넌트 | 작업 |
|---|---|---|
| `.glass` | `lg-theme.css` 의 `.aj-glass` | 두 이름 alias |
| `.metric-card` | `dashboard.tsx` 인라인 | 클래스 추출 |
| `.label-en` + `.label-ko` | scattered | utility 클래스 일관 적용 |
| `.ne-pill` | `chat.tsx` composer | wrap toggle |
| `.ne-card` | `chat.tsx` message | wrap toggle |
| `.ne-brief` | `dashboard.tsx` widget | wrap toggle |
| `.ne-orb` | 신규 — TopBar + login | 추가 |

---

## 7. 시각 회귀 + 검증

### 7.1 자동화 (Phase 5)

| 도구 | 검증 |
|---|---|
| Playwright + percy/chromatic | 18 페이지 screenshot 비교 (Light/Dark × Desktop/Tablet/Mobile = 6 variant per page) |
| axe-core | WCAG 2.1 AA + AAA contrast (dim text 8.5:1) |
| Lighthouse | Performance ≥80, A11y ≥95, Best Practices ≥90 |
| `scripts/visual_regression.spec.ts` 신규 | 18 페이지 + 3 viewport × 2 theme = **108 screenshots** baseline |

### 7.2 수동 체크리스트 (D-Day 직전)

- [ ] 모바일 Safari (iPhone) — Drawer 스와이프 + Bottom Nav touch
- [ ] 모바일 Chrome (Android) — Liquid Glass backdrop-filter 동작
- [ ] iPad 가로 (1024px) — Slim sidebar + Right panel toggle
- [ ] iPad 세로 (768px) — Bottom Nav (가로 모드와 분기)
- [ ] 데스크탑 1280px+ — 3-column 표준
- [ ] Dark mode → Light mode 토글 (모든 페이지)
- [ ] Neural 활성 → 비활성 토글 (chat, dashboard)
- [ ] CRAG ambiguous/incorrect 배너 표시 (PR #13 통합)

---

## 8. 일정 (D-15 본선 고려)

| 일정 | 작업 | PR |
|---|---|---|
| **D-12 (2026-05-30)** | Phase 1 — 토큰 + Neural overlay | `feat/ui-design-tokens-neural` |
| **D-9 (2026-06-02)** | Phase 2 — 모바일 Drawer + Bottom Nav | `feat/ui-mobile-shell` |
| **D-7 (2026-06-04)** | Phase 3 — 태블릿 Slim sidebar | `feat/ui-tablet-layout` |
| **D-5 (2026-06-06)** | Phase 4 — login/chat/dashboard 마이그레이션 | `feat/ui-page-migration-core` |
| **D-3 (2026-06-08)** | Phase 4 후속 — search/compliance/equipment | `feat/ui-page-migration-modules` |
| **D-1 (2026-06-10)** | 시연 리허설 + 회귀 검증 | (수동) |
| **D+1 ~ D+7** | Phase 5 — Neural 확장 + Playwright 회귀 자동화 | `feat/ui-neural-and-vrt` |

### 의존성

- Phase 1 → Phase 4 (토큰 정렬 후 페이지 마이그레이션)
- Phase 2 + 3 → Phase 4 (반응형 토큰 + slim sidebar 가 페이지 적용 base)
- Phase 5 는 본선 후 (회귀 자동화 + Neural 확장)

---

## 9. 리스크 + 완화책

| 리스크 | 영향 | 완화 |
|---|---|---|
| AJIN Sans 폰트 파일 경로 (`__________-1Thin.otf`) 미공개 | weight 100-300 미적용 → 본문은 정상 (400+ 만 사용) | Phase 1: 기존 weight 만 적용 + Pretendard fallback 보존 |
| Liquid Glass backdrop-filter — 구형 Android Chrome 미지원 | 시각 손실 (글래스 → flat surface) | 자동 fallback (CSS @supports) — 이미 lg-theme.css 에 분기 있음 |
| Neural overlay 통합 시 chat.tsx 기존 CRAGVerdictBanner 와 충돌 | `ne-card` 가 banner 위치 침범 가능 | Phase 5 시 z-index + margin 조정 검증 |
| 모바일 Drawer + Bottom Nav 시각 회귀 | 데스크탑에 영향 X 검증 필요 | `@media (max-width: 640px)` 명시적 분기 |
| 태블릿 (641-1024px) 별도 디자인 spec 미존재 | 데스크탑 축소 → 태블릿으로 fallback 시 좌측 240px 너무 큼 | 본 PR §3 의 64px slim 적용 |
| weight ladder 100-900 추가 → 폰트 파일 크기 증가 (~2MB) | 초기 로드 느림 | font-display: swap + 100/200/800/900 lazy 옵션 |
| 18 페이지 마이그레이션 — 본선 D-15 일정 부족 | 일부 페이지 미적용 | Phase 4 우선순위 P0 (login/chat/dashboard) → P1 → P2 단계화 |
| Playwright VRT 자동화 시간 부족 | 본선 후 진행 — D+1~D+7 | Phase 5 deferred (시연 후 안정화) |

---

## 10. 의사결정 포인트 (사용자 confirm 필요)

본 계획 승인 전 사용자 결정 필요:

1. **Neural Expressive 활성 범위**: chat + dashboard 만 (권장) vs 전체 페이지 vs 토글로 사용자 선택 노출?
2. **weight ladder 100-900 확장**: 폰트 파일 크기 증가 허용? (약 2MB 추가)
3. **Bottom Nav 5 탭 선정**: Dashboard/Chat/Search/Compliance/Profile (권장) vs 다른 조합?
4. **Phase 5 (Playwright VRT)**: 본선 후 (권장) vs 본선 직전 D-1 까지?
5. **AJIN Sans 폰트 파일**: 정확한 경로 + 라이센스 확인 (현재 `__________` 익명화 파일명)
6. **Liquid Glass 의 backdrop-filter fallback** — Android Chrome 구형 (60%+ 점유) 정상 표시 확인 필수?

---

## 11. 참고 자료

### 11.1 디자인 시스템 (uiux/)
- `uiux/AJIN AI Assistant Design System/README.md` — 핵심 가이드 (197 lines)
- `uiux/AJIN AI Assistant Design System/SKILL.md` — agent 가이드
- `uiux/AJIN AI Assistant Design System/colors_and_type.css` — 토큰 248 lines
- `uiux/AJIN AI Assistant Design System/ui_kits/neural-expressive.css` — Neural overlay 683 lines
- `uiux/AJIN AI Assistant Design System/preview/*.html` — 컴포넌트 preview
- `uiux/AJIN AI Assistant Design System/screenshots/*.png` — Light pad / Mobile mockup 25개

### 11.2 frontend 현재 styles
- `frontend/src/styles/tokens.css` (243)
- `frontend/src/styles/theme.css` (1,898)
- `frontend/src/styles/components.css` (3,462)
- `frontend/src/styles/lg-theme.css` (1,976)
- `frontend/src/styles/breakpoints.css` (65)
- `frontend/src/styles/responsive-overrides.css` (216)
- `frontend/src/styles/animations.css` (37)

### 11.3 외부 참조
- Apple Liquid Glass — https://developer.apple.com/design/human-interface-guidelines/
- Apple Korea — https://www.apple.com/kr/
- Lucide icons — https://lucide.dev (현재 frontend 에 통합)
- Pretendard — https://github.com/orioncactus/pretendard
- Noto Sans KR — Google Fonts CDN

---

**다음 단계**: §10 의 6개 의사결정 사항 confirm 후 Phase 1 (`feat/ui-design-tokens-neural`) 작업 시작.
