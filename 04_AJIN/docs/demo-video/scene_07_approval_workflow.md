# Scene 07 — 승인 워크플로우 (0:54–1:04)

## 역할 / Beat
**확장 1.** 알람을 받은 뒤 → **전자결재 / 위임**으로 조치가 흐른다. "감지에서 조치까지" 연결.

## 스펙
16:9 · ≈10초 · **UI 소스:** 실제 앱 스크린샷(결재선/위임) 권장 + GPT IMAGE 합성

## 온스크린 텍스트 (한글)
- 메인: **승인 워크플로우**
- 서브: **전자결재 · 위임 규칙 · 상태 추적** (대기 → 검토 → 승인)
- 노드 라벨: `담당자` → `팀장` → `임원` / `위임(Delegation)` 뱃지

## 🖼️ GPT IMAGE 2.0 — 스틸 프롬프트
**Prompt (EN):**
> **[AJIN VISUAL DNA]** Dark dashboard, navy (#0A0E1A), glass panels, cyan/blue glow, status amber #F59E0B (pending) / green #34D399 (approved), 16:9, cinematic, ultra-detailed.
>
> A horizontal **approval-chain flow** on a dark glass panel: connected circular avatar nodes labeled "담당자", "팀장", "임원" linked by glowing connector lines. The first node shows a green approved check, the middle node pulses amber as "in review", the last is pending. A small **"위임" (delegation) badge** branches one step to a side delegate node with a dotted re-route line. A document/regulation card sits at the start of the chain. Clean process-flow diagram aesthetic, premium enterprise.

**이미지 내 렌더 문자열(짧게):** `담당자` · `팀장` · `임원` · `위임` · `승인`. *세부는 스크린샷/AE.*
**Settings:** 16:9 (1792×1024) · quality high
**Avoid:** org-chart clutter, unreadable text, cartoon, watermark

## 🎬 Google Omni — 영상 프롬프트 (image→video)
**Input:** scene_07 스틸
**Prompt (EN):** The document enters the chain from the left and travels along the glowing connector line. Each node activates in sequence: first node flips to a green check, the connector fills with light to the next, the middle node pulses amber→green. The **"위임" badge** lights up and a dotted line animates to re-route to the delegate node. Status chips flip 대기→검토→승인. Camera slow lateral dolly following the flow. Smooth, procedural, confident.
**Duration:** 10s · **Camera:** slow lateral dolly (L→R) · **Motion:** token travel + sequential node activation + delegation re-route, ease-out
**오디오/SFX:** 각 승인 단계 "딩딩딩"(상승 음정) + 커넥터 차오르는 whoosh; 그루브 유지

## 트랜지션
- IN: Scene 06 상세 패널에서 결재선으로 연속 팬 · OUT: 결재 완료 펄스가 네트워크로 퍼짐 → Scene 08 협력사 그래프

## 일관성 앵커
상태 색(대기 amber / 승인 green)을 앱 status 체계(pending/reviewing/approved)와 일치. 노드 글래스 스타일 통일.
