import { memo } from 'react';
import { Check } from 'lucide-react';
import { getPOIById } from '@/data/hospital';
import type { Waypoint } from '@/types/session';

interface Props {
  waypoints: Waypoint[];
  currentIndex: number;
  onWaypointClick?: (index: number) => void;
}

export const RouteProgress = memo(function RouteProgress({
  waypoints,
  currentIndex,
  onWaypointClick,
}: Props) {
  return (
    <div className="w-full overflow-x-auto">
      <div className="flex items-center justify-center gap-0 px-2 py-3" style={{ minWidth: `${waypoints.length * 80}px` }}>
        {waypoints.map((wp, index) => {
          const poi = getPOIById(wp.poiId);
          const isCompleted = wp.status === 'completed';
          const isCurrent = index === currentIndex;
          return (
            <div key={`${wp.poiId}-${index}`} className="flex items-center">
              {/* 노드 */}
              <button
                onClick={() => onWaypointClick?.(index)}
                className="flex flex-col items-center gap-1.5"
                style={{ minWidth: '64px' }}
              >
                {/* 원형 마커 */}
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full transition-all ${
                    isCompleted
                      ? 'bg-green-500 text-white'
                      : isCurrent
                        ? 'bg-primary text-white shadow-lg shadow-primary/30 ring-4 ring-primary/20'
                        : 'bg-surface-container-high text-on-surface-variant'
                  }`}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <span className="text-xs font-bold">{index + 1}</span>
                  )}
                </div>

                {/* 라벨 */}
                <span
                  className={`text-center text-[11px] font-medium leading-tight ${
                    isCompleted
                      ? 'text-green-600'
                      : isCurrent
                        ? 'text-primary font-semibold'
                        : 'text-on-surface-variant/60'
                  }`}
                >
                  {poi?.shortName ?? wp.poiId}
                </span>
              </button>

              {/* 연결선 */}
              {index < waypoints.length - 1 && (
                <div
                  className={`mx-1 h-0.5 w-8 flex-shrink-0 rounded-full transition-colors ${
                    isCompleted ? 'bg-green-400' : 'bg-surface-container-high'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
});
