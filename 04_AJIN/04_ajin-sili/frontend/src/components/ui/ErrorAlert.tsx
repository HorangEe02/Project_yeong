// 에러 표시 카드 — 잠금/실패/네트워크 등 다양한 케이스

import type { ReactNode } from 'react';

interface Props {
  title?: string;
  message: string;
  severity?: 'critical' | 'warning' | 'info';
  action?: ReactNode;
}

const COLOR: Record<NonNullable<Props['severity']>, string> = {
  critical: 'var(--hud-red)',
  warning: 'var(--hud-orange)',
  info: 'var(--hud-blue)',
};

export function ErrorAlert({ title, message, severity = 'critical', action }: Props) {
  const color = COLOR[severity];
  return (
    <div
      role="alert"
      style={{
        border: `1px solid ${color}`,
        background: `color-mix(in oklab, ${color} 10%, transparent)`,
        padding: 12,
        margin: '12px 0',
        fontFamily: 'var(--hud-font)',
      }}
    >
      {title && (
        <div style={{ color, fontWeight: 700, fontSize: 13, marginBottom: 4, letterSpacing: '0.05em' }}>
          ● {title}
        </div>
      )}
      <div style={{ color: 'var(--hud-text)', fontSize: 13, lineHeight: 1.5 }}>{message}</div>
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </div>
  );
}
