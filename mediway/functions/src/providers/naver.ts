import axios from 'axios';

export interface NaverProfile {
  id: string;
  email: string | null;
  nickname: string | null;
  profileImage: string | null;
}

export async function exchangeNaverCode(
  code: string,
  state: string,
  redirectUri: string,
  clientId: string,
  clientSecret: string,
): Promise<NaverProfile> {
  const tokenResp = await axios.get<{ access_token: string }>(
    'https://nid.naver.com/oauth2.0/token',
    {
      params: {
        grant_type: 'authorization_code',
        client_id: clientId,
        client_secret: clientSecret,
        code,
        state,
        redirect_uri: redirectUri,
      },
    },
  );

  const accessToken = tokenResp.data.access_token;

  const userResp = await axios.get<{
    response: {
      id: string;
      email?: string;
      nickname?: string;
      profile_image?: string;
    };
  }>('https://openapi.naver.com/v1/nid/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  const r = userResp.data.response;
  return {
    id: r.id,
    email: r.email ?? null,
    nickname: r.nickname ?? null,
    profileImage: r.profile_image ?? null,
  };
}
