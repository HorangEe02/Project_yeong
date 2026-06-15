# Scene 04 — 실시간 컴플라이언스 알람 (D 모듈) (0:27–0:36)

## 역할 / Beat
**히어로 1.** 법규 변경이 발생하자 **실시간 알람**이 즉시 뜬다. 제품의 핵심 가치 첫 증명.

## 스펙
16:9 · ≈9초 · **UI 소스:** ✅ 실제 앱 스크린샷(D 알람 카드/토스트) 오버레이 권장 + GPT IMAGE 배경/디바이스

## 온스크린 텍스트 (한글)
- 메인: **실시간 컴플라이언스 알람**
- 서브: **법규 변경 → 즉시 감지 · 등급 자동 분류**
- 알람 카드 카피(실데이터 기반):
  - 🔴 **CRITICAL** · `산업안전보건법 시행규칙(프레스 안전거리) 시행 D-7`
  - 🟠 **HIGH** · `EU REACH 6가 크롬 화합물 인가(Authorization) 필수화`
  - 🟠 **HIGH** · `Uyghur Forced Labor Prevention Act (UFLPA)`

## 🖼️ GPT IMAGE 2.0 — 스틸 프롬프트
**Prompt (EN):**
> **[AJIN VISUAL DNA]** Dark compliance dashboard close-up, deep navy (#0A0E1A), glass panels, cyan/blue glow, severity colors red #EF4444 / amber #F59E0B, monospace timestamps, 16:9, cinematic, ultra-detailed.
>
> Close-up on the upper-right of the dark dashboard where a **toast alarm notification** is sliding in: a glass card with a glowing **red "CRITICAL" badge**, a small "D" module chip, a Korean title line, a monospace timestamp, and an "확인(Ack)" button. Behind/below it a vertical **alarm feed** of stacked cards with red/amber severity dots and left color bars. Soft red glow pulse around the newest card, shallow depth-of-field, premium enterprise UI. The dashboard continues blurred in the background.

**이미지 내 렌더 문자열(짧게):** `CRITICAL` · `D` · `확인` · `AJIN`. *카드 본문 한글은 실제 스크린샷/AE 오버레이.*
**Settings:** 16:9 (1792×1024) · quality high
**Avoid:** dense unreadable Korean body text (keep as overlay), neon overkill, watermark

## 🎬 Google Omni — 영상 프롬프트 (image→video)
**Input:** scene_04 스틸
**Prompt (EN):** A new alarm toast slides in from the top-right with a soft red glow pulse and a subtle scale-bounce; the CRITICAL badge flares once. The alarm feed below shifts down to make room (smooth list reflow). A cursor moves to the "확인(Ack)" button and it depresses with a ripple. Camera holds with a slow micro push-in, shallow DOF. Crisp, responsive, real-time feel.
**Duration:** 9s · **Camera:** slow micro push-in · **Motion:** toast slide+pulse, list reflow, button ack, ease-out
**오디오/SFX:** 알람 "핑"(높은 신스) + 글로우 스웰 + 버튼 클릭 "틱"; 비트 위 그루브 유지

## 트랜지션
- IN: Scene 03에서 알람 피드로 push-in 연속 · OUT: 알람 카드가 카메라를 채우며 화이트 스윕 → Scene 05(설비)로 모듈 전환

## 일관성 앵커
Severity 색·뱃지·"확인(Ack)" 버튼 디자인을 Scene 05·06과 통일. (실데이터: `D-*` 알람 ID 체계와 일치)
