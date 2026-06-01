// useHotkeys — 전역 키보드 단축키 훅.
// W5 산출물: ⌘K / Ctrl+K 같은 시스템 단축키를 가볍게 등록.
// 입력 필드(input/textarea/contentEditable) 위에서는 기본 비활성, allowInInput 으로 명시 허용.

import { useEffect } from 'react';

interface HotkeyOptions {
  /** 'meta+k' / 'ctrl+k' / 'meta+/' 같은 키 시퀀스. + 로 구분. 키는 소문자. */
  combo: string;
  /** 입력 필드 위에서도 동작시키려면 true. 기본 false. */
  allowInInput?: boolean;
  /** 비활성화 토글 — 모달 열림 등 상황별 끄기. */
  enabled?: boolean;
}

function parseCombo(combo: string): {
  key: string;
  ctrl: boolean;
  meta: boolean;
  shift: boolean;
  alt: boolean;
} {
  const parts = combo.toLowerCase().split('+');
  const key = parts.pop() ?? '';
  const set = new Set(parts);
  return {
    key,
    ctrl: set.has('ctrl'),
    meta: set.has('meta') || set.has('cmd') || set.has('⌘'),
    shift: set.has('shift'),
    alt: set.has('alt') || set.has('option'),
  };
}

function isInputTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useHotkey(handler: () => void, options: HotkeyOptions): void {
  const { combo, allowInInput = false, enabled = true } = options;

  useEffect(() => {
    if (!enabled) return;
    const spec = parseCombo(combo);

    const listener = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== spec.key) return;
      if (spec.ctrl && !e.ctrlKey) return;
      if (spec.meta && !e.metaKey) return;
      if (spec.shift && !e.shiftKey) return;
      if (spec.alt && !e.altKey) return;
      // meta/ctrl 둘 중 하나만 명시한 경우 — 다른 모디파이어는 OS 차이 흡수
      if (!spec.ctrl && !spec.meta) {
        if (e.ctrlKey || e.metaKey) return;
      }
      if (!allowInInput && isInputTarget(e.target)) return;
      e.preventDefault();
      handler();
    };

    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [combo, allowInInput, enabled, handler]);
}
