// Legacy Firebase RTDB value hook shim.
//
// Feedback and alarm writes/read models now use backend APIs. This hook returns
// an empty value so older UI counters fail closed while Firebase fallback exits.

export interface RTDBResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useRTDBValue<T>(_path: string): RTDBResult<T> {
  return { data: null, loading: false, error: null };
}
