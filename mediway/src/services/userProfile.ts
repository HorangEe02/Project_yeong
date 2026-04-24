import {
  ref,
  get,
  set,
  update,
  onValue,
  type Unsubscribe,
} from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { UserProfile, UserRole, UserStatus } from '@/types/auth';

/** 사용자 프로필 조회 */
export async function getUserProfile(uid: string): Promise<UserProfile | null> {
  if (!isFirebaseConfigured()) return null;
  const snapshot = await get(ref(db, `users/${uid}`));
  if (!snapshot.exists()) return null;
  return snapshot.val() as UserProfile;
}

/** 사용자 프로필 저장(최초 생성) */
export async function createUserProfile(profile: UserProfile): Promise<void> {
  if (!isFirebaseConfigured()) return;
  await set(ref(db, `users/${profile.uid}`), profile);
}

/** 프로필이 없거나 손상된 경우 기본값으로 생성하고 반환.
 *  기존 부분 프로필에 role/createdAt 등이 있으면 보존하여 관리자 역할 유실 방지.
 *  optional 필드는 값이 있을 때만 포함(Firebase는 undefined 거부). */
export async function ensureUserProfile(
  uid: string,
  defaults: Partial<UserProfile> & Pick<UserProfile, 'email' | 'providers'>,
): Promise<UserProfile> {
  const existing = await getUserProfile(uid);
  if (existing && existing.role && existing.createdAt) return existing;

  const now = Date.now();
  const profile: UserProfile = {
    uid,
    email: defaults.email ?? existing?.email ?? null,
    displayName: defaults.displayName ?? existing?.displayName ?? null,
    role: existing?.role ?? defaults.role ?? 'patient',
    status: existing?.status ?? defaults.status ?? 'active',
    providers: existing?.providers ?? defaults.providers,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
  const hospitalId = defaults.hospitalId ?? existing?.hospitalId;
  if (hospitalId) profile.hospitalId = hospitalId;
  const department = defaults.department ?? existing?.department;
  if (department) profile.department = department;
  const staffCode = defaults.staffCode ?? existing?.staffCode;
  if (staffCode) profile.staffCode = staffCode;

  await createUserProfile(profile);
  return profile;
}

/** 부분 업데이트 — undefined 필드를 제거해 Firebase set 실패 방지 */
export async function updateUserProfile(
  uid: string,
  patch: Partial<Omit<UserProfile, 'uid' | 'createdAt'>>,
): Promise<void> {
  if (!isFirebaseConfigured()) return;
  const cleaned = Object.fromEntries(
    Object.entries(patch).filter(([, v]) => v !== undefined),
  );
  await update(ref(db, `users/${uid}`), { ...cleaned, updatedAt: Date.now() });
}

/** 상태 변경 (admin 전용) */
export async function setUserStatus(uid: string, status: UserStatus): Promise<void> {
  await updateUserProfile(uid, { status });
}

/** 역할 변경 (admin 전용) */
export async function setUserRole(uid: string, role: UserRole): Promise<void> {
  await updateUserProfile(uid, { role });
}

/** 프로필 실시간 구독 */
export function subscribeUserProfile(
  uid: string,
  callback: (profile: UserProfile | null) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    callback(null);
    return () => {};
  }
  return onValue(ref(db, `users/${uid}`), (snapshot) => {
    callback(snapshot.exists() ? (snapshot.val() as UserProfile) : null);
  });
}
