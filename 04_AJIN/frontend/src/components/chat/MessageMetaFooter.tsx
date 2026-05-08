// Day 5++ — 메시지 footer 메타 (DAY5_PLUS_HUD_PLAN Section 6-2).
// 토큰 X/Y · 컨텍스트 N턴 · 모델 M · 의도 분류 5ms

import { useTranslation } from 'react-i18next';
import { useChatStore } from '@store/chat';
import type { ChatMessage } from '@/types/chat';

interface Props {
  message: ChatMessage;
}

const TOKEN_BUDGET_MAP = {
  education: 3000,
  work: 2000,
} as const;

/** 모델명 라벨로 정규화 — `gemini-2.5-pro` → `GEMINI-2.5-PRO`, `qwen3.5:9b` → `QWEN-3.5-9B`. */
function formatModelLabel(model?: string, finalModel?: string): string {
  const m = finalModel || model;
  if (!m) return 'AUTO';
  // qwen3.5:9b → QWEN-3.5-9B
  return m
    .replace(/:/g, '-')
    .replace(/\./g, '.')
    .toUpperCase();
}

export function MessageMetaFooter({ message }: Props) {
  const { t } = useTranslation();
  const mode = useChatStore((s) => s.mode);
  const intentMs = useChatStore((s) => s.intentMs);
  const messages = useChatStore((s) => s.messages);

  const tokenBudget = TOKEN_BUDGET_MAP[mode];
  const tokens = message.meta?.totalTokens ?? 0;
  // 컨텍스트 턴 수 — user/assistant 페어 기준 (메시지 / 2 내림).
  const historyTurns = Math.max(1, Math.floor(messages.length / 2));
  const modelLabel = formatModelLabel(message.meta?.model, message.meta?.finalModel);
  // mock — Day 13 에 실 TF-IDF 분류기 연결 시 교체.
  const intent = typeof intentMs === 'number' ? intentMs : 5;

  return (
    <div className="message-meta-footer" role="contentinfo">
      <span className="message-meta-footer__item">
        {t('chat.meta.tokens', { n: tokens, max: tokenBudget })}
      </span>
      <span className="message-meta-footer__sep">·</span>
      <span className="message-meta-footer__item">
        {t('chat.meta.context', { n: historyTurns })}
      </span>
      <span className="message-meta-footer__sep">·</span>
      <span className="message-meta-footer__item">
        {t('chat.meta.model', { name: modelLabel })}
      </span>
      <span className="message-meta-footer__sep">·</span>
      <span className="message-meta-footer__item">
        {t('chat.meta.intent', { n: intent })}
      </span>
    </div>
  );
}
