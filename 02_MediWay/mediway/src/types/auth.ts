/**
 * 사용자 역할.
 * - patient: 환자 (기본)
 * - staff: 의료진
 * - admin: 병원 관리자 (hospital-scoped)
 * - platformAdmin: MediWay 플랫폼 운영자 (cross-hospital) — P1 신규
 */
export type UserRole = 'patient' | 'staff' | 'admin' | 'platformAdmin';

/** 병원 범위 역할 — hospitalRoles 맵 값에 사용 (platformAdmin 제외) */
export type HospitalScopedRole = Exclude<UserRole, 'platformAdmin'>;

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

/** 지원 언어 — P5 i18n 대비 자리 예약 */
export type SupportedLanguage = 'ko' | 'en' | 'zh' | 'ja';

/** 알림 채널 */
export type NotificationChannel = 'push' | 'sms' | 'email' | 'alimtalk';

/**
 * 사용자 환경설정 (P2 이후 사용)
 * v2 가이드: largeUi 필드는 P2에서 고령자 모드 토글로 활성
 */
export interface UserPreferences {
  /** 고령자 모드 — P2 F16 인프라 자리 예약 (v2) */
  largeUi?: boolean;
  /** 알림 채널 선호 — P3 */
  notificationChannels?: NotificationChannel[];
  /** 선호 언어 — P5 i18n */
  language?: SupportedLanguage;
  /** TTS 음성 안내 — P4 F17 (지도 길찾기 전용, v2 축소 스코프) */
  tts?: {
    enabled: boolean;
    /** 재생 속도 0.5~2.0 (기본 1.0) */
    rate?: number;
  };
}

/**
 * 사용자 프로필 (RTDB: users/{uid})
 * P1에서 Multi-Tenant 필드 추가 — 기존 hospitalId는 단일 병원 호환용으로 유지
 */
export interface UserProfile {
  uid: string;
  email: string | null;
  displayName: string | null;
  role: UserRole;
  status: UserStatus;
  providers: AuthProvider[];

  /**
   * @deprecated P1부터 primaryHospitalId 사용 권장. 호환성을 위해 유지.
   * 마이그레이션 완료 후 제거 예정.
   */
  hospitalId?: string;

  department?: string;
  staffCode?: string;
  pendingRoleRequest?: PendingRoleRequest;

  // ============================================================================
  // P1 Multi-Tenant 확장
  // ============================================================================

  /** 로그인 시 기본 진입할 병원 */
  primaryHospitalId?: string;
  /** 가입된 모든 병원 (가족 대리·다병원 이용 시) */
  hospitalIds?: string[];
  /** 병원별 역할 — primaryHospitalId 외 병원에서의 역할 (F7 가족 대리 대비) */
  hospitalRoles?: Record<string, HospitalScopedRole>;
  /** 환경설정 (P2 이후 본격 사용, P1에서 자리만 예약) */
  preferences?: UserPreferences;

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
