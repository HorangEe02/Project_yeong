// v4.7 C-1 — 브라우저 내장 Web Speech API 래퍼 훅.
// SpeechRecognition || webkitSpeechRecognition 분기, ko-KR / en-US 언어 토글.
// 인터페이스 안정성을 위해 후속 옵션 B(Whisper.cpp WASM) / C(서버 Whisper)에서도 동일 시그니처 유지.

import { useCallback, useEffect, useRef, useState } from 'react';

/** Web Speech API ErrorEvent.error 값 → 사용자 친화 i18n 키 매핑. */
type SttErrorCode = 'not-allowed' | 'no-speech' | 'network' | 'audio-capture' | 'service-not-allowed' | 'aborted' | 'language-not-supported' | 'unknown';

export interface SpeechToTextState {
  transcript: string;       // 확정(final) 누적 결과
  interim: string;          // 현재 인식 중인 임시 결과
  isListening: boolean;
  error: SttErrorCode | null;
  isSupported: boolean;
}

export interface SpeechToTextControls {
  start: (lang?: 'ko-KR' | 'en-US') => void;
  stop: () => void;
  reset: () => void;
}

export type UseSpeechToTextReturn = SpeechToTextState & SpeechToTextControls;

interface SpeechRecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResult>;
}

interface SpeechRecognitionErrorEventLike {
  error: string;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

function mapErrorCode(raw: string): SttErrorCode {
  switch (raw) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'not-allowed';
    case 'no-speech':
      return 'no-speech';
    case 'network':
      return 'network';
    case 'audio-capture':
      return 'audio-capture';
    case 'aborted':
      return 'aborted';
    case 'language-not-supported':
      return 'language-not-supported';
    default:
      return 'unknown';
  }
}

/**
 * 브라우저 음성-텍스트 인식.
 *
 * 사용법:
 *   const { transcript, interim, isListening, start, stop, isSupported, error } = useSpeechToText();
 *   start('ko-KR') 호출 → onresult 콜백이 transcript/interim 분리 누적
 *   isListening=true 중에는 사용자가 중지 가능 (stop), 자동 종료(onend)도 처리
 */
export function useSpeechToText(): UseSpeechToTextReturn {
  const Ctor = getRecognitionCtor();
  const isSupported = Ctor !== null;

  const [transcript, setTranscript] = useState('');
  const [interim, setInterim] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<SttErrorCode | null>(null);

  const recogRef = useRef<SpeechRecognitionLike | null>(null);

  // 언마운트 시 abort
  useEffect(() => {
    return () => {
      try {
        recogRef.current?.abort();
      } catch {
        /* noop */
      }
    };
  }, []);

  const reset = useCallback(() => {
    setTranscript('');
    setInterim('');
    setError(null);
  }, []);

  const start = useCallback(
    (lang: 'ko-KR' | 'en-US' = 'ko-KR') => {
      if (!Ctor) {
        setError('unknown');
        return;
      }
      // 이미 진행 중이면 재시작 (abort → start)
      try {
        recogRef.current?.abort();
      } catch {
        /* noop */
      }

      const recog = new Ctor();
      recog.continuous = true;
      recog.interimResults = true;
      recog.lang = lang;

      recog.onstart = () => {
        setIsListening(true);
        setError(null);
      };
      recog.onresult = (e) => {
        let finalDelta = '';
        let interimText = '';
        for (let i = e.resultIndex; i < e.results.length; i += 1) {
          const r = e.results[i];
          if (r.isFinal) finalDelta += r[0].transcript;
          else interimText += r[0].transcript;
        }
        if (finalDelta) {
          setTranscript((prev) => (prev ? prev + ' ' : '') + finalDelta.trim());
        }
        setInterim(interimText);
      };
      recog.onerror = (e) => {
        setError(mapErrorCode(e.error));
        setIsListening(false);
      };
      recog.onend = () => {
        setIsListening(false);
        setInterim('');
      };

      recogRef.current = recog;
      try {
        recog.start();
      } catch {
        // 같은 인스턴스 재시작 시 InvalidStateError 발생할 수 있음 — 다음 tick 재시도 안 함, 에러만 표기
        setError('unknown');
        setIsListening(false);
      }
    },
    [Ctor],
  );

  const stop = useCallback(() => {
    try {
      recogRef.current?.stop();
    } catch {
      /* noop */
    }
  }, []);

  return {
    transcript,
    interim,
    isListening,
    error,
    isSupported,
    start,
    stop,
    reset,
  };
}
