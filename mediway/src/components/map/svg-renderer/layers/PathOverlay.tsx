import { memo } from 'react';
import type { PathSegment } from '@/types/navigation';
import { PATH_STYLES } from '../styles/floorPlanStyles';

interface Props {
  segment?: PathSegment;
  variant?: 'active' | 'completed' | 'upcoming';
}

export const PathOverlay = memo(function PathOverlay({
  segment,
  variant = 'active',
}: Props) {
  if (!segment || segment.coordinates.length < 2) return null;

  const style = PATH_STYLES[variant];
  const points = segment.coordinates.map((p) => `${p.x},${p.y}`).join(' ');

  return (
    <g className="layer-path-overlay">
      {/* 경로 배경 (그림자 효과) */}
      <polyline
        points={points}
        fill="none"
        stroke="#ffffff"
        strokeWidth={style.strokeWidth + 3}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.6}
      />

      {/* 경로 본체 */}
      <polyline
        points={points}
        fill="none"
        stroke={style.stroke}
        strokeWidth={style.strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={style.dashArray}
        className={style.animated ? 'path-animated' : undefined}
      />

      {/* 시작점 마커 */}
      <circle
        cx={segment.coordinates[0].x}
        cy={segment.coordinates[0].y}
        r={6}
        fill={style.stroke}
        stroke="#ffffff"
        strokeWidth={2}
      />

      {/* 끝점 마커 */}
      <circle
        cx={segment.coordinates[segment.coordinates.length - 1].x}
        cy={segment.coordinates[segment.coordinates.length - 1].y}
        r={6}
        fill={style.stroke}
        stroke="#ffffff"
        strokeWidth={2}
      />

      {/* CSS 애니메이션 정의 */}
      {style.animated && (
        <style>{`
          .path-animated {
            animation: dash-move 0.8s linear infinite;
          }
          @keyframes dash-move {
            to { stroke-dashoffset: -18; }
          }
        `}</style>
      )}
    </g>
  );
});
