// VariableField — Module B · 단일 변수 입력 필드.
// B2 v4.0: label + ★(필수) + placeholder 예시 + 그룹 라벨 (호버 툴팁).
// 디자인 시스템 v3.5: lg-field 호환 + 12px 라운드.

import type { VarMetadata } from '@/types/draft';

interface Props {
  variable: VarMetadata;
  value: string;
  onChange: (value: string) => void;
  /** 입력 길이가 100 이상이면 자동으로 textarea 로 전환. */
  autoMultiline?: boolean;
}

export function VariableField({ variable, value, onChange, autoMultiline = true }: Props) {
  const isLong = autoMultiline && (value.length > 100 || /\n/.test(value));

  return (
    <div className="lg-field">
      <label
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 4,
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--hud-text)',
          letterSpacing: '0.02em',
        }}
        title={variable.placeholder || ''}
      >
        {variable.required && (
          <span
            aria-label="필수"
            style={{ color: 'var(--hud-primary)', fontSize: 13, fontWeight: 700 }}
          >
            ★
          </span>
        )}
        <span>{variable.label_ko || variable.name}</span>
        <span
          className="mono"
          style={{
            marginLeft: 'auto',
            fontFamily: 'var(--hud-font-mono)',
            fontSize: 9,
            letterSpacing: '0.1em',
            color: 'var(--hud-text-muted)',
            textTransform: 'uppercase',
          }}
          title={`그룹: ${variable.group}`}
        >
          {variable.name}
        </span>
      </label>

      {isLong ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={variable.placeholder}
          rows={Math.min(4, Math.ceil(value.length / 80) + 1)}
          className="lg-textarea"
          style={{ fontSize: 13, lineHeight: 1.5, minHeight: 56 }}
          aria-required={variable.required}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={variable.placeholder}
          aria-required={variable.required}
        />
      )}
    </div>
  );
}
