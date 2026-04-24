import { useCallback } from 'react';
import { MapRendererProvider } from './MapRendererContext';
import { MapRenderer } from './MapRenderer';
import { FloorSelector } from './FloorSelector';
import { useMapStore } from '@/stores/mapStore';
import { demoHospital, getFloorPlan, getPOIsByFloor } from '@/data/hospital';
import type { PathSegment } from '@/types/navigation';
import type { MapHighlights } from '@/types/map-renderer';

interface Props {
  pathSegment?: PathSegment;
  highlights?: MapHighlights;
  className?: string;
}

const floors = demoHospital.buildings[0].floors;

export function HospitalMapContainer({ pathSegment, highlights, className }: Props) {
  const rendererType = useMapStore((s) => s.rendererType);
  const currentFloor = useMapStore((s) => s.currentFloor);
  const setCurrentFloor = useMapStore((s) => s.setCurrentFloor);
  const setSelectedPoiId = useMapStore((s) => s.setSelectedPoiId);

  const floorPlanData = getFloorPlan(currentFloor);
  const pois = getPOIsByFloor(currentFloor);

  const handlePoiClick = useCallback(
    (poiId: string) => {
      setSelectedPoiId(poiId);
    },
    [setSelectedPoiId],
  );

  if (!floorPlanData) {
    return <div className="p-8 text-center text-on-surface-variant">층 데이터를 찾을 수 없습니다.</div>;
  }

  // 현재 층의 경로 세그먼트만 필터링
  const currentFloorSegment =
    pathSegment && pathSegment.floorLevel === currentFloor ? pathSegment : undefined;

  return (
    <div className={`flex flex-col gap-3 ${className ?? ''}`}>
      {/* 층 선택 탭 */}
      <div className="flex justify-center">
        <FloorSelector
          floors={floors}
          currentFloor={currentFloor}
          onFloorChange={setCurrentFloor}
        />
      </div>

      {/* 지도 렌더러 */}
      <MapRendererProvider type={rendererType}>
        <MapRenderer
          floorLevel={currentFloor}
          floorPlanData={floorPlanData}
          pois={pois}
          pathSegment={currentFloorSegment}
          highlights={highlights}
          events={{ onPoiClick: handlePoiClick }}
          className="min-h-[400px] shadow-ambient"
        />
      </MapRendererProvider>
    </div>
  );
}
