import * as admin from 'firebase-admin';
import { HttpsError } from 'firebase-functions/v2/https';
import { applyClaimsFromProfile } from './setClaims';

export type CreateStaffMode = 'email_reset' | 'temp_password';

export interface CreateStaffInput {
  email: string;
  displayName?: string;
  department: string;
  hospitalId: string;
  mode: CreateStaffMode;
}

export interface CreateStaffResult {
  uid: string;
  mode: CreateStaffMode;
  email: string;
  resetLink?: string;
  tempPassword?: string;
}

const TEMP_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
const SYMBOLS = '!@#$%';

function generateTempPassword(): string {
  const bytes = new Uint8Array(12);
  // Node crypto
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const nodeCrypto = require('crypto') as typeof import('crypto');
  nodeCrypto.randomFillSync(bytes);
  let out = '';
  for (let i = 0; i < 10; i++) out += TEMP_ALPHABET[bytes[i] % TEMP_ALPHABET.length];
  out += SYMBOLS[bytes[10] % SYMBOLS.length];
  out += String(bytes[11] % 10);
  return out;
}

export async function handleCreateStaff(
  callerUid: string,
  callerEmail: string | null | undefined,
  input: CreateStaffInput,
): Promise<CreateStaffResult> {
  const db = admin.database();

  // 1. 호출자 권한 확인
  const callerRoleSnap = await db.ref(`users/${callerUid}/role`).get();
  if (callerRoleSnap.val() !== 'admin') {
    throw new HttpsError('permission-denied', '관리자 권한이 필요합니다');
  }

  // 2. 입력 검증
  const email = input.email.trim().toLowerCase();
  const department = input.department.trim();
  const hospitalId = input.hospitalId.trim();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new HttpsError('invalid-argument', '유효한 이메일이 필요합니다');
  }
  if (!department || !hospitalId) {
    throw new HttpsError('invalid-argument', '부서와 병원 ID는 필수입니다');
  }
  if (input.mode !== 'email_reset' && input.mode !== 'temp_password') {
    throw new HttpsError('invalid-argument', 'mode 값이 올바르지 않습니다');
  }

  // 3. 기존 사용자 충돌 체크
  try {
    const existing = await admin.auth().getUserByEmail(email);
    throw new HttpsError('already-exists', '이미 가입된 이메일입니다', {
      uid: existing.uid,
    });
  } catch (err) {
    const code = (err as { code?: string }).code;
    if (code === 'already-exists') throw err;
    if (code !== 'auth/user-not-found') throw err;
  }

  // 4. Auth 계정 생성
  const tempPassword = generateTempPassword();
  const displayName =
    input.displayName?.trim() || email.split('@')[0];
  const user = await admin.auth().createUser({
    email,
    password: tempPassword,
    displayName,
    emailVerified: false,
  });

  // 5. RTDB 프로필 생성 (role=staff + 소속)
  // P1: primaryHospitalId(신규) + hospitalId(레거시 호환) 모두 세팅
  const now = Date.now();
  await db.ref(`users/${user.uid}`).set({
    uid: user.uid,
    email,
    displayName,
    role: 'staff',
    status: 'active',
    providers: ['password'],
    hospitalId, // legacy 호환
    primaryHospitalId: hospitalId,
    hospitalIds: [hospitalId],
    department,
    createdAt: now,
    updatedAt: now,
  });

  // P1: 프로필 작성 직후 Claim 주입 — 스태프가 첫 로그인 시 hospitalId가 토큰에 실림
  try {
    await applyClaimsFromProfile(user.uid);
  } catch (err) {
    console.warn('[handleCreateStaff] claim 주입 실패 (non-fatal)', user.uid, err);
  }

  // 6. 감사 로그
  await db.ref('audit_logs').push({
    actorUid: callerUid,
    actorEmail: callerEmail ?? null,
    action: 'user.account.create',
    target: user.uid,
    meta: { mode: input.mode, department, hospitalId, email },
    timestamp: now,
  });

  // 7. 모드별 후처리
  if (input.mode === 'email_reset') {
    const resetLink = await admin.auth().generatePasswordResetLink(email, {
      url: 'https://mediway-demo.web.app/login',
    });
    return {
      uid: user.uid,
      mode: 'email_reset',
      email,
      resetLink,
    };
  }
  return {
    uid: user.uid,
    mode: 'temp_password',
    email,
    tempPassword,
  };
}
