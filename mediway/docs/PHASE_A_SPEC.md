# MediWay Phase A — 프로젝트 기초 구조 및 데이터 모델 기능 설명서

> 작성일: 2026-04-16 | Phase A 구현 완료 시점 기준
> 빌드 결과: JS 168KB / CSS 8.6KB (gzip 후 ~58KB)

---

## 목차

1. [개요](#1-개요)
2. [기술 스택 및 프로젝트 구성](#2-기술-스택-및-프로젝트-구성)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [타입 시스템](#4-타입-시스템)
5. [가상 병원 데이터](#5-가상-병원-데이터)
6. [상태 관리 (Zustand)](#6-상태-관리-zustand)
7. [라우팅 및 페이지](#7-라우팅-및-페이지)
8. [공통 컴포넌트](#8-공통-컴포넌트)
9. [디자인 시스템](#9-디자인-시스템)
10. [빌드 및 실행](#10-빌드-및-실행)

---

## 1. 개요

### 1.1 Phase A의 목적

Phase A는 MediWay Phase 1 웹 데모의 **기반 인프라**를 구축하는 단계입니다. 이후 단계(Phase B~G)에서 지도 렌더링, 경로 탐색, QR 매칭, Firebase 연동 등을 구현하기 위한 토대를 마련합니다.

### 1.2 Phase A에서 구현된 것

| 영역 | 구현 내용 |
|------|----------|
| **프로젝트 스캐폴딩** | Vite + React 18 + TypeScript, 의존성 설치, 빌드 설정 |
| **디자인 시스템** | Tailwind CSS에 MediWay 디자인 토큰 통합 (DESIGN.md 준수) |
| **타입 시스템** | 6개 타입 정의 파일 — 전체 도메인 모델 완성 |
| **가상 병원 데이터** | 31개 POI, 4층 평면도, 네비게이션 그래프(56노드/~80엣지), 6개 동선 템플릿 |
| **상태 관리** | Zustand 스토어 3개 (세션, 네비게이션, 지도) |
| **라우팅** | React Router 4개 경로, 3개 페이지 (랜딩/의료진/환자) |
| **공통 UI** | Header (Glassmorphism), Loading 스피너 |

### 1.3 Phase A에서 구현되지 않은 것

- 실내 지도 렌더링 (Phase B)
- Dijkstra 경로 탐색 (Phase C)
- 의료진 UI — QR 스캐너, 동선 전송 (Phase D)
- 환자 UI — 지도 네비게이션, 도착 확인 (Phase E)
- Firebase 연동 — 인증, 실시간 DB, 푸시 알림 (Phase F)
- 통합 테스트 및 배포 (Phase G)

---

## 2. 기술 스택 및 프로젝트 구성

### 2.1 핵심 기술 스택

| 영역 | 기술 | 버전 | 용도 |
|------|------|------|------|
| 프레임워크 | React | 18.x | UI 컴포넌트 렌더링 |
| 언어 | TypeScript | 5.x | 정적 타입 검사, 도메인 모델 정의 |
| 빌드 | Vite | 8.x | 개발 서버, 프로덕션 번들링 |
| 스타일링 | Tailwind CSS | 3.x | 유틸리티 기반 스타일링, 디자인 토큰 |
| 상태 관리 | Zustand | 4.x | 전역 상태 (세션, 네비게이션, 지도) |
| 라우팅 | React Router | 6.x | SPA 클라이언트 라우팅 |

### 2.2 설치된 런타임 의존성 (Phase B~G에서 사용)

| 패키지 | 용도 | 사용 단계 |
|--------|------|----------|
| `firebase` | 인증, 실시간 DB, 푸시 알림 | Phase F |
| `leaflet` + `react-leaflet` | Leaflet 기반 실내 지도 렌더러 | Phase B |
| `react-zoom-pan-pinch` | SVG Native 렌더러 줌/패닝 | Phase B |
| `qrcode.react` | QR 코드 생성 (환자용) | Phase E |
| `html5-qrcode` | QR 코드 스캔 (의료진용) | Phase D |
| `lucide-react` | 아이콘 라이브러리 | 전 단계 |
| `uuid` | QR 토큰 및 세션 ID 생성 | Phase D, E |

### 2.3 빌드 설정

**`vite.config.ts`**
- `@/` 경로 별칭 → `src/` 디렉토리 매핑
- 개발 서버 포트: 3000

**`tsconfig.app.json`**
- `strict: true` — 엄격한 타입 검사
- `paths: { "@/*": ["./src/*"] }` — 모듈 경로 별칭
- `target: es2023`, `jsx: react-jsx`

---

## 3. 디렉토리 구조

```
mediway/src/
├── main.tsx                          # 앱 엔트리 포인트
├── App.tsx                           # BrowserRouter + 라우트 정의
├── index.css                         # Tailwind 디렉티브 + glass 유틸리티
│
├── config/                           # [Phase F] Firebase 설정
│
├── types/                            # 도메인 타입 정의 (6개)
│   ├── hospital.ts                   # POI, Coordinate, Building, Hospital
│   ├── floor-plan.ts                 # RoomData, WallData, FloorPlanData
│   ├── navigation.ts                 # NavNode, NavEdge, PathResult, RouteResult
│   ├── session.ts                    # Session, Waypoint, QRToken
│   ├── route-template.ts             # RouteTemplate
│   └── map-renderer.ts              # MapRendererProps, MapHighlights
│
├── data/                             # 가상 병원 정적 데이터
│   ├── hospital/
│   │   ├── index.ts                  # 데이터 재수출 + 헬퍼 함수
│   │   ├── pois.ts                   # 31개 POI 정의
│   │   ├── navigation-graph.ts       # 네비게이션 그래프 (56노드, ~80엣지)
│   │   └── floor-plans/
│   │       ├── floor1.ts             # 1층: 로비/접수/약국
│   │       ├── floor2.ts             # 2층: 내과/외과/채혈실
│   │       ├── floor3.ts             # 3층: 영상의학과/정형외과
│   │       └── floor4.ts             # 4층: 건강검진센터
│   └── route-templates.ts            # 6개 동선 템플릿
│
├── stores/                           # Zustand 전역 상태
│   ├── sessionStore.ts               # 세션 + QR 토큰 + 경유지 진행
│   ├── navigationStore.ts            # 경로 결과 + 현재 구간
│   └── mapStore.ts                   # 렌더러 타입 + 층 선택 + POI 선택
│
├── services/                         # [Phase C, F] 비즈니스 로직
├── hooks/                            # [Phase B~F] 커스텀 훅
│
├── components/
│   ├── common/
│   │   ├── Header.tsx                # Glassmorphism 네비게이션 바
│   │   └── Loading.tsx               # 로딩 스피너
│   ├── map/                          # [Phase B] 지도 렌더러
│   │   ├── svg-renderer/             # SVG Native 렌더러
│   │   └── leaflet-renderer/         # Leaflet 렌더러
│   ├── staff/                        # [Phase D] 의료진 UI
│   └── patient/                      # [Phase E] 환자 UI
│
└── pages/
    ├── LandingPage.tsx               # 역할 선택 화면
    ├── StaffPage.tsx                 # 의료진 대시보드 (플레이스홀더)
    └── PatientPage.tsx               # 환자 동선 안내 (플레이스홀더)
```

---

## 4. 타입 시스템

Phase A에서 정의된 6개 타입 파일은 MediWay의 전체 도메인 모델을 구성합니다.

### 4.1 `types/hospital.ts` — 병원 기본 모델

| 타입 | 설명 | 주요 필드 |
|------|------|----------|
| `Coordinate` | SVG 좌표 (viewBox 0 0 1200 800 기준) | `x`, `y` |
| `POICategory` | 관심 지점 분류 (12종) | `'clinic'`, `'lab'`, `'imaging'`, `'pharmacy'`, `'admin'`, `'elevator'`, `'stairs'`, `'restroom'`, `'parking'`, `'entrance'`, `'convenience'`, `'lobby'` |
| `POI` | 관심 지점 | `id`, `name`, `shortName`, `category`, `floorLevel`, `coordinates` |
| `Floor` | 층 정보 | `level`, `name` |
| `Building` | 건물 | `id`, `name`, `floors[]` |
| `Hospital` | 병원 | `id`, `name`, `buildings[]` |

**좌표계 규약:**
- 모든 좌표는 SVG viewBox `"0 0 1200 800"` 기준의 픽셀 좌표
- 원점 (0,0)은 좌상단, x축은 오른쪽, y축은 아래쪽
- 이 좌표계는 평면도 렌더링, POI 마커, 경로 폴리라인 등 모든 시각적 요소에 공통 적용

### 4.2 `types/floor-plan.ts` — 평면도 데이터 모델

| 타입 | 설명 | 용도 |
|------|------|------|
| `RoomType` | 방 유형 (13종) | 스타일링(색상/투명도) 결정 |
| `RoomGeometry` | 방 형태 — `rect` 또는 `polygon` | SVG `<rect>` 또는 `<polygon>` 렌더링 |
| `RoomData` | 방 정보 | `id`, `label`, `type`, `geometry`, `labelPosition` |
| `WallData` | 벽 세그먼트 | `points[]` (polyline), `thickness` |
| `DoorData` | 문 | `position`, `width`, `angle` |
| `CorridorData` | 복도 영역 | `points[]` (polygon), `label` |
| `FloorPlanData` | 한 층의 전체 평면도 | `rooms[]`, `walls[]`, `doors[]`, `corridors[]`, `buildingOutline` |

**설계 철학:**
평면도는 정적 SVG 파일이 아니라 **JSON 데이터 기반 React 컴포넌트**로 동적 생성됩니다. 이를 통해 타입 안전성, 동적 스타일링(활성 방 하이라이트), 클릭 이벤트 핸들링이 가능합니다.

### 4.3 `types/navigation.ts` — 네비게이션 그래프 및 경로 모델

| 타입 | 설명 | 주요 필드 |
|------|------|----------|
| `NavNode` | 그래프 노드 | `type: 'poi' \| 'junction'`, `floorLevel`, `coordinates`, `poiId?` |
| `NavEdge` | 그래프 엣지 | `fromNodeId`, `toNodeId`, `weight`(초), `distance`(미터), `pathCoordinates[]`, `floorTransition?` |
| `NavigationGraph` | 전체 그래프 | `nodes[]`, `edges[]` |
| `PathSegment` | 한 층 내 경로 세그먼트 | `floorLevel`, `coordinates[]`, `instruction`, `floorTransition?` |
| `PathResult` | 두 POI 간 경로 결과 | `segments[]`, `totalDistance`, `totalTime` |
| `RouteResult` | 전체 동선 (경유지 체인) | `waypoints[]`, `legs: PathResult[]` |

**그래프 구조 특징:**
- **POI 노드**: 실제 관심 지점 (진료실, 약국 등)에 대응
- **Junction 노드**: 복도 교차점 — L자형 경로를 위한 중간 노드
- **층간 이동 엣지**: `floorTransition` 속성으로 엘리베이터/계단 구분, `pathCoordinates`는 빈 배열 (지도에 그릴 것이 없음)
- **가중치**: 이동 시간(초) 기준 — Dijkstra 알고리즘의 최적화 대상

### 4.4 `types/session.ts` — 세션 및 QR 모델

| 타입 | 설명 | 주요 필드 |
|------|------|----------|
| `WaypointStatus` | 경유지 상태 | `'pending'`, `'current'`, `'completed'` |
| `Waypoint` | 경유지 | `poiId`, `status`, `arrivedAt?` |
| `SessionStatus` | 세션 상태 | `'waiting'`, `'navigating'`, `'completed'` |
| `QRTokenStatus` | QR 토큰 상태 | `'waiting'`, `'matched'`, `'expired'` |
| `QRToken` | QR 토큰 (Realtime DB) | `patientUid`, `status`, `sessionId?` |
| `Session` | 세션 (Realtime DB) | `sessionId`, `patientUid`, `staffUid?`, `waypoints[]`, `currentWaypointIndex`, `status` |

**세션 상태 머신:**
```
waiting ──→ navigating ──→ completed
(QR 대기)   (동선 안내 중)  (모든 경유지 완료)
```

### 4.5 `types/route-template.ts` — 동선 템플릿

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | `string` | 템플릿 고유 ID |
| `name` | `string` | 표시명 (예: "채혈 → 원무과 → 약국 → 귀가") |
| `departmentTag` | `string` | 소속 진료과 (예: "내과") |
| `color` | `string` | 구분 색상 (HEX) |
| `waypointPoiIds` | `string[]` | 순서대로 방문할 POI ID 배열 |
| `estimatedTotalTime` | `number` | 예상 소요 시간 (분) |
| `isDefault` | `boolean` | 기본 템플릿 여부 |

### 4.6 `types/map-renderer.ts` — 지도 렌더러 추상화

| 타입 | 설명 |
|------|------|
| `MapRendererType` | 렌더러 종류: `'leaflet'` 또는 `'svg-native'` |
| `MapViewport` | 뷰포트 상태 (center, zoom, bounds) |
| `MapEvents` | 이벤트 핸들러 (onPoiClick, onMapClick, onViewportChange) |
| `MapHighlights` | POI 하이라이트 (start, end, current, completed) |
| `MapRendererProps` | 모든 렌더러가 받는 공통 Props |

**추상화 설계:**
두 가지 지도 렌더러(SVG Native, Leaflet)가 `MapRendererProps` 인터페이스를 공통으로 구현합니다. Strategy 패턴으로 런타임에 렌더러를 전환할 수 있습니다.

---

## 5. 가상 병원 데이터

### 5.1 데모 병원 개요

| 항목 | 값 |
|------|-----|
| 병원명 | MediWay 데모 병원 |
| 건물 | 본관 1동 |
| 층수 | 4층 |
| POI 수 | 31개 |
| 네비게이션 노드 | 56개 (POI 31 + Junction 25) |
| 네비게이션 엣지 | ~80개 (같은 층 ~72 + 층간 6) |
| 동선 템플릿 | 6개 |

### 5.2 층별 구성

#### 1층 — 로비 / 접수 / 약국 (`floor1.ts`)

```
┌──────────────────────────────────────────────────┐
│  [정문 출입구]                                     │
│                                                    │
│  ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────────────┐│
│  │ 접수  │ │원무과 │ │ 외래약국  │ │    로비      ││
│  └──────┘ └──────┘ └──────────┘ └──────────────┘│
│                                                    │
│  ═══════════ [1층 중앙 복도] ══════════════════════│
│                                                    │
│  ┌──────┐ ┌──────┐              ┌────┐ ┌────┐   │
│  │편의점 │ │화장실 │              │ EV │ │계단│   │
│  └──────┘ └──────┘              └────┘ └────┘   │
└──────────────────────────────────────────────────┘
```

**POI (8개):** entrance_main, admin_reception, admin_billing, pharmacy_main, lobby_1f, elevator_1, stairs_1, convenience_store

#### 2층 — 내과 / 외과 / 채혈실 (`floor2.ts`)

```
┌──────────────────────────────────────────────────┐
│  ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────────────┐│
│  │내과1  │ │내과2  │ │  채혈실   │ │ 2층 대기실   ││
│  └──────┘ └──────┘ └──────────┘ └──────────────┘│
│                                                    │
│  ═══════════ [2층 중앙 복도] ══════════════════════│
│                                                    │
│  ┌──────┐ ┌──────┐ ┌──────┐    ┌────┐ ┌────┐   │
│  │외과1  │ │외과2  │ │화장실│    │ EV │ │계단│   │
│  └──────┘ └──────┘ └──────┘    └────┘ └────┘   │
│  ┌──────┐                                        │
│  │소아과 │                                        │
│  └──────┘                                        │
└──────────────────────────────────────────────────┘
```

**POI (8개):** clinic_internal_1, clinic_internal_2, lab_blood, clinic_surgery_1, clinic_surgery_2, clinic_pediatrics, elevator_2, stairs_2

#### 3층 — 영상의학과 / 정형외과 / 재활의학과 (`floor3.ts`)

```
┌──────────────────────────────────────────────────┐
│  ┌──────────┐ ┌────────────┐ ┌──────────────────┐│
│  │CT 촬영실  │ │MRI 촬영실   │ │   3층 대기실     ││
│  └──────────┘ └────────────┘ └──────────────────┘│
│                                                    │
│  ═══════════ [3층 중앙 복도] ══════════════════════│
│                                                    │
│  ┌──────────┐ ┌──────────────┐ ┌────┐ ┌────┐    │
│  │X-ray     │ │영상의학과 접수│ │ EV │ │계단│    │
│  └──────────┘ └──────────────┘ └────┘ └────┘    │
│  ┌──────┐ ┌────────┐                              │
│  │정형외과│ │재활의학 │                              │
│  └──────┘ └────────┘                              │
└──────────────────────────────────────────────────┘
```

**POI (8개):** imaging_ct, imaging_mri, imaging_xray, imaging_reception, clinic_orthopedics, clinic_rehab, elevator_3, stairs_3

#### 4층 — 건강검진센터 (`floor4.ts`)

```
┌──────────────────────────────────────────────────┐
│  ┌─────────────────────────────┐ ┌──────────────┐│
│  │    검진센터 접수/대기         │ │   행정실      ││
│  └─────────────────────────────┘ └──────────────┘│
│                                                    │
│  ═══════════ [4층 중앙 복도] ══════════════════════│
│                                                    │
│  ┌──────┐ ┌──────┐ ┌──────────┐ ┌────┐ ┌────┐  │
│  │검진1  │ │검진2  │ │ 내시경실  │ │ EV │ │계단│  │
│  └──────┘ └──────┘ └──────────┘ └────┘ └────┘  │
│  ┌──────┐ ┌──────┐                                │
│  │상담실 │ │화장실 │                                │
│  └──────┘ └──────┘                                │
└──────────────────────────────────────────────────┘
```

**POI (7개):** checkup_reception, checkup_room_1, checkup_room_2, checkup_endoscopy, checkup_consult, elevator_4, stairs_4

### 5.3 네비게이션 그래프 (`navigation-graph.ts`)

#### 노드 구성

| 유형 | 개수 | 설명 |
|------|------|------|
| POI 노드 | 31개 | 각 POI에 대응 (1:1) |
| Junction 노드 | 25개 | 복도 교차점 — L자형 경로를 위한 중간 노드 |
| **합계** | **56개** | |

#### 엣지 구성

| 유형 | 개수 | 가중치 기준 |
|------|------|-----------|
| POI ↔ Junction (같은 층) | ~48 | 이동 시간 8~20초 |
| Junction ↔ Junction (복도) | ~24 | 이동 시간 2~38초 |
| 엘리베이터 (층간) | 3 | 30초/층 |
| 계단 (층간) | 3 | 45초/층 |
| **합계** | **~78** | |

#### 층간 이동 설계

엘리베이터와 계단은 각 층에 **동일한 x,y 좌표**에 위치하며, 층간 엣지로 연결됩니다:

```
elevator_1 (1층, x:940, y:430)
    ↕  30초
elevator_2 (2층, x:940, y:430)
    ↕  30초
elevator_3 (3층, x:940, y:430)
    ↕  30초
elevator_4 (4층, x:940, y:430)
```

층간 이동 엣지의 `pathCoordinates`는 **빈 배열**입니다 — 지도 위에 그릴 경로가 없기 때문입니다. 대신 UI에서 텍스트 안내("엘리베이터를 타고 3층으로 이동하세요")로 처리합니다.

### 5.4 동선 템플릿 (`route-templates.ts`)

| ID | 이름 | 진료과 | 색상 | 경유지 | 예상 시간 |
|----|------|--------|------|--------|----------|
| rt_1 | 채혈 → 원무과 → 약국 → 귀가 | 내과 | 파랑 | lab_blood → admin_billing → pharmacy_main → entrance_main | 15분 |
| rt_2 | 원무과 → 약국 → 귀가 | 내과 | 초록 | admin_billing → pharmacy_main → entrance_main | 8분 |
| rt_3 | 영상의학과 → 원무과 → 약국 → 귀가 | 내과 | 노랑 | imaging_reception → admin_billing → pharmacy_main → entrance_main | 20분 |
| rt_4 | 채혈 → 영상의학과 → 원무과 → 약국 → 귀가 | 외과 | 주황 | lab_blood → imaging_reception → admin_billing → pharmacy_main → entrance_main | 25분 |
| rt_5 | 채혈 → CT → 내시경 → 상담 → 원무과 → 귀가 | 건강검진 | 청록 | lab_blood → imaging_ct → checkup_endoscopy → checkup_consult → admin_billing → entrance_main | 35분 |
| rt_6 | X-ray → 정형외과 → 원무과 → 약국 → 귀가 | 정형외과 | 보라 | imaging_xray → clinic_orthopedics → admin_billing → pharmacy_main → entrance_main | 22분 |

### 5.5 데이터 접근 API (`data/hospital/index.ts`)

| 함수/상수 | 시그니처 | 설명 |
|----------|---------|------|
| `demoHospital` | `Hospital` | 병원 메타데이터 |
| `allPOIs` | `POI[]` | 전체 31개 POI 배열 |
| `getPOIsByFloor(level)` | `(number) → POI[]` | 층별 POI 필터링 |
| `getPOIById(id)` | `(string) → POI \| undefined` | ID로 POI 단건 조회 |
| `getFloorPlan(level)` | `(number) → FloorPlanData \| undefined` | 층별 평면도 데이터 |
| `floorPlanMap` | `Record<number, FloorPlanData>` | 층→평면도 맵 |
| `navigationGraph` | `NavigationGraph` | 전체 네비게이션 그래프 |

---

## 6. 상태 관리 (Zustand)

### 6.1 `mapStore` — 지도 상태

| 상태 | 타입 | 기본값 | 설명 |
|------|------|-------|------|
| `rendererType` | `MapRendererType` | `'svg-native'` | 현재 지도 렌더러 |
| `currentFloor` | `number` | `1` | 현재 표시 중인 층 |
| `selectedPoiId` | `string \| null` | `null` | 선택된 POI |

| 액션 | 시그니처 | 설명 |
|------|---------|------|
| `setRendererType` | `(type) → void` | 렌더러 전환 |
| `setCurrentFloor` | `(floor) → void` | 층 변경 |
| `setSelectedPoiId` | `(id) → void` | POI 선택/해제 |

### 6.2 `sessionStore` — 세션 상태

| 상태 | 타입 | 설명 |
|------|------|------|
| `session` | `Session \| null` | 현재 활성 세션 |
| `qrToken` | `string \| null` | 환자 QR 토큰 |
| `isConnected` | `boolean` | Firebase 연결 상태 |

| 액션 | 설명 |
|------|------|
| `setSession` | 세션 설정/해제 |
| `setQrToken` | QR 토큰 설정 |
| `updateSessionStatus` | 세션 상태 변경 (waiting/navigating/completed) |
| `advanceWaypoint` | 현재 경유지 완료 → 다음 경유지로 이동. 마지막이면 세션 완료 처리 |

**`advanceWaypoint` 로직:**
1. 현재 경유지(currentWaypointIndex)를 `completed`로 변경, `arrivedAt` 타임스탬프 기록
2. 다음 경유지를 `current`로 변경
3. `currentWaypointIndex` 1 증가
4. 마지막 경유지였으면 세션 `status`를 `completed`로 변경

### 6.3 `navigationStore` — 네비게이션 상태

| 상태 | 타입 | 설명 |
|------|------|------|
| `routeResult` | `RouteResult \| null` | 계산된 전체 경로 |
| `currentLegIndex` | `number` | 현재 진행 중인 구간 인덱스 |

| 액션 | 설명 |
|------|------|
| `setRouteResult` | 경로 설정 (인덱스 초기화) |
| `advanceLeg` | 다음 구간으로 이동 |
| `reset` | 경로 및 인덱스 초기화 |

---

## 7. 라우팅 및 페이지

### 7.1 라우트 구조

| 경로 | 컴포넌트 | 역할 |
|------|---------|------|
| `/` | `LandingPage` | 역할 선택 (의료진 / 환자) |
| `/staff` | `StaffPage` | 의료진 대시보드 |
| `/patient` | `PatientPage` | 환자 동선 안내 (QR 대기) |
| `/patient/:sessionId` | `PatientPage` | 특정 세션의 동선 안내 |

### 7.2 LandingPage

역할 선택 화면으로, 두 개의 카드를 제공합니다:

- **의료진 카드** (`/staff`): Stethoscope 아이콘, "QR 스캔 후 환자에게 동선을 전송합니다"
- **환자 카드** (`/patient`): User 아이콘, "QR 코드를 보여주고 동선 안내를 받습니다"

디자인 특징:
- MediWay 로고 (MapPin 아이콘 + 그라디언트 배경)
- `shadow-ambient` 카드 스타일 (DESIGN.md의 Ambient Shadows)
- 호버 시 `shadow-ambient-lg`로 승격

### 7.3 StaffPage / PatientPage

현재 플레이스홀더 상태. Phase D, E에서 각각 구현 예정.

---

## 8. 공통 컴포넌트

### 8.1 Header

| 속성 | 값 |
|------|-----|
| 스타일 | Glassmorphism (`glass` 유틸리티: bg-white/80 + backdrop-blur-20px) |
| 위치 | `sticky top-0 z-50` |
| 좌측 | MediWay 로고 (MapPin + 그라디언트 아이콘) |
| 우측 | 현재 역할 뱃지 (의료진/환자) — 경로 기반 자동 감지 |

### 8.2 Loading

최소한의 로딩 인디케이터:
- 중앙 정렬 스피너 (border-top 색상 애니메이션)
- 커스텀 메시지 prop

---

## 9. 디자인 시스템

### 9.1 Tailwind 커스텀 토큰

DESIGN.md의 "Editorial Clinical Excellence" 디자인 시스템을 Tailwind 설정에 통합했습니다.

#### 색상 토큰

| 토큰 | 값 | 용도 |
|------|-----|------|
| `primary` | `#004e9f` | MediWay Blue — 핵심 액션 |
| `primary-container` | `#0066cc` | 그라디언트 끝점, 보조 액센트 |
| `surface` | `#f9f9fb` | 기본 배경 캔버스 |
| `surface-container-lowest` | `#ffffff` | 최상위 카드, 활성 요소 |
| `surface-container-high` | `#e8e8ea` | 오목한 영역 (검색바, 비활성 배경) |
| `on-surface` | `#1a1c1d` | 기본 텍스트 (순수 검정 금지) |
| `on-surface-variant` | `#414753` | 보조 텍스트 |
| `error` | `#ba1a1a` | 에러 상태 |

#### POI 카테고리 색상

| 카테고리 | 토큰 | 색상 | 용도 |
|---------|------|------|------|
| 진료실 | `poi-clinic` | `#dbeafe` | 파란 계열 |
| 검사실 | `poi-lab` | `#fef3c7` | 노란 계열 |
| 영상의학 | `poi-imaging` | `#ede9fe` | 보라 계열 |
| 약국 | `poi-pharmacy` | `#d1fae5` | 초록 계열 |
| 원무/행정 | `poi-admin` | `#e0e7ff` | 인디고 계열 |
| 건강검진 | `poi-checkup` | `#ecfeff` | 청록 계열 |

#### 커스텀 애니메이션

| 애니메이션 | 클래스 | 용도 |
|-----------|--------|------|
| `dash-move` | `animate-dash-move` | 경로 폴리라인 이동 효과 |
| `pulse` | `animate-poi-pulse` | 현재 POI 마커 펄스 효과 |

### 9.2 Glass 유틸리티

```css
.glass      → bg-white/80 + backdrop-blur-20px  /* Header, 부유 요소 */
.glass-modal → bg-surface/80 + backdrop-blur-20px /* 모달 오버레이 */
```

### 9.3 DESIGN.md 준수 사항

| 규칙 | 구현 상태 |
|------|----------|
| No-Line Rule (1px border 금지) | 모든 카드/영역에서 배경색 차이로 구분 |
| 순수 검정 금지 | `on-surface: #1a1c1d` 사용 |
| xl 둥근 모서리 (1.5rem) | `rounded-xl` 클래스 |
| 최소 터치 타겟 44px | 버튼/링크 최소 크기 확보 |
| Ambient Shadows | `shadow-ambient` (primary-tinted, 4~8% opacity) |
| Glassmorphism | `glass` 유틸리티 (Header에 적용) |

---

## 10. 빌드 및 실행

### 10.1 개발 서버

```bash
cd mediway
npm run dev
# → http://localhost:3000
```

### 10.2 프로덕션 빌드

```bash
npm run build
# 출력: dist/ (index.html + assets/)
# JS: 168KB (gzip 55KB)
# CSS: 8.6KB (gzip 2.7KB)
```

### 10.3 타입 체크

```bash
npx tsc --noEmit
# 에러 없음 — 전체 타입 검사 통과
```

### 10.4 다음 단계

Phase A 완료 후 다음 구현 순서:

| 단계 | 내용 | 의존성 |
|------|------|--------|
| **Phase B** | 지도 추상화 + SVG 평면도 렌더러 | Phase A |
| **Phase C** | Dijkstra 경로 탐색 + 단위 테스트 | Phase A |
| **Phase D** | 의료진 UI (QR 스캔, 동선 선택, 전송) | Phase A, C |
| **Phase E** | 환자 UI (QR, 지도, 도착 확인) | Phase B, C |
| **Phase F** | Firebase (인증, 실시간 DB, FCM) | Phase D, E |
| **Phase G** | 통합 테스트 + Leaflet 렌더러 + 배포 | 전체 |

---

*본 문서는 MediWay Phase A 구현 완료 시점의 기능 명세입니다.*
*다음 Phase 구현 시 본 문서의 타입/데이터 정의를 참조하세요.*
