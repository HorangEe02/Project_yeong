// firestore-draft.ts — Day 8 Phase 4: 초안 영구화 + Storage 통합.
// Firestore: /documents/{user_uid}/items/{doc_id}
// Storage:   /pdfs/drafts/{user_uid}/{doc_id}.{ext}
//
// fire-and-forget 패턴 (Day 5 firestore-chat 동일) — 실패해도 사용자 흐름 차단 X.

import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  limit,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
} from 'firebase/firestore';
import { getDownloadURL, ref, uploadBytes } from 'firebase/storage';
import { auth, firestore, storage } from '@lib/firebase';
import type { DraftDocument, ExportFormat } from '@/types/draft';

const COLLECTION = 'documents';
const STORAGE_BASE = 'pdfs/drafts';

function currentUid(): string | null {
  return auth?.currentUser?.uid ?? null;
}

function itemsCollection(userId: string) {
  if (!firestore) throw new Error('Firestore 미초기화');
  return collection(firestore, COLLECTION, userId, 'items');
}

// ──────────────────────────────────────────────────────────────────
// 저장 / 조회 / 삭제
// ──────────────────────────────────────────────────────────────────

/** 초안 1건 저장 — fire-and-forget. */
export async function saveDraft(d: DraftDocument): Promise<void> {
  const uid = currentUid();
  if (!firestore || !uid) {
    if (import.meta.env.DEV) {
      console.info('[firestore-draft] save skipped — Firestore 미초기화 또는 비로그인');
    }
    return;
  }
  try {
    await setDoc(doc(firestore, COLLECTION, uid, 'items', d.id), {
      ...d,
      user_uid: uid,
      _at: serverTimestamp(),
    });
    if (import.meta.env.DEV) {
      console.info('[firestore-draft] saved:', d.id);
    }
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[firestore-draft] save 실패:', e);
    }
  }
}

/** 최근 N개 이력 로드 (기본 30개). */
export async function loadHistory(n = 30): Promise<DraftDocument[]> {
  const uid = currentUid();
  if (!firestore || !uid) return [];
  try {
    const q = query(itemsCollection(uid), orderBy('updated_at', 'desc'), limit(n));
    const snap = await getDocs(q);
    return snap.docs.map((d) => d.data() as DraftDocument);
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[firestore-draft] loadHistory 실패:', e);
    }
    return [];
  }
}

/** 1건 삭제. */
export async function deleteDraft(id: string): Promise<boolean> {
  const uid = currentUid();
  if (!firestore || !uid) return false;
  try {
    await deleteDoc(doc(firestore, COLLECTION, uid, 'items', id));
    return true;
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[firestore-draft] delete 실패:', e);
    }
    return false;
  }
}

// ──────────────────────────────────────────────────────────────────
// Storage 업로드 (옵션 — 다운로드 시 백업)
// ──────────────────────────────────────────────────────────────────

/**
 * 다운로드된 blob을 Storage 에 백업 + signed URL 반환.
 * 경로: /pdfs/drafts/{uid}/{docId}.{ext}
 */
export async function uploadDraftFile(
  docId: string,
  ext: ExportFormat | string,
  blob: Blob,
): Promise<string | null> {
  const uid = currentUid();
  if (!storage || !uid) return null;
  try {
    const path = `${STORAGE_BASE}/${uid}/${docId}.${ext}`;
    const r = ref(storage, path);
    await uploadBytes(r, blob);
    const url = await getDownloadURL(r);
    if (import.meta.env.DEV) {
      console.info('[firestore-draft] storage uploaded:', path);
    }
    return url;
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn('[firestore-draft] storage 업로드 실패:', e);
    }
    return null;
  }
}

// ──────────────────────────────────────────────────────────────────
// 자동 영구화 헬퍼 (SSE done 시 1회 호출)
// ──────────────────────────────────────────────────────────────────

interface AutoPersistArgs {
  docTypeId: string;
  toneId: string;
  context: 'internal' | 'external';
  meta: { title?: string; recipient?: string; cc?: string[] };
  content: string;
  qualityTotal?: number;
  qualityGrade?: string;
}

/**
 * SSE done 직후 호출 — 자동 Firestore 영구화 (mint new doc).
 * @returns 생성된 docId (성공 시) 또는 null (실패/skip)
 */
export async function autoPersistDraft(args: AutoPersistArgs): Promise<string | null> {
  const uid = currentUid();
  if (!firestore || !uid) return null;
  if (!args.content || args.content.trim().length < 50) return null;

  const id = `draft-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const now = Date.now();
  const docPayload: DraftDocument = {
    id,
    user_uid: uid,
    doc_type: args.docTypeId,
    tone: args.toneId,
    context: args.context,
    meta: {
      title: args.meta.title,
      recipient: args.meta.recipient,
      cc: args.meta.cc ?? [],
      custom_fields: {},
    },
    content: args.content,
    quality: args.qualityTotal !== undefined
      ? {
          total_score: args.qualityTotal,
          grade: args.qualityGrade ?? 'C',
        }
      : undefined,
    versions: [{ content: args.content, _at: now, source: 'llm' }],
    status: 'draft',
    created_at: now,
    updated_at: now,
  };

  await saveDraft(docPayload);
  return id;
}

// 개발 편의: window 디버그 hook
if (typeof window !== 'undefined' && import.meta.env.DEV) {
  (window as unknown as { __draftHistory: typeof loadHistory }).__draftHistory = loadHistory;
}
