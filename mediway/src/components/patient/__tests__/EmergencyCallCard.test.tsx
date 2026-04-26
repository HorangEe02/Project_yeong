import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { EmergencyCallCard } from '../EmergencyCallCard';

// --- navigator.geolocation mock ---

type SuccessCb = (position: GeolocationPosition) => void;
type ErrorCb = (err: GeolocationPositionError) => void;

let lastSuccess: SuccessCb | null = null;
let lastError: ErrorCb | null = null;
const mockGetCurrentPosition = vi.fn(
  (success: SuccessCb, error?: ErrorCb) => {
    lastSuccess = success;
    lastError = error ?? null;
  },
);

function installGeolocation() {
  Object.defineProperty(global.navigator, 'geolocation', {
    configurable: true,
    value: { getCurrentPosition: mockGetCurrentPosition },
  });
}

function uninstallGeolocation() {
  // @ts-expect-error — 명시적 제거 (jsdom 기본은 undefined)
  delete (global.navigator as { geolocation?: unknown }).geolocation;
}

beforeEach(() => {
  mockGetCurrentPosition.mockClear();
  lastSuccess = null;
  lastError = null;
  installGeolocation();
});

afterEach(() => {
  uninstallGeolocation();
});

// --- helpers ---

function fireSuccess(lat: number, lng: number, accuracy = 25): void {
  if (!lastSuccess) throw new Error('getCurrentPosition not yet called');
  // GeolocationPosition 형 부분 충족 — 본 컴포넌트가 사용하는 필드만 채움
  const position = {
    coords: {
      latitude: lat,
      longitude: lng,
      accuracy,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: null,
    },
    timestamp: Date.now(),
  } as GeolocationPosition;
  act(() => lastSuccess!(position));
}

function fireError(code: 1 | 2 | 3): void {
  if (!lastError) throw new Error('error callback not registered');
  // GeolocationPositionError 의 PERMISSION_DENIED=1 / POSITION_UNAVAILABLE=2 / TIMEOUT=3
  const err = {
    code,
    message: 'mock',
    PERMISSION_DENIED: 1 as const,
    POSITION_UNAVAILABLE: 2 as const,
    TIMEOUT: 3 as const,
  } as unknown as GeolocationPositionError;
  act(() => lastError!(err));
}

// =====================================================================
// 기본 렌더
// =====================================================================

describe('EmergencyCallCard — 기본 렌더', () => {
  it('region role + aria-label="응급 호출" + testid', () => {
    render(<EmergencyCallCard />);
    expect(screen.getByRole('region', { name: '응급 호출' })).toBeTruthy();
    expect(screen.getByTestId('emergency-call-card')).toBeTruthy();
  });

  it('헤드라인 "응급 호출" + 안내 메시지', () => {
    render(<EmergencyCallCard />);
    expect(screen.getByText('응급 호출')).toBeTruthy();
    expect(screen.getByText(/119 에 신고하고/)).toBeTruthy();
  });

  it('초기 상태 — 「현재 위치 가져오기」 + 「119 신고」 표시', () => {
    render(<EmergencyCallCard />);
    expect(screen.getByTestId('emergency-location-request')).toBeTruthy();
    expect(screen.getByTestId('emergency-call-button')).toBeTruthy();
  });

  it('하단 안내 — 위치 자동 전송 없음 명시', () => {
    render(<EmergencyCallCard />);
    expect(
      screen.getByText(/위치 정보 자동 전송 기능이 없습니다/),
    ).toBeTruthy();
  });
});

// =====================================================================
// 위치 가져오기 흐름
// =====================================================================

