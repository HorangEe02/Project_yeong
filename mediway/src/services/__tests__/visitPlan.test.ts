import { describe, it, expect } from 'vitest';
import { canAutoSend, isPlanExpired } from '../visitPlan';
import type { VisitPlan } from '@/types/visit-plan';

const basePlan = (partial: Partial<VisitPlan> = {}): VisitPlan => ({
  uid: 'u1',
  waypoints: [{ poiId: 'admin_billing' }],
  source: 'staff',
  updatedBy: 's1',
  updatedAt: 1000,
  expiresAt: 10_000,
  ...partial,
});

describe('isPlanExpired', () => {
  it('null 계획은 만료 취급', () => {
    expect(isPlanExpired(null)).toBe(true);
  });
  it('expiresAt 이전이면 유효', () => {
    expect(isPlanExpired(basePlan({ expiresAt: 5000 }), 4000)).toBe(false);
  });
  it('expiresAt 이후면 만료', () => {
    expect(isPlanExpired(basePlan({ expiresAt: 5000 }), 6000)).toBe(true);
  });
});

describe('canAutoSend', () => {
  it('환자가 직접 입력한 계획은 자동 전송 불가', () => {
    const p = basePlan({ source: 'patient', autoSendOptIn: true });
    expect(canAutoSend(p, undefined, 0)).toBe(false);
  });

  it('optIn=false면 불가', () => {
    const p = basePlan({ source: 'staff', autoSendOptIn: false });
    expect(canAutoSend(p, undefined, 0)).toBe(false);
  });

  it('의료진 배정 + optIn=true + 유효기간 → 가능', () => {
    const p = basePlan({ source: 'staff', autoSendOptIn: true, expiresAt: 10_000 });
    expect(canAutoSend(p, undefined, 5000)).toBe(true);
  });

  it('만료된 계획은 불가', () => {
    const p = basePlan({ source: 'staff', autoSendOptIn: true, expiresAt: 100 });
    expect(canAutoSend(p, undefined, 200)).toBe(false);
  });

  it('병원 ID 불일치 시 불가', () => {
    const p = basePlan({
      source: 'admin',
      autoSendOptIn: true,
      hospitalId: 'hospA',
      expiresAt: 10_000,
    });
    expect(canAutoSend(p, 'hospB', 5000)).toBe(false);
  });

  it('계획에 hospitalId 없으면 병원 검증 생략', () => {
    const p = basePlan({ source: 'staff', autoSendOptIn: true, expiresAt: 10_000 });
    expect(canAutoSend(p, 'anyHospital', 5000)).toBe(true);
  });

  it('null 계획은 불가', () => {
    expect(canAutoSend(null)).toBe(false);
  });
});
