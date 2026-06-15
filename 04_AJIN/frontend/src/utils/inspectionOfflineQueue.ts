// 점검 제출 offline queue — IndexedDB (v4.3 A12).
//
// PWA `/equipment/field` 가 네트워크 부재 시 제출을 IndexedDB 큐에 적재.
// online 복귀 시 useOnlineStatus 가 flushQueue() 호출 (또는 수동).
// 중복 제출 차단: client_uuid 키.

import {
  submitInspection,
  type InspectionSubmitPayload,
} from '@api/equipment';

const DB_NAME = 'ajin_inspection_offline';
const DB_VERSION = 1;
const STORE = 'pending';
const MAX_RETRY = 5;
const RETRY_BACKOFF_SECONDS = [10, 30, 120, 600, 1800] as const;

export type PendingInspectionStatus = 'pending' | 'sending' | 'dead_letter';

interface PendingItem {
  client_uuid: string;
  payload: InspectionSubmitPayload;
  queued_at: string;
  retry_count: number;
  last_error?: string;
  next_retry_at?: string | null;
  status: PendingInspectionStatus;
}

function nowIso(): string {
  return new Date().toISOString();
}

function nextRetryIso(retryCount: number): string {
  const idx = Math.min(Math.max(retryCount - 1, 0), RETRY_BACKOFF_SECONDS.length - 1);
  return new Date(Date.now() + RETRY_BACKOFF_SECONDS[idx] * 1000).toISOString();
}

function errorStatus(err: unknown): number | undefined {
  return (err as { response?: { status?: number } })?.response?.status;
}

function errorMessage(err: unknown): string {
  const status = errorStatus(err);
  if (status) return `HTTP ${status}`;
  return err instanceof Error ? err.message : String(err);
}

function shouldAttempt(item: PendingItem): boolean {
  if (item.status === 'dead_letter') return false;
  if (!item.next_retry_at) return true;
  return Date.parse(item.next_retry_at) <= Date.now();
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'client_uuid' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function enqueueInspection(payload: InspectionSubmitPayload): Promise<string> {
  const client_uuid =
    payload.client_uuid ??
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `inspection-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`);

  const item: PendingItem = {
    client_uuid,
    payload: { ...payload, client_uuid },
    queued_at: nowIso(),
    retry_count: 0,
    last_error: undefined,
    next_retry_at: null,
    status: 'pending',
  };

  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(item);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
  return client_uuid;
}

export async function pendingCount(): Promise<number> {
  if (typeof indexedDB === 'undefined') return 0;
  const db = await openDb();
  return new Promise<number>((resolve) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).count();
    req.onsuccess = () => {
      db.close();
      resolve(req.result);
    };
    req.onerror = () => {
      db.close();
      resolve(0);
    };
  });
}

async function deleteByUuid(db: IDBDatabase, uuid: string): Promise<void> {
  await new Promise<void>((resolve) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(uuid);
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
}

async function putItem(db: IDBDatabase, item: PendingItem): Promise<void> {
  await new Promise<void>((resolve) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(item);
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
}

async function getAll(db: IDBDatabase): Promise<PendingItem[]> {
  return new Promise<PendingItem[]>((resolve) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve((req.result as PendingItem[]) ?? []);
    req.onerror = () => resolve([]);
  });
}

export interface FlushResult {
  attempted: number;
  succeeded: number;
  failed: number;
  dead_letter: number;
  skipped: number;
  remaining: number;
}

export async function flushQueue(): Promise<FlushResult> {
  if (typeof indexedDB === 'undefined') {
    return { attempted: 0, succeeded: 0, failed: 0, dead_letter: 0, skipped: 0, remaining: 0 };
  }
  const db = await openDb();
  const items = await getAll(db);
  const attemptedItems = items.filter(shouldAttempt);
  let succeeded = 0;
  let failed = 0;
  let deadLetter = items.filter((item) => item.status === 'dead_letter').length;
  const skipped = items.length - attemptedItems.length;
  for (const item of attemptedItems) {
    try {
      await putItem(db, { ...item, status: 'sending' });
      await submitInspection(item.payload);
      await deleteByUuid(db, item.client_uuid);
      succeeded += 1;
    } catch (err) {
      console.warn('[inspection-queue] flush failed for', item.client_uuid, err);
      failed += 1;
      const status = errorStatus(err);
      const nextRetryCount = (item.retry_count ?? 0) + 1;
      const terminal = Boolean(status && status >= 400 && status < 500) || nextRetryCount >= MAX_RETRY;
      if (terminal) deadLetter += 1;
      await putItem(db, {
        ...item,
        retry_count: nextRetryCount,
        last_error: errorMessage(err),
        next_retry_at: terminal ? null : nextRetryIso(nextRetryCount),
        status: terminal ? 'dead_letter' : 'pending',
      });
    }
  }
  const remaining = Math.max(0, items.length - succeeded);
  db.close();
  return { attempted: attemptedItems.length, succeeded, failed, dead_letter: deadLetter, skipped, remaining };
}
