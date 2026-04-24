import { memo } from 'react';
import type { POI } from '@/types/hospital';
import type { MapHighlights } from '@/types/map-renderer';
import { HIGHLIGHT_STYLES } from '../styles/floorPlanStyles';

interface Props {
  pois: POI[];
  highlights?: MapHighlights;
  onPoiClick?: (poiId: string) => void;
}

function getPoiStyle(poiId: string, highlights?: MapHighlights) {
  if (!highlights) return HIGHLIGHT_STYLES.default;
  if (highlights.currentPoiId === poiId) return HIGHLIGHT_STYLES.current;
  if (highlights.startPoiId === poiId) return HIGHLIGHT_STYLES.start;
  if (highlights.endPoiId === poiId) return HIGHLIGHT_STYLES.end;
  if (highlights.completedPoiIds?.includes(poiId)) return HIGHLIGHT_STYLES.completed;
  return HIGHLIGHT_STYLES.pending;
}

export const POIMarkerLayer = memo(function POIMarkerLayer({
  pois,
  highlights,
  onPoiClick,
}: Props) {
  return (
    <g className="layer-poi-markers">
      {pois.map((poi) => {
        const style = getPoiStyle(poi.id, highlights);
        const hasHighlights = highlights && (
          highlights.startPoiId || highlights.endPoiId || highlights.currentPoiId
        );

        return (
          <g
            key={poi.id}
            className="poi-marker"
            style={{ cursor: onPoiClick ? 'pointer' : 'default' }}
            onClick={() => onPoiClick?.(poi.id)}
          >
            {/* 펄스 애니메이션 링 */}
            {style.pulse && (
              <circle
                cx={poi.coordinates.x}
                cy={poi.coordinates.y}
                r={style.radius + 4}
                fill="none"
                stroke={style.fill}
                strokeWidth={1.5}
                opacity={0.4}
              >
                <animate
                  attributeName="r"
                  values={`${style.radius + 2};${style.radius + 10};${style.radius + 2}`}
                  dur="2s"
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="opacity"
                  values="0.4;0.1;0.4"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </circle>
            )}

            {/* 마커 원 */}
            <circle
              cx={poi.coordinates.x}
              cy={poi.coordinates.y}
              r={style.radius}
              fill={style.fill}
              stroke="#ffffff"
              strokeWidth={style.strokeWidth}
            />

            {/* 마커 내부 아이콘 텍스트 (EV, 계단 등 짧은 약어) */}
            {(poi.category === 'elevator' || poi.category === 'stairs') && (
              <text
                x={poi.coordinates.x}
                y={poi.coordinates.y}
                textAnchor="middle"
                dominantBaseline="central"
                fill="#ffffff"
                fontSize={8}
                fontWeight={700}
                style={{ pointerEvents: 'none' }}
              >
                {poi.shortName}
              </text>
            )}

            {/* 라벨 (마커 아래) */}
            {(!hasHighlights || style !== HIGHLIGHT_STYLES.pending) && (
              <text
                x={poi.coordinates.x}
                y={poi.coordinates.y + style.radius + 14}
                textAnchor="middle"
                dominantBaseline="central"
                fill={style.fill}
                fontSize={11}
                fontWeight={600}
                style={{ pointerEvents: 'none', userSelect: 'none' }}
              >
                {poi.shortName}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
});
