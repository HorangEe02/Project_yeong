import { memo } from 'react';
import type { Coordinate } from '@/types/hospital';
import { STRUCTURE_STYLES } from '../styles/floorPlanStyles';

interface Props {
  outline: Coordinate[];
}

export const BuildingOutline = memo(function BuildingOutline({ outline }: Props) {
  if (outline.length === 0) return null;
  const s = STRUCTURE_STYLES.buildingOutline;
  const points = outline.map((p) => `${p.x},${p.y}`).join(' ');

  return (
    <polygon
      points={points}
      fill={s.fill}
      stroke={s.stroke}
      strokeWidth={s.strokeWidth}
      strokeLinejoin="round"
    />
  );
});
