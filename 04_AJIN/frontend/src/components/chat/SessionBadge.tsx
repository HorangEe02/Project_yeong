// Day 5++ — 세션 ID + LIVE 배지 (DAY5_PLUS_HUD_PLAN Section 7).
// 시안: 세션 #A47-2026 [● LIVE]

import { useTranslation } from 'react-i18next';

interface Props {
  sessionId: string;
  isLive: boolean;
}

export function SessionBadge({ sessionId, isLive }: Props) {
  const { t } = useTranslation();
  return (
    <div className="session-badge" data-live={isLive ? 'true' : 'false'}>
      <span className="label-en">{t('chat.session.label_en')}</span>
      <span className="session-badge__id">#{sessionId}</span>
      <span className="session-badge__state" data-live={isLive ? 'true' : 'false'}>
        <span className="dot" aria-hidden="true" />
        <span>{isLive ? t('chat.session.live') : t('chat.session.idle')}</span>
      </span>
    </div>
  );
}
