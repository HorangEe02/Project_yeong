import { useSearchParams } from 'react-router-dom';
import { Calendar, MapPin, Ticket, Siren } from 'lucide-react';
import type { ComponentType } from 'react';

/**
 * 홈 하단 Quick Actions — 시안 PlusUltra SaaS 1의 하단 4개 원형 아이콘 행.
 *
 * 현재 P4.U MVP:
 * - 4개 버튼 모두 URL ?tab= 파라미터로 해당 탭 전환
 * - Emergency는 guide 탭 (응급실 안내) 진입. 119 확인 모달은 기존
 *   EmergencyCtaWidget이 계속 담당 (중복 방지 목적 quick action은 탭 점프).
 */
interface Action {
  id: 'appointments' | 'guide' | 'home' | 'emergency';
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
  label: string;
  tab: 'appointments' | 'guide' | 'home';
  tone?: 'default' | 'error';
}

const ACTIONS: Action[] = [
  { id: 'appointments', icon: Calendar, label: '예약', tab: 'appointments' },
  { id: 'guide', icon: MapPin, label: '길 안내', tab: 'guide' },
  { id: 'home', icon: Ticket, label: '대기 순번', tab: 'home' },
  { id: 'emergency', icon: Siren, label: '응급', tab: 'guide', tone: 'error' },
];

export function QuickActionRow() {
  const [, setParams] = useSearchParams();

  const onClick = (tab: Action['tab']) => {
    setParams(
      (p) => {
        p.set('tab', tab);
        return p;
      },
      { replace: false },
    );
  };

  return (
    <div
      role="group"
      aria-label="빠른 작업"
      className="grid grid-cols-4 gap-3"
    >
      {ACTIONS.map((a) => (
        <QuickActionCard key={a.id} action={a} onClick={() => onClick(a.tab)} />
      ))}
    </div>
  );
}

function QuickActionCard({
  action,
  onClick,
}: {
  action: Action;
  onClick: () => void;
}) {
  const Icon = action.icon;
  const isError = action.tone === 'error';
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center gap-2 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 text-center hover:bg-surface-container-low sm:p-4"
    >
      <span
        className={`flex h-10 w-10 items-center justify-center rounded-full ${
          isError ? 'bg-error-container' : 'bg-primary/10'
        }`}
      >
        <Icon
          className={`h-5 w-5 ${isError ? 'text-error' : 'text-primary'}`}
          aria-hidden
        />
      </span>
      <span className="text-xs font-medium text-on-surface sm:text-sm">
        {action.label}
      </span>
    </button>
  );
}
