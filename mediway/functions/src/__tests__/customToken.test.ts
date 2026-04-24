import { describe, it, expect } from 'vitest';
import { buildSocialUid } from '../customToken';

describe('buildSocialUid', () => {
  it('kakao provider uid', () => {
    expect(buildSocialUid('kakao', '12345')).toBe('kakao:12345');
  });
  it('naver provider uid', () => {
    expect(buildSocialUid('naver', 'abc-xyz')).toBe('naver:abc-xyz');
  });
});
