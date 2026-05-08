---
name: ajin-design
description: Use this skill to generate well-branded interfaces and assets for AJIN (아진산업) AI Assistant, either for production or throwaway prototypes/mocks. Contains the v3.5 HUD design system — 60-30-10 monotone + gold, bilingual EN/KO labels, 2px corners, Pretendard typography, Apple Liquid Glass material treatments, and a working 3-Column HUD UI kit.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out of `assets/` and create static HTML files for the user to view. The single source of truth for tokens is `colors_and_type.css` — link it directly. The `ui_kits/web_app/` folder has reusable React components for the AJIN HUD shell (TopBar, LeftSidebar, RightPanel, Dashboard, Chat, Search, Login).

If working on production code, copy assets and read the rules in `README.md` to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions (always confirm: which page or module? Light/Dark/Auto? Right panel on/off?), and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

**Hard rules.**
- Never use emoji in UI. Status is conveyed by `●` / `○` glyphs and color.
- Every primary section uses `ENGLISH UPPERCASE` + `한글 부제` paired together.
- Corners are `2px`. Never `8px`/`12px` rounded.
- Gold (`#D89400` light / `#FCB132` dark) is reserved for CTA, active state, and hero metric values. Never decorative.
- Liquid Glass is for top bar, right panel, modals, and the chat composer only. The rest stays flat.
- Korean is primary reading language; English is structural label.
