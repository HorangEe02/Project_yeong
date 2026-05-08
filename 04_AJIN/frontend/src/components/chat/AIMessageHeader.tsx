// Day 5++ — AI 메시지 헤더 (DAY5_PLUS_HUD_PLAN Section 6-1).
// AI [SOP_GUIDE] 신뢰도 ─ Xms HH:MM
// 카테고리 별 배지: SOP_GUIDE / SCENARIO / ACTION / CHAT / VISION

import { useTranslation } from 'react-i18next';
import type { ChatMessage, MessageCategory } from '@/types/chat';

interface Props {
  message: ChatMessage;
}

const CATEGORY_KEYS: Record<MessageCategory, string> = {
  sop: 'chat.ai.label.sop',
  scenario: 'chat.ai.label.scenario',
  action: 'chat.ai.label.action',
  chat: 'chat.ai.label.chat',
  vision: 'chat.ai.label.vision',
};

function fmtTime(ts: number): string {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

function resolveCategory(message: ChatMessage): MessageCategory {
  // 1) message.meta.category (백엔드 echo 또는 store 분기 시 부착)
  if (message.meta?.category) return message.meta.category;
  // 2) source 로부터 추정 (Day 5 흐름과 호환)
  if (message.source === 'scenario') return 'scenario';
  if (message.source === 'action') return 'action';
  // 3) 기본 — chat
  return 'chat';
}

export function AIMessageHeader({ message }: Props) {
  const { t } = useTranslation();
  const category = resolveCategory(message);
  const labelKey = CATEGORY_KEYS[category];
  const ttftMs = message.meta?.ttftMs;
  const isZeroLLM = message.source === 'scenario' || message.source === 'action';
  const time = fmtTime(message.createdAt);

  return (
    <div className="ai-message-header">
      <span className="ai-message-header__src">AI</span>
      <span className="ai-message-header__badge">[{t(labelKey)}]</span>
      {isZeroLLM && (
        <span className="ai-message-header__zero-llm" title="LLM 호출 0회">
          ●
        </span>
      )}
      <span className="ai-message-header__sep">─</span>
      <span className="ai-message-header__ttft">
        {typeof ttftMs === 'number' ? `${ttftMs}ms` : '—'}
      </span>
      <span className="ai-message-header__sep">·</span>
      <span className="ai-message-header__time">{time}</span>
    </div>
  );
}
