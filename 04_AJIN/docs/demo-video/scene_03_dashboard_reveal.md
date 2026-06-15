# Scene 03 — 대시보드 리빌 (0:17–0:27)

## 역할 / Beat
**솔루션 등장.** 혼돈이 하나의 관제탑 대시보드로 정렬된다. 제품의 "와이드 히어로 샷".

## 스펙
16:9 · ≈10초 · **UI 소스:** ✅ **실제 앱 스크린샷**(`ajin-ai-assistant-react` 대시보드) 합성 권장 + GPT IMAGE는 배경/룸/디바이스 담당

## 온스크린 텍스트 (한글)
- 메인: **하나의 관제탑** · *AJIN Compliance Control Tower*
- 서브: **규제·설비·협력사를 한 화면에서**
- KPI 타일은 **카운트업**(예: 활성 알람 · 금주 변경 · 평균 처리시간)

## 🖼️ GPT IMAGE 2.0 — 스틸 프롬프트
**Prompt (EN):**
> **[AJIN VISUAL DNA]** Dark "compliance control tower", deep navy (#0A0E1A), glassmorphism panels (#111A2E), cyan (#22D3EE)/blue (#3B82F6) data glow, 1px grid, 2% grain, cinematic rim light, 16:9, ultra-detailed enterprise dashboard.
>
> Wide hero shot of a sleek dark analytics dashboard displayed on a large frosted-glass screen floating in a dim control room. Layout: a left rail of **module cards** labeled "D 컴플라이언스", "E", "F 설비"; top row of KPI tiles with large monospace numbers; a central dark world map with glowing regulation hotspots (cyan/amber nodes + connecting arcs); a right-side live alarm feed list with small colored severity dots (red/amber/blue). Subtle reflections, volumetric haze, depth. Premium Bloomberg-terminal-meets-Linear aesthetic.

**이미지 내 렌더 문자열(짧게):** `D 컴플라이언스` · `F 설비` · `AJIN`. *정밀 UI 텍스트는 실제 스크린샷/AE 오버레이로 대체.*
**Settings:** 16:9 (1792×1024) · quality high
**Avoid:** gibberish dense text, oversaturation, toy-like UI, watermark

## 🎬 Google Omni — 영상 프롬프트 (image→video)
**Input:** scene_03 스틸 (또는 실제 스크린샷 합성본)
**Prompt (EN):** Camera pulls back and slightly cranes up, revealing the full dashboard within the control room. UI assembles with staggered motion: module cards slide in (60–120ms stagger), KPI numbers count up rapidly, world-map hotspots light up one by one with traveling arcs, the alarm feed populates top-to-bottom. Gentle parallax between glass screen and background. Confident, smooth, locked.
**Duration:** 10s · **Camera:** pull-back + slight crane-up · **Motion:** staggered UI assemble + count-up, ease-out
**오디오/SFX:** 임팩트 히트(대시보드 등장) → 그루브 진입 + 미세 UI "틱틱"(카드 등장 동기)

## 트랜지션
- IN: Scene 02 문서가 빨려든 빛 → 대시보드로 "정리" · OUT: 카메라가 알람 피드로 push-in → Scene 04

## 일관성 앵커
모듈 카드(D/E/F) 디자인·위치를 Scene 04·06과 동일 유지. 실제 스크린샷 사용 시 다크모드·동일 해상도 캡처.
