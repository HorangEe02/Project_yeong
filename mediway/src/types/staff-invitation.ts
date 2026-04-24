export type StaffInvitationStatus = 'pending' | 'accepted' | 'expired' | 'revoked';

/** 의료진 초대 (RTDB: staff_invitations/{token}) */
export interface StaffInvitation {
  token: string;
  email: string;
  displayName: string | null;
  department: string;
  hospitalId: string;
  invitedBy: string; // admin uid
  invitedByEmail: string | null;
  invitedAt: number;
  expiresAt: number;
  status: StaffInvitationStatus;
  claimedBy?: string;
  claimedAt?: number;
}

export type StaffInvitationResult =
  | { valid: true; invitation: StaffInvitation }
  | { valid: false; reason: 'not_found' | 'expired' | 'accepted' | 'revoked' };

export const INVITE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7일
