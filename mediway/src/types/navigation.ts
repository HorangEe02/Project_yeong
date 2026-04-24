import type { Coordinate } from './hospital';

/** 네비게이션 그래프 노드 — POI 또는 복도 교차점 */
export interface NavNode {
  id: string;
  type: 'poi' | 'junction';
  floorLevel: number;
  coordinates: Coordinate;
  poiId?: string;
}

/** 네비게이션 그래프 엣지 */
export interface NavEdge {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  /** 가중치 = 예상 이동 시간 (초) */
  weight: number;
  /** 물리적 거리 (미터, 표시용) */
  distance: number;
  /** 지도 위 경로 렌더링용 SVG 좌표 배열 */
  pathCoordinates: Coordinate[];
  /** 층간 이동 시 */
  floorTransition?: {
    fromFloor: number;
    toFloor: number;
    via: 'elevator' | 'stairs';
  };
  wheelchairAccessible?: boolean;
}

/** 전체 네비게이션 그래프 */
export interface NavigationGraph {
  hospitalId: string;
  nodes: NavNode[];
  edges: NavEdge[];
}

/** 한 층 내 경로 세그먼트 */
export interface PathSegment {
  floorLevel: number;
  coordinates: Coordinate[];
  distance: number;
  time: number;
  instruction: string;
  floorTransition?: {
    toFloor: number;
    via: 'elevator' | 'stairs';
    instruction: string;
  };
}

/** 두 POI 간 경로 탐색 결과 */
export interface PathResult {
  fromPoiId: string;
  toPoiId: string;
  totalDistance: number;
  totalTime: number;
  segments: PathSegment[];
  nodeIds: string[];
}

/** 전체 동선 = 연속 경유지 쌍의 PathResult 체인 */
export interface RouteResult {
  waypoints: string[];
  legs: PathResult[];
  totalDistance: number;
  totalTime: number;
}
