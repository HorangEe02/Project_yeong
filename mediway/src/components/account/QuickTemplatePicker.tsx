import { routeTemplates } from '@/data/route-templates';
import { getPOIById } from '@/data/hospital/pois';
import type { RouteTemplate } from '@/types/route-template';

interface QuickTemplatePickerProps {
  onApply: (waypointPoiIds: string[]) => void;
}

export function QuickTemplatePicker({ onApply }: QuickTemplatePickerProps) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
        빠른 시작 — 병원 표준 템플릿
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {routeTemplates.map((t) => (
          <TemplateCard key={t.id} template={t} onApply={onApply} />
        ))}
      </div>
      <p className="mt-1 text-[11px] text-on-surface-variant/70">
        템플릿을 선택하면 현재 계획이 **덮어쓰기** 됩니다.
      </p>
    </div>
  );
}

function TemplateCard({
  template,
  onApply,
}: {
  template: RouteTemplate;
  onApply: (ids: string[]) => void;
}) {
  const summary = template.waypointPoiIds
    .map((id) => getPOIById(id)?.shortName ?? id)
    .join(' → ');
  return (
    <button
      type="button"
      onClick={() => onApply(template.waypointPoiIds)}
      className="group flex items-start gap-3 rounded-xl border border-surface-container-high bg-surface p-3 text-left transition-colors hover:border-primary"
    >
      <span
        className="mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
        style={{ backgroundColor: template.color }}
      />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-on-surface">{template.name}</p>
        <p className="truncate text-[11px] text-on-surface-variant">
          {template.departmentTag} · 약 {template.estimatedTotalTime}분
        </p>
        <p className="mt-1 truncate text-[11px] text-on-surface-variant/70">{summary}</p>
      </div>
    </button>
  );
}
