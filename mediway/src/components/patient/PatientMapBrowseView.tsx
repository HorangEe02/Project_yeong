import { X } from 'lucide-react';
import { HospitalMapContainer } from '@/components/map/HospitalMapContainer';
import { useMapStore } from '@/stores/mapStore';
import { getPOIById } from '@/data/hospital';
import type { POICategory } from '@/types/hospital';

const CATEGORY_LABEL: Record<POICategory, string> = {
  clinic: '진료과',
  lab: '검사실',
  imaging: '영상진단',
  pharmacy: '약국',
  admin: '원무·행정',
  elevator: '엘리베이터',
  stairs: '계단',
  restroom: '화장실',
  parking: '주차',
  entrance: '출입구',
  convenience: '편의시설',
  lobby: '로비',
};

export function PatientMapBrowseView() {
  const selectedPoiId = useMapStore((s) => s.selectedPoiId);
  const setSelectedPoiId = useMapStore((s) => s.setSelectedPoiId);
  const poi = selectedPoiId ? getPOIById(selectedPoiId) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl bg-surface-container-lowest p-3 shadow-ambient sm:p-4">
        <p className="mb-2 text-xs text-on-surface-variant">
          POI 마커를 탭하면 상세 정보를 볼 수 있어요.
        </p>
        <HospitalMapContainer />
      </div>

      {poi && (
        <div className="rounded-xl bg-surface-container-lowest p-4 shadow-ambient">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-on-surface">{poi.name}</h3>
                <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-[11px] text-on-surface-variant">
                  {CATEGORY_LABEL[poi.category]}
                </span>
                <span className="text-[11px] text-on-surface-variant">
                  {poi.floorLevel}층
                </span>
              </div>
              {poi.description && (
                <p className="mt-2 text-sm text-on-surface-variant">{poi.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => setSelectedPoiId(null)}
              aria-label="닫기"
              title="닫기"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-surface-container-high text-on-surface-variant hover:bg-surface-container-low"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
