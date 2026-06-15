// v4.7 C-2 — 챗봇 응답 언어 3-way 토글 (KO / EN / Auto).
// UI 언어(`ajin-lang`)와 분리된 응답 언어(`ajin-chat-lang`) 영속.

import { useTranslation } from 'react-i18next';

export type ChatLanguage = 'ko' | 'en' | 'auto';

interface Props {
  value: ChatLanguage;
  onChange: (v: ChatLanguage) => void;
  disabled?: boolean;
}

export function LanguageToggle({ value, onChange, disabled }: Props) {
  const { t } = useTranslation();
  const options: { v: ChatLanguage; label: string }[] = [
    { v: 'auto', label: t('chat.language.auto') },
    { v: 'ko', label: 'KO' },
    { v: 'en', label: 'EN' },
  ];

  return (
    <div
      role="group"
      aria-label={t('chat.language.label')}
      title={t('chat.language.tooltip')}
      style={{
        display: 'inline-flex',
        gap: 0,
        border: '1px solid var(--hud-border, #2a2a2a)',
        borderRadius: 6,
        overflow: 'hidden',
        fontSize: 11,
      }}
    >
      {options.map((o) => {
        const active = value === o.v;
        return (
          <button
            key={o.v}
            type="button"
            disabled={disabled}
            onClick={() => onChange(o.v)}
            aria-pressed={active}
            style={{
              padding: '4px 10px',
              background: active ? 'var(--hud-primary, #3b82f6)' : 'transparent',
              color: active ? 'var(--hud-on-primary, #fff)' : 'var(--hud-text-dim, #9ca3af)',
              border: 'none',
              borderRight: '1px solid var(--hud-border, #2a2a2a)',
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontWeight: active ? 600 : 400,
              letterSpacing: 0.4,
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
