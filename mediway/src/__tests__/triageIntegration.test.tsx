import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';
import type { TriageError, TriageResponse } from '@/types/triage';

/**
 * P3 Scenario E — AI Triage 통합 smoke.
 *
 * prod e2e (`public/e2e-wait-queue.html`) 시나리오 E 가 local source 의
 * HomeTab + TriageWidget + triage service 결합 동작에서 만족됨을 자동 검증.
 *
 * 시나리오:
 *   E1. features.aiTriage=true 인 병원 → 환자 홈 위젯 노출
 *   E2. features.aiTriage 미설정 (default false) → 위젯 미노출
 *   E3. 정상 입력 → 진료과 3개 + disclaimer
 *   E4. 응급 입력 → emergencyNotice + 응급의학과
 *   E5. rate_limited → 분 단위 안내
 */

// --- Mocks ---

const mockTriage = vi.fn();
vi.mock('@/services/triage', () => ({
  requestTriageRecommendation: (...args: unknown[]) => mockTriage(...args),
}));

// 다른 위젯 (waitQueue, chatbot) 의 부수 효과 차단 — 본 테스트 비범위
vi.mock('@/services/waitQueue', () => ({
  subscribeMyWaitQueue: () => () => {},
  selectPrimaryActive: () => null,
  todayDateKST: () => '2026-04-26',
}));

vi.mock('@/components/patient/ChatbotWidget', () => ({
  ChatbotWidget: () => <div data-testid="chatbot-stub" />,
}));

vi.mock('@/hooks/useFcmToken', () => ({
  useFcmToken: () => null,
}));

interface FakeAuthState {
  user: { uid: string; isAnonymous: boolean } | null;
  profile: { hospitalId?: string } | null;
}
let authState: FakeAuthState = {
  user: { uid: 'u-patient', isAnonymous: false },
  profile: { hospitalId: 'demo' },
};
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: FakeAuthState) => T): T | FakeAuthState =>
    selector ? selector(authState) : authState,
}));

import { HomeTab } from '@/components/patient/tabs/HomeTab';
import { HospitalProvider } from '@/contexts/HospitalContext';

function makeProfile(features?: Record<string, boolean>): HospitalProfile {
  return {
    id: 'demo',
    name: 'MediWay 데모',
    status: 'active',
    ...(features ? { features } : {}),
  };
}

function withShell(features?: Record<string, boolean>) {
  return render(
    <MemoryRouter initialEntries={['/h/demo/patient/home']}>
      <HospitalProvider value={{ slug: 'demo', profile: makeProfile(features) }}>
        <HomeTab />
      </HospitalProvider>
    </MemoryRouter>,
  );
}

const SAMPLE_OK_RESPONSE: TriageResponse = {
  recommendations: [
    {
      department: '내과',
      confidence: 0.85,
      reason: '기침과 발열은 호흡기 감염 가능성이 높습니다.',
    },
    { department: '가정의학과', confidence: 0.55, reason: '종합 평가 적합.' },
    { department: '이비인후과', confidence: 0.4, reason: '인후 자극 가능성.' },
  ],
  disclaimer: '본 답변은 진단이 아니며 최종 판단은 의료진이 합니다.',
  model: 'gemini-2.5-flash',
  tokensIn: 120,
  tokensOut: 80,
  rateLimit: { remainingHour: 9 },
};

beforeEach(() => {
  mockTriage.mockReset();
  authState = {
    user: { uid: 'u-patient', isAnonymous: false },
    profile: { hospitalId: 'demo' },
  };
});

// =====================================================================
// E1 — features.aiTriage=true → 위젯 노출
// =====================================================================

describe('Scenario E1 — features.aiTriage=true', () => {
  it('aiTriage=true → TriageWidget 마운트 + 입력란 표시', () => {
    withShell({ aiTriage: true });
    expect(screen.getByTestId('triage-widget')).toBeTruthy();
    expect(screen.getByLabelText('증상 입력')).toBeTruthy();
  });
});

// =====================================================================
// E2 — features.aiTriage 미설정 → 위젯 미노출
// =====================================================================

