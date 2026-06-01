// 스트리밍 상태 인디케이터 — "응답 생성 중..." 또는 "Gemini → Ollama 폴백 중".

import { useTranslation } from 'react-i18next';
import type { SSEMeta } from '@hooks/useSSE';

interface Props {
  isStreaming: boolean;
  meta: SSEMeta;
  errorMessage?: string | null;
}

const PROVIDER_KEY: Record<string, string> = {
  gemini: 'chat.provider.gemini',
  ollama: 'chat.provider.ollama',
  lm_studio: 'chat.provider.lm_studio',
};

function providerLabel(t: (k: string) => string, p: string | undefined): string {
  if (!p) return '';
  const k = PROVIDER_KEY[p];
  return k ? t(k) : p;
}

export function StreamStatus({ isStreaming, meta, errorMessage }: Props) {
  const { t } = useTranslation();

  if (errorMessage) {
    return (
      <div className="chat-room-foot" role="status">
        <span style={{ color: 'var(--hud-red)' }}>● {t('chat.status.error')}</span>
        <span style={{ color: 'var(--hud-text-dim)' }}>{errorMessage}</span>
      </div>
    );
  }

  if (!isStreaming && !meta.provider && !meta.fallbackFrom) return null;

  const fallbackFrom = meta.fallbackFrom ?? null;
  const currentProvider = meta.finalProvider ?? meta.provider;

  return (
    <div className="chat-room-foot" role="status" aria-live="polite">
      {isStreaming ? (
        <span style={{ color: 'var(--hud-primary)' }}>● {t('chat.status.streaming')}</span>
      ) : (
        meta.finalModel && (
          <span style={{ color: 'var(--hud-green)' }}>
            ● {t('chat.status.done', { model: meta.finalModel })}
          </span>
        )
      )}
      {fallbackFrom && currentProvider && (
        <span style={{ color: 'var(--hud-orange)' }}>
          ⚡{' '}
          {t('chat.status.fallback', {
            from: providerLabel(t, fallbackFrom),
            to: providerLabel(t, currentProvider),
          })}
        </span>
      )}
      {!fallbackFrom && currentProvider && isStreaming && (
        <span>
          <b>{providerLabel(t, currentProvider)}</b>
          {meta.model && <span style={{ marginLeft: 8 }}>{meta.model}</span>}
        </span>
      )}
      {meta.ttftMs && <span>TTFT {Math.round(meta.ttftMs)}ms</span>}
    </div>
  );
}
