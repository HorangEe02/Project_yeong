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

/**
 * 병원 운영 상태.
 * `active` — 정상 서비스. `suspended` — 일시 중단 (forbidden 분기).
 *
 * RTDB 가 미존재이거나 누락된 경우 `HospitalShell` 가 `'active'` 로 간주.
 */
export type HospitalStatus = 'active' | 'suspended';

/**
 * `/hospitals/{slug}/profile` 의 read-side 매핑.
 *
 * 이 객체는 `HospitalShell` 가 slug 기반 라우팅에서 로드한다.
 *  - `id` 는 slug 와 동일 (consistency 거울)
 *  - `themeColor` 는 `#RRGGBB` 6자리 hex. 검증 실패 시 컨슈머가 `#004e9f` 로 fallback.
 *  - `features` 는 hospital 단위 feature flag (예: `{ kakao: true }`). 미존재 OK.
 *  - 옵션 메타(`address`, `phone`, `createdAt`, `updatedAt`) 는 admin 화면에서만 사용.
 *
 * 쓰기 측은 `AdminHospitalDetailPage` 가 담당하며, 본 인터페이스는 호환 가능한
 * 부분 집합으로 유지.
 */
export interface HospitalProfile {
  id: string;
  name: string;
  themeColor?: string;
  status?: HospitalStatus;
  features?: Record<string, boolean>;
  address?: string;
  phone?: string;
  createdAt?: number;
  updatedAt?: number;
}
