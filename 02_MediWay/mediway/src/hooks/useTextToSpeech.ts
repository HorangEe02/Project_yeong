import { useCallback, useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';

/**
 * TTS(SpeechSynthesis) 훅 — v2 §4.2 축소 스코프: 지도 길찾기 전용.
 *
 * 설계 원칙:
 * - 브라우저 미지원 시 `supported=false` → 조용히 skip (시각 알림 fallback 책임은 consumer)
 * - iOS Safari 자동재생 정책: 최초 speak 호출은 반드시 사용자 gesture 내에서
 *   (버튼 onClick 등). 이 훅은 그것을 강제할 수 없으므로 consumer가 주의.
 * - 전역 TTS·Cloud TTS 서버 백업은 의도적으로 Drop (v2 §4.2)
 * - 사용자 설정 `/users/{uid}/preferences/tts = { enabled, rate? }` 기반
 *
 * 사용:
 * ```tsx
 * const tts = useTextToSpeech();
 * if (tts.supported && tts.enabled) {
 *   <button onClick={() => tts.speak('다음: 엘리베이터에서 좌회전 15미터')}>
 *     음성 안내 시작
 *   </button>
 * }
 * ```
 */
export interface UseTTSOptions {
  /** 0.5 ~ 2.0 (default: 사용자 preference 또는 1.0) */
  rate?: number;
  /** 0 ~ 2 (default: 1) */
  pitch?: number;
  /** 'ko-KR' 기본. voice가 있을 때는 voice.lang 우선 */
  lang?: string;
}

export interface UseTextToSpeechResult {
  /** 브라우저가 SpeechSynthesis API 지원 여부 */
  supported: boolean;
  /** 지원 + 사용자 opt-in AND */
  enabled: boolean;
  /** 발화. 미지원·미허락 시 no-op */
  speak: (text: string, opts?: UseTTSOptions) => void;
  /** 발화 큐 flush */
  cancel: () => void;
}

function isSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.speechSynthesis !== 'undefined' &&
    typeof window.SpeechSynthesisUtterance !== 'undefined'
  );
}

/** 한국어 voice 우선 선택 (iOS Yuna, Android ko-KR). 없으면 null. */
export function pickKoreanVoice(
  voices: SpeechSynthesisVoice[],
): SpeechSynthesisVoice | null {
  return (
    voices.find((v) => v.lang === 'ko-KR') ??
    voices.find((v) => v.lang.toLowerCase().startsWith('ko')) ??
    null
  );
}

export function useTextToSpeech(): UseTextToSpeechResult {
  const profile = useAuthStore((s) => s.profile);
  const userPref = profile?.preferences?.tts;
  const userEnabled = Boolean(userPref?.enabled);
  const userRate = typeof userPref?.rate === 'number' ? userPref.rate : 1.0;

  const supported = isSupported();
  const enabled = supported && userEnabled;

  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);

  useEffect(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const pick = () => {
      setVoice(pickKoreanVoice(synth.getVoices()));
    };
    pick();
    // voices는 브라우저 별로 비동기 로드 — 이벤트로 재시도
    synth.addEventListener?.('voiceschanged', pick);
    return () => {
      synth.removeEventListener?.('voiceschanged', pick);
    };
  }, [supported]);

  const cancel = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);

  const speak = useCallback(
    (text: string, opts: UseTTSOptions = {}) => {
      if (!enabled) return;
      const trimmed = text.trim();
      if (!trimmed) return;
      const utter = new window.SpeechSynthesisUtterance(trimmed);
      if (voice) utter.voice = voice;
      utter.lang = opts.lang ?? voice?.lang ?? 'ko-KR';
      utter.rate = clampRate(opts.rate ?? userRate);
      utter.pitch = opts.pitch ?? 1;
      // 이전 발화 중단 — 경유지 전환 시 말이 겹치지 않도록
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utter);
    },
    [enabled, voice, userRate],
  );

  return { supported, enabled, speak, cancel };
}

function clampRate(rate: number): number {
  if (!Number.isFinite(rate)) return 1;
  return Math.max(0.5, Math.min(2, rate));
}
