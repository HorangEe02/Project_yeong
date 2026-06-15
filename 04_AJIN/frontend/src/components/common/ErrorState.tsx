// 패널/테이블/차트 영역에서 API 실패·오프라인·빈 데이터를 명시적으로 노출.
// equipment.tsx 의 mock fallback 제거(Phase 3)와 함께 도입.

import type { ReactNode } from 'react';
import { AlertTriangle, Inbox, RotateCw, WifiOff } from 'lucide-react';
import clsx from 'clsx';

export type ErrorStateIcon = 'error' | 'offline' | 'empty';

interface Props {
  message: string;
  title?: string;
  icon?: ErrorStateIcon;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
  className?: string;
  children?: ReactNode;
}

const ICONS = {
  error: AlertTriangle,
  offline: WifiOff,
  empty: Inbox,
} as const;

const COLORS: Record<ErrorStateIcon, string> = {
  error: 'var(--hud-red)',
  offline: 'var(--hud-orange)',
  empty: 'var(--hud-text-dim)',
};

const DEFAULT_TITLES: Record<ErrorStateIcon, string> = {
  error: '데이터를 불러올 수 없습니다',
  offline: '네트워크 연결이 끊겼습니다',
  empty: '데이터가 없습니다',
};

export function ErrorState({
  message,
  title,
  icon = 'error',
  onRetry,
  retryLabel = '다시 시도',
  compact = false,
  className,
  children,
}: Props) {
  const Icon = ICONS[icon];
  const color = COLORS[icon];
  const headingText = title ?? DEFAULT_TITLES[icon];

  return (
    <div
      role="alert"
      aria-live="polite"
      className={clsx('ui-glass', 'error-state', compact && 'is-compact', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: compact ? '16px 12px' : '32px 24px',
        gap: compact ? 8 : 12,
        minHeight: compact ? 120 : 200,
        fontFamily: 'var(--hud-font)',
      }}
    >
      <Icon
        size={compact ? 24 : 36}
        strokeWidth={1.5}
        color={color}
        aria-hidden
      />
      <div
        style={{
          color,
          fontWeight: 700,
          fontSize: compact ? 13 : 15,
          letterSpacing: '0.04em',
        }}
      >
        {headingText}
      </div>
      <div
        style={{
          color: 'var(--hud-text-dim)',
          fontSize: compact ? 12 : 13,
          lineHeight: 1.5,
          maxWidth: 420,
        }}
      >
        {message}
      </div>
      {children}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="ui-btn-ghost"
          style={{
            marginTop: compact ? 4 : 8,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 14px',
            fontSize: 13,
            fontFamily: 'var(--hud-font)',
            color: 'var(--hud-text)',
            background: 'transparent',
            border: '1px solid var(--hud-border)',
            borderRadius: 4,
            cursor: 'pointer',
          }}
        >
          <RotateCw size={14} aria-hidden />
          {retryLabel}
        </button>
      )}
    </div>
  );
}
