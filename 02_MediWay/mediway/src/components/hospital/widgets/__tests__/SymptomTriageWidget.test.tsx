import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const requestTriageMock = vi.fn();
vi.mock('@/services/triage', () => ({
  requestTriage: (s: string) => requestTriageMock(s),
}));

import { SymptomTriageWidget } from '../SymptomTriageWidget';

beforeEach(() => {
  requestTriageMock.mockReset();
});

describe('SymptomTriageWidget', () => {
  it('초기 — 타이틀 + 고지문 + 버튼 비활성화', () => {
    render(<SymptomTriageWidget />);
    expect(screen.getByText('AI 진료과 추천')).toBeTruthy();
    expect(screen.getByText(/참고용이며 진단이 아닙니다/)).toBeTruthy();
    const btn = screen.getByRole('button', { name: /진료과 추천/ });
    expect(btn.hasAttribute('disabled')).toBe(true);
  });

  it('증상 3자 이상 → 제출 버튼 활성화', () => {
    render(<SymptomTriageWidget />);
    const ta = screen.getByPlaceholderText(/기침과 미열/);
    fireEvent.change(ta, { target: { value: '기침 2일' } });
    const btn = screen.getByRole('button', { name: /진료과 추천/ });
    expect(btn.hasAttribute('disabled')).toBe(false);
  });

  it('제출 성공 → 추천 목록 렌더 + disclaimer 노출', async () => {
    requestTriageMock.mockResolvedValueOnce({
      recommendations: [
        { department: '내과', confidence: 0.9, reason: '호흡기 증상' },
        { department: '이비인후과', confidence: 0.6, reason: '목 통증' },
      ],
      disclaimer: '본 추천은 참고용이며 진단이 아닙니다.',
    });
    render(<SymptomTriageWidget />);
    fireEvent.change(screen.getByPlaceholderText(/기침과 미열/), {
      target: { value: '기침 고열' },
    });
    fireEvent.click(screen.getByRole('button', { name: /진료과 추천/ }));
    await waitFor(() => {
      expect(screen.getByText('내과')).toBeTruthy();
    });
    expect(screen.getByText('이비인후과')).toBeTruthy();
    expect(screen.getByText('신뢰도 90%')).toBeTruthy();
    expect(screen.getByText('본 추천은 참고용이며 진단이 아닙니다.')).toBeTruthy();
    expect(requestTriageMock).toHaveBeenCalledWith('기침 고열');
  });

  it('제출 실패 → error 메시지 렌더', async () => {
    requestTriageMock.mockRejectedValueOnce(new Error('rate limit'));
    render(<SymptomTriageWidget />);
    fireEvent.change(screen.getByPlaceholderText(/기침과 미열/), {
      target: { value: '기침 고열' },
    });
    fireEvent.click(screen.getByRole('button', { name: /진료과 추천/ }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/rate limit/)).toBeTruthy();
  });

  it('"다시 입력" 버튼 → 초기 상태 복귀', async () => {
    requestTriageMock.mockResolvedValueOnce({
      recommendations: [
        { department: '내과', confidence: 0.9, reason: '이유' },
      ],
      disclaimer: 'd',
    });
    render(<SymptomTriageWidget />);
    fireEvent.change(screen.getByPlaceholderText(/기침과 미열/), {
      target: { value: '기침 3일' },
    });
    fireEvent.click(screen.getByRole('button', { name: /진료과 추천/ }));
    await waitFor(() => {
      expect(screen.getByText('내과')).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('button', { name: '다시 입력' }));
    expect(screen.queryByText('내과')).toBeNull();
    expect(screen.getByPlaceholderText(/기침과 미열/)).toBeTruthy();
  });
});
