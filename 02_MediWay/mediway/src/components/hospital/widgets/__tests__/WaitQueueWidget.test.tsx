import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import type { WaitEntryIndex } from '@/types/wait-queue';

// 훅 모킹 — useHospital은 slug만 사용.
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => ({
    slug: 'demo',
    hospital: { features: {} },
  }),
}));

// authStore 모킹 — selector 패턴 지원.
vi.mock('@/stores/authStore', () => {
  const state = { user: { uid: 'user-a' } };
  return {
    useAuthStore: <T,>(selector: (s: typeof state) => T) => selector(state),
  };
});

// subscribeMyEntries 모킹 — 최근 콜백을 테스트에서 수동 트리거.
let lastCb: ((list: Array<WaitEntryIndex & { id: string }>) => void) | null =
  null;
vi.mock('@/services/waitQueue', () => ({
  subscribeMyEntries: (
    _hid: string,
    _uid: string,
    cb: (list: Array<WaitEntryIndex & { id: string }>) => void,
  ) => {
    lastCb = cb;
    return () => {
      lastCb = null;
    };
  },
}));

import { WaitQueueWidget } from '../WaitQueueWidget';

function feed(entries: Array<WaitEntryIndex & { id: string }>) {
  act(() => {
    lastCb?.(entries);
  });
}

beforeEach(() => {
  lastCb = null;
});

describe('WaitQueueWidget', () => {
  it('빈 상태 — "접수된 진료가 없습니다" 메시지', () => {
    render(<WaitQueueWidget />);
    feed([]);
    expect(screen.getByText('진료 대기')).toBeTruthy();
    expect(screen.getByText('접수된 진료가 없습니다.')).toBeTruthy();
  });

  it('waiting — 순번 + "대기 중" 표시', () => {
    render(<WaitQueueWidget />);
    feed([
      {
        id: 'e-1',
        department: '내과',
        date: '2026-04-23',
        number: 5,
        status: 'waiting',
      },
    ]);
    expect(screen.getByText(/순번/)).toBeTruthy();
    expect(screen.getByText('5')).toBeTruthy();
    expect(screen.getByText('대기 중')).toBeTruthy();
    expect(screen.getByText(/내과.*2026-04-23/)).toBeTruthy();
  });

  it('called — 강조 메시지 "진료실로 이동해 주세요"', () => {
    render(<WaitQueueWidget />);
    feed([
      {
        id: 'e-2',
        department: '정형외과',
        date: '2026-04-23',
        number: 3,
        status: 'called',
      },
    ]);
    expect(screen.getByText(/호출됨/)).toBeTruthy();
    expect(screen.getByText(/진료실로 이동해 주세요/)).toBeTruthy();
  });

  it('in-progress — "진료 중"', () => {
    render(<WaitQueueWidget />);
    feed([
      {
        id: 'e-3',
        department: '내과',
        date: '2026-04-23',
        number: 1,
        status: 'in-progress',
      },
    ]);
    expect(screen.getByText('진료 중')).toBeTruthy();
  });

  it('completed/cancelled만 있으면 빈 상태', () => {
    render(<WaitQueueWidget />);
    feed([
      {
        id: 'e-done',
        department: '내과',
        date: '2026-04-23',
        number: 2,
        status: 'completed',
      },
      {
        id: 'e-cancel',
        department: '외과',
        date: '2026-04-23',
        number: 1,
        status: 'cancelled',
      },
    ]);
    expect(screen.getByText('접수된 진료가 없습니다.')).toBeTruthy();
  });

  it('활성 여러 개 중 number 최소값 우선 표시 (subscribeMyEntries가 정렬 책임)', () => {
    render(<WaitQueueWidget />);
    feed([
      {
        id: 'e-1',
        department: '내과',
        date: '2026-04-23',
        number: 2,
        status: 'waiting',
      },
      {
        id: 'e-2',
        department: '외과',
        date: '2026-04-23',
        number: 7,
        status: 'waiting',
      },
    ]);
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText(/내과/)).toBeTruthy();
  });
});
