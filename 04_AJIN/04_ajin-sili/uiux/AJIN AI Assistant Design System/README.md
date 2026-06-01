# AJIN AI Assistant — Design System

**Version**: v3.5
**Date**: 2026-04-26
**Project**: 제3회 KNU SILLI 경진대회 본선 진출 — Streamlit → React 마이그레이션 기준 자료
**Maintainer**: Design Systems Team

> A "HUD Command Center Dashboard" — an information-dense, industrial interface for **AJIN Industry's** internal AI assistant. Inspired by aerospace head-up displays, Bloomberg Terminal, and Iron Man HUD aesthetics, paired with **Apple Liquid Glass** material treatments per the latest direction.

---

## What is AJIN AI Assistant?

AJIN (아진산업) is a Korean industrial manufacturer (auto parts: CCH, OBC, bumper beam, doors, ball seats). The **AJIN AI Assistant** is an on-premise, RBAC-controlled, LLM-powered web app that serves engineers and managers across 29 departments. It's built as a 3-column HUD — left sidebar (modules + security log), center panel (the work surface), right panel (system analytics). Six "Core Modules":

| Code | Module | Purpose |
|------|--------|---------|
| A | 인원검색 (People Search) | FTS5 + ChromaDB semantic search across employees |
| B | 문서 작성 (Document Drafting) | Few-shot RAG + 7-format export (DOCX/ODT/PDF/XLSX/CSV/TXT/copy) |
| C | AI 업무 도우미 (AI Work Assistant) | Streaming chat (Qwen 3.5/EXAONE/Gemma 4/GPT-OSS/Nemotron) with vision |
| D | 법규 모니터링 (Compliance Monitor) | Risk scoring + Plotly Gantt + tariff simulator |
| E | 인사 관리 (HR Admin) | 6-tab admin (users/security/analytics/stats/tools) |
| F | 설비/공정 AI (Equipment/Process AI) | Nelson 8 Rules SPC + XGBoost mold lifespan |

The visual identity is **monotone beige + AJIN gold (`#D89400` light / `#FCB132` dark)**, near-square corners (2px radius), bilingual labels (`CORE MODULES (핵심 모듈)`), and a Pretendard / Noto Sans KR type system.

---

## Sources Used

