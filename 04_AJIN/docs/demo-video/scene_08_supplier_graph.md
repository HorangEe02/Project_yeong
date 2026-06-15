# Scene 08 — 협력사 영향 그래프 (1:04–1:14)

## 역할 / Beat
**확장 2.** 규제 변경이 우리 회사뿐 아니라 **협력사망 전체**에 미치는 파급을 한눈에.

## 스펙
16:9 · ≈10초 · **UI 소스:** 실제 앱 스크린샷(협력사 네트워크 그래프) 권장 + GPT IMAGE 합성

## 온스크린 텍스트 (한글)
- 메인: **협력사 영향까지 한눈에**
- 서브: **규제 → 품목 → 협력사 파급 · 리스크 자동 하이라이트**
- 노드 라벨(짧게): `규제` · `품목` · `협력사` · 리스크 뱃지 `높음/중간`

## 🖼️ GPT IMAGE 2.0 — 스틸 프롬프트
**Prompt (EN):**
> **[AJIN VISUAL DNA]** Dark control-tower, navy (#0A0E1A), glass, cyan/blue glow, risk red #EF4444 / amber #F59E0B, 16:9, cinematic, ultra-detailed.
>
> A premium **force-directed network graph** floating on a dark canvas: a bright central **"규제" (regulation) node** in cyan, connected by glowing edges to a ring of **"품목" (part/item) nodes**, which connect outward to many **"협력사" (supplier) nodes**. Several supplier nodes downstream glow **red/amber** to indicate risk exposure, with subtle pulse halos. Faint depth haze, particles along edges, elegant data-viz. Interactive analytics aesthetic (Palantir/Linear vibe).

**이미지 내 렌더 문자열(짧게):** `규제` · `협력사` · `품목` · `AJIN`. *세부 라벨은 스크린샷/AE.*
**Settings:** 16:9 (1792×1024) · quality high
**Avoid:** hairball overload, unreadable labels, cartoon, watermark

## 🎬 Google Omni — 영상 프롬프트 (image→video)
**Input:** scene_08 스틸
**Prompt (EN):** The central "규제" node pulses and a **ripple of light travels outward** along the edges — first to 품목 nodes, then cascading to 협력사 nodes. As the ripple reaches downstream suppliers, several **light up red/amber** with expanding risk halos. The graph gently breathes (force-directed settle), nodes drift subtly. Camera slow orbit around the network with parallax depth. Mesmerizing, intelligent, premium.
**Duration:** 10s · **Camera:** slow orbit · **Motion:** ripple propagation + risk highlight + graph breathe, ease-in-out
**오디오/SFX:** 파급되는 신스 스윕(저→고) + 리스크 노드 점등 "틱"; 그루브 유지

## 트랜지션
- IN: Scene 07 결재 완료 펄스가 그래프 중심으로 수렴 · OUT: 네트워크가 축소되어 빛 입자로 흩어짐 → Scene 09

## 일관성 앵커
리스크 색 = Severity 팔레트. 노드 글로우/엣지 스타일을 Scene 01 레이더·Scene 03 월드맵과 시각적으로 호응.
