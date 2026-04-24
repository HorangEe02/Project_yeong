import type {
  NavigationGraph,
  NavNode,
  NavEdge,
  PathResult,
  PathSegment,
  RouteResult,
} from '@/types/navigation';

// ============================================================
// C1. PriorityQueue — 바이너리 min-heap
// ============================================================

interface PQItem {
  nodeId: string;
  priority: number;
}

class PriorityQueue {
  private heap: PQItem[] = [];

  get size(): number {
    return this.heap.length;
  }

  isEmpty(): boolean {
    return this.heap.length === 0;
  }

  push(nodeId: string, priority: number): void {
    this.heap.push({ nodeId, priority });
    this.bubbleUp(this.heap.length - 1);
  }

  pop(): PQItem | undefined {
    if (this.heap.length === 0) return undefined;
    const min = this.heap[0];
    const last = this.heap.pop()!;
    if (this.heap.length > 0) {
      this.heap[0] = last;
      this.sinkDown(0);
    }
    return min;
  }

  private bubbleUp(idx: number): void {
    while (idx > 0) {
      const parentIdx = Math.floor((idx - 1) / 2);
      if (this.heap[parentIdx].priority <= this.heap[idx].priority) break;
      [this.heap[parentIdx], this.heap[idx]] = [this.heap[idx], this.heap[parentIdx]];
      idx = parentIdx;
    }
  }

  private sinkDown(idx: number): void {
    const length = this.heap.length;
    while (true) {
      let smallest = idx;
      const left = 2 * idx + 1;
      const right = 2 * idx + 2;
      if (left < length && this.heap[left].priority < this.heap[smallest].priority) {
        smallest = left;
      }
      if (right < length && this.heap[right].priority < this.heap[smallest].priority) {
        smallest = right;
      }
      if (smallest === idx) break;
      [this.heap[smallest], this.heap[idx]] = [this.heap[idx], this.heap[smallest]];
      idx = smallest;
    }
  }
}

// ============================================================
// C2. 인접 리스트 빌더 + Dijkstra
// ============================================================

interface AdjEntry {
  neighborId: string;
  edge: NavEdge;
}

/** 그래프 엣지를 양방향 인접 리스트로 변환 */
function buildAdjacencyList(graph: NavigationGraph): Map<string, AdjEntry[]> {
  const adj = new Map<string, AdjEntry[]>();

  // 모든 노드 초기화
  for (const node of graph.nodes) {
    adj.set(node.id, []);
  }

  // 엣지를 양방향으로 추가
  for (const edge of graph.edges) {
    adj.get(edge.fromNodeId)?.push({ neighborId: edge.toNodeId, edge });

    // 역방향 엣지 생성 (floorTransition도 반전)
    const reverseEdge: NavEdge = {
      ...edge,
      id: `${edge.id}_rev`,
      fromNodeId: edge.toNodeId,
      toNodeId: edge.fromNodeId,
      pathCoordinates: [...edge.pathCoordinates].reverse(),
      floorTransition: edge.floorTransition
        ? {
            fromFloor: edge.floorTransition.toFloor,
            toFloor: edge.floorTransition.fromFloor,
            via: edge.floorTransition.via,
          }
        : undefined,
    };
    adj.get(edge.toNodeId)?.push({ neighborId: edge.fromNodeId, edge: reverseEdge });
  }

  return adj;
}

/**
 * Dijkstra 최단 경로 알고리즘
 * 가중치: 이동 시간(초)
 *
 * @returns 노드 ID 순서 배열 + 사용된 엣지 배열, 또는 경로 없으면 null
 */
