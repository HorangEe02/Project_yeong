import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import type { WaitEntry } from '@/types/wait-queue';

vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => ({ slug: 'demo', hospital: {} }),
}));

let lastCb: ((entries: WaitEntry[]) => void) | null = null;
const callNextMock = vi.fn();
const startMock = vi.fn();
const completeMock = vi.fn();

vi.mock('@/services/waitQueue', () => ({
  getTodayDateKst: () => '2026-04-23',
  subscribeDeptQueue: (
    _h: string,
    _d: string,
    _dt: string,
    cb: (entries: WaitEntry[]) => void,
  ) => {
    lastCb = cb;
    return () => {
      lastCb = null;
    };
  },
  callNext: (...args: unknown[]) => callNextMock(...args),
  startConsultation: (...args: unknown[]) => startMock(...args),
  completeEntry: (...args: unknown[]) => completeMock(...args),
}));

import { StaffQueuePage } from '../StaffQueuePage';

function feed(entries: WaitEntry[]) {
  act(() => {
    lastCb?.(entries);
  });
}

beforeEach(() => {
  lastCb = null;
  callNextMock.mockReset();
  startMock.mockReset();
  completeMock.mockReset();
});

describe('StaffQueuePage', () => {
  it('빈 대기열 — "활성 대기 환자가 없습니다" + Call Next 비활성화', () => {
    render(<StaffQueuePage />);
    feed([]);
    expect(screen.getByText('대기 환자 호출 콘솔')).toBeTruthy();
    expect(screen.getByText('활성 대기 환자가 없습니다.')).toBeTruthy();
    const btn = screen.getByRole('button', { name: /다음 환자 호출/ });
    expect(btn.hasAttribute('disabled')).toBe(true);
  });

  it('waiting 존재 — Call Next 활성화, 클릭 시 callNext 호출', async () => {
    render(<StaffQueuePage />);
    feed([
      {
        id: 'e-1',
        hospitalId: 'demo',
        department: '내과',
        date: '2026-04-23',
        number: 1,
        patientUid: 'uid-a',
        status: 'waiting',
        createdAt: 1,
      },
    ]);
    callNextMock.mockResolvedValueOnce({ id: 'e-1', number: 1 });
    const btn = screen.getByRole('button', { name: /다음 환자 호출/ });
    expect(btn.hasAttribute('disabled')).toBe(false);
    fireEvent.click(btn);
    expect(callNextMock).toHaveBeenCalledWith('demo', '내과', '2026-04-23');
  });

  it('called 상태에서 "진료 시작" + "완료" 버튼 노출', () => {
    render(<StaffQueuePage />);
    feed([
      {
        id: 'e-2',
        hospitalId: 'demo',
        department: '내과',
        date: '2026-04-23',
        number: 2,
        patientUid: 'uid-b',
        status: 'called',
        createdAt: 1,
      },
    ]);
    expect(screen.getByRole('button', { name: /진료 시작/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /완료/ })).toBeTruthy();
  });

  it('in-progress — 완료 버튼만 (진료 시작 없음)', () => {
    render(<StaffQueuePage />);
    feed([
      {
        id: 'e-3',
        hospitalId: 'demo',
        department: '내과',
        date: '2026-04-23',
        number: 3,
        patientUid: 'uid-c',
        status: 'in-progress',
        createdAt: 1,
      },
    ]);
    expect(screen.getByRole('button', { name: /완료/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /진료 시작/ })).toBeNull();
  });

  it('진료 시작 클릭 → startConsultation 호출', () => {
    render(<StaffQueuePage />);
    const entry: WaitEntry = {
      id: 'e-4',
      hospitalId: 'demo',
      department: '내과',
      date: '2026-04-23',
      number: 4,
      patientUid: 'uid-d',
      status: 'called',
      createdAt: 1,
    };
    feed([entry]);
    startMock.mockResolvedValueOnce(undefined);
    fireEvent.click(screen.getByRole('button', { name: /진료 시작/ }));
    expect(startMock).toHaveBeenCalledWith('demo', entry);
  });

  it('여러 entry가 모두 리스트에 렌더', () => {
    render(<StaffQueuePage />);
    feed([
      {
        id: 'a',
        hospitalId: 'demo',
        department: '내과',
        date: '2026-04-23',
        number: 1,
        patientUid: 'uid-abc123',
        status: 'waiting',
        createdAt: 1,
      },
      {
        id: 'b',
        hospitalId: 'demo',
        department: '내과',
        date: '2026-04-23',
        number: 2,
        patientUid: 'uid-def456',
        status: 'called',
        createdAt: 1,
      },
    ]);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(screen.getByText('환자 #uid-ab')).toBeTruthy();
    expect(screen.getByText('환자 #uid-de')).toBeTruthy();
  });
});
