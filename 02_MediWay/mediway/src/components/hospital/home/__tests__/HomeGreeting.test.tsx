import { describe, it, expect } from 'vitest';
import { getTimeBasedGreeting } from '../HomeGreeting';

describe('getTimeBasedGreeting', () => {
  it('05-11시는 아침', () => {
    expect(getTimeBasedGreeting(new Date('2026-04-23T06:00:00'))).toBe(
      '좋은 아침입니다',
    );
    expect(getTimeBasedGreeting(new Date('2026-04-23T11:59:00'))).toBe(
      '좋은 아침입니다',
    );
  });

  it('12-17시는 오후', () => {
    expect(getTimeBasedGreeting(new Date('2026-04-23T12:00:00'))).toBe(
      '좋은 오후입니다',
    );
    expect(getTimeBasedGreeting(new Date('2026-04-23T17:59:00'))).toBe(
      '좋은 오후입니다',
    );
  });

  it('18시 이후와 새벽은 저녁', () => {
    expect(getTimeBasedGreeting(new Date('2026-04-23T18:00:00'))).toBe(
      '좋은 저녁입니다',
    );
    expect(getTimeBasedGreeting(new Date('2026-04-23T23:30:00'))).toBe(
      '좋은 저녁입니다',
    );
    expect(getTimeBasedGreeting(new Date('2026-04-23T03:00:00'))).toBe(
      '좋은 저녁입니다',
    );
  });
});
