import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useSearchParams } from 'react-router-dom';
import type { HospitalProfile } from '@/types/hospital';

// PatientMapBrowseView 는 HospitalMapContainer + mapStore + 정적 데이터 의존성을 끌어옴 — 본 단위 테스트
// 비범위로 stub. browse 모드 분기만 검증.
vi.mock('@/components/patient/PatientMapBrowseView', () => ({
  PatientMapBrowseView: () => <div data-testid="map-browse-stub" />,
}));

// EmergencyCallCard 는 navigator.geolocation 의존 — emergency 모드는 별도 테스트 영역
vi.mock('@/components/patient/EmergencyCallCard', () => ({
  EmergencyCallCard: () => <div data-testid="emergency-stub" />,
}));

import { GuideTab } from '../GuideTab';
import { HospitalProvider } from '@/contexts/HospitalContext';

function renderAt(
  initialPath: string = '/h/demo/patient/home?tab=guide',
  features?: Record<string, boolean>,
) {
  const profile: HospitalProfile = {
    id: 'demo',
    name: 'MediWay 데모',
    status: 'active',
    ...(features ? { features } : {}),
  };
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <HospitalProvider value={{ slug: 'demo', profile }}>
        <GuideTab />
        <UrlProbe />
      </HospitalProvider>
    </MemoryRouter>,
  );
}

function UrlProbe() {
  const [params] = useSearchParams();
  return <pre data-testid="url-params">{params.toString()}</pre>;
}

beforeEach(() => {
  // no shared state to reset
});

describe('GuideTab — 기본 렌더', () => {
  it('헤더 + 안내 모드 토글 + 두 panel 마운트', () => {
    renderAt();
    expect(screen.getByText('안내')).toBeTruthy();
    expect(screen.getByRole('tablist', { name: '안내 모드' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /지도 보기/ })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /QR 안내/ })).toBeTruthy();
    // mount-all — 두 panel 모두 DOM
    expect(screen.getByTestId('map-browse-stub')).toBeTruthy();
    expect(screen.getByTestId('qr-guide-placeholder')).toBeTruthy();
  });
});

describe('GuideTab — default mode', () => {
  it('?mode= 누락 → guide (QR 안내) 활성', () => {
    renderAt('/h/demo/patient/home?tab=guide');
    const qrTab = screen.getByRole('tab', { name: /QR 안내/ });
    const browseTab = screen.getByRole('tab', { name: /지도 보기/ });
    expect(qrTab.getAttribute('aria-selected')).toBe('true');
    expect(browseTab.getAttribute('aria-selected')).toBe('false');
  });

  it('알 수 없는 mode 값 → guide 로 fallback', () => {
    renderAt('/h/demo/patient/home?tab=guide&mode=unknown');
    const qrTab = screen.getByRole('tab', { name: /QR 안내/ });
    expect(qrTab.getAttribute('aria-selected')).toBe('true');
  });
});

describe('GuideTab — URL 진입', () => {
  it('?mode=browse 진입 → 지도 보기 활성', () => {
    renderAt('/h/demo/patient/home?tab=guide&mode=browse');
    const browseTab = screen.getByRole('tab', { name: /지도 보기/ });
    expect(browseTab.getAttribute('aria-selected')).toBe('true');
  });

  it('hidden 속성 토글 — guide 모드에선 map panel hidden', () => {
    const { container } = renderAt('/h/demo/patient/home?tab=guide');
    const browsePanel = container.querySelector(
      'div[aria-label="지도 보기 패널"]',
    );
    const qrPanel = container.querySelector(
      'div[aria-label="QR 안내 패널"]',
    );
    expect(browsePanel?.hasAttribute('hidden')).toBe(true);
    expect(qrPanel?.hasAttribute('hidden')).toBe(false);
  });

  it('hidden 속성 토글 — browse 모드에선 qr panel hidden', () => {
    const { container } = renderAt('/h/demo/patient/home?tab=guide&mode=browse');
    const browsePanel = container.querySelector(
      'div[aria-label="지도 보기 패널"]',
    );
    const qrPanel = container.querySelector(
      'div[aria-label="QR 안내 패널"]',
    );
    expect(browsePanel?.hasAttribute('hidden')).toBe(false);
    expect(qrPanel?.hasAttribute('hidden')).toBe(true);
  });
});

describe('GuideTab — 모드 전환 시 URL 갱신', () => {
  it('[지도 보기] 클릭 → ?mode=browse 추가 + tab 보존', () => {
    renderAt('/h/demo/patient/home?tab=guide');
    fireEvent.click(screen.getByRole('tab', { name: /지도 보기/ }));
    const params = screen.getByTestId('url-params').textContent;
    expect(params).toContain('tab=guide');
    expect(params).toContain('mode=browse');
  });

  it('[QR 안내] 클릭 → ?mode= 제거 (default 로 환원)', () => {
    renderAt('/h/demo/patient/home?tab=guide&mode=browse');
    fireEvent.click(screen.getByRole('tab', { name: /QR 안내/ }));
    const params = screen.getByTestId('url-params').textContent ?? '';
    expect(params.includes('mode=')).toBe(false);
    // tab 은 보존
    expect(params).toContain('tab=guide');
  });

  it('전환 후 aria-selected 갱신', () => {
    renderAt('/h/demo/patient/home?tab=guide');
    fireEvent.click(screen.getByRole('tab', { name: /지도 보기/ }));
    expect(
      screen.getByRole('tab', { name: /지도 보기/ }).getAttribute('aria-selected'),
    ).toBe('true');
    expect(
      screen.getByRole('tab', { name: /QR 안내/ }).getAttribute('aria-selected'),
    ).toBe('false');
  });
});

describe('GuideTab — 다른 query 보존', () => {
  it('?tab=guide 외 추가 파라미터 (foo=bar) 도 보존', () => {
    renderAt('/h/demo/patient/home?tab=guide&foo=bar');
    fireEvent.click(screen.getByRole('tab', { name: /지도 보기/ }));
    const params = screen.getByTestId('url-params').textContent ?? '';
    expect(params).toContain('foo=bar');
    expect(params).toContain('mode=browse');
  });
});
