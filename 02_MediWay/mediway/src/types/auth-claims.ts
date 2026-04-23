import type { UserRole } from '@/types/auth';

/**
 * Firebase Auth Custom Claims — ID 토큰 payload에 주입되는 MediWay 전용 필드.
 *
 * RTDB 보안 규칙에서 `auth.token.role`, `auth.token.hospitalId` 등으로 평가됨.
 * Cloud Function (`functions/src/setClaims.ts`)에서만 쓰기 가능.
 *
 * 주의:
 * - ID 토큰은 최대 1시간 캐시됨. claim 변경 후 즉시 반영하려면
 *   클라이언트에서 `getIdToken(true)`로 강제 갱신 필요.
 * - Firebase Rules는 claim이 없을 때 undefined를 반환하므로 null check 필수.
 */
export interface MediwayClaims {
  /** 사용자 역할 */
  role: UserRole;
  /** 현재 활성 병원 (primary) */
  hospitalId?: string;
  /** 가입된 전체 병원 목록 */
  hospitalIds?: string[];
  /** Custom claim 세팅 시각 — 디버깅용 */
  claimsSetAt?: number;
}

/**
 * Firebase SDK getIdTokenResult() 반환 토큰의 claims 타입
 * (Firebase 내장 필드 + MediwayClaims)
 */
export interface MediwayTokenResult {
  claims: MediwayClaims & {
    /** Firebase 내장 — UID */
    sub?: string;
    /** Firebase 내장 — 이메일 검증 여부 */
    email_verified?: boolean;
    /** Firebase 내장 — provider */
    firebase?: {
      sign_in_provider: string;
      identities: Record<string, unknown>;
    };
    [key: string]: unknown;
  };
}
