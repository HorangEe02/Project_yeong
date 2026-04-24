import * as admin from 'firebase-admin';

export type SocialProvider = 'kakao' | 'naver';

export interface MintInput {
  provider: SocialProvider;
  externalId: string;
  email: string | null;
  displayName: string | null;
  photoUrl?: string | null;
}

/**
 * 소셜 외부 ID를 Firebase uid로 매핑.
 * uid 규칙: `{provider}:{externalId}`
 */
export function buildSocialUid(provider: SocialProvider, externalId: string): string {
  return `${provider}:${externalId}`;
}

export async function mintCustomToken(input: MintInput): Promise<string> {
  const uid = buildSocialUid(input.provider, input.externalId);

  // Auth에 사용자 존재 여부 확인 후 생성/갱신
  try {
    await admin.auth().getUser(uid);
    await admin.auth().updateUser(uid, {
      email: input.email ?? undefined,
      displayName: input.displayName ?? undefined,
      photoURL: input.photoUrl ?? undefined,
    });
  } catch (err) {
    if ((err as { code?: string }).code === 'auth/user-not-found') {
      await admin.auth().createUser({
        uid,
        email: input.email ?? undefined,
        displayName: input.displayName ?? undefined,
        photoURL: input.photoUrl ?? undefined,
        emailVerified: !!input.email,
      });
    } else {
      throw err;
    }
  }

  return admin.auth().createCustomToken(uid, { provider: input.provider });
}
