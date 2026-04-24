import { describe, it, expect } from 'vitest';
import { normalizeTabId, TAB_ORDER } from '../types';

describe('normalizeTabId', () => {
  it('유효한 tab id 는 그대로 반환', () => {
    for (const tab of TAB_ORDER) {
      expect(normalizeTabId(tab.id)).toBe(tab.id);
    }
  });

  it('null/undefined/빈 문자열은 home 으로 정규화', () => {
    expect(normalizeTabId(null)).toBe('home');
    expect(normalizeTabId(undefined)).toBe('home');
    expect(normalizeTabId('')).toBe('home');
  });

  it('알 수 없는 값은 home 으로 정규화', () => {
    expect(normalizeTabId('unknown')).toBe('home');
    expect(normalizeTabId('HOME')).toBe('home'); // 대소문자 구분
    expect(normalizeTabId('home ')).toBe('home'); // trailing space
  });
});

describe('TAB_ORDER', () => {
  it('6개 탭이 순서대로 정의됨', () => {
    expect(TAB_ORDER.map((t) => t.id)).toEqual([
      'home',
      'appointments',
      'inpatient',
      'checkup',
      'guide',
      'more',
    ]);
  });

  it('모든 탭에 한국어 라벨이 있음', () => {
    for (const tab of TAB_ORDER) {
      expect(tab.label).toBeTruthy();
      expect(tab.label.length).toBeGreaterThan(0);
    }
  });
});
