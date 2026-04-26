import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';
import type { TriageError, TriageResponse } from '@/types/triage';

// --- Mocks ---

const mockRequest = vi.fn();
vi.mock('@/services/triage', () => ({
  requestTriageRecommendation: (...args: unknown[]) => mockRequest(...args),
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

import { TriageWidget } from '../TriageWidget';
import { HospitalProvider } from '@/contexts/HospitalContext';

function makeProfile(features?: Record<string, boolean>): HospitalProfile {
  return {
    id: 'demo',
    name: 'MediWay 데모',
    status: 'active',
    ...(features ? { features } : {}),
  };
}

function renderWidget(opts?: { features?: Record<string, boolean> }) {
  // 기본은 aiTriage=true (default false 라 명시 enable 필요)
  const features = opts?.features ?? { aiTriage: true };
  return render(
    <MemoryRouter initialEntries={['/h/demo/patient/home']}>
      <HospitalProvider value={{ slug: 'demo', profile: makeProfile(features) }}>
        <TriageWidget />
      </HospitalProvider>
    </MemoryRouter>,
  );
}

const SAMPLE_OK_RESPONSE: TriageResponse = {
  recommendations: [
    { department: '내과', confidence: 0.85, reason: '기침과 발열은 호흡기 감염 가능성이 높습니다.' },
    { department: '가정의학과', confidence: 0.55, reason: '종합 평가에 적합합니다.' },
    { department: '이비인후과', confidence: 0.4, reason: '인후 자극 가능성.' },
  ],
  disclaimer: '본 답변은 진단이 아니며 최종 판단은 의료진이 합니다.',
  model: 'gemini-2.5-flash',
  tokensIn: 120,
  tokensOut: 80,
  rateLimit: { remainingHour: 9 },
};

beforeEach(() => {
  mockRequest.mockReset();
  authState = {
    user: { uid: 'u-patient', isAnonymous: false },
    profile: { hospitalId: 'demo' },
  };
});

// =====================================================================
// 가시성 가드
// =====================================================================

describe('TriageWidget — 가시성', () => {
  it('미로그인 → 미렌더', () => {
    authState = { user: null, profile: null };
    renderWidget();
    expect(screen.queryByTestId('triage-widget')).toBeNull();
  });

  it('익명 → 미렌더', () => {
    authState = {
      user: { uid: 'anon', isAnonymous: true },
      profile: null,
    };
    renderWidget();
    expect(screen.queryByTestId('triage-widget')).toBeNull();
  });

  it('features.aiTriage=false → 미렌더', () => {
    renderWidget({ features: { aiTriage: false } });
    expect(screen.queryByTestId('triage-widget')).toBeNull();
  });

  it('features 미명시(default false) → 미렌더', () => {
    renderWidget({ features: {} });
    expect(screen.queryByTestId('triage-widget')).toBeNull();
  });

  it('features.aiTriage=true → 마운트', () => {
    renderWidget();
    expect(screen.getByTestId('triage-widget')).toBeTruthy();
    expect(screen.getByText('AI 진료과 추천')).toBeTruthy();
  });
});

// =====================================================================
// 입력 검증
// =====================================================================

describe('TriageWidget — 입력 검증', () => {
  it('초기 제출 버튼 disabled (입력 없음)', () => {
    renderWidget();
    const btn = screen.getByRole('button', { name: '진료과 추천 받기' });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('< 10자 입력 → 버튼 비활성', () => {
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '아파' },
    });
    const btn = screen.getByRole('button', { name: '진료과 추천 받기' });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('10자 이상 입력 → 버튼 활성 + 글자 수 표시', () => {
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    const btn = screen.getByRole('button', { name: '진료과 추천 받기' });
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText(/15 \/ 500/)).toBeTruthy();
  });
});

// =====================================================================
// 정상 흐름
// =====================================================================

describe('TriageWidget — 정상 흐름', () => {
  it('제출 → 결과 카드 3개 + disclaimer 노출', async () => {
    mockRequest.mockResolvedValue(SAMPLE_OK_RESPONSE);
    renderWidget();
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
  });

  it('각 추천에 confidence % 표시', async () => {
    mockRequest.mockResolvedValue(SAMPLE_OK_RESPONSE);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() =>
      expect(screen.getByTestId('triage-results')).toBeTruthy(),
    );
    expect(screen.getByText('85%')).toBeTruthy();
    expect(screen.getByText('55%')).toBeTruthy();
    expect(screen.getByText('40%')).toBeTruthy();
  });

  it('추천 요청 시 hospitalId=slug, symptomText 전달', async () => {
    mockRequest.mockResolvedValue(SAMPLE_OK_RESPONSE);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() => expect(mockRequest).toHaveBeenCalled());
    expect(mockRequest).toHaveBeenCalledWith({
      hospitalId: 'demo',
      symptomText: '2일째 기침과 미열이 있어요',
    });
  });

  it('[다시 입력] 클릭 → 결과 초기화 + 입력란 표시', async () => {
    mockRequest.mockResolvedValue(SAMPLE_OK_RESPONSE);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() =>
      expect(screen.getByTestId('triage-results')).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole('button', { name: '새 추천' }));
    expect(screen.queryByTestId('triage-results')).toBeNull();
    expect(screen.getByLabelText('증상 입력')).toBeTruthy();
  });
});

