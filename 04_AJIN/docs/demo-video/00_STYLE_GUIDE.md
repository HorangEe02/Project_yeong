# AJIN 웹 시연 영상 — 스타일 가이드 (전 씬 공통 백본)

> 모든 씬 프롬프트(`scene_01`~`scene_10`)는 이 문서의 **시각 DNA / 모션 원칙 / 모델 설정**을 상속한다.
> 레퍼런스(`UIUX모션작업 포트폴리오_어플시연영상 COZY`, ≈1:46, 음악 only UI/UX 모션 쇼릴)의 **포맷**을 차용하되,
> 톤은 COZY의 라이프스타일 감성 → **AJIN의 "규제 관제탑(Compliance Control Tower)"** 으로 전환한다.

---

## 1. 컨셉 한 줄
**"쏟아지는 규제를 하나의 관제탑에서 실시간으로 통제한다."**
B2B 제조 컴플라이언스 SaaS. 무드: 권위 있고 정밀한 *미션 컨트롤 / 관제탑*. 프리미엄·시네마틱·데이터 드리븐.
레퍼런스: Bloomberg 터미널 × Linear × Palantir Foundry, 단 **다크 글래스모피즘 + 네온 데이터 글로우**.

## 2. 타깃 스펙
- **화면비**: 16:9 (가로) — 1792×1024 (GPT IMAGE 2.0) → 1920×1080 업스케일
- **총 길이**: ≈90초, **10씬** (씬당 8~10초)
- **오디오**: 음악 only (내레이션 없음) + 한글 **온스크린 키네틱 타이포** + 미세 UI SFX
- **언어**: 화면 내 텍스트·UI 라벨 = **한글**

## 3. 컬러 시스템 (HEX 고정)
| 역할 | HEX | 용도 |
|---|---|---|
| Ink (배경 베이스) | `#0A0E1A` / `#0F172A` | 다크 캔버스, 딥 네이비 |
| Panel (글래스) | `#111A2E` @ 70% + blur | 카드/패널 글래스모피즘 |
| Primary (시그널) | `#22D3EE` (cyan) | 브랜드 액센트·데이터 글로우·라인 |
| Secondary | `#3B82F6` (electric blue) | 보조 강조·링크·그래프 |
| Safe/Compliant | `#34D399` (green) | 정상·준수 상태 |
| **Severity — CRITICAL** | `#EF4444` (red) | 최상위 알람·위반 |
| **Severity — HIGH** | `#F59E0B` (amber) | 높음 |
| **Severity — MEDIUM** | `#3B82F6` (blue) | 중간 |
| **Severity — LOW** | `#94A3B8` (slate) | 낮음 |
| Text hi / lo | `#E2E8F0` / `#94A3B8` | 본문/캡션 |
> 알람 카드·뱃지·차트의 색은 **반드시 위 Severity 색**을 따른다(앱 실제 규칙과 일치).

## 4. 타이포그래피
- **UI/본문**: Pretendard / SUIT (모던 지오메트릭 산세리프, 한글)
- **디스플레이(키네틱 타이틀)**: Pretendard ExtraBold / Black — 큰 자간 축소, 강한 웨이트
- **데이터/수치/타임스탬프/코드**: JetBrains Mono / IBM Plex Mono
- 숫자는 **카운트업** 모션 전제(예: KPI, 영향점수 88 등)

## 5. UI 키트 (대시보드 룩)
- 다크 글래스 카드, 1px 헤어라인 그리드(`#1E293B`), 코너 라운드 16px
- 네온 데이터 라인/노드 글로우, 미세 스캔라인·노이즈(2%), 깊이감 있는 패럴랙스 레이어
- 컴포넌트: 모듈 카드(D 컴플라이언스 / E / F 설비), KPI 타일(카운트업), 실시간 알람 피드, SPC 관제 차트(관리한계선 UCL/LCL + Nelson 위반점), 결재선 체인, 협력사 네트워크 그래프, 학습 진도 링
- 디바이스: 플로팅 글래스 스크린(베젤리스), 살짝 3D 틸트, 반사/그림자