function dijkstra(
  adj: Map<string, AdjEntry[]>,
  startId: string,
  endId: string,
): { nodeIds: string[]; edges: NavEdge[] } | null {
  const dist = new Map<string, number>();
  const prev = new Map<string, { nodeId: string; edge: NavEdge } | null>();
  const pq = new PriorityQueue();

  // 초기화
  for (const nodeId of adj.keys()) {
    dist.set(nodeId, Infinity);
    prev.set(nodeId, null);
  }
  dist.set(startId, 0);
  pq.push(startId, 0);

  // 탐색
  while (!pq.isEmpty()) {
    const current = pq.pop()!;
    const { nodeId: currentId, priority: currentDist } = current;

    // 목적지 도달
    if (currentId === endId) break;

    // 이미 더 짧은 경로가 발견된 경우 스킵
    if (currentDist > (dist.get(currentId) ?? Infinity)) continue;

    const neighbors = adj.get(currentId) ?? [];
    for (const { neighborId, edge } of neighbors) {
      const newDist = currentDist + edge.weight;
      if (newDist < (dist.get(neighborId) ?? Infinity)) {
        dist.set(neighborId, newDist);
        prev.set(neighborId, { nodeId: currentId, edge });
        pq.push(neighborId, newDist);
      }
    }
  }

  // 경로 역추적
  if (dist.get(endId) === Infinity) return null;

  const nodeIds: string[] = [];
  const edges: NavEdge[] = [];
  let current: string | undefined = endId;

  while (current) {
    nodeIds.unshift(current);
    const prevEntry = prev.get(current);
    if (prevEntry) {
      edges.unshift(prevEntry.edge);
      current = prevEntry.nodeId;
    } else {
      break;
    }
  }

  return { nodeIds, edges };
}

// ============================================================
// C3. 층별 세그먼트 분할 + 한국어 instruction
// ============================================================

/** 노드 맵 생성 헬퍼 */
function buildNodeMap(graph: NavigationGraph): Map<string, NavNode> {
  const map = new Map<string, NavNode>();
  for (const node of graph.nodes) {
    map.set(node.id, node);
  }
  return map;
}

/** POI 이름 조회 (poiId가 있으면 해당 노드의 id 사용) */
function getNodeDisplayName(node: NavNode): string {
  if (node.type === 'junction') return '복도';
  return node.poiId ?? node.id;
}

/** 경로를 층별 세그먼트로 분할 */
function segmentPathByFloor(
  nodeIds: string[],
  edges: NavEdge[],
  nodeMap: Map<string, NavNode>,
): PathSegment[] {
  if (edges.length === 0) return [];

  const segments: PathSegment[] = [];
  let currentCoords: { x: number; y: number }[] = [];
  let currentFloor = nodeMap.get(nodeIds[0])?.floorLevel ?? 1;
  let segmentDistance = 0;
  let segmentTime = 0;

  // 시작 노드 좌표 추가
  const startNode = nodeMap.get(nodeIds[0]);
  if (startNode) {
    currentCoords.push({ ...startNode.coordinates });
  }

  for (let i = 0; i < edges.length; i++) {
    const edge = edges[i];

    if (edge.floorTransition) {
      // 현재 층 세그먼트 저장
      if (currentCoords.length >= 2) {
        const endNode = nodeMap.get(edge.fromNodeId);
        segments.push({
          floorLevel: currentFloor,
          coordinates: currentCoords,
          distance: segmentDistance,
          time: segmentTime,
          instruction: generateSameFloorInstruction(currentFloor, endNode),
        });
      }

      // 층 전환 세그먼트
      segments.push({
        floorLevel: currentFloor,
        coordinates: [],
        distance: 0,
        time: edge.weight,
        instruction: '',
        floorTransition: {
          toFloor: edge.floorTransition.toFloor,
          via: edge.floorTransition.via,
          instruction: generateFloorTransitionInstruction(edge.floorTransition),
        },
      });

      // 새 층 시작
      currentFloor = edge.floorTransition.toFloor;
      currentCoords = [];
      segmentDistance = 0;
      segmentTime = 0;

      // 새 층의 시작 노드 좌표
      const newFloorNode = nodeMap.get(edge.toNodeId);
      if (newFloorNode) {
        currentCoords.push({ ...newFloorNode.coordinates });
      }
    } else {
      // 같은 층 — 경로 좌표 누적
      if (edge.pathCoordinates.length > 0) {
        // 첫 좌표가 이전 좌표와 중복되면 스킵
        const startIdx =
          currentCoords.length > 0 &&
          edge.pathCoordinates[0].x === currentCoords[currentCoords.length - 1].x &&
          edge.pathCoordinates[0].y === currentCoords[currentCoords.length - 1].y
            ? 1
            : 0;
        for (let j = startIdx; j < edge.pathCoordinates.length; j++) {
          currentCoords.push({ ...edge.pathCoordinates[j] });
        }
      }
      segmentDistance += edge.distance;
      segmentTime += edge.weight;
    }
  }

  // 마지막 세그먼트 저장
  if (currentCoords.length >= 2) {
    const lastNodeId = nodeIds[nodeIds.length - 1];
    const lastNode = nodeMap.get(lastNodeId);
    segments.push({
      floorLevel: currentFloor,
      coordinates: currentCoords,
      distance: segmentDistance,
      time: segmentTime,
      instruction: generateArrivalInstruction(lastNode),
    });
  }

  return segments;
}