// =====================================================================
// Emergency 분기
// =====================================================================

describe('TriageWidget — Emergency 분기', () => {
  it('emergencyNotice 가 있으면 alert 배너 + 빨간 강조', async () => {
    mockRequest.mockResolvedValue({
      recommendations: [
        {
          department: '응급의학과',
          confidence: 1,
          reason: '응급 가능성. 즉시 119 또는 응급실.',
        },
      ],
      disclaimer: '본 답변은 진단이 아닙니다',
      emergencyNotice: '🚨 응급 가능성이 있습니다. 119 또는 가까운 응급실로 즉시 이동하세요.',
      model: 'gemini-2.5-flash',
      tokensIn: 0,
      tokensOut: 0,
      rateLimit: { remainingHour: 10 },
    } as TriageResponse);
    renderWidget();
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
// 에러 흐름
// =====================================================================

describe('TriageWidget — 에러 흐름', () => {
  it('rate_limited + retryAfterSeconds → 분 단위 안내', async () => {
    const err: TriageError = {
      code: 'rate_limited',
      message: '한도 초과',
      retryAfterSeconds: 600, // 10분
    };
    mockRequest.mockRejectedValue(err);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() =>
      expect(screen.getByTestId('triage-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('triage-error').textContent).toMatch(
      /약 10분 후/,
    );
  });

  it('invalid_argument → 서버 메시지 노출', async () => {
    mockRequest.mockRejectedValue({
      code: 'invalid_argument',
      message: '증상 설명은 10자 이상 입력해 주세요',
    } as TriageError);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() =>
      expect(screen.getByTestId('triage-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('triage-error').textContent).toMatch(
      /10자 이상/,
    );
  });

  it('network 에러 → 친근 안내', async () => {
    mockRequest.mockRejectedValue({
      code: 'network',
      message: '연결 실패',
    } as TriageError);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() =>
      expect(screen.getByTestId('triage-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('triage-error').textContent).toMatch(
      /네트워크/,
    );
  });

  it('feature_disabled → 친근 안내', async () => {
    mockRequest.mockRejectedValue({
      code: 'feature_disabled',
      message: '기능 비활성',
    } as TriageError);
    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    await waitFor(() =>
      expect(screen.getByTestId('triage-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('triage-error').textContent).toMatch(
      /AI 진료과 추천이 제공되지 않/,
    );
  });
});

// =====================================================================
// 로딩 상태
// =====================================================================

describe('TriageWidget — 로딩', () => {
  it('제출 중 버튼 라벨 "추천 중..."', async () => {
    let resolver: (v: TriageResponse) => void = () => {};
    const pending = new Promise<TriageResponse>((resolve) => {
      resolver = resolve;
    });
    mockRequest.mockReturnValue(pending);

    renderWidget();
    fireEvent.change(screen.getByLabelText('증상 입력'), {
      target: { value: '2일째 기침과 미열이 있어요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '진료과 추천 받기' }));
    expect(screen.getByRole('button', { name: '추천 중...' })).toBeTruthy();
    act(() => resolver(SAMPLE_OK_RESPONSE));
    await waitFor(() =>
      expect(screen.getByTestId('triage-results')).toBeTruthy(),
    );
  });
});
