// 메시지 풍선의 모델/공급자 인디케이터.
// 폴백이 발생했으면 "Gemini → Ollama" 형태로 노출 (시연 차별점).

import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import type { ChatMessageMeta } from '@/types/chat';

interface Props {
  meta: ChatMessageMeta | undefined;
  className?: string;
}

const PROVIDER_KEY: Record<string, string> = {
  gemini: 'chat.provider.gemini',
  ollama: 'chat.provider.ollama',
  lm_studio: 'chat.provider.lm_studio',
};

function providerLabel(t: (k: string) => string, provider: string | undefined): string {
  if (!provider) return '';
  const key = PROVIDER_KEY[provider];
  return key ? t(key) : provider;
}

export function ProviderBadge({ meta, className }: Props) {
  const { t } = useTranslation();
  if (!meta) return null;

  const provider = meta.finalProvider ?? meta.provider;
  const model = meta.finalModel ?? meta.model;
  const fallbackFrom = meta.fallbackFrom ?? null;

  if (!provider && !model && !fallbackFrom) return null;

  const fromLabel = providerLabel(t, fallbackFrom ?? undefined);
  const nowLabel = providerLabel(t, provider);

  const forcedLabel = meta.forcedProvider ? t('chat.model.forced_indicator') : '';

  return (
    <span className={clsx('provider-badge', className)} aria-label="provider">
      {fallbackFrom && fromLabel ? (
        <>
          <span className="provider-from">{fromLabel}</span>
          <span className="provider-arrow" aria-hidden>
            →
          </span>
          <span className="provider-now">{nowLabel}</span>
        </>
      ) : (
        nowLabel && <span className="provider-now">{nowLabel}</span>
      )}
      {model && <span className="provider-model">{model}</span>}
      {forcedLabel && <span className="provider-forced">{forcedLabel}</span>}
    </span>
  );
}
