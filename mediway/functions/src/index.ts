import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { SocialAuthRequest } from './validation';
import { exchangeKakaoCode } from './providers/kakao';
import { exchangeNaverCode } from './providers/naver';
import { buildSocialUid, mintCustomToken } from './customToken';
import { ensureUserRecord } from './userLink';
import { handleCreateStaff, type CreateStaffInput } from './adminCreateStaff';
import {
  kakaoClientId,
  kakaoClientSecret,
  naverClientId,
  naverClientSecret,
} from './secrets';

admin.initializeApp();

export { refreshMyClaims, setUserClaims } from './setClaims';
export { migrateAllClaims } from './migrations/migrateAllClaims';
export { verifyMigration } from './migrations/verifyMigration';
export { onQueueCall } from './wait_queue/onQueueCall';

const region = 'asia-northeast3';

/** 카카오 인가 코드 → Firebase Custom Token */
export const kakaoAuth = onCall(
  { region, cors: true, secrets: [kakaoClientId, kakaoClientSecret] },
  async (request) => {
    const parsed = SocialAuthRequest.safeParse(request.data);
    if (!parsed.success) {
      throw new HttpsError('invalid-argument', '요청 파라미터가 올바르지 않습니다');
    }
    const { code, redirectUri } = parsed.data;
    const clientId = kakaoClientId.value();
    const clientSecret = kakaoClientSecret.value() || undefined;
    if (!clientId) {
      throw new HttpsError('failed-precondition', 'KAKAO_CLIENT_ID 미설정');
    }

    try {
      const profile = await exchangeKakaoCode(code, redirectUri, clientId, clientSecret);
      const token = await mintCustomToken({
        provider: 'kakao',
        externalId: profile.id,
        email: profile.email,
        displayName: profile.nickname,
        photoUrl: profile.profileImage,
      });
      await ensureUserRecord(
        buildSocialUid('kakao', profile.id),
        'kakao',
        profile.email,
        profile.nickname,
      );
      return { token };
    } catch (err) {
      console.error('[kakaoAuth]', err);
      throw new HttpsError('internal', '카카오 로그인에 실패했습니다');
    }
  },
);

/** Admin이 의료진 계정을 직접 생성 (D1 email_reset / D2 temp_password) */
export const adminCreateStaffAccount = onCall({ region, cors: true }, async (request) => {
  if (!request.auth?.uid) {
    throw new HttpsError('unauthenticated', '로그인이 필요합니다');
  }
  const data = request.data as Partial<CreateStaffInput>;
  if (
    !data ||
    typeof data.email !== 'string' ||
    typeof data.department !== 'string' ||
    typeof data.hospitalId !== 'string' ||
    (data.mode !== 'email_reset' && data.mode !== 'temp_password')
  ) {
    throw new HttpsError('invalid-argument', '요청 파라미터가 올바르지 않습니다');
  }
  try {
    return await handleCreateStaff(request.auth.uid, request.auth.token.email, {
      email: data.email,
      displayName: data.displayName,
      department: data.department,
      hospitalId: data.hospitalId,
      mode: data.mode,
    });
  } catch (err) {
    if (err instanceof HttpsError) throw err;
    console.error('[adminCreateStaffAccount]', err);
    throw new HttpsError('internal', '계정 생성에 실패했습니다');
  }
});

/** 네이버 인가 코드 → Firebase Custom Token */
export const naverAuth = onCall(
  { region, cors: true, secrets: [naverClientId, naverClientSecret] },
  async (request) => {
    const parsed = SocialAuthRequest.safeParse(request.data);
    if (!parsed.success) {
      throw new HttpsError('invalid-argument', '요청 파라미터가 올바르지 않습니다');
    }
    const { code, state, redirectUri } = parsed.data;
    if (!state) {
      throw new HttpsError('invalid-argument', 'state 파라미터가 필요합니다');
    }
    const clientId = naverClientId.value();
    const clientSecret = naverClientSecret.value();
    if (!clientId || !clientSecret) {
      throw new HttpsError('failed-precondition', 'NAVER_CLIENT_ID/SECRET 미설정');
    }

    try {
      const profile = await exchangeNaverCode(
        code,
        state,
        redirectUri,
        clientId,
        clientSecret,
      );
      const token = await mintCustomToken({
        provider: 'naver',
        externalId: profile.id,
        email: profile.email,
        displayName: profile.nickname,
        photoUrl: profile.profileImage,
      });
      await ensureUserRecord(
        buildSocialUid('naver', profile.id),
        'naver',
        profile.email,
        profile.nickname,
      );
      return { token };
    } catch (err) {
      console.error('[naverAuth]', err);
      throw new HttpsError('internal', '네이버 로그인에 실패했습니다');
    }
  },
);
