# Scene 05 — 실시간 설비 SPC 알람 (F 모듈) (0:36–0:45)

## 역할 / Beat
**히어로 2.** 컴플라이언스(D)뿐 아니라 **설비 품질(F)** 이상도 같은 관제탑에서 실시간 감지.

## 스펙
16:9 · ≈9초 · **UI 소스:** 실제 앱 스크린샷(SPC 관제 차트) 권장 + GPT IMAGE 합성

## 온스크린 텍스트 (한글)
- 메인: **설비 SPC 이상 즉시 감지**
- 서브: **Nelson 룰 위반 → 실시간 알람 (F 설비)**
- 알람 카드 카피: 🔴 `SPC 사출2호기 위반 · Rule 1 (관리한계 이탈)` / 🟠 `Rule 5 (연속 추세)`

## 🖼️ GPT IMAGE 2.0 — 스틸 프롬프트
**Prompt (EN):**
> **[AJIN VISUAL DNA]** Dark control-tower dashboard, deep navy (#0A0E1A), glass panels, cyan/blue data glow, severity red #EF4444 / amber #F59E0B, monospace numbers, 16:9, cinematic, ultra-detailed.
>
> Center stage: a glowing **SPC control chart (statistical process control)** on a dark glass panel — a horizontal time-series line of data points with dashed **UCL / center / LCL** control limit lines in cyan; one out-of-limit point flares **red** with a pulsing glow ring (a "Nelson rule violation"). To the right, a compact **alarm card with an "F" module chip** and a red severity bar. Faint streaming PLC/sensor data ticker in monospace along the bottom. Precise industrial-analytics feel, premium and clean.

**이미지 내 렌더 문자열(짧게):** `UCL` · `LCL` · `F` · `SPC`. *카드 본문은 스크린샷/AE 오버레이.*
**Settings:** 16:9 (1792×1024) · quality high
**Avoid:** messy chart, unreadable dense numbers, cartoon, watermark

## 🎬 Google Omni — 영상 프롬프트 (image→video)
**Input:** scene_05 스틸
**Prompt (EN):** The SPC line draws left-to-right in real time; data points appear sequentially. As the line breaches the upper control limit, the offending point **flares red and pulses**, a red glow ring expands, and the "F" alarm card snaps in on the right with a subtle shake. The bottom data ticker scrolls. Camera slow push-in to the violation point, shallow DOF. Tense, precise, real-time.
**Duration:** 9s · **Camera:** slow push-in to violation point · **Motion:** chart draw + red flare pulse + card snap, ease-out
**오디오/SFX:** 데이터 그려지는 미세 "틱틱" → 위반 순간 낮은 경고 "붕" + 핑; 그루브 유지

## 트랜지션
- IN: Scene 04 화이트 스윕에서 모듈 D→F 전환(칩 색/라벨 모핑) · OUT: 차트가 축소되어 통합 피드의 한 카드로 합쳐짐 → Scene 06

## 일관성 앵커
F 알람 카드 = D와 동일 카드 시스템(색·뱃지·Ack). "같은 통로(live_alarms)·module 칩만 다름" 메시지를 시각적으로.
