// 입력 컴포저 — textarea + 전송/중지. Enter 전송, Shift+Enter 줄바꿈.
// Day 5 Phase 4-B: AttachmentTray 통합 + 이미지/파일 미리보기.

import { useEffect, useRef, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Square, AtSign, X } from 'lucide-react';
import type { AttachmentSlot } from '@/types/chat';
import { useChatStore } from '@store/chat';
import { useSearchStore, type PaletteItem } from '@store/search';
import { AttachmentTray } from './AttachmentTray';
import { ImagePreview } from './ImagePreview';
import { AttachmentPreview } from './AttachmentPreview';
import { VoiceButton } from './VoiceButton';

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
  const { t, i18n } = useTranslation();
  const [text, setText] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);

  // v4.7 C-1 — i18n UI 언어(`ajin-lang`)를 Web Speech 언어 코드로 매핑.
  // 추가 옵션: ko-KR / en-US 외 언어는 ko-KR fallback.
  const sttLang: 'ko-KR' | 'en-US' = useMemo(() => {
    const raw = (i18n.language || '').toLowerCase();
    return raw.startsWith('en') ? 'en-US' : 'ko-KR';
  }, [i18n.language]);

  const handleVoiceCommit = (finalText: string) => {
    if (!finalText) return;
    setText((prev) => (prev.trim() ? `${prev.trim()} ${finalText}` : finalText));
    // 포커스를 textarea 로 이동하여 사용자가 즉시 편집/전송 가능
    requestAnimationFrame(() => taRef.current?.focus());
  };

  // v4.7 Sprint 2 P0 (축 ①) — InputComposer "/" → CommandPalette overlay.
  const references = useChatStore((s) => s.references);
  const addReference = useChatStore((s) => s.addReference);
  const removeReference = useChatStore((s) => s.removeReference);
  const openPalette = useSearchStore((s) => s.openPalette);

  /** Palette 결과 클릭 시 — textarea 에 @<title> 토큰 삽입 + references 배열 추가. */
  const handleReference = (item: PaletteItem) => {
    addReference({ kind: item.kind, id: item.id, title: item.title });
    setText((prev) => {
      const token = `@${item.title}`;
      const trimmed = prev.trim();
      return trimmed ? `${trimmed} ${token} ` : `${token} `;
    });
    requestAnimationFrame(() => taRef.current?.focus());
  };

  /** "/" 입력 가로채기:
   *  - textarea 가 비어 있을 때 첫 글자 "/" → palette 오픈 (chat-overlay 또는 vision-search).
   *  - 이미지 첨부 상태면 vision-search 모드.
   */
  const handleSlashTrigger = (e: React.KeyboardEvent<HTMLTextAreaElement>): boolean => {
    if (e.key !== '/') return false;
    if (text.length !== 0) return false;
    // 이미지 첨부 시 vision-search 모드, 그 외에는 chat-overlay
    const isImage = attachment?.kind === 'image';
    e.preventDefault();
    openPalette({
      mode: isImage ? 'vision-search' : 'chat-overlay',
      onSelect: handleReference,
      image: isImage ? attachment?.file ?? null : null,
    });
    return true;
  };

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
    if (handleSlashTrigger(e)) return;
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="composer-wrap">
      {references.length > 0 && (
        <div
          className="composer-references"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            padding: '6px 8px',
          }}
          aria-label="인용된 검색 항목"
        >
          {references.map((r) => (
            <span
              key={r.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: 8,
                fontSize: 12,
                background: 'color-mix(in oklab, var(--hud-primary) 12%, transparent)',
                color: 'var(--hud-primary)',
                border: '1px solid color-mix(in oklab, var(--hud-primary) 24%, transparent)',
              }}
            >
              <AtSign size={11} strokeWidth={2} />
              {r.title}
              <button
                type="button"
                onClick={() => removeReference(r.id)}
                aria-label={`${r.title} 인용 제거`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  marginLeft: 2,
                  color: 'inherit',
                }}
              >
                <X size={11} strokeWidth={2} />
              </button>
            </span>
          ))}
        </div>
      )}
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
        <VoiceButton disabled={isStreaming} lang={sttLang} onCommit={handleVoiceCommit} />
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
