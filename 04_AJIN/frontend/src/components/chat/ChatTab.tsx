// Day 5++.4 — CHAT 탭 (메인 2-Tab 의 첫 번째 탭).
// 채팅 풀화면 — 트래픽 라이트 / 외곽선 헤더 / sticky QuickPrompts / 모드 토글 모두 제거 (시연 polish).

import { useChatStore } from '@store/chat';
import { MessageList } from './MessageList';
import { InputComposer } from './InputComposer';
import { StreamStatus } from './StreamStatus';
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

export function ChatTab({
  isStreaming,
  attachment,
  meta,
  errorMessage,
  onSend,
  onStop,
  onAttachImage,
  onAttachFile,
  onClearAttachment,
}: Props) {
  const messages = useChatStore((s) => s.messages);
  const activeMessageId = useChatStore((s) => s.activeMessageId);

  return (
    <div className="chat-tab">
      <div className="chat-tab__room">
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          activeMessageId={activeMessageId}
          onPickExample={onSend}
        />

        <StreamStatus
          isStreaming={isStreaming}
          meta={meta}
          errorMessage={errorMessage}
        />
      </div>

      <div className="chat-tab__composer">
        <InputComposer
          isStreaming={isStreaming}
          attachment={attachment}
          onSend={onSend}
          onStop={onStop}
          onAttachImage={onAttachImage}
          onAttachFile={onAttachFile}
          onClearAttachment={onClearAttachment}
        />
      </div>
    </div>
  );
}
