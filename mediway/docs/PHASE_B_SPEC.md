# MediWay Phase B — 지도 추상화 + SVG 평면도 렌더러 기능 설명서

> 작성일: 2026-04-16 | Phase B 구현 완료 시점 기준
> 빌드 결과: JS 232KB / CSS 9.8KB (gzip 후 ~75KB)

---

## 목차

1. [개요](#1-개요)
2. [아키텍처 — Strategy 패턴 지도 추상화](#2-아키텍처--strategy-패턴-지도-추상화)
3. [SVG Native 렌더러](#3-svg-native-렌더러)
4. [SVG 레이어 컴포넌트 상세](#4-svg-레이어-컴포넌트-상세)
5. [POI 마커 시스템](#5-poi-마커-시스템)
6. [경로 오버레이 시스템](#6-경로-오버레이-시스템)
7. [HospitalMapContainer — 오케스트레이터](#7-hospitalmapcontainer--오케스트레이터)
8. [FloorSelector — 층 전환 UI](#8-floorselector--층-전환-ui)
9. [디자인 스타일 시스템](#9-디자인-스타일-시스템)
10. [환자 페이지 통합](#10-환자-페이지-통합)
11. [컴포넌트 의존성 다이어그램](#11-컴포넌트-의존성-다이어그램)
12. [Phase C 연계](#12-phase-c-연계)

---

## 1. 개요

### 1.1 Phase B의 목적

Phase B는 MediWay의 **실내 지도 렌더링 시스템**을 구축하는 단계입니다. Phase A에서 정의한 JSON 평면도 데이터(RoomData, WallData 등)를 **인터랙티브한 SVG 평면도**로 동적 렌더링하며, 향후 Leaflet 렌더러 추가를 위한 **추상화 레이어**를 설계합니다.

### 1.2 Phase B에서 구현된 것

| 영역 | 구현 내용 | 파일 수 |
|------|----------|--------|
| **지도 추상화** | Strategy 패턴 Context, 다형성 MapRenderer, 오케스트레이터 | 4개 |
| **SVG 렌더러** | react-zoom-pan-pinch 줌/패닝 + 7개 SVG 레이어 조합 | 1개 |
| **SVG 레이어** | BuildingOutline, CorridorLayer, RoomLayer, WallLayer, DoorLayer, POIMarkerLayer, PathOverlay | 7개 |
| **스타일 시스템** | 방 13종 색상, POI 6종 하이라이트, 경로 3종, 구조물 스타일 | 1개 |
| **UI 컴포넌트** | FloorSelector (층 전환 탭) | 1개 |
| **페이지 통합** | PatientPage에 HospitalMapContainer 연결 | 수정 1개 |

### 1.3 핵심 설계 결정

| 결정 | 이유 |
|------|------|
| SVG Native를 기본 렌더러로 사용 | JSON→SVG 직접 변환, 좌표 변환 불필요, 가벼운 번들 |
| react-zoom-pan-pinch 사용 | 핀치 줌, 부드러운 패닝, 더블클릭 리셋 내장 |
| 7개 레이어를 각각 `React.memo` | 층 전환/경로 변경 시 변경된 레이어만 리렌더링 |
| SVG `<defs>` + `<filter>` 활용 | 활성 방 glow 효과를 CSS 없이 SVG 네이티브로 구현 |

---

## 2. 아키텍처 — Strategy 패턴 지도 추상화

### 2.1 설계 원칙

두 가지 지도 렌더러(SVG Native, Leaflet)가 **동일한 인터페이스**(`MapRendererProps`)를 구현합니다. 소비 측 컴포넌트(HospitalMapContainer, PatientDashboard 등)는 렌더러 구현을 모르고, Context를 통해 런타임에 렌더러가 결정됩니다.

### 2.2 컴포넌트 계층 구조

```
MapRendererProvider (type="svg-native")     ← Context로 렌더러 선택
└── HospitalMapContainer                    ← 오케스트레이터 (데이터 로드 + 층 필터)
    ├── FloorSelector                       ← 층 전환 탭 (1F/2F/3F/4F)
    └── MapRenderer                         ← 다형성 디스패처
        └── SvgNativeMapRenderer            ← SVG 렌더러 (현재 유일한 구현체)
            └── <TransformWrapper>          ← react-zoom-pan-pinch
                └── <svg viewBox="0 0 1200 800">
                    ├── <defs> (filters)    ← active-glow 필터
                    ├── BuildingOutline     ← Layer 0: 건물 외벽
                    ├── CorridorLayer       ← Layer 1: 복도 영역
                    ├── RoomLayer           ← Layer 2: 방 (rect/polygon + 라벨)
                    ├── WallLayer           ← Layer 3: 구조벽
                    ├── DoorLayer           ← Layer 4: 문
                    ├── PathOverlay         ← Layer 5: 경로 폴리라인
                    └── POIMarkerLayer      ← Layer 6: POI 마커
```

### 2.3 데이터 흐름

```
useMapStore (currentFloor, rendererType)
    ↓
HospitalMapContainer
    ├── getFloorPlan(currentFloor) → FloorPlanData
    ├── getPOIsByFloor(currentFloor) → POI[]
    ├── pathSegment?.floorLevel === currentFloor → 현재 층 경로만 필터
    ↓
MapRenderer (MapRendererProps)
    ↓
SvgNativeMapRenderer
    ├── floorPlanData → BuildingOutline, CorridorLayer, RoomLayer, WallLayer, DoorLayer
    ├── pois → POIMarkerLayer
    ├── pathSegment → PathOverlay
    └── highlights → POIMarkerLayer (마커 스타일 결정)
```

### 2.4 주요 인터페이스

**`MapRendererProps`** — 모든 렌더러가 받는 공통 Props:

| Prop | 타입 | 설명 |
|------|------|------|
| `floorLevel` | `number` | 현재 표시할 층 |
| `floorPlanData` | `FloorPlanData` | 방, 벽, 복도, 문 데이터 |
| `pois` | `POI[]` | 현재 층의 POI 목록 |
| `pathSegment?` | `PathSegment` | 현재 층의 경로 세그먼트 |
| `highlights?` | `MapHighlights` | POI 하이라이트 상태 |
| `events?` | `MapEvents` | 이벤트 핸들러 (onPoiClick 등) |
| `className?` | `string` | 외부 컨테이너 CSS |

**`MapHighlights`** — POI 하이라이트 제어:

| 필드 | 설명 |
|------|------|
| `startPoiId` | 출발지 POI (파랑, 펄스) |
| `endPoiId` | 도착지 POI (빨강, 펄스) |
| `currentPoiId` | 현재 진행 중인 POI (파랑, 큰 펄스) |
| `completedPoiIds` | 완료된 POI 배열 (초록) |

---

## 3. SVG Native 렌더러

### 3.1 `SvgNativeMapRenderer.tsx`

**파일 위치:** `src/components/map/svg-renderer/SvgNativeMapRenderer.tsx`

**역할:** react-zoom-pan-pinch로 줌/패닝을 제공하는 SVG 컨테이너에 7개 레이어를 Z-순서대로 배치합니다.

**주요 기능:**

| 기능 | 구현 방식 |
|------|----------|
| 줌 | `TransformWrapper` — minScale 0.5, maxScale 3 |
| 패닝 | velocity 기반 부드러운 드래그 |
| 더블클릭 리셋 | `doubleClick.mode: 'reset'` |
| 핀치 줌 | 모바일 터치 자동 지원 |
| 뷰포트 | `viewBox="0 0 1200 800"`, maxHeight 70vh |

**SVG 필터 정의:**

```xml
<filter id="active-glow">
  <!-- 활성 방에 MediWay Blue(#004e9f) 20% glow 효과 -->
  <feGaussianBlur stdDeviation="4" />
  <feFlood floodColor="#004e9f" floodOpacity="0.2" />
  <feComposite operator="in" />
  <feMerge> glow + SourceGraphic </feMerge>
</filter>
```

### 3.2 좌표계 규약

| 항목 | 값 |
|------|-----|
| viewBox | `0 0 1200 800` |
| 원점 | 좌상단 (0,0) |
| x축 | 오른쪽 증가 (0→1200) |
| y축 | 아래쪽 증가 (0→800) |
| 단위 | SVG 픽셀 (비지리적) |

POI 좌표, 방 geometry, 경로 pathCoordinates가 모두 이 좌표계를 공유합니다. SVG Native 렌더러에서는 좌표 변환이 필요 없습니다. (Leaflet 렌더러에서는 `[x,y]` → `[y,x]` 변환 필요)

---

## 4. SVG 레이어 컴포넌트 상세

### 4.1 레이어 렌더링 순서

SVG에서는 나중에 그려진 요소가 위에 표시됩니다. 따라서 아래 순서로 레이어를 배치합니다:

| Z-순서 | 레이어 | 역할 | 상호작용 |
|--------|--------|------|---------|
| 0 | `BuildingOutline` | 건물 외벽 polygon | 없음 |
| 1 | `CorridorLayer` | 복도 영역 + 라벨 | 없음 |
| 2 | `RoomLayer` | 방 rect/polygon + 라벨 | activeRoomId 하이라이트 |
| 3 | `WallLayer` | 구조벽 polyline | 없음 |
| 4 | `DoorLayer` | 문 위치 대시선 | 없음 |
| 5 | `PathOverlay` | 경로 폴리라인 + 애니메이션 | 없음 |
| 6 | `POIMarkerLayer` | POI 마커 + 라벨 + 펄스 | 클릭 이벤트 |

### 4.2 `BuildingOutline` — Layer 0

**파일:** `layers/BuildingOutline.tsx`

건물 외벽을 단일 `<polygon>`으로 렌더링합니다. Phase A 데이터의 `buildingOutline: Coordinate[]`를 사용합니다.

| 스타일 속성 | 값 |
|------------|-----|
| fill | `#ffffff` (흰색 배경) |
| stroke | `#cbd5e1` (회색 테두리) |
| strokeWidth | 3 |
| strokeLinejoin | round |

### 4.3 `CorridorLayer` — Layer 1

**파일:** `layers/CorridorLayer.tsx`

복도 영역을 반투명 `<polygon>`으로 렌더링합니다. 선택적으로 복도 이름 라벨을 중앙에 표시합니다.

| 스타일 속성 | 값 |
|------------|-----|
| fill | `#f8fafc` |
| fillOpacity | 0.4 |
| stroke | none |
| 라벨 색상 | `#cbd5e1`, 10px |

라벨 위치는 polygon 꼭짓점들의 **중심점(centroid)**을 자동 계산합니다.

### 4.4 `RoomLayer` — Layer 2

**파일:** `layers/RoomLayer.tsx`

가장 복잡한 레이어입니다. 각 방을 `RoomType`에 따라 다른 색상으로 렌더링합니다.

**방 geometry 처리:**

| geometry.kind | SVG 요소 | 추가 속성 |
|---------------|---------|----------|
| `rect` | `<rect>` | rx=6, ry=6 (둥근 모서리) |
| `polygon` | `<polygon>` | points 문자열 변환 |

**활성 상태 (activeRoomId 일치 시):**

| 변경 속성 | 기본값 → 활성값 |
|----------|---------------|
| fillOpacity | 0.7 → 0.95 |
| strokeWidth | 1 → 2.5 |
| filter | 없음 → `url(#active-glow)` |

**라벨 속성:**

| 속성 | 값 |
|------|-----|
| textAnchor | `middle` |
| dominantBaseline | `central` |
| fontSize | RoomType별 11~13px |
| fontWeight | 600 |
| pointerEvents | `none` (클릭 방지) |
| labelRotation | 선택적 회전 (transform rotate) |

### 4.5 `WallLayer` — Layer 3

**파일:** `layers/WallLayer.tsx`

구조벽을 `<polyline>`으로 렌더링합니다. 방과 방 사이의 분리벽을 표현합니다.

| 스타일 속성 | 값 |
|------------|-----|
| stroke | `#94a3b8` |
| strokeWidth | 기본 4, WallData.thickness로 오버라이드 가능 |
| strokeLinecap | round |
| strokeLinejoin | round |

### 4.6 `DoorLayer` — Layer 4

**파일:** `layers/DoorLayer.tsx`

문 위치를 대시선(`<line>`)으로 표시합니다. 벽의 "열린 부분"을 시각적으로 나타냅니다.

| 스타일 속성 | 값 |
|------------|-----|
| stroke | `#e2e8f0` (밝은 회색) |
| strokeWidth | 2 |
| strokeDasharray | `4 3` |
| strokeLinecap | round |

문은 `position`을 중심으로 `width/2`만큼 좌우로 펼쳐지며, `angle`이 있으면 SVG `transform="rotate()"` 적용됩니다.

---

## 5. POI 마커 시스템

### 5.1 `POIMarkerLayer` — Layer 6

**파일:** `layers/POIMarkerLayer.tsx`

각 POI를 원형 마커 + 텍스트 라벨로 렌더링합니다.

### 5.2 하이라이트 우선순위

`MapHighlights`에 따라 POI별 스타일이 결정됩니다. 우선순위:

| 순위 | 조건 | 스타일 | 색상 | 반경 | 펄스 |
|------|------|--------|------|------|------|
| 1 | `currentPoiId` 일치 | current | `#2563eb` | 12px | O |
| 2 | `startPoiId` 일치 | start | `#004e9f` | 10px | O |
| 3 | `endPoiId` 일치 | end | `#dc2626` | 10px | O |
| 4 | `completedPoiIds`에 포함 | completed | `#16a34a` | 8px | X |
| 5 | 그 외 | pending | `#9ca3af` | 6px | X |
| — | highlights 미지정 시 | default | `#64748b` | 7px | X |

### 5.3 펄스 애니메이션

`pulse: true`인 마커에는 SVG `<animate>` 요소로 주의를 끄는 파동 효과가 적용됩니다:

```xml
<circle r="16" fill="none" stroke="#2563eb" opacity="0.4">
  <animate attributeName="r" values="14;22;14" dur="2s" repeatCount="indefinite" />
  <animate attributeName="opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
</circle>
```

- 반지름이 `radius+2` ~ `radius+10` 사이에서 2초 주기로 변동
- opacity가 0.4 ~ 0.1 사이에서 페이드

### 5.4 마커 구성 요소

각 POI 마커는 다음 SVG 요소로 구성됩니다:

```
<g class="poi-marker">           ← 클릭 이벤트 핸들러
  <circle ... animate />          ← (선택) 펄스 링
  <circle />                      ← 본체 원 (fill + 흰색 테두리)
  <text />                        ← (선택) 내부 텍스트 (EV, 계단)
  <text />                        ← 라벨 (마커 아래쪽)
</g>
```

### 5.5 라벨 표시 규칙

- highlights가 **없을 때**: 모든 POI 라벨 표시
- highlights가 **있을 때**: `pending` 상태인 POI의 라벨은 숨김 (정보 과부하 방지)
- `elevator`/`stairs` 카테고리: 마커 내부에 짧은 약어(EV, 계단) 표시

---

## 6. 경로 오버레이 시스템

### 6.1 `PathOverlay` — Layer 5

**파일:** `layers/PathOverlay.tsx`

`PathSegment`의 좌표 배열을 SVG `<polyline>`으로 렌더링합니다.

### 6.2 경로 구성 요소

```
<g class="layer-path-overlay">
  <polyline />     ← 배경 (흰색, 넓은 선 — 그림자 역할)
  <polyline />     ← 본체 (색상, 대시 패턴, 애니메이션)
  <circle />       ← 시작점 마커
  <circle />       ← 끝점 마커
  <style />        ← (선택) dash 이동 애니메이션 CSS
</g>
```

### 6.3 경로 변형 (variant)

| variant | 용도 | 색상 | 선 두께 | 대시 | 애니메이션 |
|---------|------|------|---------|------|-----------|
| `active` | 현재 진행 중인 경로 | `#004e9f` (MediWay Blue) | 4px | `12 6` | O (0.8초 주기) |
| `completed` | 이미 지나간 경로 | `#9ca3af` (회색) | 3px | none (실선) | X |
| `upcoming` | 아직 도착 전 경로 | `#93c5fd` (연한 파랑) | 2px | `6 4` | X |

### 6.4 Dash 이동 애니메이션

```css
@keyframes dash-move {
  to { stroke-dashoffset: -18; }
}
.path-animated {
  animation: dash-move 0.8s linear infinite;
}
```

`strokeDasharray="12 6"` (12px 선 + 6px 간격)이 적용된 상태에서 `dashoffset`이 지속적으로 감소하여 "경로를 따라 이동하는" 시각 효과를 만듭니다.

### 6.5 배경 라인

본체 경로 아래에 흰색 반투명(opacity 0.6) 배경 라인을 깔아 경로가 방/복도 위에서도 명확히 보이도록 합니다. 배경 라인은 본체보다 3px 더 넓습니다.

---

## 7. HospitalMapContainer — 오케스트레이터

### 7.1 역할

**파일:** `src/components/map/HospitalMapContainer.tsx`

데이터 계층과 렌더링 계층을 연결하는 **오케스트레이터** 컴포넌트입니다.

### 7.2 데이터 로직

| 동작 | 구현 |
|------|------|
| 현재 층 데이터 로드 | `getFloorPlan(currentFloor)` → FloorPlanData |
| 현재 층 POI 필터 | `getPOIsByFloor(currentFloor)` → POI[] |
| 경로 세그먼트 필터 | `pathSegment?.floorLevel === currentFloor` 검사 |
| 렌더러 타입 | `useMapStore(s => s.rendererType)` |
| 층 변경 | `useMapStore(s => s.setCurrentFloor)` |
| POI 클릭 | `useMapStore(s => s.setSelectedPoiId)` |

### 7.3 Props

| Prop | 타입 | 설명 |
|------|------|------|
| `pathSegment?` | `PathSegment` | 표시할 경로 (Phase C에서 Dijkstra 결과 전달) |
| `highlights?` | `MapHighlights` | POI 하이라이트 (Phase E에서 세션 상태 기반 전달) |
| `className?` | `string` | 추가 CSS |

### 7.4 에러 처리

`getFloorPlan(currentFloor)`이 undefined를 반환하면 "층 데이터를 찾을 수 없습니다" 메시지를 표시합니다.

---

## 8. FloorSelector — 층 전환 UI

### 8.1 동작

**파일:** `src/components/map/FloorSelector.tsx`

MediWay 데모 병원의 4개 층(1층~4층)을 탭 버튼으로 표시합니다.

### 8.2 스타일

| 상태 | 배경 | 텍스트 | 그림자 |
|------|------|--------|--------|
| 비활성 | 투명 | `on-surface-variant` | 없음 |
| 호버 | `surface-container` | `on-surface-variant` | 없음 |
| 활성 | `surface-container-lowest` | `primary` | `shadow-ambient` |

컨테이너는 `surface-container-high` 배경에 `rounded-xl` + `p-1`로 DESIGN.md의 No-Line Rule을 준수합니다 (border 대신 배경색 차이로 영역 구분).

### 8.3 Props

| Prop | 타입 | 설명 |
|------|------|------|
| `floors` | `{ level: number; name: string }[]` | 층 목록 |
| `currentFloor` | `number` | 현재 선택된 층 |
| `onFloorChange` | `(level: number) => void` | 층 변경 콜백 |

---

## 9. 디자인 스타일 시스템

### 9.1 `floorPlanStyles.ts`

**파일:** `src/components/map/svg-renderer/styles/floorPlanStyles.ts`

지도 렌더링에 사용되는 모든 시각적 상수를 중앙 관리합니다.

### 9.2 방 유형별 색상 팔레트

| 방 유형 | fill | stroke | label 색상 | 용도 |
|---------|------|--------|-----------|------|
| clinic | `#dbeafe` | `#93c5fd` | `#1e40af` | 진료실 (내과, 외과, 소아과 등) |
| lab | `#fef3c7` | `#fcd34d` | `#92400e` | 검사실 (채혈실) |
| imaging | `#ede9fe` | `#c4b5fd` | `#5b21b6` | 영상의학 (CT, MRI, X-ray) |
| pharmacy | `#d1fae5` | `#6ee7b7` | `#065f46` | 약국 |
| admin | `#e0e7ff` | `#a5b4fc` | `#3730a3` | 원무과, 접수, 행정 |
| elevator | `#f3f4f6` | `#9ca3af` | `#374151` | 엘리베이터 |
| stairs | `#f3f4f6` | `#9ca3af` | `#374151` | 계단 |
| restroom | `#f9fafb` | `#d1d5db` | `#6b7280` | 화장실 |
| convenience | `#fff7ed` | `#fdba74` | `#9a3412` | 편의점 |
| lobby | `#f0fdf4` | `#86efac` | `#166534` | 로비, 대기실 |
| corridor | `#f9fafb` | none | `#9ca3af` | 복도 (거의 투명) |
| checkup | `#ecfeff` | `#67e8f9` | `#155e75` | 건강검진 관련 |
| consultation | `#fdf2f8` | `#f9a8d4` | `#9d174d` | 상담실 |

### 9.3 구조물 스타일

| 구조물 | fill | stroke | strokeWidth |
|--------|------|--------|------------|
| 건물 외벽 | `#ffffff` | `#cbd5e1` | 3 |
| 구조벽 | — | `#94a3b8` | 4 |
| 문 | — | `#e2e8f0` | 2 (dash) |
| 복도 | `#f8fafc` (40%) | none | — |

---

## 10. 환자 페이지 통합

### 10.1 `PatientPage.tsx` 변경

Phase A의 플레이스홀더를 대체하여 `HospitalMapContainer`를 통합했습니다.

**현재 표시 내용:**
- 제목: "환자 동선 안내"
- 안내 텍스트: "아래 지도에서 병원 내부 구조를 확인할 수 있습니다."
- **HospitalMapContainer** — 4층 평면도 (층 탭으로 전환 가능, 줌/패닝 가능)
- Phase E 예고 카드: "QR 코드 표시 및 동선 안내 UI가 Phase E에서 구현됩니다."

### 10.2 현재 사용자 인터랙션

| 인터랙션 | 동작 |
|---------|------|
| 층 탭 클릭 | 해당 층 평면도로 전환 |
| 지도 드래그 | 패닝 |
| 마우스 휠 / 핀치 | 줌 인/아웃 |
| 더블클릭 | 줌 리셋 |
| POI 마커 클릭 | mapStore.selectedPoiId 업데이트 (현재는 시각적 변화 없음) |

---

## 11. 컴포넌트 의존성 다이어그램

```
                  PatientPage
                      │
                      ▼
              HospitalMapContainer
              ┌───────┴───────┐
              ▼               ▼
        FloorSelector    MapRendererProvider
                              │
                              ▼
                         MapRenderer
                              │
                              ▼
                   SvgNativeMapRenderer
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               BuildingOutline  ...  POIMarkerLayer
                    ▲         ▲         ▲
                    │         │         │
              floorPlanStyles.ts (공통 스타일 상수)
                    ▲
                    │
              ROOM_STYLES / HIGHLIGHT_STYLES / PATH_STYLES / STRUCTURE_STYLES

데이터 흐름 (Zustand):
  mapStore ──→ HospitalMapContainer
  (currentFloor, rendererType, selectedPoiId)

데이터 흐름 (정적 데이터):
  data/hospital/index.ts ──→ HospitalMapContainer
  (floorPlanMap, allPOIs, demoHospital)
```

---

## 12. Phase C 연계

### 12.1 Phase C에서 PathOverlay가 활성화되는 시점

Phase C에서 Dijkstra 알고리즘이 구현되면, `computeRoute()` 함수가 `RouteResult`를 반환합니다. 이 결과의 `legs[i].segments`에서 현재 층에 해당하는 `PathSegment`를 추출하여 `HospitalMapContainer`의 `pathSegment` prop으로 전달하면, 경로가 지도 위에 애니메이션과 함께 표시됩니다.

### 12.2 Phase E에서 highlights가 활성화되는 시점

Phase E에서 환자 세션의 `waypoints` 상태를 기반으로 `MapHighlights` 객체를 구성합니다:

```typescript
const highlights: MapHighlights = {
  currentPoiId: session.waypoints[session.currentWaypointIndex].poiId,
  completedPoiIds: session.waypoints
    .filter(wp => wp.status === 'completed')
    .map(wp => wp.poiId),
  endPoiId: session.waypoints[session.waypoints.length - 1].poiId,
};
```

이것을 `HospitalMapContainer`에 전달하면 POI 마커가 자동으로 하이라이트됩니다.

---

*본 문서는 MediWay Phase B 구현 완료 시점의 기능 명세입니다.*
*Phase C(Dijkstra)와 Phase E(환자 UI)에서 pathSegment/highlights를 연결하면 지도가 완전히 동작합니다.*
