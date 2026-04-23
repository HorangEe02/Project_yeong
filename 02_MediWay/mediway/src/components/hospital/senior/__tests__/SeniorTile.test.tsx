import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Calendar } from 'lucide-react';
import { SeniorTile } from '../SeniorTile';

describe('SeniorTile', () => {
  it('label + sub + 아이콘 렌더', () => {
    render(<SeniorTile icon={Calendar} label="병원 예약하기" sub="새 진료" />);
    expect(screen.getByText('병원 예약하기')).toBeTruthy();
    expect(screen.getByText('새 진료')).toBeTruthy();
  });

  it('badge가 있으면 숫자 노출', () => {
    render(<SeniorTile icon={Calendar} label="내 순번" badge={3} />);
    expect(screen.getByLabelText('알림 3건')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('badge가 0이거나 없으면 숨김', () => {
    const { rerender } = render(
      <SeniorTile icon={Calendar} label="내 순번" badge={0} />,
    );
    expect(screen.queryByLabelText(/알림/)).toBeNull();
    rerender(<SeniorTile icon={Calendar} label="내 순번" />);
    expect(screen.queryByLabelText(/알림/)).toBeNull();
  });

  it('disabled — aria-disabled + 클릭 무효', () => {
    const onClick = vi.fn();
    render(
      <SeniorTile icon={Calendar} label="가족" onClick={onClick} disabled />,
    );
    const btn = screen.getByRole('button', { name: /가족/ });
    expect(btn.getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('href 있으면 anchor (disabled 아님)', () => {
    render(<SeniorTile icon={Calendar} label="외부" href="https://x" />);
    const a = screen.getByText('외부').closest('a');
    expect(a?.getAttribute('href')).toBe('https://x');
  });
});
