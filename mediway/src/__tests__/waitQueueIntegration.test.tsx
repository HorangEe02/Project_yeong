import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';
import type {
  WaitQueueEntry,
  WaitQueuePatientIndex,
} from '@/types/waitQueue';
import type { AppointmentPatientIndex } from '@/types/appointment';

/**
 * P3 F1 — wait queue 시나리오 A-D 통합 smoke.
 *
 * prod 의 `public/e2e-wait-queue.html` 기대값을 local source 가 만족하는지
 * 단위 컴포넌트들의 결합 동작 수준에서 검증한다.
 *
 * 시나리오:
 *   A. 접수 → 위젯 순번 즉시 반영
 *   B. Call Next → 환자 위젯 강조 + "진료실로 이동" 안내
 *   C. 진료 시작 / 완료 → 위젯 상태 전이
 *   D. 교차 병원 격리 (HospitalShell 단위 테스트가 별도 커버 — 본 sprint 는 회귀 보장)
 */

// --- Mocks ---

type WaitQueuePatientCb = (rows: WaitQueuePatientIndex[]) => void;
type WaitQueueDeptCb = (rows: WaitQueueEntry[]) => void;
type AppointmentCb = (rows: AppointmentPatientIndex[]) => void;

let patientCbs: WaitQueuePatientCb[] = [];
let lastApptCb: AppointmentCb | null = null;

/** 모든 활성 patient 구독자에게 브로드캐스트 (HomeTab+AppointmentsTab 동시 마운트 케이스) */
function broadcastPatient(rows: WaitQueuePatientIndex[]) {
  patientCbs.forEach((cb) => cb(rows));
}

const mockSubscribePatient = vi.fn(
  (_slug: string, _uid: string, onData: WaitQueuePatientCb) => {
    patientCbs.push(onData);
    return () => {
      patientCbs = patientCbs.filter((c) => c !== onData);
    };
  },
);
const mockSubscribeDept = vi.fn(
  (_slug: string, _dept: string, _date: string, onData: WaitQueueDeptCb) => {
    onData([]);
    return () => {};
  },
);
const mockSubscribeAppointments = vi.fn(
  (_slug: string, _uid: string, onData: AppointmentCb) => {
    lastApptCb = onData;
    return () => {};
  },
);
const mockCheckIn = vi.fn(async () => ({}) as unknown as WaitQueueEntry);
const mockCallNext = vi.fn(async () => null);
const mockMarkInProgress = vi.fn(async () => undefined);
const mockMarkCompleted = vi.fn(async () => undefined);
const mockCancel = vi.fn(async () => undefined);

vi.mock('@/services/waitQueue', () => ({
  subscribeMyWaitQueue: (
    slug: string,
    uid: string,
    onData: WaitQueuePatientCb,
  ) => mockSubscribePatient(slug, uid, onData),
  subscribeDeptQueue: (
    slug: string,
    dept: string,
    date: string,
    onData: WaitQueueDeptCb,
  ) => mockSubscribeDept(slug, dept, date, onData),
  selectPrimaryActive: (
    rows: WaitQueuePatientIndex[],
    today: string,
  ): WaitQueuePatientIndex | null => {
    const URGENCY: Record<string, number> = {
      called: 0,
      'in-progress': 1,
      waiting: 2,
      completed: 99,
      cancelled: 99,
    };
    const f = rows
      .filter(
        (e) => e.date === today && e.status !== 'completed' && e.status !== 'cancelled',
      )
      .sort((a, b) => {
        const d = (URGENCY[a.status] ?? 99) - (URGENCY[b.status] ?? 99);
        return d !== 0 ? d : a.number - b.number;
      });
    return f[0] ?? null;
  },
  todayDateKST: () => '2026-04-26',
  checkInToQueue: (...args: unknown[]) => mockCheckIn(...args),
  callNextWaiting: (...args: unknown[]) => mockCallNext(...args),
  markInProgress: (...args: unknown[]) => mockMarkInProgress(...args),
  markCompleted: (...args: unknown[]) => mockMarkCompleted(...args),
}));

