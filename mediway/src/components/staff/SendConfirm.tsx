import { Clock, MapPin, Send, X } from 'lucide-react';
import { getPOIById } from '@/data/hospital';
import { computeRoute } from '@/services/pathfinding';
import { navigationGraph } from '@/data/hospital/navigation-graph';
import { formatDuration } from '@/utils/distance';

interface Props {
  waypointPoiIds: string[];
  templateName?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SendConfirm({ waypointPoiIds, templateName, onConfirm, onCancel }: Props) {
  const route = computeRoute(navigationGraph, waypointPoiIds);
  const waypoints = waypointPoiIds.map((id) => getPOIById(id));

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Vitality Glass 배경 */}
      <div className="absolute inset-0 glass-modal" onClick={onCancel} />

      {/* 모달 */}
      <div className="relative w-full max-w-md rounded-2xl bg-surface-container-lowest p-6 shadow-ambient-lg">
        {/* 닫기 */}
        <button
          onClick={onCancel}
          className="absolute right-4 top-4 rounded-full p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high"
        >
          <X className="h-5 w-5" />
        </button>

        {/* 헤더 */}
        <div className="mb-5">
          <h2 className="text-lg font-bold text-on-surface">동선 전송 확인</h2>
          {templateName && (
            <p className="mt-1 text-sm text-on-surface-variant">{templateName}</p>
          )}
        </div>

        {/* 경유지 목록 */}
        <div className="mb-5 flex flex-col gap-0">
          {waypoints.map((poi, index) => (
            <div key={poi?.id ?? index} className="flex items-start gap-3">
              {/* 타임라인 */}
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                    index === waypoints.length - 1
                      ? 'bg-primary text-on-primary'
                      : 'bg-primary/10 text-primary'
                  }`}
                >
                  {index + 1}
                </div>
                {index < waypoints.length - 1 && (
                  <div className="h-6 w-px bg-surface-container-high" />
                )}
              </div>

              {/* 정보 */}
              <div className="pb-4">
                <p className="text-sm font-semibold text-on-surface">
                  {poi?.name ?? '알 수 없음'}
                </p>
                <p className="text-xs text-on-surface-variant">
                  {poi?.floorLevel ? `본관 ${poi.floorLevel}층` : ''}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* 요약 정보 */}
        {route && (
          <div className="mb-5 flex gap-4 rounded-xl bg-surface-container-low p-3">
            <div className="flex items-center gap-1.5 text-sm text-on-surface-variant">
              <MapPin className="h-4 w-4" />
              <span>{waypointPoiIds.length}단계</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-on-surface-variant">
              <Clock className="h-4 w-4" />
              <span>예상 {formatDuration(route.totalTime)}</span>
            </div>
          </div>
        )}

        {/* 버튼 */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 rounded-xl bg-surface-container-high py-3 text-sm font-semibold text-on-surface-variant transition-colors hover:bg-surface-container"
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-primary-container py-3 text-sm font-semibold text-on-primary transition-transform active:scale-[0.98]"
          >
            <Send className="h-4 w-4" />
            환자에게 전송
          </button>
        </div>
      </div>
    </div>
  );
}
