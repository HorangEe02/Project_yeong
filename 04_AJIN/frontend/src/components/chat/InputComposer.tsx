// 입력 컴포저 — textarea + 전송/중지. Enter 전송, Shift+Enter 줄바꿈.
// Day 5 Phase 4-B: AttachmentTray 통합 + 이미지/파일 미리보기.

import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Square } from 'lucide-react';
import type { AttachmentSlot } from '@/types/chat';
import { AttachmentTray } from './AttachmentTray';
import { ImagePreview } from './ImagePreview';
import { AttachmentPreview } from './AttachmentPreview';

interface Props {
  isStreaming: boolean;
  attachment: AttachmentSlot | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onAttachImage: (file: File) => void;
  onAttachFile: (file: File) => void;
  onClearAttachment: () => void;
}

const MAX_INPUT_CHARS = 8000;

export function InputComposer({
  isStreaming,
  attachment,
  onSend,
  onStop,
  onAttachImage,
  onAttachFile,
  onClearAttachment,
}: Props) {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);

  // textarea 자동 리사이즈
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const trimmed = text.trim();
  // 첨부가 있으면 빈 텍스트도 허용 (백엔드 query 는 placeholder 로 보강)
  const hasContent = trimmed.length > 0 || attachment !== null;
  const canSend = !isStreaming && hasContent && trimmed.length <= MAX_INPUT_CHARS;

  const handleSend = () => {
    if (!canSend) return;
    const finalText = trimmed.length > 0
      ? trimmed
      : attachment?.kind === 'image'
        ? t('chat.vision.default_query')
        : t('chat.attachment.default_query');
    onSend(finalText);
    setText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="composer-wrap">
      {attachment && (
        <div className="composer-attachments">
          {attachment.kind === 'image' ? (
            <ImagePreview file={attachment.file} onRemove={onClearAttachment} />
          ) : (
            <AttachmentPreview file={attachment.file} onRemove={onClearAttachment} />
          )}
        </div>
      )}
      <div className="composer" role="group" aria-label="message composer">
        <AttachmentTray
          disabled={isStreaming}
          onAttachImage={onAttachImage}
          onAttachFile={onAttachFile}
        />
        <textarea
          ref={taRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.composer.placeholder')}
          rows={1}
          maxLength={MAX_INPUT_CHARS}
          disabled={isStreaming}
          aria-label={t('chat.composer.placeholder')}
        />
        {isStreaming ? (
          <button
            type="button"
            className="send"
            onClick={onStop}
            aria-label={t('chat.composer.stop')}
          >
            <Square size={14} strokeWidth={2.5} />
            <span style={{ marginLeft: 6 }}>{t('chat.composer.stop')}</span>
          </button>
        ) : (
          <button
            type="button"
            className="send"
            onClick={handleSend}
            disabled={!canSend}
            aria-label={t('chat.composer.send')}
          >
            <Send size={14} strokeWidth={2.5} />
            <span style={{ marginLeft: 6 }}>{t('chat.composer.send')}</span>
          </button>
        )}
      </div>
    </div>
  );
}
