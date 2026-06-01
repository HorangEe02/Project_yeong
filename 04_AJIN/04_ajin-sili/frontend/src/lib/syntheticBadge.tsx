// syntheticBadge — Module A · Sprint 1 P0.
// 합성(seed) 데이터 행을 사용자가 실데이터로 오인하지 않도록 시각 표지.
// employees.is_synthetic = 1 인 row 에 적용. 0 (ERP/LDAP 실데이터) 는 표시 안 함.

import type { CSSProperties } from 'react';

export type DataClass = 'real' | 'synthetic' | 'system' | 'unknown' | string | null | undefined;

/**
 * is_synthetic 값이 합성 데이터를 가리키는지 판정.
 * - 1 (number) / "1" / true / "true" → true
 * - 0 / null / undefined → false (실데이터 또는 미정)
 */
export function isSynthetic(value: unknown): boolean {
  if (value === 1 || value === '1' || value === true || value === 'true') return true;
  return false;
}

interface BadgeProps {
  /** true 일 때만 렌더. 단순한 조건부 표시용 prop. */
  show?: boolean;
  /** 외부에서 직접 is_synthetic 값을 전달할 때. show 보다 우선. */
  value?: unknown;
  /** Tooltip / aria-label */
  title?: string;
  /** 인라인 스타일 override */
  style?: CSSProperties;
}

const BASE_STYLE: CSSProperties = {
  display: 'inline-block',
  padding: '1px 6px',
  marginLeft: 6,
  borderRadius: 4,
  border: '1px solid color-mix(in oklab, var(--hud-warn, #f5a623) 60%, transparent)',
  background: 'color-mix(in oklab, var(--hud-warn, #f5a623) 18%, transparent)',
  color: 'var(--hud-warn, #f5a623)',
  fontFamily: 'var(--hud-font-mono, ui-monospace, monospace)',
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  verticalAlign: 'middle',
  lineHeight: 1.4,
  userSelect: 'none',
};

export function SyntheticBadge({ show, value, title, style }: BadgeProps) {
  const visible = value !== undefined ? isSynthetic(value) : !!show;
  if (!visible) return null;
  return (
    <span
      role="status"
      aria-label={title ?? '시연용 합성 데이터'}
      title={title ?? '시연용 합성 데이터 — ERP 실연동 전'}
      style={{ ...BASE_STYLE, ...style }}
    >
      DEMO
    </span>
  );
}

interface DataClassBadgeProps {
  dataClass?: DataClass;
  sourceSystem?: string;
  style?: CSSProperties;
}

const DATA_CLASS_STYLE: CSSProperties = {
  ...BASE_STYLE,
  marginLeft: 0,
  letterSpacing: 0,
  textTransform: 'none',
};

const DATA_CLASS_LABEL: Record<string, string> = {
  real: '실데이터',
  synthetic: '합성',
  system: '시스템',
  unknown: '출처미상',
};

export function DataClassBadge({ dataClass, sourceSystem, style }: DataClassBadgeProps) {
  const normalized = String(dataClass || 'unknown').toLowerCase();
  const label = DATA_CLASS_LABEL[normalized] ?? DATA_CLASS_LABEL.unknown;
  const color =
    normalized === 'real'
      ? 'var(--hud-green)'
      : normalized === 'system'
        ? 'var(--hud-primary)'
        : normalized === 'synthetic'
          ? 'var(--hud-warn, #f5a623)'
          : 'var(--hud-text-dim)';
  return (
    <span
      role="status"
      aria-label={`데이터 출처: ${label}`}
      title={`data_class=${normalized}${sourceSystem ? ` · source_system=${sourceSystem}` : ''}`}
      style={{ ...DATA_CLASS_STYLE, borderColor: color, color, ...style }}
    >
      {label}
    </span>
  );
}
