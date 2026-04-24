# MediWay Phase C — Dijkstra 경로 탐색 알고리즘 기능 설명서

> 작성일: 2026-04-16 | Phase C 구현 완료 시점 기준
> 테스트 결과: 13/13 통과 (4ms)

---

## 목차

1. [개요](#1-개요)
2. [PriorityQueue — 바이너리 Min-Heap](#2-priorityqueue--바이너리-min-heap)
3. [인접 리스트 빌더](#3-인접-리스트-빌더)
4. [Dijkstra 최단 경로 알고리즘](#4-dijkstra-최단-경로-알고리즘)
5. [층별 세그먼트 분할](#5-층별-세그먼트-분할)
6. [한국어 안내 문구 생성](#6-한국어-안내-문구-생성)
7. [공개 API](#7-공개-api)
8. [유틸리티 함수](#8-유틸리티-함수)
9. [단위 테스트](#9-단위-테스트)
10. [알고리즘 실행 예시](#10-알고리즘-실행-예시)
11. [Phase D/E 연계](#11-phase-de-연계)

---

## 1. 개요

### 1.1 Phase C의 목적

Phase C는 MediWay의 **경로 탐색 엔진**을 구현합니다. Phase A에서 정의한 네비게이션 그래프(56노드, ~80엣지)에 대해 Dijkstra 알고리즘으로 최단 경로를 계산하고, 결과를 층별 세그먼트로 분할하여 Phase B의 지도 렌더러에서 시각화할 수 있는 형태로 반환합니다.

### 1.2 구현 범위

| 구현 항목 | 파일 | 설명 |
|----------|------|------|
| PriorityQueue | `pathfinding.ts` | 바이너리 min-heap (O(log n) push/pop) |
| 인접 리스트 빌더 | `pathfinding.ts` | 엣지 → 양방향 인접 리스트 변환 |
| Dijkstra 알고리즘 | `pathfinding.ts` | 가중치(이동 시간) 기반 최단 경로 |
| 세그먼트 분할 | `pathfinding.ts` | 층 전환 지점에서 경로를 PathSegment[]로 분할 |
| 한국어 instruction | `pathfinding.ts` | 각 세그먼트에 안내 문구 자동 생성 |
| `findShortestPath()` | `pathfinding.ts` | 두 POI 간 최단 경로 API |
| `computeRoute()` | `pathfinding.ts` | 동선 템플릿 전체 경로 계산 API |
| 거리/시간 유틸리티 | `distance.ts` | 유클리드 거리, 보행 시간 추정, 포맷터 |
| Vitest 설정 | `vitest.config.ts` | jsdom 환경, @/ alias |
| 단위 테스트 | `pathfinding.test.ts` | 13개 테스트 케이스 |

### 1.3 핵심 설계 결정

| 결정 | 이유 |
|------|------|
| 가중치 = 이동 시간(초) | 거리보다 시간이 사용자 경험에 직접적 (엘리베이터 대기 30초 반영) |
| 양방향 그래프 | 병원 복도는 양방향 통행 가능 — 역방향 엣지 자동 생성 |
| 클라이언트 사이드 계산 | 그래프 규모가 작아(56노드) 서버 불필요, 즉시 응답 |
| 세그먼트 분할을 알고리즘 내부에서 수행 | 렌더러가 층별 세그먼트만 받으면 되므로 관심사 분리 |

---

## 2. PriorityQueue — 바이너리 Min-Heap

### 2.1 구조

```typescript
interface PQItem {
  nodeId: string;
  priority: number;  // = 누적 이동 시간(초)
}

class PriorityQueue {
  private heap: PQItem[];
  push(nodeId, priority): void;  // O(log n)
  pop(): PQItem | undefined;     // O(log n)
  isEmpty(): boolean;             // O(1)
  get size(): number;             // O(1)
}
```

### 2.2 내부 동작

| 연산 | 시간 복잡도 | 동작 |
|------|-----------|------|
| `push` | O(log n) | 배열 끝에 삽입 → `bubbleUp`으로 힙 속성 복원 |
| `pop` | O(log n) | 루트(최소값) 제거 → 마지막 요소를 루트로 → `sinkDown`으로 힙 속성 복원 |
| `bubbleUp` | O(log n) | 자식이 부모보다 작으면 교환, 루트까지 반복 |
| `sinkDown` | O(log n) | 부모가 자식보다 크면 더 작은 자식과 교환, 리프까지 반복 |

### 2.3 Dijkstra에서의 역할

PriorityQueue는 "아직 방문하지 않은 노드 중 최소 비용 노드"를 효율적으로 추출합니다. Dijkstra의 전체 시간 복잡도: **O((V + E) log V)** — V=56, E≈160(양방향)이므로 사실상 즉시 완료됩니다.

---

## 3. 인접 리스트 빌더

### 3.1 `buildAdjacencyList(graph)`

**입력:** `NavigationGraph` (nodes + edges)
**출력:** `Map<string, AdjEntry[]>` — 각 노드 ID → 이웃 노드 + 엣지 배열

### 3.2 양방향 엣지 처리

모든 엣지를 **양방향**으로 추가합니다:

```
원본 엣지: A → B (weight: 15, distance: 10)
  → adj[A].push({ neighbor: B, edge: 원본 })
  → adj[B].push({ neighbor: A, edge: 역방향 })
```

**역방향 엣지 생성 규칙:**

| 필드 | 원본 | 역방향 |
|------|------|--------|
| `id` | `e1` | `e1_rev` |
| `fromNodeId` | A | B |
| `toNodeId` | B | A |
| `pathCoordinates` | `[p1, p2, p3]` | `[p3, p2, p1]` (역순) |
| `weight` | 15 | 15 (동일) |
| `distance` | 10 | 10 (동일) |
| `floorTransition.fromFloor` | 1 | 2 (반전) |
| `floorTransition.toFloor` | 2 | 1 (반전) |

### 3.3 최종 그래프 규모

| 항목 | 원본 | 양방향 변환 후 |
|------|------|---------------|
| 노드 | 56 | 56 (동일) |
| 엣지 | ~78 | ~156 (×2) |

---

## 4. Dijkstra 최단 경로 알고리즘

### 4.1 알고리즘 흐름

```
입력: adj (인접 리스트), startId, endId
출력: { nodeIds: string[], edges: NavEdge[] } 또는 null

1. 초기화
   - dist[모든 노드] = Infinity
   - dist[startId] = 0
   - prev[모든 노드] = null
   - PQ.push(startId, 0)

2. 탐색 루프
   while PQ is not empty:
     current = PQ.pop()  (최소 비용 노드)
     if current === endId: break (조기 종료)
     if current.dist > dist[current]: skip (더 짧은 경로 이미 발견)
     
     for each neighbor of current:
       newDist = dist[current] + edge.weight
       if newDist < dist[neighbor]:
         dist[neighbor] = newDist
         prev[neighbor] = { nodeId: current, edge }
         PQ.push(neighbor, newDist)

3. 경로 역추적
   if dist[endId] === Infinity: return null (도달 불가)
   
   path = []
   current = endId
   while prev[current] exists:
     path.unshift(current)
     edges.unshift(prev[current].edge)
     current = prev[current].nodeId
   path.unshift(startId)
   
   return { nodeIds: path, edges }
```

### 4.2 조기 종료

목적지에 도달하면 즉시 루프를 종료합니다. 전체 그래프를 탐색할 필요 없이 최단 경로가 확정된 시점에서 멈추므로, 실제 실행 시간이 더 짧습니다.

### 4.3 중복 방문 방지

`if (currentDist > dist[currentId]) continue` — PQ에 같은 노드가 여러 번 들어갈 수 있지만(decrease-key 대신 중복 삽입 방식), 이미 더 짧은 경로가 발견된 경우 스킵합니다.

---

## 5. 층별 세그먼트 분할

### 5.1 `segmentPathByFloor(nodeIds, edges, nodeMap)`

Dijkstra가 반환한 원시 경로(노드 ID 배열 + 엣지 배열)를 **층별 `PathSegment[]`**로 분할합니다.

### 5.2 분할 규칙

| 상황 | 동작 |
|------|------|
| 같은 층 엣지 | `pathCoordinates`를 현재 세그먼트에 누적 |
| 층 전환 엣지 (floorTransition) | 현재 세그먼트 저장 → 전환 세그먼트 추가 → 새 층 세그먼트 시작 |

### 5.3 좌표 중복 제거

연속 엣지의 pathCoordinates에서 이전 엣지의 끝 좌표와 다음 엣지의 시작 좌표가 동일할 수 있습니다. 이를 감지하여 중복 좌표를 제거합니다:

```typescript
// 이전 세그먼트의 마지막 좌표와 현재 엣지의 첫 좌표가 같으면 스킵
const startIdx = (currentCoords[last] === edge.pathCoordinates[0]) ? 1 : 0;
```

### 5.4 층 전환 세그먼트 구조

층 전환 세그먼트는 특별한 구조를 가집니다:

| 필드 | 값 | 설명 |
|------|-----|------|
| `coordinates` | `[]` (빈 배열) | 지도에 그릴 경로가 없음 |
| `distance` | `0` | 수평 이동 없음 |
| `time` | `30` 또는 `45` | 엘리베이터 30초 / 계단 45초 |
| `instruction` | `''` | 메인 instruction은 비어있음 |
| `floorTransition.toFloor` | 이동할 층 | |
| `floorTransition.via` | `'elevator'` 또는 `'stairs'` | |
| `floorTransition.instruction` | 한국어 안내 | "엘리베이터를 타고 3층으로 이동하세요" |

### 5.5 분할 예시

**2층 채혈실 → 1층 원무과** 경로:

```
Dijkstra 원시 결과:
  nodeIds: [lab_blood, jn_2_c, jn_2_d, elevator_2, elevator_1, jn_1_e, jn_1_b, admin_billing]
  edges:   [e_2층복도, e_2층복도, e_엘리베이터접근, e_층간이동, e_1층복도, e_1층복도, e_원무과접근]

세그먼트 분할 결과:
  Segment 1 (2층, 같은 층):
    coordinates: [채혈실→jn_2_c→jn_2_d→엘리베이터2층]
    instruction: "2층 복도를 따라 엘리베이터(으)로 이동하세요"

  Segment 2 (층 전환):
    coordinates: []
    floorTransition: { toFloor: 1, via: 'elevator' }
    floorTransition.instruction: "엘리베이터를 타고 1층으로 이동하세요"

  Segment 3 (1층, 같은 층):
    coordinates: [엘리베이터1층→jn_1_e→jn_1_b→원무과]
    instruction: "admin_billing에 도착합니다"
```

---

## 6. 한국어 안내 문구 생성

### 6.1 문구 생성 함수

| 함수 | 입력 | 출력 예시 |
|------|------|---------|
| `generateSameFloorInstruction` | 층 번호, 대상 노드 | "2층 복도를 따라 엘리베이터(으)로 이동하세요" |
| `generateFloorTransitionInstruction` | floorTransition 객체 | "엘리베이터를 타고 3층으로 이동하세요" |
| `generateArrivalInstruction` | 도착 노드 | "admin_billing에 도착합니다" |

### 6.2 층 전환 문구 패턴

| via | 문구 |
|-----|------|
| `elevator` | "엘리베이터를 타고 {N}층으로 이동하세요" |
| `stairs` | "계단을 이용하여 {N}층으로 이동하세요" |

### 6.3 노드 표시명 규칙

| 노드 type | 표시명 | 예시 |
|-----------|--------|------|
| `poi` | poiId 또는 node.id | `admin_billing`, `lab_blood` |
| `junction` | "복도" (고정) | 복도 |

---

## 7. 공개 API

### 7.1 `findShortestPath(graph, fromPoiId, toPoiId)`

**파일:** `src/services/pathfinding.ts`

두 POI 사이의 최단 경로를 탐색합니다.

**매개변수:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `graph` | `NavigationGraph` | 전체 네비게이션 그래프 |
| `fromPoiId` | `string` | 출발 POI ID |
| `toPoiId` | `string` | 도착 POI ID |

**반환값:** `PathResult | null`

| 필드 | 타입 | 설명 |
|------|------|------|
| `fromPoiId` | `string` | 출발 POI ID |
| `toPoiId` | `string` | 도착 POI ID |
| `totalDistance` | `number` | 총 거리 (미터) |
| `totalTime` | `number` | 총 시간 (초) |
| `segments` | `PathSegment[]` | 층별 경로 세그먼트 |
| `nodeIds` | `string[]` | 전체 경로의 노드 ID 순서 |

**특수 케이스:**

| 상황 | 반환값 |
|------|--------|
| 출발 = 도착 | `{ totalDistance: 0, totalTime: 0, segments: [] }` |
| 존재하지 않는 POI | `null` |
| 도달 불가능 | `null` |

### 7.2 `computeRoute(graph, waypointPoiIds)`

동선 템플릿의 경유지 배열을 기반으로 전체 경로를 계산합니다.

**매개변수:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `graph` | `NavigationGraph` | 전체 네비게이션 그래프 |
| `waypointPoiIds` | `string[]` | 순서대로 방문할 POI ID 배열 |

**반환값:** `RouteResult | null`

| 필드 | 타입 | 설명 |
|------|------|------|
| `waypoints` | `string[]` | 입력된 경유지 배열 (그대로) |
| `legs` | `PathResult[]` | 연속 쌍별 최단 경로 (N-1개) |
| `totalDistance` | `number` | 전체 거리 합산 (미터) |
| `totalTime` | `number` | 전체 시간 합산 (초) |

**동작 원리:**

```
waypointPoiIds: [A, B, C, D]
  → legs[0] = findShortestPath(A, B)
  → legs[1] = findShortestPath(B, C)
  → legs[2] = findShortestPath(C, D)
  → totalDistance = sum(legs[*].totalDistance)
  → totalTime = sum(legs[*].totalTime)
```

**실패 조건:**
- 경유지가 2개 미만 → `null`
- 연속 쌍 중 하나라도 경로를 찾을 수 없으면 → `null` (전체 실패)

---

## 8. 유틸리티 함수

### 8.1 `distance.ts`

**파일:** `src/utils/distance.ts`

| 함수 | 시그니처 | 설명 |
|------|---------|------|
| `euclideanDistance` | `(a: Coordinate, b: Coordinate) → number` | 두 좌표 간 유클리드 거리 (SVG 픽셀) |
| `estimateWalkingTime` | `(meters: number) → number` | 보행 시간 추정 (초). 속도: 1.2m/s |
| `formatDuration` | `(seconds: number) → string` | "15초", "2분", "3분 30초" 형식 |
| `formatDistance` | `(meters: number) → string` | "120m", "1.5km" 형식 |

### 8.2 보행 속도 기준

병원 내 보행 속도는 **1.2m/s (4.3km/h)**로 설정했습니다. 이는 일반 보행 속도(1.4m/s)보다 느린 값으로, 다음을 고려한 것입니다:
- 병원 내 복도 혼잡
- 고령 환자/보호자의 느린 걸음
- 안내 표지판 확인 시간

---

## 9. 단위 테스트

### 9.1 테스트 환경

| 항목 | 설정 |
|------|------|
| 프레임워크 | Vitest 1.6.1 |
| 환경 | jsdom |
| 별칭 | `@/` → `src/` |
| 설정 파일 | `vitest.config.ts` |

### 9.2 테스트 케이스 (13개)

#### `findShortestPath` 테스트 (5개)

| # | 테스트명 | 검증 내용 |
|---|---------|----------|
| 1 | 같은 층 내 경로 (1층: 접수→약국) | 경로 존재, 시간/거리 > 0, 모든 세그먼트 1층 |
| 2 | 층간 이동 경로 (2층 채혈실→1층 원무과) | 층 전환 세그먼트 존재, 한국어 instruction 포함 |
| 3 | 여러 층 건너뛰기 (4층 내시경→1층 약국) | 세그먼트 3개 이상 (4→...→1) |
| 4 | 동일 출발/도착 | 거리=0, 시간=0, 세그먼트 빈 배열 |
| 5 | 존재하지 않는 POI | null 반환 |

#### `computeRoute` 테스트 (8개)

| # | 테스트명 | 검증 내용 |
|---|---------|----------|
| 6 | 템플릿 1: 채혈→원무과→약국→귀가 | legs 3개, waypoints 일치 |
| 7 | 템플릿 2: 원무과→약국→귀가 | legs 2개 |
| 8 | 템플릿 3: 영상의학과→원무과→약국→귀가 | legs 3개, 층간 전환 포함 |
| 9 | 템플릿 4: 채혈→영상의학과→원무과→약국→귀가 | legs 4개 |
| 10 | 템플릿 5: 채혈→CT→내시경→상담→원무과→귀가 | legs 5개 |
| 11 | 템플릿 6: X-ray→정형외과→원무과→약국→귀가 | legs 4개 |
| 12 | 경유지 1개 이하 | null 반환 |
| 13 | 존재하지 않는 POI 포함 | null 반환 |

### 9.3 실행 명령어

```bash
npx vitest run
# 또는
npm test  # (package.json에 스크립트 추가 시)
```

### 9.4 실행 결과

```
 ✓ src/services/__tests__/pathfinding.test.ts  (13 tests) 4ms

 Test Files  1 passed (1)
      Tests  13 passed (13)
   Duration  710ms
```

---

## 10. 알고리즘 실행 예시

### 10.1 템플릿 1 실행: "채혈 → 원무과 → 약국 → 귀가"

```typescript
import { computeRoute } from '@/services/pathfinding';
import { navigationGraph } from '@/data/hospital';

const result = computeRoute(navigationGraph, [
  'lab_blood',        // 2층 채혈실
  'admin_billing',    // 1층 원무과
  'pharmacy_main',    // 1층 약국
  'entrance_main',    // 1층 정문
]);
```

**반환 구조:**

```
RouteResult {
  waypoints: ['lab_blood', 'admin_billing', 'pharmacy_main', 'entrance_main']
  totalDistance: ~65m
  totalTime: ~120초 (약 2분)
  legs: [
    Leg 0: lab_blood → admin_billing
      segments: [
        { floorLevel: 2, instruction: "2층 복도를 따라 이동...", coordinates: [...] }
        { floorTransition: { toFloor: 1, via: 'elevator', instruction: "엘리베이터를 타고 1층..." } }
        { floorLevel: 1, instruction: "admin_billing에 도착합니다", coordinates: [...] }
      ]
    
    Leg 1: admin_billing → pharmacy_main
      segments: [
        { floorLevel: 1, instruction: "pharmacy_main에 도착합니다", coordinates: [...] }
      ]
    
    Leg 2: pharmacy_main → entrance_main
      segments: [
        { floorLevel: 1, instruction: "entrance_main에 도착합니다", coordinates: [...] }
      ]
  ]
}
```

### 10.2 지도 렌더링 연결

```typescript
// Phase B의 HospitalMapContainer에 경로 전달
const currentLeg = result.legs[currentLegIndex];
const currentFloorSegment = currentLeg.segments.find(
  s => s.floorLevel === currentFloor && s.coordinates.length > 0
);

<HospitalMapContainer
  pathSegment={currentFloorSegment}
  highlights={{
    currentPoiId: currentWaypoint.poiId,
    completedPoiIds: completedWaypoints.map(w => w.poiId),
    endPoiId: 'entrance_main',
  }}
/>
```

---

## 11. Phase D/E 연계

### 11.1 Phase D (의료진 UI) 연계

의료진이 동선 템플릿을 선택하면, `computeRoute()`로 전체 경로를 미리 계산하여 예상 시간을 표시합니다:

```typescript
const preview = computeRoute(navigationGraph, template.waypointPoiIds);
// preview.totalTime → "예상 15분"
// preview.legs.length → "4단계"
```

### 11.2 Phase E (환자 UI) 연계

환자가 동선을 수신하면:

1. `computeRoute()`로 전체 RouteResult 계산
2. `navigationStore.setRouteResult(result)` 저장
3. 현재 leg의 segments를 `HospitalMapContainer.pathSegment`로 전달
4. "도착" 버튼 클릭 → `navigationStore.advanceLeg()` → 다음 leg의 segments로 전환
5. 층 전환 세그먼트 → FloorSelector 자동 전환 + 텍스트 안내 표시

### 11.3 성능 특성

| 항목 | 값 |
|------|-----|
| 그래프 규모 | 56노드, ~160엣지(양방향) |
| 단일 경로 계산 | < 1ms |
| 6-경유지 전체 경로 | < 1ms |
| 메모리 | 인접 리스트 ~10KB |

데모 규모에서는 성능 이슈가 전혀 없습니다. 프로덕션(1000+노드)에서는 서버 사이드 계산 또는 A* 알고리즘 전환을 고려해야 합니다.

---

*본 문서는 MediWay Phase C 구현 완료 시점의 기능 명세입니다.*
*Phase D(의료진 UI)와 Phase E(환자 UI)에서 `findShortestPath`/`computeRoute` API를 호출하여 경로 탐색 기능을 활용합니다.*