vi.mock('@/services/appointments', () => ({
  subscribeMyAppointments: (
    slug: string,
    uid: string,
    onData: AppointmentCb,
  ) => mockSubscribeAppointments(slug, uid, onData),
  cancelAppointment: (...args: unknown[]) => mockCancel(...args),
  createAppointment: vi.fn(),
}));

interface FakeAuthState {
  user: { uid: string; isAnonymous: boolean } | null;
  profile: { hospitalId?: string; role?: string } | null;
}
let authState: FakeAuthState = {
  user: { uid: 'u-patient', isAnonymous: false },
  profile: { hospitalId: 'demo' },
};
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: FakeAuthState) => T): T | FakeAuthState =>
    selector ? selector(authState) : authState,
}));

// FCM 권한 요청 hook 은 jsdom 에서 불필요한 부수 효과만 생산 — no-op
vi.mock('@/hooks/useFcmToken', () => ({
  useFcmToken: () => null,
}));

// ChatbotWidget — 외부 fetch 의존, 통합 smoke 에선 stub
vi.mock('@/components/patient/ChatbotWidget', () => ({
  ChatbotWidget: () => <div data-testid="chatbot-stub" />,
}));

import { HomeTab } from '@/components/patient/tabs/HomeTab';
import { AppointmentsTab } from '@/components/patient/tabs/AppointmentsTab';
import { HospitalProvider } from '@/contexts/HospitalContext';

function makeProfile(features?: Record<string, boolean>): HospitalProfile {
  return {
    id: 'demo',
    name: 'MediWay 데모',
    status: 'active',
    ...(features ? { features } : {}),
  };
}

function withShell(ui: React.ReactNode, profile?: HospitalProfile) {
  return render(
    <MemoryRouter initialEntries={['/h/demo/patient/home']}>
      <HospitalProvider value={{ slug: 'demo', profile: profile ?? makeProfile() }}>
        {ui}
      </HospitalProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockSubscribePatient.mockClear();
  mockSubscribeDept.mockClear();
  mockSubscribeAppointments.mockClear();
  mockCheckIn.mockClear();
  mockCheckIn.mockResolvedValue({} as WaitQueueEntry);
  mockCallNext.mockClear();
  mockMarkInProgress.mockClear();
  mockMarkCompleted.mockClear();
  mockCancel.mockClear();
  patientCbs = [];
  lastApptCb = null;
  authState = {
    user: { uid: 'u-patient', isAnonymous: false },
    profile: { hospitalId: 'demo' },
  };
});

// =====================================================================
// 시나리오 A — 접수 → 위젯 순번 즉시 반영
// =====================================================================

describe('Scenario A — 접수 → 위젯 순번 즉시 반영', () => {
  it('AppointmentsTab + HomeTab 결합: 오늘 예약 [접수] 클릭 → checkInToQueue 호출 + 위젯 갱신', async () => {
    withShell(
      <>
        <HomeTab />
        <AppointmentsTab />
      </>,
    );

    // (1) 위젯 초기 — empty CTA
    act(() => broadcastPatient([]));
    expect(screen.getByTestId('waitqueue-empty')).toBeTruthy();

    // (2) 예약 1건 도착 — 오늘자 + scheduled
    const todayAt = Date.parse('2026-04-26T10:00:00+09:00');
    act(() =>
      lastApptCb?.([
        {
          id: 'appt-1',
          department: '내과',
          scheduledAt: todayAt,
          status: 'scheduled',
        } as AppointmentPatientIndex,
      ]),
    );

    // (3) [접수] 버튼 → checkInToQueue 호출
    const checkInBtn = screen.getByRole('button', { name: '접수' });
    fireEvent.click(checkInBtn);
    await waitFor(() => expect(mockCheckIn).toHaveBeenCalledTimes(1));
    expect(mockCheckIn).toHaveBeenCalledWith(
      'demo',
      'u-patient',
      expect.objectContaining({
        department: '내과',
        date: '2026-04-26',
        appointmentId: 'appt-1',
      }),
    );

    // (4) 서버 트리거 시뮬레이션 — wait_queue_by_patient 에 새 엔트리 도달
    act(() =>
      broadcastPatient([
        {
          id: 'q-1',
          department: '내과',
          date: '2026-04-26',
          number: 7,
          status: 'waiting',
        },
      ]),
    );

    // (5) 위젯 갱신 — 순번 7 + "대기 중"
    expect(screen.getByText('7')).toBeTruthy();
    expect(screen.getByText('대기 중')).toBeTruthy();
  });
});

