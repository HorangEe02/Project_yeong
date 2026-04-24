import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle2, Mail, Stethoscope } from 'lucide-react';
import { AuthCard } from '@/components/auth/AuthCard';
import { TextField } from '@/components/auth/TextField';
import { PasswordStrength } from '@/components/auth/PasswordStrength';
import { signUpPatient, signInWithEmail, signOutUser } from '@/services/auth';
import {
  acceptStaffInvitation,
  getStaffInvitation,
} from '@/services/staffInvitation';
import { useAuthStore } from '@/stores/authStore';
import { scorePassword } from '@/utils/password';
import type { StaffInvitation } from '@/types/staff-invitation';

type PageState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'new'; invitation: StaffInvitation } // 신규 가입 필요
  | { kind: 'existing'; invitation: StaffInvitation } // 기존 로그인 상태
  | { kind: 'mismatch'; invitation: StaffInvitation; userEmail: string }
  | { kind: 'done'; invitation: StaffInvitation };

export function InviteAcceptPage() {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const initialized = useAuthStore((s) => s.initialized);

  const [state, setState] = useState<PageState>({ kind: 'loading' });
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // 초대 + 사용자 상태 기반 분기
  useEffect(() => {
    if (!initialized) return;
    void (async () => {
      const res = await getStaffInvitation(token);
      if (!res.valid) {
        const msg =
          res.reason === 'expired'
            ? '초대 링크가 만료되었습니다 (7일 유효)'
            : res.reason === 'accepted'
              ? '이미 수락된 초대입니다'
              : res.reason === 'revoked'
                ? '관리자가 폐기한 초대입니다'
                : '유효하지 않은 초대 링크입니다';
        setState({ kind: 'error', message: msg });
        return;
      }
      const invitation = res.invitation;

      // 로그인된 사용자가 있는 경우
      if (user && !user.isAnonymous) {
        if (user.email && user.email.toLowerCase() === invitation.email) {
          setState({ kind: 'existing', invitation });
        } else {
          setState({
            kind: 'mismatch',
            invitation,
            userEmail: user.email ?? '(이메일 없음)',
          });
        }
      } else {
        setState({ kind: 'new', invitation });
      }
    })();
  }, [token, user, initialized]);

  const onNewSignup = async (e: FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'new') return;
    setFormError(null);
    if (scorePassword(password).strength === 'too-short') {
      setFormError('비밀번호는 8자 이상이어야 합니다');
      return;
    }
    if (password !== confirmPassword) {
      setFormError('비밀번호 확인이 일치하지 않습니다');
      return;
    }
    setSubmitting(true);
    try {
      // 1. 이메일/비밀번호로 가입 (role=patient로 임시 생성)
      await signUpPatient({
        email: state.invitation.email,
        password,
        displayName: state.invitation.displayName ?? state.invitation.email,
      });
      // 2. 초대 수락 (role=staff로 자동 승격)
      await acceptStaffInvitation(state.invitation.token);
      setState({ kind: 'done', invitation: state.invitation });
      setTimeout(() => navigate('/staff', { replace: true }), 1500);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('auth/email-already-in-use')) {
        setFormError('이미 가입된 이메일입니다. 로그인 후 이 링크를 다시 클릭해주세요.');
      } else {
        setFormError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onExistingAccept = async () => {
    if (state.kind !== 'existing') return;
    setSubmitting(true);
    setFormError(null);
    try {
      await acceptStaffInvitation(state.invitation.token);
      setState({ kind: 'done', invitation: state.invitation });
      setTimeout(() => navigate('/staff', { replace: true }), 1500);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  // 에러 상태
  if (state.kind === 'error') {
    return (
      <AuthCard title="초대 수락 불가" subtitle={`토큰: ${token.slice(0, 12)}...`}>
        <p className="rounded-lg bg-red-50 px-3 py-3 text-sm text-red-600">
          {state.message}
        </p>
        <button
          type="button"
          onClick={() => navigate('/login', { replace: true })}
          className="mt-3 w-full rounded-lg border border-surface-container-high px-3 py-2 text-sm"
        >
          로그인 페이지로
        </button>
      </AuthCard>
    );
  }

  if (state.kind === 'loading') {
    return (
      <AuthCard title="의료진 초대" subtitle="초대 정보를 확인 중입니다...">
        <p className="text-sm text-on-surface-variant">잠시만 기다려주세요.</p>
      </AuthCard>
    );
  }

  if (state.kind === 'mismatch') {
    return (
      <AuthCard
        title="다른 이메일로 로그인되어 있습니다"
        subtitle={`초대 이메일: ${state.invitation.email}`}
      >
        <p className="mb-3 rounded-lg bg-amber-50 px-3 py-3 text-xs text-amber-700">
          현재 <span className="font-mono">{state.userEmail}</span> 로 로그인되어 있습니다.
          초대를 수락하려면 <span className="font-semibold">{state.invitation.email}</span> 계정으로 다시 로그인해주세요.
        </p>
        <button
          type="button"
          onClick={async () => {
            await signOutUser();
            navigate(`/invite/${state.invitation.token}`, { replace: true });
          }}
          className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary"
        >
          로그아웃 후 다시 시도
        </button>
      </AuthCard>
    );
  }

  if (state.kind === 'existing') {
    return (
      <AuthCard
        title="의료진 초대 수락"
        subtitle={`${state.invitation.department} 의료진으로 승격됩니다`}
      >
        <div className="flex flex-col gap-3">
          <InvitationBrief invitation={state.invitation} />
          {formError && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
              {formError}
            </p>
          )}
          <button
            type="button"
            onClick={onExistingAccept}
            disabled={submitting}
            className="flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            <Stethoscope className="h-4 w-4" />
            {submitting ? '수락 중...' : '초대 수락하고 의료진 되기'}
          </button>
        </div>
      </AuthCard>
    );
  }

  if (state.kind === 'new') {
    return (
      <AuthCard
        title="의료진 가입"
        subtitle={`${state.invitation.department} 초대장을 수락하시려면 비밀번호를 설정하세요`}
      >
        <form onSubmit={onNewSignup} className="flex flex-col gap-4">
          <InvitationBrief invitation={state.invitation} />
          <TextField
            label="이메일"
            type="email"
            value={state.invitation.email}
            readOnly
            disabled
          />
          <div className="flex flex-col gap-2">
            <TextField
              label="비밀번호"
              type="password"
              required
              autoComplete="new-password"
              hint="8자 이상"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <PasswordStrength password={password} />
          </div>
          <TextField
            label="비밀번호 확인"
            type="password"
            required
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={
              confirmPassword && password !== confirmPassword
                ? '비밀번호가 일치하지 않습니다'
                : undefined
            }
          />

          {formError && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
              {formError}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            {submitting ? '가입 중...' : '가입하고 의료진 되기'}
          </button>
          <p className="text-center text-[11px] text-on-surface-variant">
            이미 계정이 있으신가요?{' '}
            <button
              type="button"
              onClick={() => navigate(`/login?redirect=/invite/${state.invitation.token}`)}
              className="font-medium text-primary"
            >
              로그인 후 수락
            </button>
          </p>
        </form>
      </AuthCard>
    );
  }

  // done
  return (
    <AuthCard title="수락 완료!" subtitle="의료진 대시보드로 이동합니다">
      <div className="flex items-center gap-3 rounded-lg bg-green-50 p-4 text-green-800">
        <CheckCircle2 className="h-5 w-5 shrink-0" />
        <p className="text-sm font-medium">
          의료진으로 승격되었습니다 — {state.invitation.department}
        </p>
      </div>
    </AuthCard>
  );
}

// 임시 로그인 헬퍼 (현재 미사용이나 retain)
export async function loginForInvite(email: string, password: string) {
  return signInWithEmail(email, password);
}

function InvitationBrief({ invitation }: { invitation: StaffInvitation }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg bg-surface-container-low p-3 text-xs">
      <div className="flex items-center gap-2 text-on-surface-variant">
        <Mail className="h-3 w-3" />
        <span className="font-mono">{invitation.email}</span>
      </div>
      <div className="flex items-center gap-2 text-on-surface-variant">
        <Stethoscope className="h-3 w-3" />
        <span>
          {invitation.hospitalId} · {invitation.department}
        </span>
      </div>
      {invitation.displayName && (
        <p className="text-on-surface-variant">이름: {invitation.displayName}</p>
      )}
    </div>
  );
}
