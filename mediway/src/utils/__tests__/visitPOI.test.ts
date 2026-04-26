import { describe, it, expect } from 'vitest';
import { findPOIByZoneHint } from '../visitPOI';
import type { POI } from '@/types/hospital';

function poi(overrides: Partial<POI>): POI {
  return {
    id: 'p',
    name: '내과',
    shortName: '내과',
    category: 'department',
    buildingId: 'main',
    floorLevel: 1,
    coordinates: { x: 0, y: 0 },
    ...overrides,
  } as POI;
}

const SAMPLE_POIS: POI[] = [
  poi({ id: 'admin_reception', name: '접수', shortName: '접수' }),
  poi({ id: 'dept_im', name: '내과', shortName: '내과' }),
  poi({ id: 'dept_gs', name: '외과', shortName: '외과' }),
  poi({ id: 'lab_blood', name: '채혈실', shortName: '채혈' }),
  poi({ id: 'pharmacy_main', name: '약국', shortName: '약국' }),
  poi({ id: 'entrance_main', name: '정문', shortName: '정문' }),
];

describe('findPOIByZoneHint', () => {
  it('빈 string → undefined', () => {
    expect(findPOIByZoneHint('', SAMPLE_POIS)).toBeUndefined();
    expect(findPOIByZoneHint('   ', SAMPLE_POIS)).toBeUndefined();
  });

  it('정확 일치 (name) → 해당 POI', () => {
    const found = findPOIByZoneHint('내과', SAMPLE_POIS);
    expect(found?.id).toBe('dept_im');
  });

  it('정확 일치 (shortName) → 해당 POI', () => {
    const found = findPOIByZoneHint('채혈', SAMPLE_POIS);
    expect(found?.id).toBe('lab_blood');
  });

  it('POI name 이 zone substring (예: "내과 외래" → 내과)', () => {
    const found = findPOIByZoneHint('내과 외래', SAMPLE_POIS);
    expect(found?.id).toBe('dept_im');
  });

  it('zone 이 POI name 의 substring (예: "약" → "약국")', () => {
    const found = findPOIByZoneHint('약', SAMPLE_POIS);
    expect(found?.id).toBe('pharmacy_main');
  });

  it('대소문자 무시', () => {
    const englishPOIs = [poi({ id: 'er_a', name: 'Emergency Room A', shortName: 'ER-A' })];
    const found = findPOIByZoneHint('emergency room a', englishPOIs);
    expect(found?.id).toBe('er_a');
  });

  it('매칭 없음 → undefined', () => {
    const found = findPOIByZoneHint('알 수 없는 zone', SAMPLE_POIS);
    expect(found).toBeUndefined();
  });

  it('다중 일치 시 첫 번째 발견 반환 (deterministic)', () => {
    const dups = [
      poi({ id: 'a1', name: '대기실' }),
      poi({ id: 'a2', name: '대기실' }),
    ];
    const found = findPOIByZoneHint('대기실', dups);
    expect(found?.id).toBe('a1');
  });

  it('Zone 문자열의 앞뒤 공백 trim', () => {
    const found = findPOIByZoneHint('  내과  ', SAMPLE_POIS);
    expect(found?.id).toBe('dept_im');
  });
});