- **Spec document** (provided by user, v3.5, 2026-04-26) — authoritative source for all design tokens, layout dimensions, and component definitions.
- **Apple Korea** (https://www.apple.com/kr/) — referenced per user note for "design language" inspiration.
- **Apple Liquid Glass** — referenced per user note as a treatment to layer onto AJIN HUD components.
- **VoltAgent/awesome-design-md** — design-context repo (browsed on demand).

> The user has not attached the AJIN codebase directly. All component recreations in `ui_kits/` are derived from the v3.5 spec text (line-by-line CSS variables, layout tokens, file inventory in Appendix A). Where the spec is silent, we follow Apple Liquid Glass conventions per user direction.

---

## Index — what's in this folder

| Path | Purpose |
|------|---------|
| `README.md` | This file |
| `SKILL.md` | Agent skill manifest (cross-compatible with Claude Code skills) |
| `colors_and_type.css` | All design tokens — color, type, spacing, shadow, glass — as CSS vars |
| `assets/` | Logos, brand SVGs, illustrations |
| `fonts/` | Webfont references (Pretendard, Noto Sans KR — loaded via CDN) |
| `preview/` | Per-token preview cards rendered in the Design System tab |
| `ui_kits/web_app/` | AJIN web app (3-column HUD) recreation — login, dashboard, chat |
| `ui_kits/web_app/index.html` | Interactive click-thru of the AJIN HUD |

---

## Content Fundamentals

**Voice & Tone.** Industrial, precise, bilingual. Korean is the primary reading language; English is the **structural label** that gives the interface its "command center" feel.

- **Pattern**: every primary section uses **English uppercase + Korean subtitle** stacked or inline.
  - `CORE MODULES` / `핵심 모듈`
  - `SYSTEM REGISTRY` / `시스템 등록 현황`
  - `SECURITY LOG` / `보안 로그`
  - `QUERY RESULTS` / `검색 결과`
- **Casing**: English labels are **ALL CAPS** with `letter-spacing: 0.08em–0.1em`. Korean retains natural casing with **no letter-spacing**.
- **Pronouns**: formal Korean (`-습니다`, `-십시오`). Avoid `너` / `당신`. The system addresses the user as a department member, not a friend. English copy uses imperative voice (`SEARCH`, `EXECUTE`, `EXPORT`).
- **Numbers and units**: spelled with units inline. `지연시간 124ms`, `QPS 8.4k`, `토큰 420`, `D-3`, `42% GPU`.
- **No emoji** anywhere in the UI. Status is conveyed by `●` / `○` glyphs, color, and English status keywords (`ON-LINE`, `WARNING`, `CRITICAL`, `OFFLINE`).
- **Status keywords** are short, English, and uppercase: `OK`, `FAIL`, `SYNC`, `LLM`, `AUTH`, `RBAC`. They are wrapped in brackets in log lines: `[AUTH] OK`, `[RBAC] L6`.
- **Versioning** is always present and visible: `v3.5 // KNU SILLI 2026`. The `//` separator is part of the look.
- **Vibe**: Solid, Reliable, Realtime, Industrial. The interface should feel like equipment, not an app.

**Sample copy strings**

```
ON-PREMISE · JWT_ACTIVE · LLM:QWEN3.5 ●
환경: ON-PREMISE  ·  인증: 활성  ·  엔진: QWEN 3.5
검색 결과                                일치: 12건
출처: ChromaDB        신뢰도: 87%
AI 세션 메모리 요약                    토큰: 420
SYS_MEM: 사용자가 8D 보고서 생성을 요청...
> FTS5/SQL:  SELECT processes FROM SPC WHERE anor...
```

---

## Visual Foundations

**Color philosophy — 60/30/10.**
- **60% base**: warm beige whites (light) or deep navy (dark) — `#FAF8F5` / `#0A0E14`.
- **30% neutral**: borders, sidebars, secondary text — `#F0EBE3` / `#111820`, `#D6CFC3` / `#2A2520`.
- **10% accent**: AJIN gold — `#D89400` (light) / `#FCB132` (dark). Reserved for **CTA, active states, and key metric values only**. Never used for decoration.

**Semantic colors** are shared across modes: `#2D8A4E` success, `#E8A317` warning, `#C0392B` danger, `#2980B9` info. These never appear as backgrounds large enough to compete with the gold.

**Typography.** A single family — **Pretendard** with **Noto Sans KR** fallback — covers display, body, mono, and Korean. Sizes step in 2px increments from 12 → 36px. Weights: 400 / 600 / 700. The mono-feel comes from letter-spacing on English labels, not a separate mono font.

**Spacing & layout.**
- 3-column shell: `240px` left + flex center + `280px` right, top bar `52px`.
- Card padding `16px`, section gap `20px`.
- Section hierarchy: **page title 28px → section 18px → card 16px → body 15px**.

**Corners.** `2px` radius everywhere. Square enough to read as industrial; soft enough to avoid harshness.

**Borders.** Single-pixel hairlines in muted neutrals. Dashed (`1px dashed`) for memory/separator zones. Cards rely on **border + flat surface**, not shadow, in light mode.

**Shadows.** No shadow in light mode; **gold glow** in dark mode only:
```
--hud-primary-glow: 0 0 10px #FCB13244, 0 0 20px #FCB13222;
```
Reserved for active CTAs and active module cards.

**Liquid Glass treatment** (per user direction).
- Apply to: top bar, right system-analytics panel, focused metric cards, modal scrims, and the chat composer.
- Recipe:
  ```
  background: color-mix(in oklab, var(--hud-surface) 55%, transparent);
  backdrop-filter: blur(24px) saturate(140%);
  -webkit-backdrop-filter: blur(24px) saturate(140%);
  border: 1px solid color-mix(in oklab, var(--hud-border) 65%, transparent);
  box-shadow:
    inset 0 1px 0 color-mix(in oklab, white 18%, transparent),
    0 1px 0 color-mix(in oklab, black 8%, transparent);
  ```
- Glass surfaces still respect `2px` radius — they remain industrial, not iOS-soft.

**Imagery.** No stock photography. The assistant is text-and-data first. When images appear (login splash, error states), they're warm-toned, slightly grainy, and either monochrome or beige-tinted. No saturated brand photography.

**Animation.**
- Hovers: 200ms ease-out. Backgrounds shift to `rgba(200,138,0,0.05)` on the sidebar logo zone; buttons gain border + text gold.
- Metric cards: `transform: scale(1.0 → 1.02)` over 300ms ease-out.
- Streaming indicator: pulsing gold dot, 1.6s sine.
- No bounces, no spring overshoot. Movement is "instrument" not "playful."

**Hover / press.**
- Hover (secondary): border + text turn gold.
- Hover (primary): bg shifts to `#E89E1A`.
- Press: no shrink — instead, a 1px inset gold ring (`box-shadow: inset 0 0 0 1px var(--hud-primary)`).
- Disabled: `opacity: 0.5; cursor: not-allowed`.

**Transparency & blur.** Blur is a **functional accent**, not decoration:
- Top bar floats over content.
- Right panel is glass over the page.
- Modals dim the page with a 60% navy scrim, then a glass card sits on top.

**Layout rules.**
- Top bar is **sticky** at all viewports.
- Left sidebar collapses below 768px.
- Right panel hides below 768px **and** can be toggled via `[HIDE]` / `[SYS]`.
- Center panel reflows from `4 / 0.8` ratio to `1` (full width) when right panel is off.

---

## Iconography

**Approach.** Stroke-based, 24×24 viewBox, `stroke-width: 1.5`, `stroke-linecap: round`. Single-color via `currentColor`. The set is **16 custom SVGs** defined in `ui/icons.py` in the source codebase.

**Catalog**: `dashboard`, `employee`, `documents`, `onboarding`, `compliance`, `admin`, `equipment`, `internal`, `external`, `login`, `password`, `email`, `report`, `search`, `download`, `chart`, `analytics`, `toggle_panel`.

**Status glyphs** (used in place of icons in many places):
- `●` filled circle — ON, OK, success
- `○` open circle — OFF, inactive
- `▣` filled square — active module
- `▢` open square — inactive module
- `─ ─ ─` dashed rule — memory/separator zones

**No emoji.** Anywhere. Status uses Unicode geometric shapes only.

**Substitution.** The original codebase's 16 SVGs are not yet imported here. We substitute **Lucide** (https://lucide.dev) loaded from CDN — same `1.5` stroke, same `round` linecap, same 24×24 viewBox. **Flagged for the user**: if you want pixel-fidelity, please share `ui/icons.py` and we'll inline the originals.

**Material Symbols.** The spec mentions `'Material Symbols Rounded'` for "some icons." We don't import these by default; if you need them, add `<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded" rel="stylesheet">` to your page.

**Logo.** AJIN provides theme-aware logos:
- `assets/ajin_logo_dark.svg` — full lockup for dark backgrounds (white "AJIN INDUSTRIAL CO., LTD." wordmark + gold symbol)
- `assets/ajin_logo_light.svg` — full lockup for light backgrounds (`#1A1A1A` wordmark + gold symbol)
- `assets/ajin_logo_official.png` — original PNG (transparent background, dark wordmark — use only on light surfaces)
- `assets/ajin_symbol.svg` — symbol mark only (the gold tri-arc circle), use at small sizes (≤48px)

---

## Caveats & Substitutions

| Asset | Status | Action |
|-------|--------|--------|
| AJIN logo SVGs | Reconstructed from spec | Please share originals |
| 16-icon SVG set (`ui/icons.py`) | Substituted with Lucide CDN | Please share `ui/icons.py` |
| Pretendard webfont | Loaded via jsDelivr CDN | OK as-is |
| Noto Sans KR | Loaded via Google Fonts | OK as-is |
| Page screenshots | Not provided; recreated from spec text | Visual fidelity may differ from production |

---

## Index of Sub-folders

- `assets/` — logos, illustrative SVGs
- `fonts/` — webfont CSS (CDN-linked)
- `preview/` — per-token Design System cards (registered)
- `ui_kits/web_app/` — interactive AJIN HUD recreation
