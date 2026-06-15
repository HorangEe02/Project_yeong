// Firebase RTDB 직접 write를 제거하고 백엔드 /feedback API로 기록한다.

import { api } from '@api/client';

export type FeedbackRating = 'thumbs_up' | 'thumbs_down';

export interface FeedbackPayload {
  message_id: string;
  rating: FeedbackRating;
}

export async function recordFeedback(
  messageId: string,
  rating: FeedbackRating,
): Promise<void> {
  if (!messageId) throw new Error('messageId 가 비어 있습니다.');
  const payload: FeedbackPayload = {
    message_id: messageId,
    rating,
  };
  await api.post('/feedback', payload);
}
