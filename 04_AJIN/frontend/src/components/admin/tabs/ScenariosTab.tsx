// ScenariosTab — 협업 시나리오 관리 탭 (HR_ADMIN+ L4).
// admin.tsx 라우트의 7번째 탭. ScenarioListPanel 을 그대로 노출.

import { useAuthStore } from '@store/auth';
import { ScenarioListPanel } from '@components/admin/scenarios/ScenarioListPanel';

export function ScenariosTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>협업 시나리오 관리는 HR_ADMIN(L4) 이상에게만 노출됩니다.</p>
      </div>
    );
  }
  return <ScenarioListPanel />;
}
