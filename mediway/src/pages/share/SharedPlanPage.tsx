import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { MapPin, Clock, User, Hourglass } from 'lucide-react';
import { AuthCard } from '@/components/auth/AuthCard';
import { getSharedPlan } from '@/services/sharedPlan';
import { getPOIById } from '@/data/hospital/pois';
import type { SharedPlan } from '@/types/shared-plan';

export function SharedPlanPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [state, setState] = useState<
    | { kind: 'idle' }
    | { kind: 'loading' }
    | { kind: 'error'; message: string }
    | { kind: 'loaded'; plan: SharedPlan }
  >({ kind: code ? 'loading' : 'idle' });

  useEffect(() => {
    if (!code) return;
    void (async () => {
      const res = await getSharedPlan(code);
      if (res.valid) {
        setState({ kind: 'loaded', plan: res.plan });
      } else {
        setState({
          kind: 'error',
          message:
            res.reason === 'expired'
              ? '공유 코드가 만료되었습니다 (30분 유효)'
              : '유효하지 않은 공유 코드입니다',
        });
      }
    })();
  }, [code]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const normalized = input.trim().toUpperCase();
    if (normalized.length < 6) return;
    navigate(`/share/plan/${normalized}`);
  };

  if (!code) {
    return (
      <AuthCard title="공유된 방문 계획 보기" subtitle="6자리 공유 코드를 입력하세요">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            placeholder="ABCDEF"
            maxLength={6}
            className="rounded-lg border border-surface-container-high bg-surface px-4 py-3 text-center font-mono text-2xl tracking-[0.3em] outline-none focus:border-primary"
            autoCapitalize="characters"
          />
          <button
            type="submit"
            disabled={input.trim().length < 6}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            조회
          </button>
          <p className="text-center text-[11px] text-on-surface-variant">
            공유 코드는 30분간만 유효합니다.
          </p>
        </form>
      </AuthCard>
    );
  }

  if (state.kind === 'loading') {
    return (
      <AuthCard title="공유된 방문 계획" subtitle={`코드: ${code}`}>
        <p className="text-sm text-on-surface-variant">불러오는 중...</p>
      </AuthCard>
    );
  }

  if (state.kind === 'error') {
    return (
      <AuthCard title="공유 조회 실패" subtitle={`코드: ${code}`}>
        <p className="rounded-lg bg-red-50 px-3 py-3 text-sm text-red-600">
          {state.message}
        </p>
        <button
          type="button"
          onClick={() => navigate('/share/plan')}
          className="mt-3 w-full rounded-lg border border-surface-container-high px-3 py-2 text-sm"
        >
          다른 코드 입력
        </button>
      </AuthCard>
    );
  }

  if (state.kind === 'loaded') {
    const { plan } = state;
    const minutesLeft = Math.max(0, Math.round((plan.expiresAt - Date.now()) / 60_000));
    return (
      <AuthCard
        title="공유된 방문 계획"
        subtitle={
          plan.snapshot.sharerName
            ? `${plan.snapshot.sharerName} 님이 공유한 계획`
            : '공유된 계획'
        }
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between text-xs text-on-surface-variant">
            <span className="flex items-center gap-1">
              <Hourglass className="h-3 w-3" />
              {minutesLeft}분 남음
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {new Date(plan.snapshot.sharedAt).toLocaleString()}
            </span>
          </div>

          <ol className="flex flex-col overflow-hidden rounded-xl border border-surface-container-high">
            {plan.snapshot.waypoints.map((w, i) => {
              const poi = getPOIById(w.poiId);
              return (
                <li
                  key={`${w.poiId}-${i}`}
                  className="flex items-center gap-3 border-b border-surface-container-high/60 bg-surface px-3 py-2.5 last:border-0"
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-on-surface">
                      {poi?.name ?? w.poiId}
                    </p>
                    <p className="truncate text-[11px] text-on-surface-variant">
                      {poi
                        ? `${poi.buildingId === 'main' ? '본관' : poi.buildingId} · ${poi.floorLevel}F`
                        : ''}
                    </p>
                  </div>
                  <MapPin className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" />
                </li>
              );
            })}
          </ol>

          <div className="flex items-start gap-2 rounded-lg bg-surface-container-low p-3 text-[11px] text-on-surface-variant">
            <User className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div>
              <p className="font-medium">읽기 전용</p>
              <p>공유받은 계획은 수정할 수 없습니다. 본인이 직접 계획을 관리하려면 로그인 후 방문 계획 페이지를 이용하세요.</p>
            </div>
          </div>
        </div>
      </AuthCard>
    );
  }

  return null;
}
