import type { Coordinate, POI } from './hospital';
import type { FloorPlanData } from './floor-plan';
import type { PathSegment } from './navigation';

/** 렌더러 유형 */
export type MapRendererType = 'leaflet' | 'svg-native';

/** 뷰포트 상태 */
export interface MapViewport {
  center: Coordinate;
  zoom: number;
  bounds?: {
    topLeft: Coordinate;
    bottomRight: Coordinate;
  };
}

/** 지도 이벤트 */
export interface MapEvents {
  onViewportChange?: (viewport: MapViewport) => void;
  onPoiClick?: (poiId: string) => void;
  onMapClick?: (coordinate: Coordinate) => void;
}

/** POI 하이라이트 상태 */
export interface MapHighlights {
  startPoiId?: string;
  endPoiId?: string;
  completedPoiIds?: string[];
  currentPoiId?: string;
}

/** 모든 렌더러가 받는 공통 Props */
export interface MapRendererProps {
  floorLevel: number;
  floorPlanData: FloorPlanData;
  pois: POI[];
  pathSegment?: PathSegment;
  highlights?: MapHighlights;
  viewport?: Partial<MapViewport>;
  events?: MapEvents;
  className?: string;
}