## 6. 모션 원칙 (Google Omni 공통)
- 이징: **ease-out cubic** 기본, 묵직하고 confident. 튀지 않게.
- 카메라: 느린 push-in / 가벼운 오빗 / 패럴랙스 슬라이드. 손떨림 없음(잠금 트라이포드 또는 스무스 짐벌 느낌).
- UI는 "조립되듯" 등장(stagger 60~120ms), 데이터는 좌→우로 그려짐, 알람은 **펄스+글로우**.
- 씬 전환: whip/whoosh + 라이트 스윕 또는 글래스 패널 슬라이드. 비트에 맞춘 컷.
- **금지**: 과한 렌즈플레어, 빠른 카메라 흔들림, 만화풍, 워터마크, 깨진(가짜) 텍스트 떡칠.

## 7. GPT IMAGE 2.0 — 공통 설정 & 재사용 스타일 블록
- **Aspect**: 16:9 (1792×1024) · **Quality**: high · **Rendering**: photoreal UI / cinematic 3D composite
- 각 씬 이미지 프롬프트 맨 앞에 아래 **[AJIN VISUAL DNA]** 블록을 붙여 일관성 유지:

> **[AJIN VISUAL DNA]** Cinematic dark "compliance control tower" UI showcase. Deep navy ink background (#0A0E1A) with subtle 1px grid and 2% film grain. Glassmorphism panels (#111A2E, frosted, soft inner glow). Neon data accents in cyan (#22D3EE) and electric blue (#3B82F6); status colors red #EF4444 / amber #F59E0B / blue #3B82F6 / slate #94A3B8 / green #34D399. Modern Korean geometric sans-serif (Pretendard-like) for labels, monospace for numbers/timestamps. Premium, precise, trustworthy, enterprise B2B. Volumetric depth, soft bokeh, cinematic rim light, 16:9, ultra-detailed, high fidelity. No watermark, no gibberish text, no lens-flare overdose.

- **이미지 내 한글 텍스트**: 짧은 라벨만 정확한 문자열로 명시(따옴표). 긴 문장/정밀 UI 텍스트는 렌더가 불완전할 수 있으므로 **후반 합성(AE) 또는 실제 앱 스크린샷 오버레이** 권장(§9).

## 8. Google Omni — 공통 설정
- **입력**: 해당 씬의 GPT IMAGE 2.0 스틸(image-to-video)
- **길이**: 씬별 8~10초 · **FPS**: 24 · **화면비**: 16:9
- 프롬프트에 카메라 무브 / UI 모션 / 타이밍 / 이징 / 전환 / SFX 큐를 명시(§6 준수)
- 출력 클립은 편집 타임라인에서 비트 컷 + 한글 키네틱 타이포 오버레이로 마감

## 9. UI 정확도 팁 (중요)
GPT IMAGE 2.0는 **분위기·구도·디바이스 합성**에 강하지만, 촘촘한 한글 대시보드 텍스트는 부정확할 수 있다. 권장 하이브리드:
1. **실제 앱 스크린샷**(`ajin-ai-assistant-react` 로컬 실행 화면)을 UI 레이어로 사용 → 텍스트 100% 정확
2. GPT IMAGE 2.0는 **히어로/추상/배경/디바이스 목업/아웃트로** 등 시네마틱 프레임 담당
3. 정밀 라벨은 **After Effects 키네틱 타이포**로 오버레이(한글 가독성·모션 품질 ↑)
> 각 씬 파일의 `UI 소스` 항목에 "GPT IMAGE / 실제 스크린샷 / AE 타이포" 중 무엇을 쓸지 표기.

## 10. 일관성 체크리스트 (씬 생성 시)
- [ ] [AJIN VISUAL DNA] 블록 선두 포함
- [ ] 팔레트·Severity 색 준수 / 타이포 규칙 준수
- [ ] 16:9 · 다크 글래스 · 네온 데이터 글로우
- [ ] 카메라/모션 = ease-out, confident, 흔들림 없음
- [ ] 한글 온스크린 카피 1~2줄(짧게) + 후반 타이포 권장 표기
- [ ] 전 씬 통틀어 동일한 "AJIN 로고 락업"과 모듈 카드 디자인 유지
