import { EmergencyCallCard } from '@/components/patient/EmergencyCallCard';
import { StaffSubNav } from '@/components/staff/StaffSubNav';

/**
 * 의료진 응급 호출 페이지 — `/h/:slug/staff/emergency`.
 *
 * 환자 측 EmergencyCallCard 와 동일한 컴포넌트를 재사용 (119 + 위치 + 확인 dialog).
 * 의료진이 자기 자신 / 동료 / 환자를 대신해 119 신고 + 현재 위치 안내 가능.
 *
 * features.emergencyCall=false 인 hospital 에선 StaffSubNav 가 「응급」 탭을 숨기지만,
 * 직접 URL 진입 시에도 카드는 노출 (의료진 보호자 정책 — 응급 호출은 항상 사용 가능).
 *
 * 윤리 안전 장치:
 *  - 단일 클릭 119 통화 트리거 X (확인 dialog 강제 — EmergencyCallCard 내부 처리)
 *  - 위치 자동 전송 X — 통화 중 화면 안내 직접 전달
 */
export function StaffEmergencyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <StaffSubNav active="emergency" />
      <header className="mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
          Emergency Response
        </p>
        <h1 className="text-2xl font-bold text-on-surface">응급 호출</h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          119 에 즉시 신고하고 현재 위치를 직접 안내해 주세요.
        </p>
      </header>
      <EmergencyCallCard />
    </main>
  );
}
