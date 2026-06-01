# AJIN Web App — UI Kit

Interactive recreation of the **AJIN AI Assistant 3-Column HUD** with **Apple Liquid Glass** material treatments layered onto the top bar, right panel, and modal scrims per the latest direction.

## Files

- `index.html` — full click-thru shell (login → dashboard → chat → search)
- `theme.jsx` — globals + glass utilities
- `TopBar.jsx` — sticky 52px Liquid Glass status bar
- `LeftSidebar.jsx` — logo, user card, theme selector, modules nav, registry, security log
- `RightPanel.jsx` — system analytics: GPU gauge, latency/QPS, ingestion bars
- `Login.jsx` — bilingual sign-in with password-policy live checklist
- `Dashboard.jsx` — 4 metric cards + 6 module cards
- `Chat.jsx` — AI work assistant with streaming bubble, memory rail, sticky composer
- `Search.jsx` — FTS5/SQL bar + query result cards
- `Icons.jsx` — inlined 1.5-stroke icon set

The kit is presentation-only. All actions are local state; no network.
