// Legacy Firestore chat persistence shim.
//
// Chat persistence now belongs behind backend APIs. These functions intentionally
// no-op so chat UX is not blocked while Firebase client fallback is removed.

import type { ChatMessage } from '@/types/chat';

/** Skip legacy Firebase chat writes after the Supabase/Postgres cutover. */
export async function saveMessage(_message: ChatMessage): Promise<void> {
  return;
}

/** Return no legacy Firebase chat history; backend history should be used instead. */
export async function loadRecentMessages(_n = 20): Promise<ChatMessage[]> {
  return [];
}
