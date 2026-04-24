/** POI 카테고리 */
export type POICategory =
  | 'clinic'
  | 'lab'
  | 'imaging'
  | 'pharmacy'
  | 'admin'
  | 'elevator'
  | 'stairs'
  | 'restroom'
  | 'parking'
  | 'entrance'
  | 'convenience'
  | 'lobby';

/** SVG 좌표 (viewBox 0 0 1200 800 기준) */
export interface Coordinate {
  x: number;
  y: number;
}

/** 관심 지점 (Point of Interest) */
export interface POI {
  id: string;
  name: string;
  shortName: string;
  category: POICategory;
  buildingId: string;
  floorLevel: number;
  coordinates: Coordinate;
  description?: string;
  icon?: string;
}

/** 층 정보 */
export interface Floor {
  level: number;
  name: string;
}

/** 건물 */
export interface Building {
  id: string;
  name: string;
  floors: Floor[];
}

/** 병원 */
export interface Hospital {
  id: string;
  name: string;
  buildings: Building[];
}
