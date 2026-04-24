import type { RoomType } from '@/types/floor-plan';

/** 방 유형별 SVG 스타일 */
export const ROOM_STYLES: Record<
  RoomType,
  {
    fill: string;
    fillOpacity: number;
    stroke: string;
    strokeWidth: number;
    labelColor: string;
    labelSize: number;
  }
> = {
  clinic:       { fill: '#dbeafe', fillOpacity: 0.7, stroke: '#93c5fd', strokeWidth: 1,   labelColor: '#1e40af', labelSize: 13 },
  lab:          { fill: '#fef3c7', fillOpacity: 0.7, stroke: '#fcd34d', strokeWidth: 1,   labelColor: '#92400e', labelSize: 13 },
  imaging:      { fill: '#ede9fe', fillOpacity: 0.7, stroke: '#c4b5fd', strokeWidth: 1,   labelColor: '#5b21b6', labelSize: 13 },
  pharmacy:     { fill: '#d1fae5', fillOpacity: 0.7, stroke: '#6ee7b7', strokeWidth: 1,   labelColor: '#065f46', labelSize: 13 },
  admin:        { fill: '#e0e7ff', fillOpacity: 0.7, stroke: '#a5b4fc', strokeWidth: 1,   labelColor: '#3730a3', labelSize: 13 },
  elevator:     { fill: '#f3f4f6', fillOpacity: 0.9, stroke: '#9ca3af', strokeWidth: 1.5, labelColor: '#374151', labelSize: 11 },
  stairs:       { fill: '#f3f4f6', fillOpacity: 0.9, stroke: '#9ca3af', strokeWidth: 1.5, labelColor: '#374151', labelSize: 11 },
  restroom:     { fill: '#f9fafb', fillOpacity: 0.6, stroke: '#d1d5db', strokeWidth: 1,   labelColor: '#6b7280', labelSize: 11 },
  convenience:  { fill: '#fff7ed', fillOpacity: 0.7, stroke: '#fdba74', strokeWidth: 1,   labelColor: '#9a3412', labelSize: 13 },
  lobby:        { fill: '#f0fdf4', fillOpacity: 0.5, stroke: '#86efac', strokeWidth: 1,   labelColor: '#166534', labelSize: 13 },
  corridor:     { fill: '#f9fafb', fillOpacity: 0.3, stroke: 'none',    strokeWidth: 0,   labelColor: '#9ca3af', labelSize: 11 },
  checkup:      { fill: '#ecfeff', fillOpacity: 0.7, stroke: '#67e8f9', strokeWidth: 1,   labelColor: '#155e75', labelSize: 13 },
  consultation: { fill: '#fdf2f8', fillOpacity: 0.7, stroke: '#f9a8d4', strokeWidth: 1,   labelColor: '#9d174d', labelSize: 13 },
};

/** POI 하이라이트 상태별 스타일 */
export const HIGHLIGHT_STYLES = {
  start:     { fill: '#004e9f', radius: 10, pulse: true,  strokeWidth: 2 },
  end:       { fill: '#dc2626', radius: 10, pulse: true,  strokeWidth: 2 },
  current:   { fill: '#2563eb', radius: 12, pulse: true,  strokeWidth: 2.5 },
  completed: { fill: '#16a34a', radius: 8,  pulse: false, strokeWidth: 1.5 },
  pending:   { fill: '#9ca3af', radius: 6,  pulse: false, strokeWidth: 1 },
  default:   { fill: '#64748b', radius: 7,  pulse: false, strokeWidth: 1 },
} as const;

/** 경로 선 스타일 */
export const PATH_STYLES = {
  active:    { stroke: '#004e9f', strokeWidth: 4, dashArray: '12 6', animated: true },
  completed: { stroke: '#9ca3af', strokeWidth: 3, dashArray: 'none', animated: false },
  upcoming:  { stroke: '#93c5fd', strokeWidth: 2, dashArray: '6 4',  animated: false },
} as const;

/** 건물 외벽 / 벽 / 문 / 복도 스타일 */
export const STRUCTURE_STYLES = {
  buildingOutline: { fill: '#ffffff', stroke: '#cbd5e1', strokeWidth: 3 },
  wall:            { stroke: '#94a3b8', strokeWidth: 4 },
  door:            { stroke: '#e2e8f0', strokeWidth: 2, dashArray: '4 3' },
  corridor:        { fill: '#f8fafc', fillOpacity: 0.4, stroke: 'none' },
} as const;
