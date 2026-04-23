import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

const useAuthStoreMock = vi.fn();
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(sel: (s: unknown) => T) => sel(useAuthStoreMock()),
}));

// speechSynthesis + SpeechSynthesisUtterance 모킹
interface MockUtterance {
  text: string;
  lang: string;
  rate: number;
  pitch: number;
  voice: SpeechSynthesisVoice | null;
}

const synthSpeak = vi.fn();
const synthCancel = vi.fn();
const synthGetVoices = vi.fn();
const synthAddListener = vi.fn();
const synthRemoveListener = vi.fn();

const originalSynth = globalThis.speechSynthesis;
const originalUtter = (globalThis as Record<string, unknown>)
  .SpeechSynthesisUtterance;

function setupGlobals() {
  (globalThis as Record<string, unknown>).speechSynthesis = {
    speak: synthSpeak,
    cancel: synthCancel,
    getVoices: synthGetVoices,
    addEventListener: synthAddListener,
    removeEventListener: synthRemoveListener,
  };
  class MockUtt {
    text: string;
    lang = '';
    rate = 1;
    pitch = 1;
    voice: SpeechSynthesisVoice | null = null;
    constructor(text: string) {
      this.text = text;
    }
  }
  (globalThis as Record<string, unknown>).SpeechSynthesisUtterance = MockUtt;
}

function teardownGlobals() {
  (globalThis as Record<string, unknown>).speechSynthesis = originalSynth;
  (globalThis as Record<string, unknown>).SpeechSynthesisUtterance =
    originalUtter;
}

function setProfile(tts?: { enabled: boolean; rate?: number } | null) {
  useAuthStoreMock.mockReturnValue({
    profile: tts === null ? null : { preferences: { tts } },
  });
}

const koVoice = {
  lang: 'ko-KR',
  name: 'Yuna',
  default: true,
  localService: true,
  voiceURI: 'ko',
} as SpeechSynthesisVoice;

const enVoice = {
  lang: 'en-US',
  name: 'Samantha',
  default: false,
  localService: true,
  voiceURI: 'en',
} as SpeechSynthesisVoice;

beforeEach(() => {
  synthSpeak.mockReset();
  synthCancel.mockReset();
  synthGetVoices.mockReset().mockReturnValue([koVoice, enVoice]);
  synthAddListener.mockReset();
  synthRemoveListener.mockReset();
  useAuthStoreMock.mockReset();
  setupGlobals();
});

afterEach(() => {
  teardownGlobals();
});

import { useTextToSpeech, pickKoreanVoice } from '../useTextToSpeech';

describe('pickKoreanVoice', () => {
  it('ko-KR voice 우선', () => {
    expect(pickKoreanVoice([enVoice, koVoice])?.lang).toBe('ko-KR');
  });

  it('ko-KR 없으면 ko 계열 prefix 매치', () => {
    const koKP = { ...koVoice, lang: 'ko' } as SpeechSynthesisVoice;
    expect(pickKoreanVoice([enVoice, koKP])?.lang).toBe('ko');
  });

  it('한국어 없음 → null', () => {
    expect(pickKoreanVoice([enVoice])).toBeNull();
  });
});

describe('useTextToSpeech', () => {
  it('브라우저 지원 + 사용자 OFF → enabled=false, speak no-op', () => {
    setProfile({ enabled: false });
    const { result } = renderHook(() => useTextToSpeech());
    expect(result.current.supported).toBe(true);
    expect(result.current.enabled).toBe(false);
    act(() => result.current.speak('테스트'));
    expect(synthSpeak).not.toHaveBeenCalled();
  });

  it('사용자 ON + 한국어 voice 존재 → speak 호출 + utterance voice 세팅', () => {
    setProfile({ enabled: true, rate: 1.2 });
    const { result } = renderHook(() => useTextToSpeech());
    expect(result.current.enabled).toBe(true);
    act(() => result.current.speak('다음: 엘리베이터에서 좌회전'));
    expect(synthCancel).toHaveBeenCalled(); // 이전 발화 flush
    expect(synthSpeak).toHaveBeenCalledOnce();
    const utter = synthSpeak.mock.calls[0][0] as MockUtterance;
    expect(utter.text).toBe('다음: 엘리베이터에서 좌회전');
    expect(utter.voice?.lang).toBe('ko-KR');
    expect(utter.rate).toBe(1.2);
  });

  it('빈 문자열 / 공백만 → speak 호출 안 함', () => {
    setProfile({ enabled: true });
    const { result } = renderHook(() => useTextToSpeech());
    act(() => result.current.speak('   '));
    act(() => result.current.speak(''));
    expect(synthSpeak).not.toHaveBeenCalled();
  });

  it('rate 0.3 → 0.5로 clamp, 3.0 → 2.0으로 clamp', () => {
    setProfile({ enabled: true });
    const { result } = renderHook(() => useTextToSpeech());
    act(() => result.current.speak('느리게', { rate: 0.3 }));
    expect(
      (synthSpeak.mock.calls[0][0] as MockUtterance).rate,
    ).toBe(0.5);
    act(() => result.current.speak('빠르게', { rate: 3 }));
    expect(
      (synthSpeak.mock.calls[1][0] as MockUtterance).rate,
    ).toBe(2);
  });

  it('cancel() 호출 → synth.cancel', () => {
    setProfile({ enabled: true });
    const { result } = renderHook(() => useTextToSpeech());
    act(() => result.current.cancel());
    expect(synthCancel).toHaveBeenCalled();
  });

  it('voiceschanged 이벤트 리스너 마운트 시 등록 + 언마운트 시 해제', () => {
    setProfile({ enabled: true });
    const { unmount } = renderHook(() => useTextToSpeech());
    expect(synthAddListener).toHaveBeenCalledWith(
      'voiceschanged',
      expect.any(Function),
    );
    unmount();
    expect(synthRemoveListener).toHaveBeenCalledWith(
      'voiceschanged',
      expect.any(Function),
    );
  });

  it('profile null (로그아웃) → enabled=false', () => {
    setProfile(null);
    const { result } = renderHook(() => useTextToSpeech());
    expect(result.current.enabled).toBe(false);
  });
});
