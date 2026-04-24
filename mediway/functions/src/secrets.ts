import { defineSecret } from 'firebase-functions/params';

/**
 * Firebase Functions 2세대 Secret 참조.
 *
 * 로컬 개발:
 *   `functions/.secret.local` 파일에 `KAKAO_CLIENT_ID=...` 형식으로 작성 (gitignore 적용됨).
 *
 * 프로덕션 등록 (최초 1회):
 *   firebase functions:secrets:set KAKAO_CLIENT_ID
 *   firebase functions:secrets:set KAKAO_CLIENT_SECRET
 *   firebase functions:secrets:set NAVER_CLIENT_ID
 *   firebase functions:secrets:set NAVER_CLIENT_SECRET
 *
 * 배포된 Function이 Secret에 접근하려면 onCall 옵션의 `secrets` 배열에 포함해야 한다.
 * 접근: `kakaoClientId.value()` — 런타임에만 해석, 빌드 타임엔 노출 X.
 */
export const kakaoClientId = defineSecret('KAKAO_CLIENT_ID');
export const kakaoClientSecret = defineSecret('KAKAO_CLIENT_SECRET');

export const naverClientId = defineSecret('NAVER_CLIENT_ID');
export const naverClientSecret = defineSecret('NAVER_CLIENT_SECRET');

/** P3 알림톡에서 사용 예정 — 현 커밋 기준 미배포 */
export const kakaoAdminKey = defineSecret('KAKAO_ADMIN_KEY');
