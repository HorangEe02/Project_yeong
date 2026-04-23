import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const useHospitalMock = vi.fn();
vi.mock('@/hooks/useHospital', () => ({
  useHospital: () => useHospitalMock(),
}));

import { HospitalGate } from '../HospitalGate';

describe('HospitalGate', () => {
  it('loading 상태일 때 로딩 메시지', () => {
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: null,
      loading: true,
      error: null,
      notFound: false,
    });
    render(
      <HospitalGate>
        <div>CHILD</div>
      </HospitalGate>,
    );
    expect(screen.getByRole('status').textContent).toContain(
      '병원 정보를 불러오는 중',
    );
    expect(screen.queryByText('CHILD')).toBeNull();
  });

  it('error 상태일 때 에러 메시지', () => {
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: null,
      loading: false,
      error: new Error('permission denied'),
      notFound: false,
    });
    render(
      <HospitalGate>
        <div>CHILD</div>
      </HospitalGate>,
    );
    expect(screen.getByRole('alert').textContent).toContain('permission denied');
  });

  it('notFound일 때 안내 메시지', () => {
    useHospitalMock.mockReturnValue({
      slug: 'ghost',
      hospital: null,
      loading: false,
      error: null,
      notFound: true,
    });
    render(
      <HospitalGate>
        <div>CHILD</div>
      </HospitalGate>,
    );
    expect(screen.getByText('존재하지 않는 병원입니다')).toBeTruthy();
    expect(screen.queryByText('CHILD')).toBeNull();
  });

  it('정상 로드 시 children 렌더', () => {
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: {
        name: 'Demo',
        slug: 'demo',
        themeColor: '#004e9f',
        contractStatus: 'active',
        features: {},
        createdAt: 1,
        updatedAt: 1,
      },
      loading: false,
      error: null,
      notFound: false,
    });
    render(
      <HospitalGate>
        <div>CHILD</div>
      </HospitalGate>,
    );
    expect(screen.getByText('CHILD')).toBeTruthy();
  });

  it('loadingFallback 커스터마이즈', () => {
    useHospitalMock.mockReturnValue({
      slug: 'demo',
      hospital: null,
      loading: true,
      error: null,
      notFound: false,
    });
    render(
      <HospitalGate loadingFallback={<div>커스텀 로딩</div>}>
        <div>CHILD</div>
      </HospitalGate>,
    );
    expect(screen.getByText('커스텀 로딩')).toBeTruthy();
  });
});
