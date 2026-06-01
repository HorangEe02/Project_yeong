// 듀얼 모드 토글 — 교육 / 업무. .chat-h .seg 스타일 재사용.

import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import type { ChatMode } from '@/types/chat';

interface Props {
  mode: ChatMode;
  onChange: (m: ChatMode) => void;
  disabled?: boolean;
}

const MODES: { id: ChatMode; labelKey: string; hintKey: string }[] = [
  { id: 'education', labelKey: 'chat.mode.education', hintKey: 'chat.mode.educationHint' },
  { id: 'work', labelKey: 'chat.mode.work', hintKey: 'chat.mode.workHint' },
];

export function ModeToggle({ mode, onChange, disabled = false }: Props) {
  const { t } = useTranslation();
  return (
    <div className="seg" role="radiogroup" aria-label={t('chat.mode.label')}>
      {MODES.map((m) => {
        const active = mode === m.id;
        return (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={active}
            className={clsx(active && 'on')}
            disabled={disabled}
            title={t(m.hintKey)}
            onClick={() => {
              if (!active) onChange(m.id);
            }}
          >
            {t(m.labelKey)}
          </button>
        );
      })}
    </div>
  );
}
