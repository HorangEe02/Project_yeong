import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HospitalProvider } from '@/contexts/HospitalContext';
import type { HospitalProfile } from '@/types/hospital';

// --- Mocks ---

const mockIssue = vi.fn();
vi.mock('@/services/qrToken', async () => {
  const actual = await vi.importActual<typeof import('@/services/qrToken')>(
    '@/services/qrToken',
  );
  return {
    ...actual,
    issueSelfQRToken: (...args: unknown[]) => mockIssue(...args),
  };
});

vi.mock('@/services/auth', () => ({
  getCurrentUid: () => 'uid-1',
  initAnonymousAuth: async () => ({ uid: 'uid-anon' }),
}));

vi.mock('@/config/firebase', () => ({
  isFirebaseConfigured: () => true,
  functions: { __mocked: true },
  db: { __mocked: true },
}));

// useSession 은 본 테스트 범위 밖. firebase ref 호출 차단 위해 stub.
vi.mock('@/hooks/useSession', () => ({
  useSession: () => ({ qrTokenData: null, session: null, isConnected: true }),
}));

interface FakeAuthState {
  initialized: boolean;
}
let authState: FakeAuthState = { initialized: true };
vi.mock('@/stores/authStore', () => ({
  useAuthStore: <T,>(selector?: (s: FakeAuthState) => T): T | FakeAuthState =>
    selector ? selector(authState) : authState,
}));

// QRDisplay stub — onTokenGenerated 즉시 호출 (token 생성 시뮬레이션)
let lastTokenCb: ((t: string) => void) | null = null;
vi.mock('../QRDisplay', () => ({
  QRDisplay: ({ onTokenGenerated }: { onTokenGenerated: (t: string) => void }) => {
    lastTokenCb = onTokenGenerated;
    // 마운트 즉시 한 번 호출 (실제 QRDisplay 도 useEffect 로 같은 동작)
    setTimeout(() => onTokenGenerated('mock-token-001'), 0);
    return <div data-testid="qrdisplay-stub">[QRDisplay stub]</div>;
  },
}));

import { QRGuidePlaceholder } from '../QRGuidePlaceholder';
import { QRTokenRateLimitError } from '@/services/qrToken';

function makeProfile(): HospitalProfile {
  return { id: 'demo', name: 'MediWay 데모', status: 'active' };
}

