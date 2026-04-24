import {
  signInAnonymously,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
  updatePassword,
  reauthenticateWithCredential,
  EmailAuthProvider,
  sendPasswordResetEmail,
  verifyBeforeUpdateEmail,
  type User,
} from 'firebase/auth';
import { auth, googleProvider, isFirebaseConfigured } from '@/config/firebase';
import { ensureUserProfile, updateUserProfile } from '@/services/userProfile';
import { consumeStaffCode, validateStaffCode } from '@/services/staffCode';
import type {
  AuthProvider,
  PatientSignupInput,
  StaffSignupInput,
  UserProfile,
} from '@/types/auth';

/** 초기 Firebase Auth 상태가 확정될 때까지 대기 (IndexedDB 복원 완료 시점) */
function waitForInitialAuth(): Promise<User | null> {
  return new Promise((resolve) => {
    const unsub = onAuthStateChanged(auth, (user) => {
      unsub();
      resolve(user);
    });
  });
}

/** 익명 인증 — 이미 복원된 사용자가 있으면 세션 보존 (race condition 방지) */
export async function initAnonymousAuth(): Promise<User | null> {
  if (!isFirebaseConfigured()) {
    console.warn('[MediWay] Firebase 미설정 — 로컬 데모 모드');
    return null;
  }
  const existing = await waitForInitialAuth();
  if (existing) return existing; // 기존 세션(admin/staff/patient 등) 유지
  try {
    const credential = await signInAnonymously(auth);
    return credential.user;
  } catch (error) {
    console.error('[MediWay] 익명 인증 실패:', error);
    return null;
  }
}

/** 현재 인증 사용자 UID */
export function getCurrentUid(): string | null {
  return auth.currentUser?.uid ?? null;
}

/** 인증 상태 변경 구독 */
export function onAuthChange(callback: (user: User | null) => void): () => void {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  return onAuthStateChanged(auth, callback);
}

// ============================================================
// Email / Password
// ============================================================

/** 환자 회원가입 */
export async function signUpPatient(
  input: PatientSignupInput,
): Promise<UserProfile> {
  const cred = await createUserWithEmailAndPassword(
    auth,
    input.email,
    input.password,
  );
  await updateProfile(cred.user, { displayName: input.displayName });
  return ensureUserProfile(cred.user.uid, {
    email: cred.user.email,
    displayName: input.displayName,
    providers: ['password'],
    role: 'patient',
    status: 'active',
  });
}

/**
 * 의료진 회원가입
 * 1) 코드 검증 → 2) 계정 생성 → 3) 코드 consume → 4) 프로필 저장
 * 3단계 실패 시 계정을 자동으로 삭제해 정합성 유지.
 */
export async function signUpStaff(
  input: StaffSignupInput,
): Promise<UserProfile> {
  const validation = await validateStaffCode(input.staffCode);
  if (!validation.valid) {
    throw new Error(validationMessage(validation.reason));
  }

  const cred = await createUserWithEmailAndPassword(
    auth,
    input.email,
    input.password,
  );

  try {
    const consumed = await consumeStaffCode(input.staffCode, cred.user.uid);
    await updateProfile(cred.user, { displayName: input.displayName });
    return ensureUserProfile(cred.user.uid, {
      email: cred.user.email,
      displayName: input.displayName,
      providers: ['password'],
      role: 'staff',
      status: 'active',
      hospitalId: consumed.hospitalId,
      department: consumed.department,
      staffCode: consumed.code,
    });
  } catch (error) {
    // 코드 사용 처리 실패 시 계정 롤백
    try {
      await cred.user.delete();
    } catch (cleanupError) {
      console.error('[MediWay] 계정 롤백 실패:', cleanupError);
    }
    throw error;
  }
}

/** 이메일 로그인 */
export async function signInWithEmail(
  email: string,
  password: string,
): Promise<UserProfile> {
  const cred = await signInWithEmailAndPassword(auth, email, password);
  return ensureUserProfile(cred.user.uid, {
    email: cred.user.email,
    displayName: cred.user.displayName,
    providers: detectProviders(cred.user),
  });
}

/** Google 로그인 (기본 역할 = patient) */
export async function signInWithGoogle(): Promise<UserProfile> {
  const cred = await signInWithPopup(auth, googleProvider);
  return ensureUserProfile(cred.user.uid, {
    email: cred.user.email,
    displayName: cred.user.displayName,
    providers: detectProviders(cred.user),
    role: 'patient',
  });
}

