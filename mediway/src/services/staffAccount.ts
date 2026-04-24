import { httpsCallable } from 'firebase/functions';
import { functions } from '@/config/firebase';

export type CreateStaffMode = 'email_reset' | 'temp_password';

export interface CreateStaffAccountInput {
  email: string;
  displayName?: string;
  department: string;
  hospitalId: string;
  mode: CreateStaffMode;
}

export interface CreateStaffAccountResult {
  uid: string;
  mode: CreateStaffMode;
  email: string;
  resetLink?: string;
  tempPassword?: string;
}

/** Admin-only: Functions를 호출해 의료진 계정 생성
 *  Blaze 플랜 + Functions 배포 완료 후에만 작동 */
export async function createStaffAccount(
  input: CreateStaffAccountInput,
): Promise<CreateStaffAccountResult> {
  const callable = httpsCallable<CreateStaffAccountInput, CreateStaffAccountResult>(
    functions,
    'adminCreateStaffAccount',
  );
  const res = await callable(input);
  return res.data;
}
