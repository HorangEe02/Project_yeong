import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useFeature, useHospital } from '@/contexts/HospitalContext';
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
 * 데이터: `/hospitals/{slug}/wait_queue_by_patient/{uid}` 실시간 구독 →
 *        `selectPrimaryActive` 로 urgency 우선 단일 엔트리 선정.
 *
 * Slug 소스 (F1.1c):
 *  - 이전: `profile.hospitalId` (사용자 home hospital 고정)
 *  - 현재: `useHospital().slug` (URL `/h/{slug}/...` 의 현재 방문 병원)
 *  - 멀티-병원 방문 시 home != 현재 슬러그 케이스 정확히 처리. cross-tenant 가드는 HospitalShell 가 담당.
 *
 * Feature gating (F1.1c):
 *  - `features.appointments=false` → 위젯 자체 미표시 (null)
 *  - HomeTab 도 동일 가드를 두지만 widget 자체에 보호막 — 다른 곳에서 마운트해도 안전
 *
 * 표시 상태:
 *  - **called** (호출됨): 링 강조 + "진료실로 이동해 주세요" 큰 안내.
 *    FCM 미수신 시에도 이 위젯만으로 호출 확인 가능 (safety net).
 *  - **in-progress** / **waiting**: 순번 + 부서 + 상태 뱃지.
 *  - 활성 엔트리 없음: empty-state CTA → "외래 탭으로 이동" (F1.1c).
 *  - 구독 에러: 조용히 폴백 문구.
 *
 * 전제:
 *  - 로그인된 실제 유저 (익명 제외) — 익명은 wait_queue_by_patient 권한 없음
 *  - HospitalShell 하위 라우트 (useHospital() 보장)
 */
export function WaitQueueWidget() {
  const user = useAuthStore((s) => s.user);
  const { slug } = useHospital();
  const appointmentsOn = useFeature('appointments');
  const [, setSearchParams] = useSearchParams();
  const [entries, setEntries] = useState<WaitQueuePatientIndex[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const userUid = user?.uid ?? null;
  const isAnon = user?.isAnonymous ?? true;

  useEffect(() => {
    if (!userUid || isAnon || !appointmentsOn) {
      setEntries([]);
      return;
    }
    const unsub = subscribeMyWaitQueue(
      slug,
      userUid,
      (data) => {
        setEntries(data);
        setError(null);
      },
      (err) => setError(err.message || '구독 실패'),
    );
    return unsub;
  }, [slug, userUid, isAnon, appointmentsOn]);

  const today = useMemo(() => todayDateKST(), []);
  const primary = useMemo(
    () => (entries ? selectPrimaryActive(entries, today) : null),
    [entries, today],
  );

  const goToAppointments = useCallback(() => {
    setSearchParams({ tab: 'appointments' }, { replace: true });
  }, [setSearchParams]);

  // features.appointments=false 또는 익명/미로그인 → 위젯 자체 미표시
  if (!userUid || isAnon || !appointmentsOn) return null;

  // 에러 우선 — 첫 번째 onValue 가 error 로 떨어진 경우 entries 가 여전히 null 인 채로
  //          무한 skeleton 에 갇히지 않도록 한다.
  if (error) {
    return (
      <div
        className="rounded-xl bg-surface-container-lowest p-4 text-sm text-on-surface-variant"
        data-testid="waitqueue-error"
      >
        대기 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.
      </div>
    );
  }

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

  if (!primary) {
    return (
      <div
        className="rounded-xl bg-surface-container-lowest p-6 text-center"
        data-testid="waitqueue-empty"
      >
        <p className="text-sm text-on-surface-variant">오늘 접수된 진료가 없어요.</p>
        <p className="mt-1 text-xs text-on-surface-variant/80">
          외래 탭에서 예약 후 [접수] 누르면 순번이 실시간으로 표시됩니다.
        </p>
        <button
          type="button"
          onClick={goToAppointments}
          className="mt-4 inline-flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary"
        >
          외래 탭으로 이동
          <ArrowRight className="h-4 w-4" />
        </button>
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