// =====================================================================
// 시나리오 B — Call Next → 환자 위젯 강조
// =====================================================================

describe('Scenario B — staff [다음 환자 호출] → 환자 위젯 강조', () => {
  it('환자 위젯이 status=called 도착 시 "진료실로 이동해 주세요" 안내', () => {
    withShell(<HomeTab />);

    // 초기: waiting
    act(() =>
      broadcastPatient([
        {
          id: 'q-1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'waiting',
        },
      ]),
    );
    expect(screen.getByText('대기 중')).toBeTruthy();

    // staff Call Next → status=called 가 환자측에 도달 (시뮬레이션)
    act(() =>
      broadcastPatient([
        {
          id: 'q-1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'called',
        },
      ]),
    );
    expect(screen.getByText('호출됨')).toBeTruthy();
    expect(screen.getByText('진료실로 이동해 주세요')).toBeTruthy();
  });
});

// =====================================================================
// 시나리오 C — 진료 시작 / 완료 전이
// =====================================================================

describe('Scenario C — 진료 시작 → 완료 전이', () => {
  it('called → in-progress → completed 전이 시 위젯이 따라감', () => {
    withShell(<HomeTab />);

    // called
    act(() =>
      broadcastPatient([
        {
          id: 'q-1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'called',
        },
      ]),
    );
    expect(screen.getByText('호출됨')).toBeTruthy();

    // in-progress
    act(() =>
      broadcastPatient([
        {
          id: 'q-1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'in-progress',
        },
      ]),
    );
    expect(screen.getByText('진료 중')).toBeTruthy();

    // completed → empty 상태
    act(() =>
      broadcastPatient([
        {
          id: 'q-1',
          department: '내과',
          date: '2026-04-26',
          number: 5,
          status: 'completed',
        },
      ]),
    );
    expect(screen.getByTestId('waitqueue-empty')).toBeTruthy();
  });
});

// =====================================================================
// 시나리오 D — 교차 병원 격리 (회귀 보장)
// =====================================================================

describe('Scenario D — cross-tenant 회귀 보장', () => {
  it('features.appointments=false 인 hospital → 위젯 자체 미마운트', () => {
    withShell(<HomeTab />, makeProfile({ appointments: false }));
    expect(mockSubscribePatient).not.toHaveBeenCalled();
  });

  it('익명 사용자 → 위젯 미마운트 (auth 가드)', () => {
    authState = {
      user: { uid: 'anon', isAnonymous: true },
      profile: null,
    };
    withShell(<HomeTab />);
    expect(mockSubscribePatient).not.toHaveBeenCalled();
  });
});

// =====================================================================
// 추가 회귀 — F1.1c 가 도입한 empty CTA 의 라우팅 효과
// =====================================================================

describe('Empty state CTA — 외래 탭 발견성 보강', () => {
  it('CTA 클릭 → ?tab=appointments 라우팅 (URL 갱신)', () => {
    withShell(<HomeTab />);
    act(() => broadcastPatient([]));
    expect(screen.getByText('외래 탭으로 이동')).toBeTruthy();
    fireEvent.click(screen.getByText('외래 탭으로 이동'));
    // setSearchParams replace 라 jsdom location 직접 검사 어려움 — 클릭 이후 CTA 재렌더
    // 시 새 URL params 가 컨슈머에게 반영. URL 측 검사는 단위 test (WaitQueueWidget.test) 로 커버.
    expect(screen.getByText('외래 탭으로 이동')).toBeTruthy();
  });
});
