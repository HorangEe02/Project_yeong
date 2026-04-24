import { memo } from 'react';
import type { CorridorData } from '@/types/floor-plan';
import { STRUCTURE_STYLES } from '../styles/floorPlanStyles';

interface Props {
  corridors: CorridorData[];
}

export const CorridorLayer = memo(function CorridorLayer({ corridors }: Props) {
  const s = STRUCTURE_STYLES.corridor;

  return (
    <g className="layer-corridors">
      {corridors.map((corridor) => {
        const points = corridor.points.map((p) => `${p.x},${p.y}`).join(' ');
        return (
          <g key={corridor.id}>
            <polygon
              points={points}
              fill={s.fill}
              fillOpacity={s.fillOpacity}
              stroke={s.stroke}
            />
            {corridor.label && (
              <text
                x={corridor.points.reduce((sum, p) => sum + p.x, 0) / corridor.points.length}
                y={corridor.points.reduce((sum, p) => sum + p.y, 0) / corridor.points.length}
                textAnchor="middle"
                dominantBaseline="central"
                fill="#cbd5e1"
                fontSize={10}
                fontWeight={500}
              >
                {corridor.label}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
});
