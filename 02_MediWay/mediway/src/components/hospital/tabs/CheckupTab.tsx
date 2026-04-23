import { Activity, Calendar, FileCheck, Stethoscope } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';

/**
 * 건강검진 탭 — 검진 예약·결과 이력.
 *
 * P2: feature flag 기반 노출 + 준비 중 기능 목록.
 * P3에서 검진 예약, P5에서 결과 무기한 보관 (v2 MOAT #3).
 */
export function CheckupTab() {
  const { hospital } = useHospital();

  if (!hospital?.features?.checkup) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
        <div className="p-6 text-center text-on-surface-variant">
          이 병원은 건강검진 기능을 아직 활성화하지 않았습니다.
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">건강검진</h2>

      <div className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
        <header className="mb-2 flex items-center gap-2">
          <Stethoscope className="h-5 w-5 text-primary" aria-hidden="true" />
          <h3 className="text-base font-semibold">건강검진 기록</h3>
        </header>
        <p className="text-sm text-on-surface-variant">
          아직 검진 기록이 없습니다.
        </p>
      </div>

      <section aria-labelledby="checkup-upcoming">
        <h3
          id="checkup-upcoming"
          className="mb-2 text-sm font-medium text-on-surface-variant"
        >
          곧 제공될 기능
        </h3>
        <ul className="flex flex-col gap-2 text-sm">
          <PlannedFeature
            icon={<Calendar className="h-4 w-4" aria-hidden="true" />}
            label="검진 예약"
          />
          <PlannedFeature
            icon={<Activity className="h-4 w-4" aria-hidden="true" />}
            label="검진 항목별 진행 현황"
          />
          <PlannedFeature
            icon={<FileCheck className="h-4 w-4" aria-hidden="true" />}
            label="검진 결과 — 무기한 보관 (P5)"
          />
        </ul>
      </section>
    </main>
  );
}

function PlannedFeature({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <li className="flex items-center gap-2 rounded-lg bg-surface-container-low px-3 py-2 text-on-surface-variant">
      {icon}
      <span className="flex-1">{label}</span>
      <span className="rounded-full bg-surface-container px-2 py-0.5 text-xs">
        준비 중
      </span>
    </li>
  );
}
