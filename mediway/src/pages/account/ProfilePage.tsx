import { useEffect, useState, type FormEvent } from 'react';
import { Mail, Calendar, Shield, Building2, Stethoscope, Clock, AlertTriangle } from 'lucide-react';
import { AccountLayout } from '@/components/account/AccountLayout';
import { TextField } from '@/components/auth/TextField';
import { RequestStaffRoleDialog } from '@/components/account/RequestStaffRoleDialog';
import { useAuthStore } from '@/stores/authStore';
import { updateDisplayNameForCurrentUser } from '@/services/auth';
import { cancelRoleRequest } from '@/services/roleRequest';
import type { AuthProvider, UserProfile } from '@/types/auth';

export function ProfilePage() {
  const { user, profile } = useAuthStore();
  const [displayName, setDisplayName] = useState('');
  const [saving, setSaving] = useState(false);
  const [requestOpen, setRequestOpen] = useState(false);
  const [message, setMessage] = useState<
    { tone: 'ok'; text: string } | { tone: 'err'; text: string } | null
  >(null);

  useEffect(() => {
    setDisplayName(profile?.displayName ?? user?.displayName ?? '');
  }, [profile?.displayName, user?.displayName]);

  const dirty = displayName.trim() !== (profile?.displayName ?? '').trim();

  const onSave = async (e: FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setSaving(true);
    try {
      await updateDisplayNameForCurrentUser(displayName);
      setMessage({ tone: 'ok', text: '프로필이 저장되었습니다' });
    } catch (err) {
      setMessage({
        tone: 'err',
        text: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;

  return (
    <AccountLayout title="내 프로필" description="계정 정보 및 연결된 공급자를 확인합니다">
      <form onSubmit={onSave} className="flex flex-col gap-5">
        <TextField
          label="이름"
          required
          maxLength={40}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          hint="대시보드와 드롭다운에 표시되는 이름입니다"
        />

        <div className="grid gap-3 sm:grid-cols-2">
          <InfoRow
            icon={<Mail className="h-4 w-4" />}
            label="이메일"
            value={user.email ?? '미등록'}
          />
          <InfoRow
            icon={<Shield className="h-4 w-4" />}
            label="역할"
            value={roleLabel(profile?.role)}
          />
          <InfoRow
            icon={<Calendar className="h-4 w-4" />}
            label="가입일"
            value={formatDate(profile?.createdAt)}
          />
          <InfoRow
            icon={<Building2 className="h-4 w-4" />}
            label="소속"
            value={
              profile?.department
                ? `${profile.department}${profile.hospitalId ? ` (${profile.hospitalId})` : ''}`
                : '해당 없음'
            }
          />
        </div>

        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-on-surface-variant">
            연결된 로그인 공급자
          </p>
          <div className="flex flex-wrap gap-2">
            {(profile?.providers ?? []).map((p) => (
              <ProviderBadge key={p} provider={p} />
            ))}
            {(!profile?.providers || profile.providers.length === 0) && (
              <span className="text-xs text-on-surface-variant">없음</span>
            )}
          </div>
        </div>

        {message && (
          <p
            className={`rounded-lg px-3 py-2 text-xs ${
              message.tone === 'ok'
                ? 'bg-green-50 text-green-700'
                : 'bg-red-50 text-red-600'
            }`}
          >
            {message.text}
          </p>
        )}

        <div className="flex items-center justify-end gap-2 border-t border-surface-container-high pt-4">
          <button
            type="submit"
            disabled={!dirty || saving || !displayName.trim()}
            className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            {saving ? '저장 중...' : '변경 사항 저장'}
          </button>
        </div>
      </form>

      {/* 역할 전환 신청 섹션 (환자 전용) */}
      {profile?.role === 'patient' && (
        <div className="mt-6 border-t border-surface-container-high pt-6">
          <RoleRequestSection
            profile={profile}
            onOpen={() => setRequestOpen(true)}
            onCancel={async () => {
              try {
                await cancelRoleRequest();
                setMessage({ tone: 'ok', text: '신청이 취소되었습니다' });
              } catch (err) {
                setMessage({
                  tone: 'err',
                  text: err instanceof Error ? err.message : String(err),
                });
              }
            }}
          />
        </div>
      )}

      <RequestStaffRoleDialog
        open={requestOpen}
        onClose={() => setRequestOpen(false)}
        onSubmitted={() =>
          setMessage({ tone: 'ok', text: '의료진 전환 신청을 접수했습니다' })
        }
      />
    </AccountLayout>
  );
}

function RoleRequestSection({
  profile,
  onOpen,
  onCancel,
}: {
  profile: UserProfile;
  onOpen: () => void;
  onCancel: () => void;
}) {
  const req = profile.pendingRoleRequest;
  if (!req) {
    return (
      <div className="flex flex-col gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-on-surface">
          <Stethoscope className="h-4 w-4 text-primary" />
          의료진 전환
        </h3>
        <p className="text-xs text-on-surface-variant">
          의료진으로 전환을 원하시면 관리자 승인을 요청할 수 있습니다.
        </p>
        <button
          type="button"
          onClick={onOpen}
          className="self-start rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
        >
          의료진 전환 신청
        </button>
      </div>
    );
  }
  if (req.status === 'pending') {
    return (
      <div className="flex flex-col gap-2 rounded-lg bg-amber-50 p-4 text-sm">
        <div className="flex items-center gap-2 text-amber-800">
          <Clock className="h-4 w-4" />
          <p className="font-semibold">의료진 전환 승인 대기 중</p>
        </div>
        <p className="text-xs text-amber-800/80">
          {req.department} · {req.hospitalId} · {formatRelative(req.requestedAt)}
        </p>
        {req.reason && (
          <p className="text-xs text-amber-800/80">사유: {req.reason}</p>
        )}
        <button
          type="button"
          onClick={onCancel}
          className="self-start rounded-lg border border-amber-700 px-3 py-1 text-xs font-medium text-amber-800"
        >
          신청 취소
        </button>
      </div>
    );
  }
  // rejected
  return (
    <div className="flex flex-col gap-2 rounded-lg bg-red-50 p-4 text-sm">
      <div className="flex items-center gap-2 text-red-700">
        <AlertTriangle className="h-4 w-4" />
        <p className="font-semibold">전환 신청이 거절되었습니다</p>
      </div>
      {req.rejectReason && (
        <p className="text-xs text-red-700/80">사유: {req.rejectReason}</p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onOpen}
          className="self-start rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
        >
          다시 신청
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="self-start rounded-lg border border-red-300 px-3 py-1.5 text-xs text-red-700"
        >
          기록 삭제
        </button>
      </div>
    </div>
  );
}

function formatRelative(ts: number): string {
  const diff = Date.now() - ts;
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return `방금 전 신청`;
  if (h < 24) return `${h}시간 전 신청`;
  return `${Math.floor(h / 24)}일 전 신청`;
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-surface-container-low p-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface text-on-surface-variant">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-on-surface-variant/80">
          {label}
        </p>
        <p className="truncate text-sm font-medium text-on-surface">{value}</p>
      </div>
    </div>
  );
}

function ProviderBadge({ provider }: { provider: AuthProvider }) {
  const meta: Record<AuthProvider, { label: string; cls: string }> = {
    password: { label: '이메일 / 비밀번호', cls: 'bg-primary/10 text-primary' },
    google: { label: 'Google', cls: 'bg-blue-50 text-blue-600' },
    kakao: { label: '카카오', cls: 'bg-[#FEE500] text-[#191919]' },
    naver: { label: '네이버', cls: 'bg-[#03C75A] text-white' },
    anonymous: { label: '익명', cls: 'bg-surface-container-high text-on-surface-variant' },
  };
  const m = meta[provider];
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${m.cls}`}>
      {m.label}
    </span>
  );
}

function roleLabel(role: UserProfile['role'] | undefined): string {
  switch (role) {
    case 'staff':
      return '의료진';
    case 'admin':
      return '관리자';
    case 'patient':
      return '환자 · 보호자';
    default:
      return '미지정';
  }
}

function formatDate(ts: number | undefined): string {
  if (!ts) return '-';
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`;
}
