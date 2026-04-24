```markdown
# Design System Specification: Editorial Clinical Excellence

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Digital Sanctuary."** 

In a medical context, clarity is a form of care. This system moves beyond the cold, sterile nature of traditional healthcare software and instead embraces a high-end editorial aesthetic. We achieve this by rejecting "template" layouts in favor of intentional asymmetry, generous negative space, and a sophisticated layering of materials. 

The goal is to provide a sense of "High-Tech Serenity"—where the UI feels like a premium, responsive physical space rather than a digital interface. We prioritize information hierarchy through scale and tonal depth, ensuring that both medical professionals in high-pressure environments and patients seeking reassurance find immediate, intuitive clarity.

---

## 2. Colors & Surface Philosophy
The palette is rooted in clinical purity but elevated through a systematic approach to depth.

### The "No-Line" Rule
**Explicit Instruction:** Use of 1px solid borders for sectioning or containment is strictly prohibited. 
Boundaries must be defined solely through background color shifts. For example, a `surface-container-low` section should sit on a `surface` background to define its edge. This creates a more organic, seamless transition that mimics natural light and shadow.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked materials (like fine vellum or frosted glass).
- **Surface (Base):** `#f9f9fb` — The primary canvas.
- **Surface-Container-Lowest:** `#ffffff` — Used for the most elevated "top-tier" cards or active interactive elements.
- **Surface-Container-High:** `#e8e8ea` — Used for recessed areas like search bars or inactive background containers.

### The "Glass & Gradient" Rule
To inject "soul" into the clinical aesthetic:
- **Glassmorphism:** Use semi-transparent versions of `surface-container-lowest` with a `backdrop-filter: blur(20px)` for floating navigation bars and modal overlays.
- **Signature Gradients:** Use a subtle linear gradient (from `primary` #004e9f to `primary_container` #0066cc) on primary CTAs and hero headers. This prevents the "flat" look and adds a premium, high-tech sheen.

---

## 3. Typography: The Editorial Voice
We utilize a San Francisco-inspired scale to convey authority and precision.

*   **Display & Headline (The Statement):** Use `display-lg` to `headline-sm` with a `-0.02em` letter spacing. These should be treated as editorial anchors, guiding the eye to the most critical information first.
*   **Body (The Clarity):** `body-lg` (1rem) is our standard for patient instructions and medical notes. Use a generous `line-height` (1.6) to ensure readability in high-stress environments.
*   **Labels (The Metadata):** Use `label-md` in `on_surface_variant` (#414753) for secondary data, ensuring it remains legible but does not compete with primary actions.

---

## 4. Elevation & Depth
Traditional drop shadows are replaced with **Tonal Layering** and **Ambient Light.**

### The Layering Principle
Depth is achieved by "stacking" surface tiers. Place a `surface-container-lowest` card on a `surface-container-low` section. This creates a soft, natural lift that is felt rather than seen.

### Ambient Shadows
When a floating effect is required (e.g., a critical diagnostic modal):
- **Blur:** 40px to 60px.
- **Opacity:** 4%–8% of the `on_surface` color.
- **Tint:** The shadow should never be pure gray; it should carry a hint of the primary blue to maintain a "clinical-cool" temperature.

### The "Ghost Border" Fallback
If accessibility requirements (WCAG) demand a border, use a **Ghost Border**: the `outline_variant` token at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components

### Buttons
- **Primary:** Gradient fill (`primary` to `primary_container`), `xl` (1.5rem) rounded corners. Text is `on_primary` (white).
- **Secondary:** Surface-tinted. No border. Uses `secondary_fixed` background with `on_secondary_fixed` text.
- **Tertiary:** Purely typographic with a subtle `primary` underline or arrow icon.

### Cards & Lists
- **The Divider Ban:** Do not use line dividers between list items. Use vertical whitespace (1.5rem–2rem) or a subtle background shift (`surface-container-low`) on hover/active states.
- **Rounding:** All cards must use `xl` (1.5rem) corner radius to evoke the friendly, modern aesthetic of premium hardware.

### Input Fields
- **State:** Fields should be `surface-container-highest` with no border. Upon focus, they transition to `surface-container-lowest` with a soft primary-tinted ambient shadow.
- **Feedback:** Error states use `error` (#ba1a1a) text but maintain the "No-Line" rule—indicate the error via a soft `error_container` background fill.

### Signature Component: The "Vitality Glass" Modal
A full-screen or partial overlay using 80% opacity `surface` color and a heavy backdrop blur. This keeps the medical staff oriented by allowing the "ghost" of the previous screen to remain visible while they perform a specific task.

---

## 6. Do’s and Don’ts

### Do
- **Do** use whitespace as a functional tool to reduce cognitive load for patients.
- **Do** use `primary` (#004e9f) sparingly to highlight critical "Action" points.
- **Do** leverage the `surface` hierarchy to create natural grouping of related medical data.
- **Do** ensure all interactive elements have a minimum touch target of 44x44px.

### Don't
- **Don't** use black (#000000) for text. Use `on_surface` (#1a1c1d) to maintain a premium, softer contrast.
- **Don't** use sharp 90-degree corners. Everything must feel approachable and safe.
- **Don't** use 1px dividers. If you feel the need for a line, use a 16px gap of whitespace instead.
- **Don't** use standard "system" blues. Stick strictly to the "MediWay Blue" tokens provided to maintain brand trust.