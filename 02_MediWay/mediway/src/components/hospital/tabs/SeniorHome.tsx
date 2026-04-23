import { SeniorGreetingCard } from '@/components/hospital/senior/SeniorGreetingCard';
import { SeniorTileGrid } from '@/components/hospital/senior/SeniorTileGrid';
import { SeniorEmergencyCTA } from '@/components/hospital/senior/SeniorEmergencyCTA';

/**
 * 고령자 모드 전용 홈 — P4.U U1: "정보 표시 위젯"에서 "액션 런처 4 타일"로
 * 전환 (시안 PlusUltra SaaS 2/5 정렬).
 *
 * 구성:
 *  1. SeniorGreetingCard — 인사 + NEXT VISIT 가까운 예약
 *  2. SeniorTileGrid     — 병원 예약·길 안내·내 순번·가족 연락(곧 공개)
 *  3. SeniorEmergencyCTA — 풀폭 빨간 응급 버튼 (확인 모달 재사용)
 *
 * 이전 P4 C2의 위젯 3개(TodayScheduleWidget·WaitQueueWidget·EmergencyCtaWidget)
 * 구성을 시안 충실 액션 중심으로 교체. 인지 부담 요소(AI triage·Recent Results)
 * 는 senior 모드에서 제외.
 */
export function SeniorHome() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">홈</h2>
      <SeniorGreetingCard />
      <SeniorTileGrid />
      <SeniorEmergencyCTA />
    </main>
  );
}
