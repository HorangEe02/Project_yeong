import { useFcmToken } from '@/hooks/useFcmToken';
import { WaitQueueWidget } from '@/components/patient/WaitQueueWidget';

/**
 * 홈 탭 — 환자의 메인 랜딩.
 *
 * 현 step (B-1 / step 4b): FCM 토큰 등록 + 대기 순번 위젯 배선.
 * 후속 step에서 추가할 항목:
 * - ChatbotWidget (R3.4 — hospitalChatbot 연동)
 * - 공지/배너 영역
 * - (선택) 다음 방문 예약 카드 — AppointmentsTab 요약
 */
export function HomeTab() {
  // HomeTab 진입 시 알림 권한 요청 + /user_fcm_tokens/{uid} 에 토큰 저장.
  // 거부 상태면 재요청하지 않고 스킵.
  useFcmToken();

  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">홈</h2>
      <WaitQueueWidget />
      <p className="text-xs text-on-surface-variant">
        AI 진료과 추천과 공지 사항이 이곳에 추가될 예정입니다.
      </p>
    </section>
  );
}
