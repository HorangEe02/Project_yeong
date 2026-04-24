import { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import {
  selectPrimaryActive,
  subscribeMyWaitQueue,
  todayDateKST,
} from '@/services/waitQueue';
import type { WaitQueuePatientIndex, WaitQueueStatus } from '@/types/waitQueue';

const STATUS_META: Record<
  WaitQueueStatus,
  { label: string; badge: string }
> = {
  waiting: {
    label: '대기 중',
    badge: 'bg-surface-container text-on-surface-variant',
  },
  called: {
    label: '호출됨',
    badge: 'bg-primary text-on-primary',
  },
  'in-progress': {
    label: '진료 중',
    badge: 'bg-secondary-fixed text-on-secondary-fixed',
  },
  completed: {
    label: '완료',
    badge: 'bg-surface-container text-on-surface-variant',
  },
  cancelled: {
    label: '취소',
    badge: 'bg-surface-container text-on-surface-variant',
  },
};

/**
 * 환자의 오늘자 대기 순번을 큰 카드로 보여주는 위젯.
 *
 * 데이터: `/hospitals/{hospitalId}/wait_queue_by_patient/{uid}` 실시간 구독 →
 *        `selectPrimaryActive` 로 urgency 우선 단일 엔트리 선정.
 *
 * 표시 상태:
 *  - **called** (호출됨): 링 강조 + "진료실로 이동해 주세요" 큰 안내.
 *    FCM 미수신 시에도 이 위젯만으로 호출 확인 가능 (safety net).
 *  - **in-progress** / **waiting**: 순번 + 부서 + 상태 뱃지.
 *  - 활성 엔트리 없음: 친근한 빈 상태 문구.
 *  - 구독 에러: 조용히 폴백 문구.
 *
 * 전제:
 *  - 로그인된 실제 유저 (익명 제외) + profile.hospitalId 존재
 *  - 위 조건 미충족 시 위젯은 null (렌더 skip)
 *
 * TODO(B-2+): URL `:hospitalSlug` 와 profile.hospitalId 불일치 케이스 (방문 병원 ≠ 홈 병원)
 *   처리. 현재는 profile.hospitalId 만 사용.
 */
export function WaitQueueWidget() {
  const user = useAuthStore((s) => s.user);
  const profile = useAuthStore((s) => s.profile);
  const [entries, setEntries] = useState<WaitQueuePatientIndex[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hospitalId = profile?.hospitalId ?? null;
  const userUid = user?.uid ?? null;
  const isAnon = user?.isAnonymous ?? true;

  useEffect(() => {
    if (!userUid || isAnon || !hospitalId) {
      setEntries([]);
      return;
    }
    const unsub = subscribeMyWaitQueue(
      hospitalId,
      userUid,
      (data) => {
        setEntries(data);
        setError(null);
      },
      (err) => setError(err.message || '구독 실패'),
    );
    return unsub;
  }, [userUid, isAnon, hospitalId]);

  const today = useMemo(() => todayDateKST(), []);
  const primary = useMemo(
    () => (entries ? selectPrimaryActive(entries, today) : null),
    [entries, today],
  );

  if (!userUid || isAnon || !hospitalId) return null;

  if (entries === null) {
    return (
      <div
        className="animate-pulse rounded-xl bg-surface-container-lowest p-6"
        aria-label="대기 정보 불러오는 중"
      >
        <div className="mb-3 h-3 w-24 rounded bg-surface-container-high" />
        <div className="h-10 w-16 rounded bg-surface-container-high" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-surface-container-lowest p-4 text-sm text-on-surface-variant">
        대기 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.
      </div>
    );
  }

  if (!primary) {
    return (
      <div className="rounded-xl bg-surface-container-lowest p-6 text-center">
        <p className="text-sm text-on-surface-variant">오늘 접수된 진료가 없습니다.</p>
      </div>
    );
  }

  const meta = STATUS_META[primary.status];
  const isCalled = primary.status === 'called';

  return (
    <article
      className={`rounded-xl p-5 transition-all ${
        isCalled
          ? 'bg-primary/5 ring-2 ring-primary'
          : 'bg-surface-container-lowest'
      }`}
      aria-live="polite"
    >
      <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
        내 대기 순번
      </p>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="text-5xl font-bold text-primary tabular-nums">
          {primary.number}
        </span>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${meta.badge}`}
        >
          {meta.label}
        </span>
      </div>
      <p className="mt-2 text-sm text-on-surface">
        {primary.department} <span className="text-on-surface-variant">·</span> {primary.date}
      </p>
      {isCalled && (
        <p className="mt-3 rounded-lg bg-primary p-3 text-base font-semibold text-on-primary">
          진료실로 이동해 주세요
        </p>
      )}
    </article>
  );
}
