import { useRef, type ReactNode, type KeyboardEvent } from 'react';
import clsx from 'clsx';

export interface TabItem {
  id: string;
  labelEn: string;
  labelKo?: string;
  icon?: ReactNode;
  badge?: number | string;
  disabled?: boolean;
}

interface Props {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
  variant?: 'main' | 'sub';
  className?: string;
}

export function Tabs({ items, active, onChange, variant = 'main', className }: Props) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, idx: number) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const dir = e.key === 'ArrowRight' ? 1 : -1;
    const enabled = items.map((it, i) => ({ it, i })).filter(({ it }) => !it.disabled);
    const cur = enabled.findIndex(({ i }) => i === idx);
    if (cur < 0) return;
    const next = enabled[(cur + dir + enabled.length) % enabled.length];
    refs.current[next.it.id]?.focus();
    onChange(next.it.id);
  };

  return (
    <div role="tablist" className={clsx('ui-tabs', variant === 'sub' && 'sub', className)}>
      {items.map((it, idx) => {
        const isActive = it.id === active;
        return (
          <button
            key={it.id}
            ref={(el) => { refs.current[it.id] = el; }}
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${it.id}`}
            tabIndex={isActive ? 0 : -1}
            disabled={it.disabled}
            className="ui-tab"
            onClick={() => !it.disabled && onChange(it.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
          >
            {it.icon}
            <span className="ui-tab-en">{it.labelEn}</span>
            {it.labelKo && <span className="ui-tab-ko">· {it.labelKo}</span>}
            {it.badge !== undefined && <span className="ui-tab-badge">{it.badge}</span>}
          </button>
        );
      })}
    </div>
  );
}
