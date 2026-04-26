import { describe, it, expect } from 'vitest';
import {
  ensureVisibleTab,
  normalizeTabId,
  TAB_ORDER,
  visibleTabs,
} from '../types';

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

  it('feature key 매핑 정확 (F1.1b)', () => {
    const byId = Object.fromEntries(TAB_ORDER.map((t) => [t.id, t]));
    expect(byId.home.feature).toBeUndefined();
    expect(byId.appointments.feature).toBe('appointments');
    expect(byId.inpatient.feature).toBe('inpatient');
    expect(byId.checkup.feature).toBe('checkup');
    expect(byId.guide.feature).toBeUndefined();
    expect(byId.more.feature).toBeUndefined();
  });
});

describe('visibleTabs', () => {
  it('모든 features on → 6 탭 그대로', () => {
    const got = visibleTabs({
      appointments: true,
      inpatient: true,
      checkup: true,
    });
    expect(got.map((t) => t.id)).toEqual([
      'home',
      'appointments',
      'inpatient',
      'checkup',
      'guide',
      'more',
    ]);
  });

  it('features.appointments=false → appointments 제외 (5탭)', () => {
    const got = visibleTabs({ appointments: false, inpatient: true, checkup: true });
    expect(got.map((t) => t.id)).toEqual([
      'home',
      'inpatient',
      'checkup',
      'guide',
      'more',
    ]);
  });

  it('inpatient + checkup off → 4탭 (home/appointments/guide/more)', () => {
    const got = visibleTabs({ appointments: true, inpatient: false, checkup: false });
    expect(got.map((t) => t.id)).toEqual([
      'home',
      'appointments',
      'guide',
      'more',
    ]);
  });

  it('모두 off → home/guide/more 만 (3탭)', () => {
    const got = visibleTabs({});
    expect(got.map((t) => t.id)).toEqual(['home', 'guide', 'more']);
  });

  it('알 수 없는 키는 무시 — 기존 6 탭 영향 없음', () => {
    const got = visibleTabs({
      appointments: true,
      inpatient: true,
      checkup: true,
      experimental: true,
    });
    expect(got.map((t) => t.id)).toEqual([
      'home',
      'appointments',
      'inpatient',
      'checkup',
      'guide',
      'more',
    ]);
  });
});

describe('ensureVisibleTab', () => {
  it('활성 탭이 활성 상태 → 그대로', () => {
    expect(ensureVisibleTab('appointments', { appointments: true })).toBe('appointments');
  });

  it('feature 미지정 탭 (home/guide/more) → 항상 통과', () => {
    expect(ensureVisibleTab('home', {})).toBe('home');
    expect(ensureVisibleTab('guide', {})).toBe('guide');
    expect(ensureVisibleTab('more', {})).toBe('more');
  });

  it('비활성 탭 → home 으로 fallback', () => {
    expect(ensureVisibleTab('appointments', { appointments: false })).toBe('home');
    expect(ensureVisibleTab('inpatient', {})).toBe('home');
    expect(ensureVisibleTab('checkup', { checkup: false })).toBe('home');
  });

  it('명시되지 않은 feature → false 처리 → home', () => {
    expect(ensureVisibleTab('inpatient', { appointments: true })).toBe('home');
  });
});
