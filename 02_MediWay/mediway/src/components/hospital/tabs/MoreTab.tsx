import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Accessibility,
  Bell,
  Building2,
  LogOut,
  User as UserIcon,
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useHospital } from '@/hooks/useHospital';
import { useSeniorMode } from '@/hooks/useSeniorMode';
import { signOutUser } from '@/services/auth';

/**
 * 더보기 탭 — 내 정보·병원 스위처·알림·고령자 모드·로그아웃.
 *
 * v2 §Phase 2 특이사항:
 * - **고령자 모드 토글을 P2부터 노출** (v1은 P4 전용이던 것을 앞당김).
 * - 알림 설정·병원 스위처는 P2 자리만 확보, 실내용은 P3에서.
 */
export function MoreTab() {
  const user = useAuthStore((s) => s.user);
  const profile = useAuthStore((s) => s.profile);
  const { hospital } = useHospital();
  const senior = useSeniorMode();
  const navigate = useNavigate();
  const [err, setErr] = useState<string | null>(null);

  const onToggleSenior = async () => {
    setErr(null);
    try {
      await senior.toggle();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const onSignOut = async () => {
    try {
      await signOutUser();
      navigate('/', { replace: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="p-4">
      <h2 className="sr-only">더보기</h2>

      {/* 계정 정보 요약 */}
      <section
        aria-labelledby="more-account-title"
        className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      >
        <header className="mb-2 flex items-center gap-2">
          <UserIcon className="h-5 w-5 text-primary" aria-hidden="true" />
          <h3 id="more-account-title" className="text-base font-semibold">
            내 정보
          </h3>
        </header>
        <div className="text-sm">
          <div>
            <span className="text-on-surface-variant">이름: </span>
            <span>{profile?.displayName ?? '-'}</span>
          </div>
          <div>
            <span className="text-on-surface-variant">이메일: </span>
            <span>{user?.email ?? '-'}</span>
          </div>
          <div>
            <span className="text-on-surface-variant">병원: </span>
            <span>{hospital?.name ?? '-'}</span>
          </div>
        </div>
      </section>

      {/* 고령자 모드 — v2 P2 조기 도입 */}
      <section
        aria-labelledby="more-senior-title"
        className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      >
        <header className="mb-2 flex items-center gap-2">
          <Accessibility
            className="h-5 w-5 text-primary"
            aria-hidden="true"
          />
          <h3 id="more-senior-title" className="text-base font-semibold">
            고령자 모드
          </h3>
        </header>
        <p className="mb-3 text-sm text-on-surface-variant">
          글자와 버튼이 커지고, 화면이 더 단순해집니다.
        </p>
        <label className="flex items-center justify-between gap-3">
          <span className="text-sm">활성화</span>
          <button
            type="button"
            role="switch"
            aria-checked={senior.enabled}
            onClick={onToggleSenior}
            className={`relative h-6 w-11 rounded-full transition-colors ${
              senior.enabled ? 'bg-primary' : 'bg-surface-container-high'
            }`}
          >
            <span
              className={`absolute top-0.5 h-5 w-5 rounded-full bg-surface-container-lowest shadow transition-transform ${
                senior.enabled ? 'translate-x-5' : 'translate-x-0.5'
              }`}
              aria-hidden="true"
            />
          </button>
        </label>
      </section>

      {/* 기타 항목 (placeholder) */}
      <section className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest">
        <MoreMenuItem
          icon={<Building2 className="h-4 w-4" aria-hidden="true" />}
          label="병원 스위처"
          hint="다른 병원으로 전환"
          onClick={() => navigate('/hospitals/select')}
        />
        <MoreMenuItem
          icon={<Bell className="h-4 w-4" aria-hidden="true" />}
          label="알림 설정"
          hint="준비 중 (P3)"
          disabled
        />
      </section>

      {err && (
        <div className="mb-3 rounded-lg bg-error-container p-3 text-sm text-error">
          {err}
        </div>
      )}

      <button
        type="button"
        onClick={onSignOut}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-outline-variant bg-surface-container-lowest px-4 py-3 text-sm font-medium"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        로그아웃
      </button>
    </div>
  );
}

function MoreMenuItem({
  icon,
  label,
  hint,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  label: string;
  hint: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex w-full items-center gap-3 border-b border-outline-variant px-4 py-3 text-left text-sm last:border-b-0 ${
        disabled
          ? 'opacity-50'
          : 'hover:bg-surface-container-low'
      }`}
    >
      <span className="text-primary">{icon}</span>
      <div className="flex-1">
        <div>{label}</div>
        <div className="text-xs text-on-surface-variant">{hint}</div>
      </div>
    </button>
  );
}
