import type {
  ParkingAdapter,
  ParkingAdapterResolver,
  ParkingDiscountRequest,
  ParkingDiscountResult,
} from './adapter';

/**
 * 데모 · 개발용 stub — 차량번호 형식만 검증, 할인 금액 2000원 반환.
 * 파일럿 계약 후 실 어댑터가 각 병원별로 구현되어 resolver에 등록.
 */
export function createMockParkingAdapter(): ParkingAdapter {
  return {
    providerId: 'mock',
    async requestDiscount(
      req: ParkingDiscountRequest,
    ): Promise<ParkingDiscountResult> {
      const plate = req.licensePlate.trim();
      if (!/^[0-9가-힣]{2,}[가-힣][0-9]{4}$/.test(plate)) {
        return {
          success: false,
          discount: 0,
          message: '차량 번호 형식을 확인해 주세요 (예: 12가3456)',
        };
      }
      return {
        success: true,
        discount: 2000,
        message: '2,000원 할인이 적용되었습니다 (데모)',
        referenceId: `mock-${Date.now()}`,
      };
    },
  };
}

/** hospitalId → adapter mapping. 현재는 모든 병원이 mock 어댑터 사용. */
export const mockResolver: ParkingAdapterResolver = () =>
  createMockParkingAdapter();
