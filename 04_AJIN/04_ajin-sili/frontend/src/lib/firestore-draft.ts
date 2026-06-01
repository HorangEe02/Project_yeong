// Legacy Firestore/Storage draft persistence shim.
//
// Draft persistence and file handling are now routed through backend APIs and
// Supabase Storage signed URL flows. These functions fail closed to remove the
// Firebase Web SDK from the frontend bundle.

import type { DraftDocument, ExportFormat } from '@/types/draft';

interface AutoPersistArgs {
  docTypeId: string;
  toneId: string;
  context: 'internal' | 'external';
  meta: { title?: string; recipient?: string; cc?: string[] };
  content: string;
  qualityTotal?: number;
  qualityGrade?: string;
}

/** Skip legacy Firebase draft writes after the Supabase/Postgres cutover. */
export async function saveDraft(_draft: DraftDocument): Promise<void> {
  return;
}

/** Return no legacy Firebase draft history; server-side history owns this path. */
export async function loadHistory(_n = 30): Promise<DraftDocument[]> {
  return [];
}

/** Skip legacy Firebase draft deletion. */
export async function deleteDraft(_id: string): Promise<boolean> {
  return false;
}

/** Skip legacy Firebase Storage backup uploads. */
export async function uploadDraftFile(
  _docId: string,
  _ext: ExportFormat | string,
  _blob: Blob,
): Promise<string | null> {
  return null;
}

/** Skip legacy auto-persistence; backend draft APIs are the persistence path. */
export async function autoPersistDraft(_args: AutoPersistArgs): Promise<string | null> {
  return null;
}

if (typeof window !== 'undefined' && import.meta.env.DEV) {
  (window as unknown as { __draftHistory: typeof loadHistory }).__draftHistory = loadHistory;
}
