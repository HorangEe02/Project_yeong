import { Link } from 'react-router-dom';
import { Stethoscope, User } from 'lucide-react';
import { useAuthStore, selectIsStaff } from '@/stores/authStore';
import { Logo } from '@/components/common/Logo';

export function LandingPage() {
  const { user, profile, initialized } = useAuthStore();
  const isStaff = useAuthStore(selectIsStaff);
  const isLoggedIn = !!user && !user.isAnonymous;

  return (
    <main className="flex min-h-[calc(100vh-60px)] flex-col items-center justify-center px-4 pt-16 lg:pt-24">
      <div className="mb-12 flex flex-col items-center gap-4">
        <Logo size="lg" />
        <h1 className="text-3xl font-bold tracking-tight text-on-surface">
          MediWay
        </h1>
        <p className="max-w-md text-center text-on-surface-variant">
          병원 내 환자 동선 가이드 플랫폼
        </p>
        {initialized && isLoggedIn && profile && (
          <p className="text-xs text-on-surface-variant/70">
            {profile.displayName ?? user?.email}님으로 로그인됨 ·{' '}
            <span className="font-medium text-primary">{profile.role}</span>
          </p>
        )}
      </div>

      <div className="flex w-full max-w-md flex-col gap-4">
        <RoleCard
          to="/staff"
          icon={<Stethoscope className="h-6 w-6 text-primary" />}
          title="의료진"
          desc={
            isStaff
              ? '대시보드로 이동'
              : isLoggedIn
                ? '의료진 권한이 필요합니다'
                : 'QR 스캔 후 환자에게 동선을 전송합니다'
          }
          muted={isLoggedIn && !isStaff}
        />
        <RoleCard
          to="/patient"
          icon={<User className="h-6 w-6 text-primary" />}
          title="환자"
          desc="QR 코드를 보여주고 동선 안내를 받습니다"
        />
      </div>

      {initialized && !isLoggedIn && (
        <div className="mt-8 flex items-center gap-3 text-sm">
          <Link to="/login" className="font-medium text-primary">
            로그인
          </Link>
          <span className="text-on-surface-variant/50">·</span>
          <Link to="/signup" className="font-medium text-primary">
            회원가입
          </Link>
        </div>
      )}

      <p className="mt-16 text-xs text-on-surface-variant/60">
        Phase 1 Web Demo — MediWay 데모 병원
      </p>
    </main>
  );
}

function RoleCard({
  to,
  icon,
  title,
  desc,
  muted,
}: {
  to: string;
  icon: React.ReactNode;
  title: string;
  desc: string;
  muted?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`group flex items-center gap-4 rounded-xl bg-surface-container-lowest p-5 shadow-ambient transition-shadow hover:shadow-ambient-lg no-underline ${
        muted ? 'opacity-75' : ''
      }`}
    >
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 transition-colors group-hover:bg-primary/20">
        {icon}
      </div>
      <div>
        <h2 className="text-lg font-semibold text-on-surface">{title}</h2>
        <p className="text-sm text-on-surface-variant">{desc}</p>
      </div>
    </Link>
  );
}