function generateSameFloorInstruction(floor: number, targetNode?: NavNode): string {
  if (!targetNode) return `${floor}층 복도를 따라 이동하세요`;
  const name = getNodeDisplayName(targetNode);
  return `${floor}층 복도를 따라 ${name}(으)로 이동하세요`;
}

function generateFloorTransitionInstruction(transition: {
  fromFloor?: number;
  toFloor: number;
  via: 'elevator' | 'stairs';
}): string {
  const method = transition.via === 'elevator' ? '엘리베이터를 타고' : '계단을 이용하여';
  return `${method} ${transition.toFloor}층으로 이동하세요`;
}

function generateArrivalInstruction(node?: NavNode): string {
  if (!node) return '목적지에 도착합니다';
  const name = getNodeDisplayName(node);
  return `${name}에 도착합니다`;
}

// ============================================================
// C4. 공개 API
// ============================================================

/**
 * 두 POI 간 최단 경로를 탐색합니다.
 *
 * @param graph - 전체 네비게이션 그래프
 * @param fromPoiId - 출발 POI ID
 * @param toPoiId - 도착 POI ID
 * @returns PathResult 또는 경로 없으면 null
 */
export function findShortestPath(
  graph: NavigationGraph,
  fromPoiId: string,
  toPoiId: string,
): PathResult | null {
  if (fromPoiId === toPoiId) {
    return {
      fromPoiId,
      toPoiId,
      totalDistance: 0,
      totalTime: 0,
      segments: [],
      nodeIds: [fromPoiId],
    };
  }

  // POI ID → NavNode ID 매핑 (POI 노드는 id === poiId)
  const fromNode = graph.nodes.find((n) => n.poiId === fromPoiId || n.id === fromPoiId);
  const toNode = graph.nodes.find((n) => n.poiId === toPoiId || n.id === toPoiId);

  if (!fromNode || !toNode) return null;

  const adj = buildAdjacencyList(graph);
  const result = dijkstra(adj, fromNode.id, toNode.id);

  if (!result) return null;

  const nodeMap = buildNodeMap(graph);
  const segments = segmentPathByFloor(result.nodeIds, result.edges, nodeMap);

  const totalDistance = result.edges.reduce((sum, e) => sum + e.distance, 0);
  const totalTime = result.edges.reduce((sum, e) => sum + e.weight, 0);

  return {
    fromPoiId,
    toPoiId,
    totalDistance,
    totalTime,
    segments,
    nodeIds: result.nodeIds,
  };
}

/**
 * 경유지 배열(동선 템플릿)을 기반으로 전체 경로를 계산합니다.
 * 연속 경유지 쌍(A→B, B→C, C→D...)에 대해 각각 최단 경로를 구하고 체이닝합니다.
 *
 * @param graph - 전체 네비게이션 그래프
 * @param waypointPoiIds - 순서대로 방문할 POI ID 배열
 * @returns RouteResult 또는 경로 계산 실패 시 null
 */
export function computeRoute(
  graph: NavigationGraph,
  waypointPoiIds: string[],
): RouteResult | null {
  if (waypointPoiIds.length < 2) return null;

  const legs: PathResult[] = [];
  let totalDistance = 0;
  let totalTime = 0;

  for (let i = 0; i < waypointPoiIds.length - 1; i++) {
    const leg = findShortestPath(graph, waypointPoiIds[i], waypointPoiIds[i + 1]);
    if (!leg) return null; // 하나라도 실패하면 전체 실패
    legs.push(leg);
    totalDistance += leg.totalDistance;
    totalTime += leg.totalTime;
  }

  return {
    waypoints: waypointPoiIds,
    legs,
    totalDistance,
    totalTime,
  };
}
