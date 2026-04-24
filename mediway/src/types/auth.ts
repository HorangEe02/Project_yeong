/** 사용자 역할 */
export type UserRole = 'patient' | 'staff' | 'admin' | 'platformAdmin';

/** 사용자 계정 상태 */
export type UserStatus = 'active' | 'suspended' | 'deleted';

/** 인증 공급자 */
export type AuthProvider = 'password' | 'google' | 'kakao' | 'naver' | 'anonymous';

/** 역할 전환 신청 상태 */
export type RoleRequestStatus = 'pending' | 'rejected';

/** 환자가 의료진으로 전환 신청한 정보 (UserProfile에 중첩) */
export interface PendingRoleRequest {
  requestedRole: 'staff';
  hospitalId: string;
  department: string;
  reason?: string;
  requestedAt: number;
  status: RoleRequestStatus;
  rejectReason?: string;
  rejectedAt?: number;
}

/** 사용자 프로필 (RTDB: users/{uid}) */
export interface UserProfile {
  uid: string;
  email: string | null;
  displayName: string | null;
  role: UserRole;
  status: UserStatus;
  providers: AuthProvider[];
  hospitalId?: string;
  department?: string;
  staffCode?: string;
  pendingRoleRequest?: PendingRoleRequest;
  createdAt: number;
  updatedAt: number;
}

/** 의료진 회원가입 입력 */
export interface StaffSignupInput {
  email: string;
  password: string;
  displayName: string;
  staffCode: string;
}

/** 환자 회원가입 입력 */
export interface PatientSignupInput {
  email: string;
  password: string;
  displayName: string;
}
