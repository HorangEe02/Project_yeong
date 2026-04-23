import { BedDouble, Calendar, Users } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';

/**
 * 입원 탭 — 현재 입원 중인 환자용.
 *
 * P2: "준비 중" 기능 목록 + 빈 상태 표시.
 * P3에서 실제 데이터 연동 (담당 의료진·면회 예약·퇴원 수속).
 */
export function InpatientTab() {
  const { hospital } = useHospital();

  if (!hospital?.features?.inpatient) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
        <div className="p-6 text-center text-on-surface-variant">
          이 병원은 입원 기능을 아직 활성화하지 않았습니다.
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">입원</h2>
      <div className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
        <header className="mb-2 flex items-center gap-2">
          <BedDouble className="h-5 w-5 text-primary" aria-hidden="true" />
          <h3 className="text-base font-semibold">입원 현황</h3>
        </header>
        <p className="text-sm text-on-surface-variant">
          현재 입원 중이 아닙니다.
        </p>
      </div>

      <section aria-labelledby="inpatient-upcoming">
        <h3
          id="inpatient-upcoming"
          className="mb-2 text-sm font-medium text-on-surface-variant"
        >
          곧 제공될 기능
        </h3>
        <ul className="flex flex-col gap-2 text-sm">
          <PlannedFeature
            icon={<Users className="h-4 w-4" aria-hidden="true" />}
            label="담당 의료진 조회"
          />
          <PlannedFeature
            icon={<Calendar className="h-4 w-4" aria-hidden="true" />}
            label="면회 예약"
          />
          <PlannedFeature
            icon={<BedDouble className="h-4 w-4" aria-hidden="true" />}
            label="퇴원 수속 안내"
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
