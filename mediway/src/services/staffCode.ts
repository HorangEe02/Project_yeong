import { ref, get, runTransaction } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { StaffCode, StaffCodeValidation } from '@/types/staff-code';

/** 의료진 ID 코드를 조회하고 유효성을 검증한다 (사용 처리 전) */
export async function validateStaffCode(
  code: string,
): Promise<StaffCodeValidation> {
  if (!isFirebaseConfigured()) {
    return { valid: false, reason: 'not_found' };
  }
  const normalized = code.trim().toUpperCase();
  const snapshot = await get(ref(db, `staff_codes/${normalized}`));
  if (!snapshot.exists()) {
    return { valid: false, reason: 'not_found' };
  }
  const data = snapshot.val() as StaffCode;
  if (data.usedBy) {
    return { valid: false, reason: 'already_used' };
  }
  if (data.expiresAt && data.expiresAt < Date.now()) {
    return { valid: false, reason: 'expired' };
  }
  return { valid: true, code: data };
}

/**
 * 의료진 ID 코드를 원자적으로 사용 처리.
 * 이미 사용되었거나 만료된 경우 throw.
 */
export async function consumeStaffCode(
  code: string,
  uid: string,
): Promise<StaffCode> {
  if (!isFirebaseConfigured()) {
    throw new Error('Firebase 미설정 — 코드 사용 처리 불가');
  }
  const normalized = code.trim().toUpperCase();
  const codeRef = ref(db, `staff_codes/${normalized}`);

  const tx = await runTransaction(codeRef, (current: StaffCode | null) => {
    if (!current) return current; // abort
    if (current.usedBy) return; // abort
    if (current.expiresAt && current.expiresAt < Date.now()) return; // abort
    return {
      ...current,
      usedBy: uid,
      usedAt: Date.now(),
    };
  });

  if (!tx.committed || !tx.snapshot.exists()) {
    throw new Error('의료진 ID 코드 사용 처리 실패 — 만료되었거나 이미 사용됨');
  }
  return tx.snapshot.val() as StaffCode;
}
