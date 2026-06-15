// v4.7 C-1 — InputComposer 옆 음성 입력 버튼.
// useSpeechToText 훅을 컨슈머가 직접 보유하지 않도록 컴포넌트 내부 캡슐화.
// 녹음 종료 시 누적 transcript 를 onCommit 으로 한 번에 부모에 위임 (textarea append).

import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Mic, MicOff } from 'lucide-react';
import { useSpeechToText } from '@hooks/useSpeechToText';
import { useToastStore } from '@store/toast';

interface Props {
  disabled?: boolean;
  /** 'ko-KR' | 'en-US' — 부모(InputComposer)가 localStorage `ajin-lang` 으로부터 매핑해 전달. */
  lang: 'ko-KR' | 'en-US';
  /** 사용자가 stop 했거나 자동 종료된 시점에 최종 transcript 를 부모에 통보. */
  onCommit: (text: string) => void;
}

export function VoiceButton({ disabled, lang, onCommit }: Props) {
  const { t } = useTranslation();
  const { transcript, interim, isListening, error, isSupported, start, stop, reset } =
    useSpeechToText();
  const addToast = useToastStore.getState().addToast;
  const wasListening = useRef(false);

  // 녹음 종료 시점 (isListening true→false) 에 누적 transcript commit
  useEffect(() => {
    if (wasListening.current && !isListening) {
      if (transcript.trim()) {
        onCommit(transcript.trim());
      }
      reset();
    }
    wasListening.current = isListening;
  }, [isListening, transcript, onCommit, reset]);

  // 에러 토스트 (i18n)
  useEffect(() => {
    if (!error) return;
    const titleKey =
      error === 'not-allowed'
        ? 'chat.voice.error.permission'
        : error === 'no-speech'
          ? 'chat.voice.error.noSpeech'
          : error === 'network'
            ? 'chat.voice.error.network'
            : 'chat.voice.error.notSupported';
    addToast({ type: 'error', title: t(titleKey), message: '' });
  }, [error, addToast, t]);

  if (!isSupported) {
    // 미지원 브라우저는 버튼 자체를 숨김 (Safari iOS 등)
    return null;
  }

  const handleClick = () => {
    if (disabled) return;
    if (isListening) stop();
    else start(lang);
  };

  return (
    <button
      type="button"
      className={`voice-btn ${isListening ? 'voice-btn--listening' : ''}`}
      onClick={handleClick}
      disabled={disabled}
      aria-pressed={isListening}
      aria-label={isListening ? t('chat.voice.stop') : t('chat.voice.start')}
      title={isListening ? t('chat.voice.stop') : t('chat.voice.start')}
      style={{
        background: 'transparent',
        border: '1px solid var(--hud-border, #2a2a2a)',
        borderRadius: 6,
        padding: '6px 8px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        color: isListening ? 'var(--hud-red, #ef4444)' : 'var(--hud-text, #9ca3af)',
        position: 'relative',
      }}
    >
      {isListening ? (
        <>
          <MicOff size={14} strokeWidth={2.5} />
          <span
            style={{
              display: 'inline-block',
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--hud-red, #ef4444)',
              animation: 'voicePulse 1.2s ease-in-out infinite',
            }}
          />
          <span style={{ fontSize: 11 }}>{t('chat.voice.listening')}</span>
        </>
      ) : (
        <Mic size={14} strokeWidth={2.5} />
      )}
      {/* interim 결과 미니 토스트 (선택적) */}
      {isListening && interim && (
        <span
          aria-live="polite"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 4px)',
            left: 0,
            maxWidth: 280,
            padding: '4px 8px',
            background: 'var(--hud-bg, rgba(0,0,0,0.85))',
            border: '1px solid var(--hud-border, #2a2a2a)',
            borderRadius: 4,
            fontSize: 11,
            color: 'var(--hud-text-dim, #6b7280)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            pointerEvents: 'none',
          }}
        >
          {interim}
        </span>
      )}
      <style>{`
        @keyframes voicePulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.7); }
        }
      `}</style>
    </button>
  );
}
