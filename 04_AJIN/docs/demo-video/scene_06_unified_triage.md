# Scene 06 — 통합 관제 · 즉시 조치 (0:45–0:54)

## 역할 / Beat
**히어로 3.** D(컴플라이언스) + F(설비) 알람이 **하나의 피드**로 통합되고, 클릭 한 번에 상세→조치(Ack).

## 스펙
16:9 · ≈9초 · **UI 소스:** ✅ 실제 앱 스크린샷(통합 알람 피드 + 상세 패널) 권장

## 온스크린 텍스트 (한글)
- 메인: **한 화면에서 통합 관제**
- 서브: **D·F 통합 피드 · 최상위 알람 자동 정렬 · 즉시 조치(Ack)**
- 상세 패널 항목: `심각도` · `영향 부서` · `소스` · `시행일/감지시각` · `확인(Ack)`

## 🖼️ GPT IMAGE 2.0 — 스틸 프롬프트
**Prompt (EN):**
> **[AJIN VISUAL DNA]** Dark control-tower dashboard, navy (#0A0E1A), glass panels, cyan/blue glow, severity red/amber/blue/slate dots, monospace, 16:9, cinematic, ultra-detailed.
>
> Two-column dashboard view: LEFT a **unified live alarm feed** — a vertical list of glass cards mixing **"D" and "F" module chips**, each with a colored severity bar (red/amber/blue) and a left color rail, sorted with the most critical pinned at top (a highlighted "TOP ALARM" banner). RIGHT a **detail panel** that has opened for the selected alarm: severity badge, fields for 영향 부서 / 소스 / 시각, and a prominent **"확인(Ack)"** button glowing cyan. Clean information hierarchy, premium enterprise control center.

**이미지 내 렌더 문자열(짧게):** `D` · `F` · `TOP ALARM` · `확인` · `AJIN`. *세부 텍스트는 스크린샷/AE.*
**Settings:** 16:9 (1792×1024) · quality high
**Avoid:** clutter, unreadable text walls, watermark

## 🎬 Google Omni — 영상 프롬프트 (image→video)
**Input:** scene_06 스틸
**Prompt (EN):** The unified feed scrolls slightly as D and F cards interleave and re-sort, the top "TOP ALARM" card lifting into a pinned highlight. A cursor clicks it; the **detail panel slides in from the right** with staggered field reveals. The cursor hits **"확인(Ack)"**, the button ripples cyan and the card gets a green "처리됨" check, then the list reflows. Camera locked with subtle parallax. Effortless, fast, satisfying.
**Duration:** 9s · **Camera:** locked + micro parallax · **Motion:** sort + detail slide-in + ack→green check, ease-out
**오디오/SFX:** 리스트 정렬 "스르륵" + 패널 슬라이드 whoosh + Ack 성공 "딩"(상쾌한 컨펌음)

## 트랜지션
- IN: Scene 05 차트가 피드 카드로 합류 · OUT: 상세 패널이 닫히며 카메라가 결재선으로 이동(연속 팬) → Scene 07

## 일관성 앵커
D+F가 "같은 카드 시스템·같은 피드"임을 명확히(제품 핵심 메시지). TOP ALARM 정렬 = 실제 `topAlarm` 로직과 일치.
