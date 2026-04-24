import { memo } from 'react';
import { Clock, MapPin, ChevronRight } from 'lucide-react';
import type { RouteTemplate } from '@/types/route-template';
import { getPOIById } from '@/data/hospital';

interface Props {
  templates: RouteTemplate[];
  selectedId: string | null;
  onSelect: (template: RouteTemplate) => void;
}

export const RouteTemplateList = memo(function RouteTemplateList({
  templates,
  selectedId,
  onSelect,
}: Props) {
  // 진료과별 그룹핑
  const grouped = templates.reduce(
    (acc, t) => {
      (acc[t.departmentTag] ??= []).push(t);
      return acc;
    },
    {} as Record<string, RouteTemplate[]>,
  );

  return (
    <div className="flex flex-col gap-4">
      {Object.entries(grouped).map(([dept, items]) => (
        <div key={dept}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            {dept}
          </h3>
          <div className="flex flex-col gap-2">
            {items.map((template) => {
              const isSelected = template.id === selectedId;
              const waypoints = template.waypointPoiIds
                .map((id) => getPOIById(id)?.shortName ?? id)
                .join(' → ');

              return (
                <button
                  key={template.id}
                  onClick={() => onSelect(template)}
                  className={`group flex items-center gap-3 rounded-xl p-4 text-left transition-all ${
                    isSelected
                      ? 'bg-surface-container-lowest shadow-ambient-lg ring-2 ring-primary/30'
                      : 'bg-surface-container-lowest shadow-ambient hover:shadow-ambient-lg'
                  }`}
                >
                  {/* 색상 인디케이터 */}
                  <div
                    className="h-10 w-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: template.color }}
                  />

                  <div className="flex-1 min-w-0">
                    {/* 경유지 체인 */}
                    <p className="text-sm font-semibold text-on-surface truncate">
                      {waypoints}
                    </p>

                    {/* 메타 정보 */}
                    <div className="mt-1 flex items-center gap-3 text-xs text-on-surface-variant">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {template.waypointPoiIds.length}단계
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        약 {template.estimatedTotalTime}분
                      </span>
                      {template.isDefault && (
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                          기본
                        </span>
                      )}
                    </div>
                  </div>

                  <ChevronRight
                    className={`h-4 w-4 shrink-0 transition-colors ${
                      isSelected ? 'text-primary' : 'text-on-surface-variant/40'
                    }`}
                  />
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
});
