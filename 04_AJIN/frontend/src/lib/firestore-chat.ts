// Day 5 Phase 3~4 — 옵션 B: Frontend 가 Firestore Web SDK 로 직접 채팅 이력 영속.
// 보안 규칙은 firestore.rules 에서 chat_history/{uid}/messages/{msgId} 를 본인 uid 만 R/W 허용.
// fire-and-forget — 실패해도 채팅 흐름을 막지 않는다.
//
// Phase 4-A hotfix: userId 인자 제거 — `auth.currentUser?.uid` 직접 사용.
// Firebase Auth 가 미통합/비로그인 상태이면 uid=null 이고 noop 으로 우아하게 실패한다.

import {
  collection,
  doc,
  getDocs,
  limit,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
} from 'firebase/firestore';
import { auth, firestore } from '@lib/firebase';
import type { ChatMessage } from '@/types/chat';

function currentUid(): string | null {
  return auth?.currentUser?.uid ?? null;
}

function chatCollection(userId: string) {
  if (!firestore) throw new Error('Firestore 미초기화');
  return collection(firestore, 'chat_history', userId, 'messages');
}

/** 메시지 1건 영속 — 백그라운드 호출용. 실패해도 throw 하지 않는다. */
export async function saveMessage(message: ChatMessage): Promise<void> {
  const uid = currentUid();
  if (!firestore || !uid) return;
  try {
    await setDoc(doc(firestore, 'chat_history', uid, 'messages', message.id), {
      id: message.id,
      role: message.role,
      content: message.content,
      createdAt: message.createdAt,
      status: message.status,
      source: message.source ?? 'llm',
      meta: message.meta ?? null,
      _at: serverTimestamp(),
    });
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[firestore-chat] saveMessage 실패', e);
    }
  }
}

/** 최근 n 건을 시간 오름차순으로 반환. 신규 진입 시 사용. */
export async function loadRecentMessages(n = 20): Promise<ChatMessage[]> {
  const uid = currentUid();
  if (!firestore || !uid) return [];
  try {
    const q = query(chatCollection(uid), orderBy('createdAt', 'desc'), limit(n));
    const snap = await getDocs(q);
    const docs = snap.docs.map((d) => d.data() as ChatMessage).reverse();
    // status 가 'streaming' 인 잔여물은 안전하게 'done' 으로 정리 (재로드 시 영구 표시)
    return docs.map((m) => (m.status === 'streaming' ? { ...m, status: 'done' as const } : m));
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[firestore-chat] loadRecentMessages 실패', e);
    }
    return [];
  }
}
