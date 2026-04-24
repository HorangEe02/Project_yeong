import { memo } from 'react';
import type { RoomData } from '@/types/floor-plan';
import { ROOM_STYLES } from '../styles/floorPlanStyles';

interface Props {
  rooms: RoomData[];
  activeRoomId?: string;
}

export const RoomLayer = memo(function RoomLayer({ rooms, activeRoomId }: Props) {
  return (
    <g className="layer-rooms">
      {rooms.map((room) => {
        const style = ROOM_STYLES[room.type] ?? ROOM_STYLES.lobby;
        const isActive = room.id === activeRoomId;

        return (
          <g key={room.id}>
            {/* 방 geometry */}
            {room.geometry.kind === 'rect' ? (
              <rect
                x={room.geometry.x}
                y={room.geometry.y}
                width={room.geometry.width}
                height={room.geometry.height}
                rx={6}
                ry={6}
                fill={style.fill}
                fillOpacity={isActive ? 0.95 : style.fillOpacity}
                stroke={style.stroke}
                strokeWidth={isActive ? 2.5 : style.strokeWidth}
                {...(isActive && {
                  filter: 'url(#active-glow)',
                })}
              />
            ) : (
              <polygon
                points={room.geometry.points.map((p) => `${p.x},${p.y}`).join(' ')}
                fill={style.fill}
                fillOpacity={isActive ? 0.95 : style.fillOpacity}
                stroke={style.stroke}
                strokeWidth={isActive ? 2.5 : style.strokeWidth}
              />
            )}

            {/* 방 라벨 */}
            <text
              x={room.labelPosition.x}
              y={room.labelPosition.y}
              textAnchor="middle"
              dominantBaseline="central"
              fill={style.labelColor}
              fontSize={style.labelSize}
              fontWeight={600}
              style={{ pointerEvents: 'none', userSelect: 'none' }}
              {...(room.labelRotation && {
                transform: `rotate(${room.labelRotation}, ${room.labelPosition.x}, ${room.labelPosition.y})`,
              })}
            >
              {room.label}
            </text>
          </g>
        );
      })}
    </g>
  );
});
