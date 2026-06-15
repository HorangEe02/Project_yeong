// 부록 5 P3-4 — localStorage flag with TTL.
// 사용 예: 변경 안내 toast 가 7일 후 자동 만료, 그 후 재방문 시 1회 재노출.

interface FlagEnvelope {
  v: number;       // value (timestamp ms)
  exp: number;     // expiry epoch ms
}

export function markFlag(key: string, ttlMs: number): void {
  try {
    const now = Date.now();
    const payload: FlagEnvelope = { v: now, exp: now + ttlMs };
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // ignored — localStorage 비활성화 환경
  }
}

export function isFlagFresh(key: string): boolean {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return false;
    const parsed = JSON.parse(raw) as FlagEnvelope;
    if (typeof parsed?.exp !== 'number') return false;
    return parsed.exp > Date.now();
  } catch {
    return false;
  }
}

export function clearFlag(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // ignored
  }
}
