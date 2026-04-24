import { memo } from 'react';

interface Props {
  floors: { level: number; name: string }[];
  currentFloor: number;
  onFloorChange: (level: number) => void;
}

export const FloorSelector = memo(function FloorSelector({
  floors,
  currentFloor,
  onFloorChange,
}: Props) {
  return (
    <div className="flex gap-1 rounded-xl bg-surface-container-high p-1">
      {floors.map((floor) => {
        const isActive = floor.level === currentFloor;
        return (
          <button
            key={floor.level}
            onClick={() => onFloorChange(floor.level)}
            className={`
              min-w-[48px] rounded-lg px-3 py-2 text-sm font-semibold transition-all
              ${
                isActive
                  ? 'bg-surface-container-lowest text-primary shadow-ambient'
                  : 'text-on-surface-variant hover:bg-surface-container'
              }
            `}
          >
            {floor.name}
          </button>
        );
      })}
    </div>
  );
});