describe('Scenario E2 — features.aiTriage default=false', () => {
  it('features 미설정 → 위젯 미마운트 (FEATURE_DEFAULTS.aiTriage=false)', () => {
    withShell();
    expect(screen.queryByTestId('triage-widget')).toBeNull();
  });

  it('features.aiTriage=false 명시 → 위젯 미마운트', () => {
    withShell({ aiTriage: false });
    expect(screen.queryByTestId('triage-widget')).toBeNull();
  });
});

// =====================================================================
// E3 — 정상 입력 → 추천 결과
// =====================================================================

describe('Scenario E3 — 정상 입력 → 결과', () => {
  it('증상 입력 → 제출 → 진료과 3개 + disclaimer', async () => {
    mockTriage.mockResolvedValue(SAMPLE_OK_RESPONSE);
    withShell({ aiTriage: true });

    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));

    await waitFor(() =>
      expect(screen.getByTestId('triage-results')).toBeTruthy(),
    );
    expect(screen.getByText('내과')).toBeTruthy();
    expect(screen.getByText('가정의학과')).toBeTruthy();
    expect(screen.getByText('이비인후과')).toBeTruthy();
    expect(screen.getByTestId('triage-disclaimer').textContent).toMatch(
      /진단이 아니/,
    );

    // service 호출 인자
    expect(mockTriage).toHaveBeenCalledWith({
      hospitalId: 'demo',
      symptomText: '2일째 기침과 미열이 있어요',
    });
  });
});

// =====================================================================
// E4 — 응급 분기
// =====================================================================

describe('Scenario E4 — 응급 분기', () => {
  it('응급 응답 → emergencyNotice 배너 + 응급의학과 1건', async () => {
    mockTriage.mockResolvedValue({
      recommendations: [
        {
          department: '응급의학과',
          confidence: 1,
          reason: '응급 가능성 — 즉시 119 또는 응급실.',
        },
      ],
      disclaimer: '본 답변은 진단이 아닙니다',
      emergencyNotice: '🚨 응급 가능성이 있습니다. 119 또는 가까운 응급실로 즉시 이동하세요.',
      model: 'gemini-2.5-flash',
      tokensIn: 0,
      tokensOut: 0,
      rateLimit: { remainingHour: 10 },
    } as TriageResponse);
    withShell({ aiTriage: true });

    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '갑자기 가슴이 너무 아파서 숨을 못 쉬겠어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));

    await waitFor(() =>
      expect(screen.getByTestId('triage-emergency')).toBeTruthy(),
    );
    expect(screen.getByTestId('triage-emergency').textContent).toMatch(
      /119|응급실/,
    );
    expect(screen.getByText('응급의학과')).toBeTruthy();
  });
});

// =====================================================================
// E5 — rate-limit
// =====================================================================

describe('Scenario E5 — rate-limit', () => {
  it('11번째 호출 → resource-exhausted 분 단위 안내', async () => {
    const err: TriageError = {
      code: 'rate_limited',
      message: '한도 초과',
      retryAfterSeconds: 1800, // 30분
    };
    mockTriage.mockRejectedValue(err);
    withShell({ aiTriage: true });

    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));

    await waitFor(() =>
      expect(screen.getByTestId('triage-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('triage-error').textContent).toMatch(
      /약 30분 후/,
    );
  });
});

// =====================================================================
// 통합 — 다른 위젯 영향 없음
// =====================================================================

describe('Scenario E — 다른 위젯과 격리', () => {
  it('aiTriage=true 일 때 ChatbotWidget 도 그대로 마운트 (features.chatbot default=true)', () => {
    withShell({ aiTriage: true });
    expect(screen.getByTestId('triage-widget')).toBeTruthy();
    expect(screen.getByTestId('chatbot-stub')).toBeTruthy();
  });

  it('features.appointments=false + aiTriage=true → triage 만 노출', () => {
    withShell({ aiTriage: true, appointments: false });
    expect(screen.getByTestId('triage-widget')).toBeTruthy();
    // appointments off → WaitQueueWidget 미렌더
    // (WaitQueueWidget 자체는 mock 안 함 — 실 위젯이 features=false 로 null 반환)
    expect(screen.queryByTestId('waitqueue-empty')).toBeNull();
  });
});
