import { memo } from 'react';
import type { DoorData } from '@/types/floor-plan';
import { STRUCTURE_STYLES } from '../styles/floorPlanStyles';

interface Props {
  doors: DoorData[];
}

export const DoorLayer = memo(function DoorLayer({ doors }: Props) {
  const s = STRUCTURE_STYLES.door;

  return (
    <g className="layer-doors">
      {doors.map((door) => {
        const halfWidth = door.width / 2;
        const angle = door.angle ?? 0;

        return (
          <line
            key={door.id}
            x1={door.position.x - halfWidth}
            y1={door.position.y}
            x2={door.position.x + halfWidth}
            y2={door.position.y}
            stroke={s.stroke}
            strokeWidth={s.strokeWidth}
            strokeDasharray={s.dashArray}
            strokeLinecap="round"
            transform={
              angle
                ? `rotate(${angle}, ${door.position.x}, ${door.position.y})`
                : undefined
            }
          />
        );
      })}
    </g>
  );
});
