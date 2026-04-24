import { describe, it, expect } from 'vitest';
import { scorePassword } from '../password';

describe('scorePassword', () => {
  it('8자 미만은 too-short', () => {
    expect(scorePassword('abc').strength).toBe('too-short');
    expect(scorePassword('1234567').strength).toBe('too-short');
  });

  it('단일 문자 클래스는 weak', () => {
    const res = scorePassword('aaaaaaaa');
    expect(res.strength).toBe('weak');
  });

  it('대소문자+숫자+특수+충분한 길이 = strong', () => {
    const res = scorePassword('P@ssw0rd12345x');
    expect(res.strength).toBe('strong');
  });

  it('흔한 비밀번호는 감점된다', () => {
    const common = scorePassword('Password123!');
    expect(['weak', 'fair']).toContain(common.strength);
  });

  it('suggestions는 누락된 문자 클래스를 안내한다', () => {
    const res = scorePassword('onlylowercase');
    expect(res.suggestions.some((s) => s.includes('대문자'))).toBe(true);
    expect(res.suggestions.some((s) => s.includes('숫자'))).toBe(true);
    expect(res.suggestions.some((s) => s.includes('특수문자'))).toBe(true);
  });

  it('점수는 0~4 범위로 제한된다', () => {
    const scores = ['short', 'aaaaaaaa', 'Abc12345', 'Abc123!@', 'Strong#P@ss2024x'].map(
      (p) => scorePassword(p).score,
    );
    scores.forEach((s) => {
      expect(s).toBeGreaterThanOrEqual(0);
      expect(s).toBeLessThanOrEqual(4);
    });
  });
});
