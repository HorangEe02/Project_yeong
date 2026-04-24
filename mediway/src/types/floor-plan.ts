import type { Coordinate } from './hospital';

/** 방 유형 (스타일링용) */
export type RoomType =
  | 'clinic'
  | 'lab'
  | 'imaging'
  | 'pharmacy'
  | 'admin'
  | 'elevator'
  | 'stairs'
  | 'restroom'
  | 'convenience'
  | 'lobby'
  | 'corridor'
  | 'checkup'
  | 'consultation';

/** 방 geometry — rect 또는 polygon */
export type RoomGeometry =
  | { kind: 'rect'; x: number; y: number; width: number; height: number }
  | { kind: 'polygon'; points: Coordinate[] };

/** 방 데이터 */
export interface RoomData {
  id: string;
  label: string;
  type: RoomType;
  geometry: RoomGeometry;
  labelPosition: Coordinate;
  labelRotation?: number;
}

/** 벽 세그먼트 */
export interface WallData {
  id: string;
  points: Coordinate[];
  thickness?: number;
}

/** 문 */
export interface DoorData {
  id: string;
  position: Coordinate;
  width: number;
  angle?: number;
  roomId?: string;
}

/** 복도 영역 */
export interface CorridorData {
  id: string;
  points: Coordinate[];
  label?: string;
}

/** 한 층의 전체 평면도 데이터 */
export interface FloorPlanData {
  floorLevel: number;
  floorName: string;
  rooms: RoomData[];
  walls: WallData[];
  doors: DoorData[];
  corridors: CorridorData[];
  buildingOutline: Coordinate[];
}
