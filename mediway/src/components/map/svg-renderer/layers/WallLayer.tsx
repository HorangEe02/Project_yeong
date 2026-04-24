import { memo } from 'react';
import type { WallData } from '@/types/floor-plan';
import { STRUCTURE_STYLES } from '../styles/floorPlanStyles';

interface Props {
  walls: WallData[];
}

export const WallLayer = memo(function WallLayer({ walls }: Props) {
  const s = STRUCTURE_STYLES.wall;

  return (
    <g className="layer-walls">
      {walls.map((wall) => {
        const points = wall.points.map((p) => `${p.x},${p.y}`).join(' ');
        return (
          <polyline
            key={wall.id}
            points={points}
            fill="none"
            stroke={s.stroke}
            strokeWidth={wall.thickness ?? s.strokeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        );
      })}
    </g>
  );
});
