import { useFcmToken } from '@/hooks/useFcmToken';

/**
 * 홈 탭 — 환자의 메인 랜딩.
 *
 * 현 step(B-1 / step 3): 셸 + FCM 토큰 등록 트리거만.
 * 후속 step에서 채울 항목:
 * - WaitQueueWidget (접수 후 순번·대기·호출·진료 상태 실시간)
 * - ChatbotWidget (R3.4 — hospitalChatbot 연동)
 * - 공지/배너 영역
 */
export function HomeTab() {
  // HomeTab 진입 시점에 알림 권한 요청 + /user_fcm_tokens/{uid} 에 토큰 저장.
  // 거부 상태면 재요청하지 않고 스킵.
  useFcmToken();

  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">홈</h2>
      <p className="text-sm text-on-surface-variant">
        대기열 위젯과 AI 진료과 추천이 이곳에 표시될 예정입니다.
      </p>
    </section>
  );
}
