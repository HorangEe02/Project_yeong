import { ref, get, set, remove } from 'firebase/database';
import { v4 as uuidv4 } from 'uuid';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { appendAudit } from '@/services/auditLog';
import type { BulkIssueInput, StaffCode } from '@/types/staff-code';

export async function listStaffCodes(): Promise<StaffCode[]> {
  if (!isFirebaseConfigured()) return [];
  const snapshot = await get(ref(db, 'staff_codes'));
  if (!snapshot.exists()) return [];
  const rows: StaffCode[] = [];
  snapshot.forEach((child) => {
    rows.push(child.val() as StaffCode);
  });
  return rows.sort((a, b) => b.createdAt - a.createdAt);
}

function generateCode(department: string): string {
  const prefix = department.replace(/[^A-Za-z0-9가-힣]/g, '').slice(0, 3).toUpperCase();
  const suffix = uuidv4().slice(0, 6).toUpperCase();
  return `${prefix || 'MED'}-${suffix}`;
}

export async function issueStaffCode(
  input: Omit<BulkIssueInput, 'quantity'>,
): Promise<StaffCode> {
  if (!isFirebaseConfigured()) throw new Error('Firebase 미설정');
  const code = generateCode(input.department);
  const now = Date.now();
  const entry: StaffCode = {
    code,
    hospitalId: input.hospitalId,
    department: input.department,
    expiresAt: now + input.expiresInDays * 86_400_000,
    usedBy: null,
    createdAt: now,
  };
  await set(ref(db, `staff_codes/${code}`), entry);
  await appendAudit('staff_code.issue', code, {
    hospitalId: input.hospitalId,
    department: input.department,
  });
  return entry;
}

export async function issueBulkCodes(input: BulkIssueInput): Promise<StaffCode[]> {
  const n = Math.max(1, Math.min(100, Math.floor(input.quantity)));
  const results: StaffCode[] = [];
  for (let i = 0; i < n; i++) {
    // 순차 발급 — RTDB 키 충돌 최소화
    // eslint-disable-next-line no-await-in-loop
    results.push(await issueStaffCode(input));
  }
  return results;
}

export async function revokeStaffCode(code: string): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await remove(ref(db, `staff_codes/${code}`));
  await appendAudit('staff_code.revoke', code);
}
