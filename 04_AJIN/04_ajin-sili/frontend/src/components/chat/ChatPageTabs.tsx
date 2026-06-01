// Day 5++.3 — 메인 2-Tab (CHAT · 대화 / LEARN · 학습).
// 페이지 헤더 직하 배치. 디폴트 = chat. persist (ajin-ui).
// 시연 동선: LEARN 의 시나리오/SOP 카드 클릭 → CHAT 자동 전환 + 자동 전송.

import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import { useUIStore } from '@store/ui';
import { ChatTab } from './ChatTab';
import { LearnTab } from './LearnTab';
import type { AttachmentSlot } from '@/types/chat';
import type { SSEMeta } from '@hooks/useSSE';

interface Props {
  isStreaming: boolean;
  attachment: AttachmentSlot | null;
  meta: SSEMeta;
  errorMessage: string | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onAttachImage: (file: File) => void;
  onAttachFile: (file: File) => void;
  onClearAttachment: () => void;
}

export function ChatPageTabs(props: Props) {
  const { t } = useTranslation();
  const tab = useUIStore((s) => s.chatPageTab);
  const setTab = useUIStore((s) => s.setChatPageTab);

  return (
    <div className="chat-page-tabs">
      <nav role="tablist" className="chat-page-tabs__nav" aria-label={t('chat.title')}>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'chat'}
          className={clsx('chat-page-tabs__btn', {
            'chat-page-tabs__btn--active': tab === 'chat',
          })}
          onClick={() => setTab('chat')}
        >
          <span className="chat-page-tabs__dot" data-on={tab === 'chat'} aria-hidden />
          <span className="chat-page-tabs__label-en">{t('chat.pageTab.chat')}</span>
          <span className="chat-page-tabs__label-ko">{t('chat.pageTab.chatSub')}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'learn'}
          className={clsx('chat-page-tabs__btn', {
            'chat-page-tabs__btn--active': tab === 'learn',
          })}
          onClick={() => setTab('learn')}
        >
          <span className="chat-page-tabs__dot" data-on={tab === 'learn'} aria-hidden />
          <span className="chat-page-tabs__label-en">{t('chat.pageTab.learn')}</span>
          <span className="chat-page-tabs__label-ko">{t('chat.pageTab.learnSub')}</span>
        </button>
      </nav>
      <div className="chat-page-tabs__panel" role="tabpanel">
        {tab === 'chat' ? (
          <ChatTab {...props} />
        ) : (
          <LearnTab onSwitchToChat={() => setTab('chat')} onSend={props.onSend} />
        )}
      </div>
    </div>
  );
}
