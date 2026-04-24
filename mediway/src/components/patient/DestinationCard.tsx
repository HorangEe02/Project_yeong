import { memo } from 'react';
import { MapPin, Building2, Navigation } from 'lucide-react';
import type { POI } from '@/types/hospital';

interface Props {
  destination: POI;
  segmentTime?: number;
  segmentDistance?: number;
  floorInstruction?: string;
  currentLeg: number;
  totalLegs: number;
}

export const DestinationCard = memo(function DestinationCard({
  destination,
  segmentTime,
  segmentDistance,
  floorInstruction,
  currentLeg,
  totalLegs,
}: Props) {
  return (
    <div className="rounded-2xl bg-gradient-to-br from-primary to-primary-container p-5 text-white shadow-ambient-lg">
      {/* 헤더 */}
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-white/70">
          Next Destination
        </p>
        {segmentTime != null && (
          <div className="rounded-xl bg-white/20 px-3 py-1.5 backdrop-blur-sm">
            <p className="text-xs text-white/70">ETA</p>
            <p className="text-lg font-bold leading-tight">
              {Math.max(1, Math.ceil(segmentTime / 60))}{' '}
              <span className="text-sm font-medium">min</span>
            </p>
          </div>
        )}
      </div>

      {/* 목적지 이름 */}
      <h2 className="mb-4 text-2xl font-bold leading-tight">
        {destination.name}
      </h2>

      {/* 메타 정보 칩 */}
      <div className="flex flex-wrap gap-2">
        {segmentDistance != null && (
          <div className="flex items-center gap-1.5 rounded-xl bg-white/15 px-3 py-2 backdrop-blur-sm">
            <MapPin className="h-3.5 w-3.5" />
            <div>
              <p className="text-[10px] text-white/60">Distance</p>
              <p className="text-sm font-semibold">{Math.round(segmentDistance)}m</p>
            </div>
          </div>
        )}
        <div className="flex items-center gap-1.5 rounded-xl bg-white/15 px-3 py-2 backdrop-blur-sm">
          <Building2 className="h-3.5 w-3.5" />
          <div>
            <p className="text-[10px] text-white/60">Level</p>
            <p className="text-sm font-semibold">Floor {destination.floorLevel}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 rounded-xl bg-white/15 px-3 py-2 backdrop-blur-sm">
          <Navigation className="h-3.5 w-3.5" />
          <div>
            <p className="text-[10px] text-white/60">Step</p>
            <p className="text-sm font-semibold">{currentLeg + 1}/{totalLegs}</p>
          </div>
        </div>
      </div>

      {/* 층 이동 안내 */}
      {floorInstruction && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-white/10 px-3 py-2.5 backdrop-blur-sm">
          <Building2 className="h-4 w-4 text-white/70" />
          <p className="text-sm font-medium text-white/90">{floorInstruction}</p>
        </div>
      )}
    </div>
  );
});
