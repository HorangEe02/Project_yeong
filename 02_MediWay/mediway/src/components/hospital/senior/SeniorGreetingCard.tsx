import { useEffect, useState } from 'react';
import { Calendar } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useHospital } from '@/hooks/useHospital';
import { subscribeMyAppointmentIndex } from '@/services/appointments';
import type { AppointmentIndexEntry } from '@/types/appointment';
import { useSeniorCopy } from '@/hooks/useSeniorCopy';

/**
 * SeniorHome 상단 인사 카드.
 *
 * 시안 PlusUltra SaaS 2/5: 큰 인사 + NEXT VISIT 서브카드(가까운 예약).
 */
export function SeniorGreetingCard() {
  const profile = useAuthStore((s) => s.profile);
  const user = useAuthStore((s) => s.user);
  const { slug } = useHospital();
  const copy = useSeniorCopy();

  const name =
    profile?.displayName?.trim() ||
    user?.displayName?.trim() ||
    user?.email?.split('@')[0] ||
    '';

  const [next, setNext] = useState<
    (AppointmentIndexEntry & { id: string }) | null
  >(null);

  useEffect(() => {
    if (!slug || !user?.uid) {
      setNext(null);
      return;
    }
    return subscribeMyAppointmentIndex(slug, user.uid, (list) => {
      const upcoming = list
        .filter((a) => a.status === 'scheduled' && a.scheduledAt > Date.now())
        .sort((a, b) => a.scheduledAt - b.scheduledAt);
      setNext(upcoming[0] ?? null);
    });
  }, [slug, user?.uid]);

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });

  return (
    <section
      aria-label="오늘 인사 + 다음 방문"
      className="mb-6 flex flex-col gap-4 rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <p className="text-sm text-on-surface-variant">{today}</p>
        <h2 className="mt-1 text-2xl font-bold sm:text-3xl">
          안녕하세요{name && (
            <>
              , <span className="text-primary">{name}</span>
              <span className="text-on-surface">님</span>
            </>
          )}
        </h2>
        <p className="mt-1 text-base text-on-surface-variant">
          {copy('greeting.wellbeing', '오늘도 건강하세요')}
        </p>
      </div>

      <aside
        aria-label="다음 방문 정보"
        className="flex min-w-[200px] items-center gap-3 rounded-xl bg-primary/5 p-4"
      >
        <Calendar className="h-6 w-6 text-primary" aria-hidden />
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-primary">
            {copy('senior.next-visit.title', '다음 방문')}
          </p>
          {next ? (
            <>
              <p className="mt-0.5 text-base font-semibold">
                {new Date(next.scheduledAt).toLocaleDateString('ko-KR', {
                  month: 'long',
                  day: 'numeric',
                })}
                {' · '}
                {new Date(next.scheduledAt).toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
              <p className="text-sm text-on-surface-variant">
                {next.department}
              </p>
            </>
          ) : (
            <p className="mt-0.5 text-sm text-on-surface-variant">
              {copy('senior.next-visit.empty', '예약된 진료가 없어요')}
            </p>
          )}
        </div>
      </aside>
    </section>
  );
}
