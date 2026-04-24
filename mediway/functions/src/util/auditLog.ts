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
 * T1-1c cutover 모드 (2026-04-24 이후):
 *   - **v2 only**: `/audit_logs_v2/{bucket}/{pushId}`
 *   - legacy `/audit_logs` write 는 제거됨 (rules 도 write:false 로 차단)
 *
 * `hospitalId` 가 null/undefined/빈문자열 → `platform` bucket 사용
 * (platformAdmin 시스템 액션: bootstrap, claims migration 등).
 *
 * 기존 legacy entries + 백업 (`/audit_logs_backup_{ts}`) 은 T1-1a 기록 그대로
 * 유지 (platformAdmin read-only). AdminAuditPage 는 `audit_logs_v2/{hid}` 를
 * 조회한다.
 */
export async function appendAuditLog(
  db: database.Database,
  hospitalId: string | null | undefined,
  entry: AuditLogEntry,
): Promise<void> {
  const bucket = hospitalId && hospitalId.trim() ? hospitalId.trim() : 'platform';
  await db.ref(`audit_logs_v2/${bucket}`).push(entry);
}
