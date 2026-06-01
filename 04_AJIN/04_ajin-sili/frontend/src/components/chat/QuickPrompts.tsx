// Day 5++ — 좌측 컬럼 하단 50% — 자주 쓰는 질문 chip 모음 (DAY5_PLUS_HUD_PLAN Section 5-bis).
// chip 클릭 → onSend(promptText) 호출 → 시나리오/액션 매처 → LLM 호출 0회 즉시 응답.

import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import {
  DEFAULT_QUICK_PROMPTS,
  type QuickPrompt,
  type QuickPromptCategory,
} from '@/types/chat';

interface Props {
  prompts?: QuickPrompt[];
  isStreaming: boolean;
  onSend: (text: string) => void;
  /** Day 5++.3 — true 시 작은 chips · 가로 스크롤 (CHAT 탭 입력창 위 sticky 용). */
  compact?: boolean;
}

const CATEGORY_LABEL: Record<QuickPromptCategory, string> = {
  scenario: 'SCENARIO',
  action: 'ACTION',
  sop: 'SOP',
  general: 'CHAT',
};

export function QuickPrompts({
  prompts = DEFAULT_QUICK_PROMPTS,
  isStreaming,
  onSend,
  compact = false,
}: Props) {
  const { t } = useTranslation();

  const handleClick = (p: QuickPrompt) => {
    if (isStreaming) return;
    // autoSend 기본 true — 시연 가속 (즉시 전송 → 시나리오 매처 0 LLM 응답)
    onSend(p.promptText);
  };

  return (
    <section
      className={clsx('quick-prompts', { 'quick-prompts--compact': compact })}
      aria-label={`${t('chat.quick.title')} · ${t('chat.quick.subtitle')}`}
    >
      {!compact && (
        <header className="quick-prompts__header">
          <div className="quick-prompts__title">
            <span className="quick-prompts__en">{t('chat.quick.title')}</span>
            <span className="quick-prompts__ko">· {t('chat.quick.subtitle')}</span>
          </div>
          <span className="quick-prompts__hint">{t('chat.quick.hint')}</span>
        </header>
      )}
      <ul className="quick-prompts__list">
        {prompts.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              className="quick-prompts__chip"
              onClick={() => handleClick(p)}
              disabled={isStreaming}
              data-category={p.category}
              title={p.promptText}
            >
              <span className="quick-prompts__chip-cat">[{CATEGORY_LABEL[p.category]}]</span>
              <span>{p.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
