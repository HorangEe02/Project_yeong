// 상태 배지 — ●/○ 글리프 + 색상 (이모지 금지 규칙)

import type { ReactNode } from 'react';
import clsx from 'clsx';

export type BadgeStatus = 'ok' | 'warn' | 'fail' | 'info' | 'off' | 'on';

interface Props {
  status: BadgeStatus;
  children: ReactNode;
  className?: string;
}

const GLYPH: Record<BadgeStatus, string> = {
  ok: '●',
  warn: '●',
  fail: '●',
  info: '●',
  off: '○',
  on: '●',
};

const COLOR_VAR: Record<BadgeStatus, string> = {
  ok: 'var(--hud-green)',
  warn: 'var(--hud-orange)',
  fail: 'var(--hud-red)',
  info: 'var(--hud-blue)',
  off: 'var(--hud-text-muted)',
  on: 'var(--hud-green)',
};

export function Badge({ status, children, className }: Props) {
  return (
    <span
      className={clsx('hud-badge', `hud-badge-${status}`, className)}
      style={{ color: COLOR_VAR[status] }}
    >
      <span className="hud-badge-glyph" aria-hidden>{GLYPH[status]}</span>
      <span className="hud-badge-text">{children}</span>
    </span>
  );
}
