// 메시지 풍선 — user/assistant 역할별 스타일링 + markdown + ProviderBadge.
// Day 5: assistant 풍선에 ScenarioCard / DownloadActions / FeedbackActions 부착.
// Day 5++: AI 헤더 (AIMessageHeader) + 메시지 footer 메타 (MessageMetaFooter) 부착.

import clsx from 'clsx';
import { MarkdownRenderer } from '@components/ui/MarkdownRenderer';
import type { ChatMessage } from '@/types/chat';
import { ProviderBadge } from './ProviderBadge';
import { ScenarioCard } from './ScenarioCard';
import { DownloadActions } from './DownloadActions';
import { FeedbackActions } from './FeedbackActions';
import { AIMessageHeader } from './AIMessageHeader';
import { MessageMetaFooter } from './MessageMetaFooter';

interface Props {
  message: ChatMessage;
  /** 스트리밍 중인 어시스턴트 풍선이면 cursor 표시 */
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: Props) {
  const isUser = message.role === 'user';
  const isError = message.status === 'error';
  const isDone = message.status === 'done';
  const showCursor = !isUser && isStreaming && message.status === 'streaming';
  const errorText = message.meta?.error;
  const scenarioCard = message.meta?.scenarioCard;
  const isScenario = message.source === 'scenario' && scenarioCard;

  return (
    <div
      className={clsx(
        'bubble',
        isUser ? 'user' : 'ai',
        isError && 'error',
        message.source && `source-${message.source}`,
      )}
    >
      {!isUser && (
        <>
          {/* Day 5++ — v2 시안 패턴 헤더: AI [SOP_GUIDE] 신뢰도 ─ Xms HH:MM */}
          <AIMessageHeader message={message} />
          {/* Provider 폴백 표시 (Day 4 호환) — 헤더 우측 sub-line */}
          {(message.meta?.fallbackFrom || message.meta?.finalProvider) && (
            <div className="meta" style={{ marginBottom: 6 }}>
              <ProviderBadge meta={message.meta} />
            </div>
          )}
        </>
      )}

      <div className={clsx('body', showCursor && 'streaming-cursor')}>
        {isUser && message.meta?.imageUrl && message.meta.imageUrl !== 'pending' && (
          <div className="bubble-image">
            <img src={message.meta.imageUrl} alt="첨부 이미지" />
          </div>
        )}
        {isUser && message.meta?.fileName && (
          <div className="bubble-file" title={message.meta.fileName}>
            <span aria-hidden>📎</span> {message.meta.fileName}
          </div>
        )}
        {isScenario ? (
          <ScenarioCard card={scenarioCard} />
        ) : message.content ? (
          isUser ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
          ) : (
            <MarkdownRenderer content={message.content} variant="chat" />
          )
        ) : isError && errorText ? (
          <span style={{ color: 'var(--hud-red)' }}>{errorText}</span>
        ) : null}
      </div>

      {!isUser && isDone && message.content?.trim() && (
        <div className="bubble-footer">
          <DownloadActions content={message.content} filenameBase={`ajin-${message.id.slice(0, 8)}`} />
          <FeedbackActions messageId={message.id} />
          {/* Day 5++ — 토큰/컨텍스트/모델/의도 메타 */}
          <MessageMetaFooter message={message} />
        </div>
      )}
    </div>
  );
}