/** 로그아웃 */
export async function signOutUser(): Promise<void> {
  await signOut(auth);
}

/** 비밀번호 재설정 메일 */
export async function sendPasswordReset(email: string): Promise<void> {
  await sendPasswordResetEmail(auth, email);
}

/** 현재 로그인 사용자에게 비밀번호 재설정 메일을 발송 */
export async function sendPasswordResetToCurrentUser(): Promise<string> {
  const user = auth.currentUser;
  if (!user || !user.email) {
    throw new Error('이메일이 등록되지 않은 계정입니다');
  }
  await sendPasswordResetEmail(auth, user.email);
  return user.email;
}

/** 표시 이름 변경 (Firebase Auth + RTDB 프로필 동기화) */
export async function updateDisplayNameForCurrentUser(
  displayName: string,
): Promise<void> {
  const user = auth.currentUser;
  if (!user) throw new Error('로그인이 필요합니다');
  const trimmed = displayName.trim();
  if (!trimmed) throw new Error('이름을 입력하세요');
  await updateProfile(user, { displayName: trimmed });
  await updateUserProfile(user.uid, { displayName: trimmed });
}

/** 비밀번호 변경 (재인증 필수) */
export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const user = auth.currentUser;
  if (!user || !user.email) {
    throw new Error('로그인이 필요합니다');
  }
  const credential = EmailAuthProvider.credential(user.email, currentPassword);
  await reauthenticateWithCredential(user, credential);
  await updatePassword(user, newPassword);
  await updateUserProfile(user.uid, {});
}

/** 현재 사용자가 비밀번호 변경 가능한지 (이메일/비밀번호 공급자 여부) */
export function canChangePassword(user: User | null): boolean {
  if (!user) return false;
  return user.providerData.some((p) => p.providerId === 'password');
}

/** 현재 사용자가 이메일 변경 가능한지 (password 공급자 필수) */
export function canChangeEmail(user: User | null): boolean {
  if (!user) return false;
  return user.providerData.some((p) => p.providerId === 'password');
}

/**
 * 이메일 변경 요청 — 재인증 후 새 이메일로 검증 메일 발송.
 * 사용자가 메일의 링크를 클릭하면 Firebase Auth 상의 이메일이 업데이트되고
 * 이후 로그인 시 syncEmailToProfile로 RTDB에 반영된다.
 */
export async function requestEmailChange(
  currentPassword: string,
  newEmail: string,
): Promise<void> {
  const user = auth.currentUser;
  if (!user || !user.email) throw new Error('로그인이 필요합니다');
  if (!canChangeEmail(user)) {
    throw new Error('소셜 계정은 이메일을 직접 변경할 수 없습니다');
  }
  const trimmed = newEmail.trim().toLowerCase();
  if (trimmed === user.email.toLowerCase()) {
    throw new Error('현재 이메일과 동일합니다');
  }
  const credential = EmailAuthProvider.credential(user.email, currentPassword);
  await reauthenticateWithCredential(user, credential);
  await verifyBeforeUpdateEmail(user, trimmed);
}

/**
 * Firebase Auth 이메일과 RTDB profile.email을 동기화.
 * 로그인 직후 authStore에서 호출.
 */
export async function syncEmailToProfile(
  user: User,
  profileEmail: string | null,
): Promise<void> {
  if (user.isAnonymous) return;
  if (!user.email) return;
  if (profileEmail && profileEmail.toLowerCase() === user.email.toLowerCase()) {
    return;
  }
  await updateUserProfile(user.uid, { email: user.email });
}

// ============================================================
// 내부 유틸
// ============================================================

function detectProviders(user: User): AuthProvider[] {
  const providers = new Set<AuthProvider>();
  if (user.isAnonymous) providers.add('anonymous');
  user.providerData.forEach((p) => {
    if (p.providerId === 'password') providers.add('password');
    if (p.providerId === 'google.com') providers.add('google');
  });
  // 카카오/네이버는 Custom Token으로 로그인되므로 providerData에 안 나타남.
  // uid prefix로 판별.
  if (user.uid.startsWith('kakao:')) providers.add('kakao');
  if (user.uid.startsWith('naver:')) providers.add('naver');
  return Array.from(providers);
}

function validationMessage(reason: 'not_found' | 'expired' | 'already_used'): string {
  switch (reason) {
    case 'not_found':
      return '존재하지 않는 의료진 ID 코드입니다';
    case 'expired':
      return '만료된 의료진 ID 코드입니다';
    case 'already_used':
      return '이미 사용된 의료진 ID 코드입니다';
  }
}
