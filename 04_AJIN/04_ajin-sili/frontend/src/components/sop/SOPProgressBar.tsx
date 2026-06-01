// Day 5 — SOP 진행률 바 (작은 inline 인디케이터)
// 사이드 패널 항목 옆에 표시 — "3 / 6 단계"

import clsx from 'clsx';

interface Props {
  total: number;
  completed: number;
  className?: string;
}

export function SOPProgressBar({ total, completed, className }: Props) {
  const pct = total === 0 ? 0 : Math.round((completed / total) * 100);
  return (
    <div className={clsx('sop-progress', className)} aria-label={`진행률 ${pct}%`}>
      <div className="sop-progress-track">
        <div className="sop-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="sop-progress-text">
        {completed} / {total}
      </span>
    </div>
  );
}
