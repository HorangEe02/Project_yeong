// 메시지 리스트 — auto-scroll + 빈 상태 + 스트리밍 마지막 풍선.

import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { ChatMessage } from '@/types/chat';
import { MessageBubble } from './MessageBubble';

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  activeMessageId: string | null;
  onPickExample?: (text: string) => void;
}

const EXAMPLE_KEYS = [
  'chat.empty.examples.0',
  'chat.empty.examples.1',
  'chat.empty.examples.2',
];

export function MessageList({ messages, isStreaming, activeMessageId, onPickExample }: Props) {
  const { t } = useTranslation();
  const endRef = useRef<HTMLDivElement>(null);

  // auto-scroll: 메시지 추가 또는 스트리밍 토큰 누적 시 하단 고정
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="chat-stream chat-empty" aria-live="polite">
        <div className="chat-empty-title">{t('chat.empty.title')}</div>
        <div className="chat-empty-examples">
          {EXAMPLE_KEYS.map((k) => {
            const text = t(k);
            return (
              <button
                key={k}
                type="button"
                className="chat-empty-chip"
                onClick={() => onPickExample?.(text)}
              >
                {text}
              </button>
            );
          })}
        </div>
        <div ref={endRef} />
      </div>
    );
  }

  return (
    <div className="chat-stream" aria-live="polite">
      {messages.map((m) => (
        <MessageBubble
          key={m.id}
          message={m}
          isStreaming={isStreaming && m.id === activeMessageId}
        />
      ))}
      <div ref={endRef} />
    </div>
  );
}