describe('EmergencyCallCard — 위치', () => {
  it('「현재 위치 가져오기」 클릭 → loading 상태 + getCurrentPosition 호출', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    expect(mockGetCurrentPosition).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('emergency-location-loading')).toBeTruthy();
  });

  it('성공 → 위도/경도/정확도 + 지도 링크', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    fireSuccess(37.566, 126.978, 25);
    expect(screen.getByTestId('emergency-location-success')).toBeTruthy();
    expect(screen.getByText(/위도: 37\.566000/)).toBeTruthy();
    expect(screen.getByText(/경도: 126\.978000/)).toBeTruthy();
    expect(screen.getByText(/±25m/)).toBeTruthy();
    const link = screen.getByTestId(
      'emergency-location-map-link',
    ) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe(
      'https://maps.google.com/?q=37.566,126.978',
    );
  });

  it('PERMISSION_DENIED → denied 상태 + 다시 시도 버튼', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    fireError(1);
    expect(screen.getByTestId('emergency-location-denied')).toBeTruthy();
    expect(screen.getByText(/위치 권한이 거부되었습니다/)).toBeTruthy();
  });

  it('TIMEOUT → error 상태 with 시간 초과 메시지', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    fireError(3);
    expect(screen.getByTestId('emergency-location-error')).toBeTruthy();
    expect(screen.getByText(/시간 초과/)).toBeTruthy();
  });

  it('POSITION_UNAVAILABLE → error 상태 generic', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    fireError(2);
    expect(screen.getByTestId('emergency-location-error')).toBeTruthy();
    expect(screen.getByText(/가져오지 못했습니다/)).toBeTruthy();
  });

  it('navigator.geolocation 미지원 → unsupported 상태', () => {
    uninstallGeolocation(); // navigator.geolocation 제거
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    expect(screen.getByTestId('emergency-location-unsupported')).toBeTruthy();
    expect(mockGetCurrentPosition).not.toHaveBeenCalled();
    installGeolocation();
  });
});

// =====================================================================
// 119 통화 흐름 (확인 dialog)
// =====================================================================

describe('EmergencyCallCard — 119 통화', () => {
  it('1차 클릭 → 확인 dialog (alertdialog role) 표시', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-call-button'));
    expect(screen.getByRole('alertdialog')).toBeTruthy();
    expect(screen.getByTestId('emergency-confirm-dialog')).toBeTruthy();
    expect(screen.getByText(/정말 119 에 전화하시겠습니까/)).toBeTruthy();
  });

  it('확인 dialog 의 「전화 걸기」 링크 → href="tel:119"', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-call-button'));
    const callLink = screen.getByTestId(
      'emergency-confirm-button',
    ) as HTMLAnchorElement;
    expect(callLink.getAttribute('href')).toBe('tel:119');
    expect(callLink.tagName.toLowerCase()).toBe('a');
  });

  it('「취소」 클릭 → dialog 닫힘 + 「119 신고」 버튼 복귀', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-call-button'));
    expect(screen.getByTestId('emergency-confirm-dialog')).toBeTruthy();
    fireEvent.click(screen.getByTestId('emergency-cancel-button'));
    expect(screen.queryByTestId('emergency-confirm-dialog')).toBeNull();
    expect(screen.getByTestId('emergency-call-button')).toBeTruthy();
  });

  it('「전화 걸기」 클릭 → dialog 닫힘 (cancelConfirm 호출)', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-call-button'));
    fireEvent.click(screen.getByTestId('emergency-confirm-button'));
    // 클릭 후 dialog 가 닫히고 다시 「119 신고」 버튼 표시 (실제 통화는 OS 가 처리)
    expect(screen.queryByTestId('emergency-confirm-dialog')).toBeNull();
    expect(screen.getByTestId('emergency-call-button')).toBeTruthy();
  });
});

// =====================================================================
// 통합 — 위치 + 통화 같이
// =====================================================================

describe('EmergencyCallCard — 통합', () => {
  it('위치 성공 후 119 신고 흐름 정상 동작', () => {
    render(<EmergencyCallCard />);
    fireEvent.click(screen.getByTestId('emergency-location-request'));
    fireSuccess(37.5, 127.0, 10);
    expect(screen.getByTestId('emergency-location-success')).toBeTruthy();
    fireEvent.click(screen.getByTestId('emergency-call-button'));
    expect(screen.getByTestId('emergency-confirm-dialog')).toBeTruthy();
    // 위치 카드도 여전히 표시
    expect(screen.getByTestId('emergency-location-success')).toBeTruthy();
  });
});
