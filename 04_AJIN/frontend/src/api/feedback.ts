// Day 5 Phase 3~4 — 옵션 B: Frontend 가 RTDB Web SDK 로 피드백 직접 push.
// 보안 규칙은 database.rules.json 의 feedback/{messageId} 노드를 인증된 사용자만 R/W 허용.
//
// Phase 4-A hotfix: userId 인자 제거 — `auth.currentUser?.uid` 사용.
// Firebase Auth 미로그인 시 user_id 는 'anonymous' 로 기록.

import { push, ref, serverTimestamp } from 'firebase/database';
import { auth, rtdb } from '@lib/firebase';

export type FeedbackRating = 'thumbs_up' | 'thumbs_down';

export interface FeedbackPayload {
  user_id: string;
  rating: FeedbackRating;
  ts: number | object; // serverTimestamp() 는 SDK placeholder
}

export async function recordFeedback(
  messageId: string,
  rating: FeedbackRating,
): Promise<void> {
  if (!rtdb) {
    throw new Error('RTDB 미초기화 — VITE_FIREBASE_DATABASE_URL 확인');
  }
  if (!messageId) throw new Error('messageId 가 비어 있습니다.');

  const uid = auth?.currentUser?.uid ?? null;
  const payload: FeedbackPayload = {
    user_id: uid ?? 'anonymous',
    rating,
    ts: serverTimestamp(),
  };
  await push(ref(rtdb, `feedback/${messageId}`), payload);
}
