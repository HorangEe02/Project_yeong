import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

const useSeniorModeMock = vi.fn();
vi.mock('@/hooks/useSeniorMode', () => ({
  useSeniorMode: () => useSeniorModeMock(),
}));

import { useSeniorCopy, listSeniorCopyKeys } from '../useSeniorCopy';

beforeEach(() => {
  useSeniorModeMock.mockReset();
});

function setSenior(enabled: boolean) {
  useSeniorModeMock.mockReturnValue({
    enabled,
    pending: false,
    toggle: vi.fn(),
    setEnabled: vi.fn(),
  });
}

describe('useSeniorCopy', () => {
  it('senior OFF — 항상 fallback 반환 (사전 키 존재해도)', () => {
    setSenior(false);
    const { result } = renderHook(() => useSeniorCopy());
    const copy = result.current;
    expect(copy('widget.schedule.title', '오늘 일정')).toBe('오늘 일정');
    expect(copy('action.cancel', '취소')).toBe('취소');
  });

  it('senior ON + 사전 hit — 치환', () => {
    setSenior(true);
    const { result } = renderHook(() => useSeniorCopy());
    const copy = result.current;
    expect(copy('action.cancel', '취소')).toBe('그만두기');
    expect(copy('widget.wait.waiting', '대기 중')).toBe('기다리는 중이에요');
  });

  it('senior ON + 사전 miss — fallback 반환', () => {
    setSenior(true);
    const { result } = renderHook(() => useSeniorCopy());
    const copy = result.current;
    expect(copy('nonexistent.key', '원문 그대로')).toBe('원문 그대로');
  });

  it('senior ON + 의료 전문용어는 등록 안 돼있어 원문 유지', () => {
    setSenior(true);
    const { result } = renderHook(() => useSeniorCopy());
    const copy = result.current;
    // 진단명·처방·약품명 등은 사전에 없어야 함 (의료 정확성 보존)
    expect(copy('diagnosis.name', '폐렴')).toBe('폐렴');
    expect(copy('prescription.item', '아목시실린 500mg')).toBe(
      '아목시실린 500mg',
    );
  });
});

describe('listSeniorCopyKeys', () => {
  it('meta ($schema, $description)는 제외', () => {
    const keys = listSeniorCopyKeys();
    expect(keys.every((k) => !k.startsWith('$'))).toBe(true);
    expect(keys.length).toBeGreaterThan(0);
  });

  it('필수 카테고리 키들이 포함', () => {
    const keys = listSeniorCopyKeys();
    const categories = ['widget.', 'tab.', 'action.', 'status.', 'empty.'];
    for (const prefix of categories) {
      expect(keys.some((k) => k.startsWith(prefix))).toBe(true);
    }
  });
});
