import { describe, it, expect } from 'vitest';
import { buildAuthorizeUrlForTest } from '../socialAuth';

describe('buildAuthorizeUrlForTest', () => {
  it('카카오 인가 URL 포맷', () => {
    const url = buildAuthorizeUrlForTest(
      'kakao',
      'kakao-app',
      'https://app.test',
      'state-1',
    );
    const parsed = new URL(url);
    expect(parsed.origin + parsed.pathname).toBe(
      'https://kauth.kakao.com/oauth/authorize',
    );
    expect(parsed.searchParams.get('client_id')).toBe('kakao-app');
    expect(parsed.searchParams.get('redirect_uri')).toBe(
      'https://app.test/auth/callback/kakao',
    );
    expect(parsed.searchParams.get('response_type')).toBe('code');
    expect(parsed.searchParams.get('state')).toBe('state-1');
  });

  it('네이버 인가 URL 포맷', () => {
    const url = buildAuthorizeUrlForTest(
      'naver',
      'naver-app',
      'https://app.test',
      'state-xyz',
    );
    expect(url).toContain('https://nid.naver.com/oauth2.0/authorize');
    expect(url).toContain('state=state-xyz');
    expect(url).toContain('redirect_uri=https%3A%2F%2Fapp.test%2Fauth%2Fcallback%2Fnaver');
  });
});
