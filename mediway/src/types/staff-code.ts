/** 의료진 ID 코드 (RTDB: staff_codes/{code}) */
export interface StaffCode {
  code: string;
  hospitalId: string;
  department: string;
  expiresAt: number;
  usedBy: string | null;
  usedAt?: number;
  createdAt: number;
}

/** 코드 검증 결과 */
export type StaffCodeValidation =
  | { valid: true; code: StaffCode }
  | { valid: false; reason: 'not_found' | 'expired' | 'already_used' };

/** 코드 일괄 발급 입력 */
export interface BulkIssueInput {
  hospitalId: string;
  department: string;
  quantity: number;
  expiresInDays: number;
}
