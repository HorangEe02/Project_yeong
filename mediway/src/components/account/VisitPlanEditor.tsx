import { ArrowUp, ArrowDown, X, MapPin } from 'lucide-react';
import { getPOIById } from '@/data/hospital/pois';
import type { PlannedWaypoint } from '@/types/visit-plan';

interface VisitPlanEditorProps {
  waypoints: PlannedWaypoint[];
  onReorder: (from: number, to: number) => void;
  onRemove: (index: number) => void;
}

export function VisitPlanEditor({
  waypoints,
  onReorder,
  onRemove,
}: VisitPlanEditorProps) {
  if (waypoints.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-surface-container-high bg-surface-container-low/50 p-6 text-center">
        <MapPin className="mx-auto h-5 w-5 text-on-surface-variant/60" />
        <p className="mt-2 text-sm text-on-surface-variant">
          아직 선택한 목적지가 없습니다.
        </p>
        <p className="mt-0.5 text-[11px] text-on-surface-variant/70">
          위에서 템플릿을 선택하거나 직접 추가해주세요.
        </p>
      </div>
    );
  }

  return (
    <ol className="flex flex-col overflow-hidden rounded-xl border border-surface-container-high bg-surface">
      {waypoints.map((w, i) => (
        <Row
          key={`${w.poiId}-${i}`}
          index={i}
          total={waypoints.length}
          waypoint={w}
          onUp={() => onReorder(i, i - 1)}
          onDown={() => onReorder(i, i + 1)}
          onRemove={() => onRemove(i)}
        />
      ))}
    </ol>
  );
}

function Row({
  index,
  total,
  waypoint,
  onUp,
  onDown,
  onRemove,
}: {
  index: number;
  total: number;
  waypoint: PlannedWaypoint;
  onUp: () => void;
  onDown: () => void;
  onRemove: () => void;
}) {
  const poi = getPOIById(waypoint.poiId);
  const label = poi?.name ?? waypoint.poiId;
  const sub = poi
    ? `${poi.buildingId === 'main' ? '본관' : poi.buildingId} · ${poi.floorLevel}F`
    : '알 수 없는 목적지';

  return (
    <li className="flex items-center gap-3 border-b border-surface-container-high/60 px-3 py-2.5 last:border-0">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-on-surface">{label}</p>
        <p className="truncate text-[11px] text-on-surface-variant">{sub}</p>
      </div>
      <div className="flex items-center gap-1">
        <IconButton label="위로" onClick={onUp} disabled={index === 0}>
          <ArrowUp className="h-3.5 w-3.5" />
        </IconButton>
        <IconButton label="아래로" onClick={onDown} disabled={index === total - 1}>
          <ArrowDown className="h-3.5 w-3.5" />
        </IconButton>
        <IconButton label="삭제" onClick={onRemove} tone="danger">
          <X className="h-3.5 w-3.5" />
        </IconButton>
      </div>
    </li>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  tone,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: 'danger';
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className={`flex h-7 w-7 items-center justify-center rounded-lg border border-surface-container-high text-on-surface-variant disabled:opacity-30 hover:bg-surface-container-low ${
        tone === 'danger' ? 'hover:border-red-300 hover:text-red-600' : ''
      }`}
    >
      {children}
    </button>
  );
}
