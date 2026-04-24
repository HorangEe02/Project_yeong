import type { database } from 'firebase-admin';

/**
 * 감사 로그 단일 엔트리 shape.
 *
 * - `actorUid`: 행위자 UID (시스템 액션이면 'system:<funcName>' 권장)
 * - `action`: 도메인.서브.이름 형태 ('chatbot.reply', 'wait_queue.call.push')
 * - `target`: 주 대상 (uid, hospitalId, resource id 등)
 * - `meta`: 자유 구조 부가 정보
 * - `timestamp`: epoch ms
 * - 외 임의 필드 (actorEmail 등) 허용 — dual-write 에는 그대로 전달된다.
 */
export interface AuditLogEntry {
  actorUid: string;
  action: string;
  target?: string;
  meta?: Record<string, unknown>;
  timestamp: number;
  [k: string]: unknown;
}

/**
 * T1-1b dual-write 모드:
 *   - legacy `/audit_logs/{pushId}` (전체 관리용, platformAdmin 만 read)
 *   - nested `/audit_logs_v2/{bucket}/{pushId}` (hospitalId 별 격리)
 *
 * `hospitalId` 가 null/undefined/빈문자열 → `platform` bucket 사용
 * (platformAdmin 시스템 액션: bootstrap, claims migration 등).
 *
 * 두 write 는 Promise.all 로 병행. 한쪽 실패 시 전체 reject — 호출자가 처리.
 * T1-1c cutover 에서 legacy write 제거 예정.
 */
export async function appendAuditLog(
  db: database.Database,
  hospitalId: string | null | undefined,
  entry: AuditLogEntry,
): Promise<void> {
  const bucket = hospitalId && hospitalId.trim() ? hospitalId.trim() : 'platform';
  await Promise.all([
    db.ref('audit_logs').push(entry),
    db.ref(`audit_logs_v2/${bucket}`).push(entry),
  ]);
}
