import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: number | string;
  icon?: ReactNode;
  tone?: 'default' | 'primary' | 'warn' | 'danger' | 'ok';
}

export function StatCard({ label, value, icon, tone = 'default' }: StatCardProps) {
  const toneCls: Record<NonNullable<StatCardProps['tone']>, string> = {
    default: 'bg-surface-container-low text-on-surface',
    primary: 'bg-primary/10 text-primary',
    warn: 'bg-amber-50 text-amber-700',
    danger: 'bg-red-50 text-red-600',
    ok: 'bg-green-50 text-green-700',
  };
  return (
    <div className="rounded-xl bg-surface-container-lowest p-4 shadow-ambient">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
          {label}
        </p>
        {icon && (
          <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${toneCls[tone]}`}>
            {icon}
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-bold text-on-surface">{value}</p>
    </div>
  );
}