/** QRGuidePlaceholder 는 useNavigate + useHospital 사용 — Router + HospitalProvider 래퍼 필수. */
function renderQRG() {
  return render(
    <MemoryRouter initialEntries={['/h/demo/patient/home']}>
      <Routes>
        <Route
          path="/h/:hospitalSlug/patient/home"
          element={
            <HospitalProvider value={{ slug: 'demo', profile: makeProfile() }}>
              <QRGuidePlaceholder />
            </HospitalProvider>
          }
        />
        <Route path="/h/:hospitalSlug/patient/:sessionId" element={<div>Session Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockIssue.mockReset();
  mockIssue.mockResolvedValue(undefined);
  lastTokenCb = null;
  authState = { initialized: true };
});

// =====================================================================
// 기존 placeholder 모드 테스트 (회귀 보호)
// =====================================================================

describe('QRGuidePlaceholder — placeholder 모드', () => {
  it('region role + aria-label="QR 안내"', () => {
    renderQRG();
    expect(screen.getByRole('region', { name: 'QR 안내' })).toBeTruthy();
  });

  it('testid "qr-guide-placeholder" 노출', () => {
    renderQRG();
    expect(screen.getByTestId('qr-guide-placeholder')).toBeTruthy();
  });

  it('헤드라인 "QR 코드를 받아 안내를 시작하세요"', () => {
    renderQRG();
    expect(screen.getByText('QR 코드를 받아 안내를 시작하세요')).toBeTruthy();
  });

  it('3단계 안내가 순서대로 표시', () => {
    renderQRG();
    expect(screen.getByText('병원 안내 데스크 방문')).toBeTruthy();
    expect(screen.getByText('환자 QR 코드 발급 요청')).toBeTruthy();
    expect(screen.getByText('의료진이 스캔하면 동선 안내 자동 시작')).toBeTruthy();
  });

  it('단계 번호 1, 2, 3 표시', () => {
    renderQRG();
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('하단 부가 안내 (이미 QR 열려 있는 경우)', () => {
    renderQRG();
    expect(
      screen.getByText(/이미 QR 코드 화면이 열려 있다면/),
    ).toBeTruthy();
  });

  it('「내 QR 코드 발급」 버튼 — auth 초기화 시 활성', () => {
    renderQRG();
    const btn = screen.getByTestId('qr-issue-button') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it('auth 미초기화 → 발급 버튼 비활성', () => {
    authState = { initialized: false };
    renderQRG();
    const btn = screen.getByTestId('qr-issue-button') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});

// =====================================================================
// 모드 토글 — placeholder ↔ displaying
// =====================================================================

describe('QRGuidePlaceholder — 모드 토글', () => {
  it('「내 QR 코드 발급」 클릭 → displaying 모드 (QRDisplay 마운트)', async () => {
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    expect(screen.getByTestId('qr-self-issue')).toBeTruthy();
    expect(screen.getByTestId('qrdisplay-stub')).toBeTruthy();
    // placeholder 는 미렌더
    expect(screen.queryByTestId('qr-guide-placeholder')).toBeNull();
  });

  it('「다시 안내 보기」 클릭 → placeholder 모드 복귀', async () => {
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    expect(screen.getByTestId('qr-self-issue')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '안내로 돌아가기' }));
    expect(screen.getByTestId('qr-guide-placeholder')).toBeTruthy();
    expect(screen.queryByTestId('qr-self-issue')).toBeNull();
  });
});

// =====================================================================
// QRDisplay onTokenGenerated 콜백 → issueSelfQRToken
// =====================================================================

describe('QRGuidePlaceholder — 토큰 발급 흐름', () => {
  it('QRDisplay 마운트 후 issueSelfQRToken(uid=uid-1) 호출', async () => {
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    await waitFor(() => expect(mockIssue).toHaveBeenCalled());
    expect(mockIssue).toHaveBeenCalledWith('mock-token-001', 'uid-1');
  });

  it('일반 에러 → placeholder 복귀 + 친근 메시지', async () => {
    mockIssue.mockRejectedValueOnce(new Error('PERMISSION_DENIED'));
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    await waitFor(() =>
      expect(screen.getByTestId('qr-issue-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('qr-issue-error').textContent).toMatch(
      /토큰 발급에 실패했습니다/,
    );
    // 모드 복귀
    expect(screen.getByTestId('qr-guide-placeholder')).toBeTruthy();
  });

  it('rate-limit 에러 → 분 단위 안내 + placeholder 복귀', async () => {
    mockIssue.mockRejectedValueOnce(new QRTokenRateLimitError(1800)); // 30분
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    await waitFor(() =>
      expect(screen.getByTestId('qr-issue-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('qr-issue-error').textContent).toMatch(
      /약 30분 후/,
    );
    expect(screen.getByTestId('qr-guide-placeholder')).toBeTruthy();
  });

  it('rate-limit 에러 retryAfter 1초 → 최소 1분 안내', async () => {
    mockIssue.mockRejectedValueOnce(new QRTokenRateLimitError(1));
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    await waitFor(() =>
      expect(screen.getByTestId('qr-issue-error')).toBeTruthy(),
    );
    expect(screen.getByTestId('qr-issue-error').textContent).toMatch(
      /약 1분 후/,
    );
  });

  it('성공 흐름 → 에러 미노출 + displaying 유지', async () => {
    mockIssue.mockResolvedValueOnce(undefined);
    renderQRG();
    fireEvent.click(screen.getByTestId('qr-issue-button'));
    // QRDisplay 마운트 후 onTokenGenerated 호출이 setTimeout 으로 발생
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(mockIssue).toHaveBeenCalled();
    expect(screen.queryByTestId('qr-issue-error')).toBeNull();
    expect(screen.getByTestId('qr-self-issue')).toBeTruthy();
  });
});
