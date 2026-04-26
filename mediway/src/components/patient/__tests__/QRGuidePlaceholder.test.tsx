import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QRGuidePlaceholder } from '../QRGuidePlaceholder';

describe('QRGuidePlaceholder', () => {
  it('region role + aria-label="QR 안내"', () => {
    render(<QRGuidePlaceholder />);
    expect(screen.getByRole('region', { name: 'QR 안내' })).toBeTruthy();
  });

  it('testid "qr-guide-placeholder" 노출', () => {
    render(<QRGuidePlaceholder />);
    expect(screen.getByTestId('qr-guide-placeholder')).toBeTruthy();
  });

  it('헤드라인 "QR 코드를 받아 안내를 시작하세요"', () => {
    render(<QRGuidePlaceholder />);
    expect(screen.getByText('QR 코드를 받아 안내를 시작하세요')).toBeTruthy();
  });

  it('3단계 안내가 순서대로 표시', () => {
    render(<QRGuidePlaceholder />);
    expect(screen.getByText('병원 안내 데스크 방문')).toBeTruthy();
    expect(screen.getByText('환자 QR 코드 발급 요청')).toBeTruthy();
    expect(screen.getByText('의료진이 스캔하면 동선 안내 자동 시작')).toBeTruthy();
  });

  it('단계 번호 1, 2, 3 표시', () => {
    render(<QRGuidePlaceholder />);
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('하단 부가 안내 (이미 QR 열려 있는 경우)', () => {
    render(<QRGuidePlaceholder />);
    expect(
      screen.getByText(/이미 QR 코드 화면이 열려 있다면/),
    ).toBeTruthy();
  });
});
