import { useAuthStore } from '@/stores/authStore';

/**
 * 시간대·이름 기반 인사말 — 시안 PlusUltra SaaS 1 참조.
 * 05-12 아침 / 12-18 오후 / 그 외 저녁.
 */
export function getTimeBasedGreeting(now: Date = new Date()): string {
  const h = now.getHours();
  if (h >= 5 && h < 12) return '좋은 아침입니다';
  if (h >= 12 && h < 18) return '좋은 오후입니다';
  return '좋은 저녁입니다';
}

export function HomeGreeting() {
  const profile = useAuthStore((s) => s.profile);
  const user = useAuthStore((s) => s.user);
  const name =
    profile?.displayName?.trim() ||
    user?.displayName?.trim() ||
    user?.email?.split('@')[0] ||
    '';
  const greeting = getTimeBasedGreeting();

  return (
    <header className="mb-5">
      <h2 className="text-2xl font-bold sm:text-3xl">
        {greeting}
        {name && (
          <>
            , <span className="text-primary">{name}</span>
            <span className="text-on-surface">님</span>
          </>
        )}
      </h2>
      <p className="mt-1 text-sm text-on-surface-variant">
        오늘도 건강한 하루 되세요.
      </p>
    </header>
  );
}
