import type { Coordinate } from '@/types/hospital';

/** 두 좌표 간 유클리드 거리 (SVG 픽셀 단위) */
export function euclideanDistance(a: Coordinate, b: Coordinate): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * 이동 시간 추정 (초)
 * 병원 내 보행 속도: 약 1.2m/s (4.3km/h)
 */
export function estimateWalkingTime(distanceMeters: number): number {
  const WALKING_SPEED = 1.2; // m/s
  return Math.round(distanceMeters / WALKING_SPEED);
}

/** 초 → "N분" 또는 "N분 N초" 표시 형식 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return sec > 0 ? `${min}분 ${sec}초` : `${min}분`;
}

/** 미터 → "Nm" 또는 "N.Nkm" 표시 형식 */
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)}m`;
  return `${(meters / 1000).toFixed(1)}km`;
}
