/**
 * 주차 할인 어댑터 — 파일럿 병원마다 실제 구현을 주입.
 *
 * PLAN_P3 §3 C12: MVP에서는 인터페이스·mock만 제공.
 * 실 연동(주차 업체 API, 인트라넷 바코드 등)은 파일럿 계약 후 각 병원별 구현.
 */

export interface ParkingDiscountRequest {
  hospitalId: string;
  /** 차량 번호판 (원내 규칙은 병원별) */
  licensePlate: string;
  /** 방문 컨텍스트 — 외래/입원/검진 중 무엇에 연계된 할인인지 */
  visitContext?: {
    type: 'appointment' | 'inpatient' | 'checkup';
    refId?: string;
  };
}

export interface ParkingDiscountResult {
  success: boolean;
  /** 할인된 금액 (KRW) — 실패 시 0 */
  discount: number;
  /** 사용자에게 보여줄 안내 메시지 */
  message: string;
  /** 해당 병원의 참조 ID (영수증·정산) */
  referenceId?: string;
}

export interface ParkingAdapter {
  readonly providerId: string;
  requestDiscount(
    req: ParkingDiscountRequest,
  ): Promise<ParkingDiscountResult>;
}

/**
 * 특정 병원의 주차 어댑터를 resolve.
 * 현재는 mock만 등록되어 있으며 파일럿 계약 시 실 구현을 registry에 추가.
 */
export type ParkingAdapterResolver = (
  hospitalId: string,
) => ParkingAdapter | null;
