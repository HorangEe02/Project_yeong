// Legacy Firestore collection hook shim.
//
// Firebase read fallback is disabled. New realtime/read paths should use backend
// APIs, SSE, or explicit Supabase-backed endpoints instead of browser Firebase.

export interface FirestoreDoc {
  id: string;
}

export interface FirestoreCollectionResult<T> {
  data: T[];
  loading: boolean;
  error: Error | null;
}

export function useFirestoreCollection<T extends FirestoreDoc>(
  _path: string,
  ..._constraints: unknown[]
): FirestoreCollectionResult<T> {
  return { data: [], loading: false, error: null };
}
