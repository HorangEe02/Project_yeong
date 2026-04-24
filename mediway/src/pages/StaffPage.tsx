import { StaffDashboard } from '@/components/staff/StaffDashboard';

export function StaffPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      {/* 웹: 2열 레이아웃 / 모바일: 1열 */}
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
          Operational Task
        </p>
        <h1 className="text-2xl font-bold text-on-surface">동선 전송 및 관리 센터</h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          환자의 진료 경로를 설정하고 보내줄 기기로 즉시 전송합니다.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* 메인: 의료진 대시보드 */}
        <div>
          <StaffDashboard />
        </div>

        {/* 사이드바: 상태 카드 (웹에서만) */}
        <aside className="hidden space-y-4 lg:block">
          {/* 통계 카드 */}
          <div className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              Clinical Overview
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <StatCard label="진료 대기" value="24" status="pending" />
              <StatCard label="이동 및 검사 중" value="18" status="active" />
              <StatCard label="진료 완료" value="86" status="completed" />
              <StatCard label="오늘 방문자" value="128" status="total" />
            </div>
          </div>

          {/* 최근 전송 로그 */}
          <div className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              최근 전송 로그
            </h3>
            <div className="flex flex-col gap-2">
              <LogItem name="김민지" route="채혈실 → 원무과" time="2분 전" />
              <LogItem name="이현우" route="X-ray → 정형외과" time="12분 전" />
              <LogItem name="박지성" route="원무과 → 약국" time="45분 전" />
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

// --- 보조 컴포넌트 ---

function StatCard({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status: 'pending' | 'active' | 'completed' | 'total';
}) {
  const colors = {
    pending: 'text-amber-600 bg-amber-50',
    active: 'text-blue-600 bg-blue-50',
    completed: 'text-green-600 bg-green-50',
    total: 'text-on-surface bg-surface-container-low',
  };

  return (
    <div className={`rounded-xl p-3 ${colors[status]}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs font-medium opacity-70">{label}</p>
    </div>
  );
}

function LogItem({ name, route, time }: { name: string; route: string; time: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-surface-container-low p-2.5">
      <div>
        <p className="text-sm font-medium text-on-surface">{name}</p>
        <p className="text-xs text-on-surface-variant">{route}</p>
      </div>
      <span className="text-xs text-on-surface-variant/60">{time}</span>
    </div>
  );
}
