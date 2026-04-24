import { useFcmToken } from '@/hooks/useFcmToken';
import { WaitQueueWidget } from '@/components/patient/WaitQueueWidget';
import { ChatbotWidget } from '@/components/patient/ChatbotWidget';

/**
 * 홈 탭 — 환자의 메인 랜딩.
 *
 * 현 step (B-2 / step 7b): FCM 토큰 + 대기 순번 + AI 챗봇 위젯.
 * 후속 step 에서 추가 예정: 공지/배너, 다음 방문 예약 요약 등.
 */
export function HomeTab() {
  // HomeTab 진입 시 알림 권한 요청 + /user_fcm_tokens/{uid} 에 토큰 저장.
  // 거부 상태면 재요청하지 않고 스킵.
  useFcmToken();

  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">홈</h2>
      <WaitQueueWidget />
      <ChatbotWidget />
    </section>
  );
}
