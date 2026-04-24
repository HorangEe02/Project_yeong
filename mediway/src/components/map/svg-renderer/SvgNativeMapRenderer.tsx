import { memo } from 'react';
import { Plus, Minus } from 'lucide-react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import type { MapRendererProps } from '@/types/map-renderer';
import { BuildingOutline } from './layers/BuildingOutline';
import { CorridorLayer } from './layers/CorridorLayer';
import { RoomLayer } from './layers/RoomLayer';
import { WallLayer } from './layers/WallLayer';
import { DoorLayer } from './layers/DoorLayer';
import { PathOverlay } from './layers/PathOverlay';
import { POIMarkerLayer } from './layers/POIMarkerLayer';

/** SVG 뷰포트 크기 */
const SVG_WIDTH = 1200;
const SVG_HEIGHT = 800;

export const SvgNativeMapRenderer = memo(function SvgNativeMapRenderer({
  floorPlanData,
  pois,
  pathSegment,
  highlights,
  events,
  className,
}: MapRendererProps) {
  return (
    <div className={`relative overflow-hidden rounded-xl bg-white ${className ?? ''}`}>
      <TransformWrapper
        initialScale={1}
        minScale={0.5}
        maxScale={3}
        centerOnInit
        smooth
        doubleClick={{ mode: 'reset' }}
        panning={{ velocityDisabled: false }}
        wheel={{ step: 0.1, smoothStep: 0.004 }}
      >
        {({ zoomIn, zoomOut }) => (
          <>
            <TransformComponent
              wrapperStyle={{ width: '100%', height: '100%' }}
              contentStyle={{ width: '100%', height: '100%' }}
            >
              <svg
                viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
                xmlns="http://www.w3.org/2000/svg"
                className="w-full h-full"
                style={{ maxHeight: '70vh' }}
                onClick={(e) => {
                  if (e.target === e.currentTarget) {
                    events?.onMapClick?.({ x: 0, y: 0 });
                  }
                }}
              >
                {/* SVG 필터 정의 */}
                <defs>
                  <filter id="active-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feFlood floodColor="#004e9f" floodOpacity="0.2" result="color" />
                    <feComposite in="color" in2="blur" operator="in" result="glow" />
                    <feMerge>
                      <feMergeNode in="glow" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                {/* Layer 0: 건물 외벽 */}
                <BuildingOutline outline={floorPlanData.buildingOutline} />

                {/* Layer 1: 복도 */}
                <CorridorLayer corridors={floorPlanData.corridors} />

                {/* Layer 2: 방 */}
                <RoomLayer rooms={floorPlanData.rooms} />

                {/* Layer 3: 벽 */}
                <WallLayer walls={floorPlanData.walls} />

                {/* Layer 4: 문 */}
                <DoorLayer doors={floorPlanData.doors} />

                {/* Layer 5: 경로 */}
                <PathOverlay segment={pathSegment} />

                {/* Layer 6: POI 마커 */}
                <POIMarkerLayer
                  pois={pois}
                  highlights={highlights}
                  onPoiClick={events?.onPoiClick}
                />
              </svg>
            </TransformComponent>

            {/* 줌 컨트롤 (우측 상단) */}
            <div className="pointer-events-none absolute right-3 top-3 z-10 flex flex-col gap-1">
              <button
                type="button"
                onClick={() => zoomIn()}
                aria-label="확대"
                title="확대"
                className="pointer-events-auto flex h-9 w-9 items-center justify-center rounded-lg bg-white/90 text-on-surface shadow-ambient backdrop-blur transition-colors hover:bg-white"
              >
                <Plus className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => zoomOut()}
                aria-label="축소"
                title="축소"
                className="pointer-events-auto flex h-9 w-9 items-center justify-center rounded-lg bg-white/90 text-on-surface shadow-ambient backdrop-blur transition-colors hover:bg-white"
              >
                <Minus className="h-4 w-4" />
              </button>
            </div>
          </>
        )}
      </TransformWrapper>
    </div>
  );
});
