import { describe, it, expect } from 'vitest';
import { createMockParkingAdapter, mockResolver } from '../mock';

describe('createMockParkingAdapter', () => {
  it('providerId=mock', () => {
    expect(createMockParkingAdapter().providerId).toBe('mock');
  });

  it('유효한 번호판 → 2000원 할인 + referenceId', async () => {
    const adapter = createMockParkingAdapter();
    const r = await adapter.requestDiscount({
      hospitalId: 'demo',
      licensePlate: '12가3456',
    });
    expect(r.success).toBe(true);
    expect(r.discount).toBe(2000);
    expect(r.referenceId).toMatch(/^mock-/);
  });

  it('잘못된 번호판 → success=false', async () => {
    const adapter = createMockParkingAdapter();
    const r = await adapter.requestDiscount({
      hospitalId: 'demo',
      licensePlate: 'BAD_PLATE',
    });
    expect(r.success).toBe(false);
    expect(r.discount).toBe(0);
    expect(r.message).toMatch(/차량 번호 형식/);
  });

  it('공백 trim 후 검증', async () => {
    const adapter = createMockParkingAdapter();
    const r = await adapter.requestDiscount({
      hospitalId: 'demo',
      licensePlate: '  123가4567  ',
    });
    expect(r.success).toBe(true);
  });
});

describe('mockResolver', () => {
  it('hospitalId 무관하게 mock adapter 반환', () => {
    expect(mockResolver('demo')?.providerId).toBe('mock');
    expect(mockResolver('smch')?.providerId).toBe('mock');
  });
});
