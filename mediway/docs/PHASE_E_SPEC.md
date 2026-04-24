# MediWay Phase E — 환자 UI 기능 설명서

> 작성일: 2026-04-16 | Phase E 구현 완료 시점 기준
> 빌드 결과: JS 657KB / CSS 20KB (gzip 후 ~202KB) | 테스트: 13/13 통과

---

## 목차

1. [개요](#1-개요)
2. [UI/UX 디자인 분석 및 반영](#2-uiux-디자인-분석-및-반영)
3. [PatientDashboard 상태 머신](#3-patientdashboard-상태-머신)
4. [QR 코드 표시](#4-qr-코드-표시)
5. [동선 진행률 표시](#5-동선-진행률-표시)
6. [다음 목적지 카드](#6-다음-목적지-카드)
7. [도착 확인 플로우](#7-도착-확인-플로우)
8. [완료 화면](#8-완료-화면)
9. [지도 통합](#9-지도-통합)
10. [PatientPage 반응형 레이아웃](#10-patientpage-반응형-레이아웃)
11. [컴포넌트 상세 명세](#11-컴포넌트-상세-명세)
12. [Phase F 연계](#12-phase-f-연계)

---

## 1. 개요

### 1.1 Phase E의 목적

Phase E는 MediWay의 **환자 측 인터페이스**를 구현합니다. 환자가 QR 코드를 보여주고, 의료진으로부터 동선을 수신한 뒤, 실내 지도에서 경로를 확인하며 단계별로 이동하는 전체 플로우를 포함합니다.

### 1.2 구현 범위

| 구현 항목 | 파일 | 설명 |
|----------|------|------|
| QRDisplay | `components/patient/QRDisplay.tsx` | QR 코드 생성 + 3분 자동갱신 + 대기 UI |
| RouteProgress | `components/patient/RouteProgress.tsx` | 동선 진행률 (✓─◉─○) |
| DestinationCard | `components/patient/DestinationCard.tsx` | 다음 목적지 gradient 카드 |
| ArrivalButton | `components/patient/ArrivalButton.tsx` | 2단계 확인 도착 버튼 |
| CompletionScreen | `components/patient/CompletionScreen.tsx` | 전체 동선 완료 축하 화면 |
| PatientDashboard | `components/patient/PatientDashboard.tsx` | 상태 머신 + 지도/경로 통합 |
| PatientPage | `pages/PatientPage.tsx` | 반응형 레이아웃 + 사이드바 |

### 1.3 핵심 설계 결정

| 결정 | 이유 |
|------|------|
| 상태 머신 3단계 (qr_display→navigating→completed) | 환자 플로우가 단순/선형적 — 복잡한 분기 불필요 |
| 2단계 도착 확인 | 실수로 "도착" 누르는 것을 방지 (되돌리기 불가) |
| QR 3분 자동갱신 | 보안(탈취 방지) + 사용자가 인지할 필요 없는 백그라운드 처리 |
| 데모 시뮬레이션 버튼 | Phase F(Firebase) 전까지 동선 수신을 로컬에서 테스트 |
| 자동 층 전환 | "도착" 클릭 시 다음 목적지 층으로 FloorSelector 자동 전환 |

---

## 2. UI/UX 디자인 분석 및 반영

### 2.1 참조한 디자인 파일

| 디자인 | 파일 경로 | 반영 내용 |
|--------|----------|----------|
| 모바일 mediway_1 | `uiux/mobile_uiux/mediway_1/` | 다음 목적지 카드 + 실내 지도(경로 dash선) + "도착했습니다" 버튼 + 층 이동 안내 텍스트 |
| 모바일 mediway_3 | `uiux/mobile_uiux/mediway_3/` | "Your Daily Route" — 진행률(●─◉─○) + NEXT DESTINATION gradient 카드(ETA/Distance/Level 칩) + Current Indoor View |
| 모바일 mediway_4 | `uiux/mobile_uiux/mediway_4/` | Facility 탭 — Nearby Services 리스트 (사이드바 참고) |
| 모바일 mediway_qr | `uiux/mobile_uiux/mediway_qr/` | QR 코드 표시 + "간호사에게 보여주세요" 안내 + 보안 갱신 알림 + Zone 뱃지 |
| 웹 mediway_2 | `uiux/web_page_uiux/mediway_2/` | Patients 탭 — 현재 위치 + 진행률 + 3D 지도 + "안내 시작" 버튼 |
| 웹 mediway_v2 | `uiux/web_page_uiux/mediway_v2/` | Facility 탭 — 검색 + 편의시설 + 층별 지도 + 주차 정보 |
| DESIGN.md | `uiux/web_page_uiux/mediway_clinical/DESIGN.md` | Editorial Clinical Excellence 디자인 시스템 |

### 2.2 디자인 → 구현 매핑

| 디자인 요소 | 원본 디자인 | 구현 컴포넌트 | 적용 방식 |
|------------|-----------|-------------|----------|
| QR 코드 + 안내문구 | mediway_qr | QRDisplay | qrcode.react SVG + "간호사에게 보여주세요" + Zone A-1 뱃지 + 보안 안내 |
| 진행률 (✓─◉─○) | mediway_3 | RouteProgress | 수평 스크롤 가능, 3종 마커(완료=초록✓/현재=파랑링/대기=회색) |
| NEXT DESTINATION 카드 | mediway_3 | DestinationCard | gradient-primary 배경 + ETA/Distance/Level 칩 (bg-white/15 backdrop-blur) |
| 실내 지도 + 경로 | mediway_1, mediway_3 | HospitalMapContainer (Phase B) | "Current Indoor View" 헤더 + 경로 dash 애니메이션 |
| "도착했습니다" 버튼 | mediway_1 | ArrivalButton | gradient-primary → 2단계 확인("네, 도착했어요!") |
| 층 이동 안내 텍스트 | mediway_1 | DestinationCard 하단 | "엘리베이터를 타고 N층으로 이동하세요" (bg-white/10) |
| 병원 정보 사이드바 | mediway_v2 | PatientPage 사이드바 | 병원 정보 + 이용 안내 팁 + Nearby Services |
| 축하/완료 화면 | (자체 디자인) | CompletionScreen | PartyPopper 아이콘 + 통계 카드 + 홈/새동선 버튼 |

### 2.3 반응형 전략

| 뷰포트 | 레이아웃 | 특징 |
|--------|---------|------|
| **모바일** (< 1024px) | 1열 스택 | 전체 너비, 사이드바 숨김, 터치 최적화 (44px 타겟), 수직 스크롤 |
| **데스크톱** (≥ 1024px) | 2열 그리드 `[1fr_340px]` | 좌: 대시보드 메인, 우: 병원정보+이용안내+편의시설 사이드바 |

---

## 3. PatientDashboard 상태 머신

### 3.1 상태 다이어그램

```
┌──────────────────┐
│    qr_display    │ ← 초기 상태
│                  │
│  QR 코드 표시     │
│  스캔 대기 중     │
└────────┬─────────┘
         │ 의료진 스캔 (동선 수신)
         │ [데모: 시뮬레이션 버튼]
         ▼
┌──────────────────┐
│   navigating     │
│                  │
│  진행률 표시      │
│  목적지 카드      │
│  실내 지도       │    "도착" 클릭
│  도착 버튼       │ ──→ 다음 경유지
│                  │     (같은 상태 유지)
└────────┬─────────┘
         │ 마지막 경유지 도착
         ▼
┌──────────────────┐
│    completed     │
│                  │
│  축하 화면       │
│  홈/새동선 버튼   │
└──────────────────┘
         │ "새 동선 받기"
         ▼
    (qr_display로 복귀)
```

### 3.2 상태별 렌더링

| 상태 | 화면 구성 |
|------|----------|
| `qr_display` | QRDisplay + 데모 시뮬레이션 버튼 |
| `navigating` | RouteProgress + DestinationCard + HospitalMapContainer + ArrivalButton |
| `completed` | CompletionScreen |

### 3.3 상태 관리 변수

| 변수 | 타입 | 초기값 | 용도 |
|------|------|-------|------|
| `state` | `PatientState` | `'qr_display'` | 현재 상태 |
| `_qrToken` | `string \| null` | `null` | 생성된 QR 토큰 (Phase F에서 DB 등록용) |
| `waypoints` | `Waypoint[]` | `[]` | 경유지 배열 (상태 포함) |
| `currentIndex` | `number` | `0` | 현재 진행 중인 경유지 인덱스 |
| `routeResult` | `RouteResult \| null` | `null` | computeRoute() 결과 |

### 3.4 핵심 로직

**동선 수신 시 (`handleSimulateReceive`):**
1. `computeRoute(navigationGraph, waypointPoiIds)` → RouteResult 계산
2. waypoints 배열 생성 (첫 번째 = 'current', 나머지 = 'pending')
3. state → 'navigating'
4. 첫 목적지 층으로 자동 전환 (`setCurrentFloor`)

**도착 확인 시 (`handleArrival`):**
1. 현재 경유지 → 'completed' (arrivedAt 타임스탬프)
2. 다음 경유지 → 'current'
3. currentIndex 증가
4. 마지막이었으면 state → 'completed'
5. 아니면 다음 목적지 층으로 자동 전환

---

## 4. QR 코드 표시

### 4.1 QRDisplay

**파일:** `src/components/patient/QRDisplay.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `onTokenGenerated` | `(token: string) => void` | 토큰 생성 시 콜백 |

### 4.2 QR 코드 생성

| 항목 | 값 |
|------|-----|
| 라이브러리 | `qrcode.react` (QRCodeSVG) |
| 토큰 형식 | UUID v4 (`uuid` 패키지) |
| 크기 | 200 × 200px |
| 에러 보정 | Level M (15%) |
| 색상 | 흑백 (#1a1c1d / #ffffff) |

### 4.3 자동 갱신

| 항목 | 값 |
|------|-----|
| 갱신 주기 | 3분 (180,000ms) |
| 갱신 방식 | `setInterval` → `refreshCount` 증가 → `useEffect`에서 새 UUID 생성 |
| 수동 갱신 | "QR 코드 수동 갱신" 버튼 |
| 정리 | 컴포넌트 언마운트 시 `clearInterval` |

### 4.4 UI 구성

```
┌─────────────────────────────────┐
│  환자 정보                       │
│  MediWay 데모 환자   [Zone A-1]  │
├─────────────────────────────────┤
│                                 │
│          ┌─────────┐            │
│          │  QR     │            │
│          │  CODE   │            │
│          └─────────┘            │
│                                 │
│  이 QR 코드를 간호사에게 보여주세요  │
│  의료진이 스캔하면 대기 접수가...   │
│                                 │
│       ● 스캔 대기 중...           │
├─────────────────────────────────┤
│  🛡 보안 안내: 3분마다 갱신...     │
├─────────────────────────────────┤
│  [ 🔄 QR 코드 수동 갱신 ]        │
└─────────────────────────────────┘
```

---

## 5. 동선 진행률 표시

### 5.1 RouteProgress

**파일:** `src/components/patient/RouteProgress.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `waypoints` | `Waypoint[]` | 경유지 배열 (상태 포함) |
| `currentIndex` | `number` | 현재 진행 인덱스 |
| `onWaypointClick?` | `(index: number) => void` | 경유지 클릭 콜백 |

### 5.2 마커 3종 스타일

| 상태 | 마커 | 색상 | 추가 효과 |
|------|------|------|----------|
| completed | ✓ 체크 아이콘 | `bg-green-500 text-white` | — |
| current | 숫자 | `bg-primary text-white` | `shadow-lg shadow-primary/30 ring-4 ring-primary/20` |
| pending | 숫자 | `bg-surface-container-high text-on-surface-variant` | — |

### 5.3 연결선

| 상태 | 색상 | 두께 |
|------|------|------|
| 완료 구간 | `bg-green-400` | 2px |
| 미완료 구간 | `bg-surface-container-high` | 2px |

### 5.4 라벨 스타일

| 상태 | 색상 | 굵기 |
|------|------|------|
| completed | `text-green-600` | medium |
| current | `text-primary` | semibold |
| pending | `text-on-surface-variant/60` | medium |

### 5.5 수평 스크롤

경유지가 많을 때 (5개 이상) `overflow-x-auto`로 수평 스크롤을 지원합니다. `minWidth`는 `waypoints.length × 80px`로 계산됩니다.

---

## 6. 다음 목적지 카드

### 6.1 DestinationCard

**파일:** `src/components/patient/DestinationCard.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `destination` | `POI` | 목적지 POI |
| `segmentTime?` | `number` | 예상 소요 시간 (초) |
| `segmentDistance?` | `number` | 거리 (미터) |
| `floorInstruction?` | `string` | 층 이동 안내 텍스트 |
| `currentLeg` | `number` | 현재 구간 인덱스 |
| `totalLegs` | `number` | 총 구간 수 |

### 6.2 gradient-primary 디자인

mediway_3 디자인의 NEXT DESTINATION 카드를 구현합니다:

| 속성 | 값 |
|------|-----|
| 배경 | `bg-gradient-to-br from-primary to-primary-container` |
| 모서리 | `rounded-2xl` (1.5rem) |
| 그림자 | `shadow-ambient-lg` |
| 텍스트 | 전부 white 계열 |

### 6.3 카드 구성

```
┌─────────────────────────────────────┐
│ NEXT DESTINATION          ┌──────┐ │
│                           │ ETA  │ │
│ 채혈실                     │  3   │ │
│                           │ min  │ │
│                           └──────┘ │
│                                     │
│  ┌──────────┐ ┌──────────┐ ┌─────┐│
│  │📍Distance│ │🏢 Level  │ │🧭Step││
│  │  120m    │ │ Floor 2  │ │ 1/4 ││
│  └──────────┘ └──────────┘ └─────┘│
│                                     │
│  ┌─────────────────────────────────┐│
│  │🏢 엘리베이터를 타고 2층으로...    ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 6.4 정보 칩 (bg-white/15 + backdrop-blur)

| 칩 | 아이콘 | 라벨 | 값 |
|----|--------|------|-----|
| Distance | MapPin | "Distance" | `{distance}m` |
| Level | Building2 | "Level" | `Floor {N}` |
| Step | Navigation | "Step" | `{current}/{total}` |

### 6.5 층 이동 안내

`floorInstruction`이 있을 때만 하단에 표시됩니다. Phase C의 `generateFloorTransitionInstruction()`이 생성한 한국어 안내 문구가 여기에 렌더링됩니다.

```
🏢 엘리베이터를 타고 3층으로 이동하세요
```

---

## 7. 도착 확인 플로우

### 7.1 ArrivalButton

**파일:** `src/components/patient/ArrivalButton.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `onArrival` | `() => void` | 도착 확인 콜백 |

### 7.2 2단계 확인 패턴

실수로 "도착" 버튼을 누르는 것을 방지하기 위해 2단계 확인을 사용합니다:

**Step 1 — 첫 번째 클릭:**
```
┌─────────────────────────────────────┐
│  ✓ 도착했습니다                       │
│  (gradient-primary, 전체 너비)        │
└─────────────────────────────────────┘
```

**Step 2 — 확인 선택:**
```
┌────────────────┐ ┌────────────────┐
│   아직이에요    │ │ ✓ 네, 도착했어요! │
│  (회색 배경)    │ │  (초록 배경)     │
└────────────────┘ └────────────────┘
```

| 버튼 | 동작 |
|------|------|
| "아직이에요" | `isConfirming = false` → 원래 버튼으로 복귀 |
| "네, 도착했어요!" | `onArrival()` 호출 → 다음 경유지로 전환 |

### 7.3 스타일

| 상태 | 배경 | 텍스트 | 효과 |
|------|------|--------|------|
| 기본 (Step 1) | gradient-primary | white, bold | `shadow-ambient-lg`, `active:scale-[0.97]` |
| 취소 (Step 2) | `surface-container-high` | `on-surface-variant` | hover 색상 변경 |
| 확인 (Step 2) | `bg-green-500` | white, bold | `shadow-lg shadow-green-500/30`, `active:scale-[0.97]` |

---

## 8. 완료 화면

### 8.1 CompletionScreen

**파일:** `src/components/patient/CompletionScreen.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `totalSteps` | `number` | 완료한 총 단계 수 |
| `onReset?` | `() => void` | "새 동선 받기" 콜백 |

### 8.2 화면 구성

```
         ┌─────────┐
         │  🎉     │
         │ (초록)   │
         └─────────┘

    오늘 진료가 모두 끝났습니다

    4개의 동선을 모두 완료했습니다.
    귀가하셔도 됩니다. 빠른 쾌유를 빕니다.

     ┌─────────┐  ┌─────────┐
     │    4    │  │  100%   │
     │완료된 단계│  │  진행률  │
     └─────────┘  └─────────┘

    [ 🏠 홈으로 돌아가기 ]    (gradient-primary)
    [  🔄 새 동선 받기  ]    (surface 배경)
```

### 8.3 통계 카드

| 카드 | 배경 | 텍스트 색상 | 값 |
|------|------|-----------|-----|
| 완료된 단계 | `bg-green-50` | `text-green-600` | `totalSteps` |
| 진행률 | `bg-primary/5` | `text-primary` | `100%` |

---

## 9. 지도 통합

### 9.1 Phase B HospitalMapContainer 연결

PatientDashboard에서 Phase B의 `HospitalMapContainer`를 다음과 같이 연결합니다:

```typescript
<HospitalMapContainer
  pathSegment={currentFloorSegment}
  highlights={highlights}
/>
```

### 9.2 pathSegment 결정 로직

```typescript
// 현재 leg의 세그먼트 중 현재 층에 해당하는 것만 필터
const currentFloorSegment = currentSegments?.segments.find(
  s => s.floorLevel === currentFloor && s.coordinates.length > 0
);
```

- `currentSegments`는 `routeResult.legs[currentIndex]` — 현재 경유지까지의 PathResult
- `currentFloor`는 `mapStore.currentFloor` — FloorSelector에서 선택한 층
- 좌표가 빈 세그먼트(층 전환)는 제외 (`coordinates.length > 0`)

### 9.3 highlights 구성

```typescript
const highlights: MapHighlights = {
  currentPoiId: waypoints[currentIndex]?.poiId,     // 파랑 펄스
  completedPoiIds: waypoints
    .filter(wp => wp.status === 'completed')
    .map(wp => wp.poiId),                           // 초록
  endPoiId: waypoints[waypoints.length - 1]?.poiId, // 빨강 펄스
};
```

### 9.4 자동 층 전환

"도착" 버튼 클릭 시 다음 목적지의 `floorLevel`을 확인하여 `setCurrentFloor`를 호출합니다. 환자가 직접 FloorSelector를 조작할 필요 없이 자동으로 해당 층 지도가 표시됩니다.

### 9.5 층 이동 안내 텍스트

현재 leg의 세그먼트 중 `floorTransition`이 있는 세그먼트를 찾아 DestinationCard의 `floorInstruction`에 전달합니다:

```typescript
const floorInstruction = currentSegments?.segments
  .find(s => s.floorTransition)
  ?.floorTransition?.instruction;
// 예: "엘리베이터를 타고 1층으로 이동하세요"
```

---

## 10. PatientPage 반응형 레이아웃

### 10.1 전체 구조

**파일:** `src/pages/PatientPage.tsx`

```
┌──────────────────────────────────────────────────────────┐
│ PATIENT NAVIGATION                                        │
│ 환자 동선 안내                                             │
│ QR 코드를 간호사에게 보여주고, 안내에 따라 이동하세요.        │
├──────────────────────────────┬───────────────────────────┤
│                              │                           │
│   PatientDashboard           │   사이드바 (lg만)           │
│   (메인 플로우)                │                           │
│                              │   ┌── Hospital Info ─────┐│
│   상태에 따라:                 │   │ 병원: MediWay 데모    ││
│   • QR 코드 표시              │   │ 건물: 본관 (4층)      ││
│   • 진행률 + 지도 + 도착 버튼  │   │ 운영: 09:00-18:00    ││
│   • 완료 화면                 │   │ 응급: 02-000-0000    ││
│                              │   └──────────────────────┘│
│                              │                           │
│                              │   ┌── 이용 안내 ──────────┐│
│                              │   │ 🏥 엘리베이터 안내     ││
│                              │   │ 💊 약국 안내          ││
│                              │   │ 🅿️ 주차 정산         ││
│                              │   │ ❓ 도움 요청          ││
│                              │   └──────────────────────┘│
│                              │                           │
│                              │   ┌── Nearby Services ───┐│
│                              │   │ 편의점  · 1층 · 45m   ││
│                              │   │ 화장실  · 현재 층 · 30m││
│                              │   │ EV A   · 현재 층 · 20m││
│                              │   └──────────────────────┘│
└──────────────────────────────┴───────────────────────────┘
```

### 10.2 반응형 브레이크포인트

| 뷰포트 | 그리드 | 사이드바 | max-width |
|--------|--------|---------|-----------|
| 모바일 (< 1024px) | 1열 | `hidden` | `max-w-2xl` |
| 데스크톱 (≥ 1024px) | `grid-cols-[1fr_340px]` | `lg:block` | `max-w-5xl` |

### 10.3 사이드바 컴포넌트

**Hospital Info** — 병원 기본 정보:

| 항목 | 값 |
|------|-----|
| 병원 | MediWay 데모 병원 |
| 건물 | 본관 (4층) |
| 운영 시간 | 09:00 - 18:00 |
| 응급 연락 | 02-000-0000 |

**이용 안내** — 팁 카드 4개:

| 아이콘 | 제목 | 설명 |
|--------|------|------|
| 🏥 | 엘리베이터 이용 | 본관 엘리베이터는 각 층 우측에 위치합니다. |
| 💊 | 약국 안내 | 외래약국은 1층 정문 옆에 있습니다. |
| 🅿️ | 주차 정산 | 원무과에서 주차 할인 도장을 받으세요. |
| ❓ | 도움이 필요하면 | 보라색 조끼를 입은 안내 도우미에게 문의하세요. |

**Nearby Services** — 근처 편의시설:

| 이름 | 위치 |
|------|------|
| 편의점 | 1층 · 45m |
| 화장실 | 현재 층 · 30m |
| 엘리베이터 A | 현재 층 · 20m |

---

## 11. 컴포넌트 상세 명세

### 11.1 파일별 Props 요약

| 컴포넌트 | Props | 주요 이벤트 |
|---------|-------|-----------|
| `QRDisplay` | `onTokenGenerated` | 토큰 생성 |
| `RouteProgress` | `waypoints`, `currentIndex`, `onWaypointClick?` | 경유지 클릭 |
| `DestinationCard` | `destination`, `segmentTime?`, `segmentDistance?`, `floorInstruction?`, `currentLeg`, `totalLegs` | — |
| `ArrivalButton` | `onArrival` | 도착 확인 |
| `CompletionScreen` | `totalSteps`, `onReset?` | 홈/새동선 |
| `PatientDashboard` | (없음) | 내부 상태 관리 |
| `PatientPage` | (없음) | 페이지 컴포넌트 |

### 11.2 컴포넌트 의존성

```
PatientPage
└── PatientDashboard
    ├── QRDisplay
    │   └── qrcode.react (QRCodeSVG)
    │   └── uuid (v4)
    ├── RouteProgress
    │   └── getPOIById (shortName 조회)
    ├── DestinationCard
    │   └── (POI 데이터 직접 전달)
    ├── HospitalMapContainer (Phase B)
    │   └── MapRenderer → SvgNativeMapRenderer
    │       └── PathOverlay (currentFloorSegment)
    │       └── POIMarkerLayer (highlights)
    ├── ArrivalButton
    └── CompletionScreen

데이터 흐름:
  computeRoute() → routeResult → legs[currentIndex] → segments
                                                        ↓
                                          currentFloorSegment → HospitalMapContainer
                                          floorInstruction → DestinationCard
  waypoints + currentIndex → RouteProgress
  waypoints + currentIndex → highlights → HospitalMapContainer
```

---

## 12. Phase F 연계

### 12.1 현재 (Phase E) → Phase F 변경 사항

| 현재 (로컬 시뮬레이션) | Phase F (Firebase 연동) |
|---------------------|----------------------|
| "동선 수신 시뮬레이션" 버튼 | Firebase `onValue` 리스너로 자동 수신 |
| `useState`로 waypoints 관리 | `useSession` 훅 → sessionStore ↔ Realtime DB 동기화 |
| QR 토큰 로컬 생성만 | `/qr_tokens/{token}` DB 등록 + status 구독 |
| "도착" 상태 로컬만 업데이트 | `/sessions/{sessionId}/waypoints/{i}/status` DB 업데이트 |
| 알림 없음 | FCM 푸시 ("동선이 도착했습니다", "다음 목적지: ..." 등) |

### 12.2 데모 시뮬레이션 → 실제 플로우 전환

Phase F에서 `PatientDashboard`의 `handleSimulateReceive`는 제거되고, 대신:

```typescript
// useSession 훅이 Firebase onValue로 세션 변경을 구독
const { session } = useSession(qrToken);

useEffect(() => {
  if (session?.status === 'navigating') {
    const route = computeRoute(navigationGraph, session.waypoints.map(w => w.poiId));
    setRouteResult(route);
    setState('navigating');
  }
}, [session]);
```

### 12.3 세션 복원

브라우저 새로고침 시 `localStorage`에 `sessionId`를 저장하여, 페이지 재로드 후에도 진행 중인 세션을 복원합니다. Phase F에서 구현됩니다.

---

*본 문서는 MediWay Phase E 구현 완료 시점의 기능 명세입니다.*
*Phase F(Firebase)에서 로컬 시뮬레이션을 실시간 동기화로 전환하면 전체 플로우가 완성됩니다.*
