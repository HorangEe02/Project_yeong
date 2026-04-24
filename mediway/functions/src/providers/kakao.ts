import axios from 'axios';

export interface KakaoProfile {
  id: string;
  email: string | null;
  nickname: string | null;
  profileImage: string | null;
}

export async function exchangeKakaoCode(
  code: string,
  redirectUri: string,
  clientId: string,
  clientSecret?: string,
): Promise<KakaoProfile> {
  const tokenResp = await axios.post<{ access_token: string }>(
    'https://kauth.kakao.com/oauth/token',
    new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: clientId,
      redirect_uri: redirectUri,
      code,
      ...(clientSecret ? { client_secret: clientSecret } : {}),
    }).toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
  );

  const accessToken = tokenResp.data.access_token;

  const userResp = await axios.get<{
    id: number;
    kakao_account?: {
      email?: string;
      profile?: { nickname?: string; profile_image_url?: string };
    };
  }>('https://kapi.kakao.com/v2/user/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  const acc = userResp.data.kakao_account ?? {};
  return {
    id: String(userResp.data.id),
    email: acc.email ?? null,
    nickname: acc.profile?.nickname ?? null,
    profileImage: acc.profile?.profile_image_url ?? null,
  };
}
