import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MAX_WIDGETS, WidgetSlot } from '../WidgetSlot';
import { TodayScheduleWidget } from '../TodayScheduleWidget';
import { WaitQueueWidget } from '../WaitQueueWidget';
import { EmergencyCtaWidget } from '../EmergencyCtaWidget';

describe('WidgetSlot', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('4개 이하 children은 모두 렌더', () => {
    render(
      <WidgetSlot>
        <div>A</div>
        <div>B</div>
        <div>C</div>
      </WidgetSlot>,
    );
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
  });

  it('MAX_WIDGETS 초과 시 warn + 초과분 잘라냄', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    render(
      <WidgetSlot>
        <div>1</div>
        <div>2</div>
        <div>3</div>
        <div>4</div>
        <div>5</div>
      </WidgetSlot>,
    );
    expect(screen.getAllByRole('listitem')).toHaveLength(MAX_WIDGETS);
    expect(warn).toHaveBeenCalled();
    expect(warn.mock.calls[0][0]).toMatch(/5개입니다/);
  });

  it('role=list + aria-label 접근성', () => {
    render(
      <WidgetSlot>
        <div>X</div>
      </WidgetSlot>,
    );
    const list = screen.getByRole('list', { name: /홈 위젯/ });
    expect(list).toBeTruthy();
  });
});

describe('TodayScheduleWidget', () => {
  it('타이틀 + 빈 상태 메시지', () => {
    render(<TodayScheduleWidget />);
    expect(screen.getByText('오늘 일정')).toBeTruthy();
    expect(screen.getByText(/예정된 진료나 검사가 없습니다/)).toBeTruthy();
  });
});

describe('WaitQueueWidget', () => {
  it('타이틀 + placeholder 메시지', () => {
    render(<WaitQueueWidget />);
    expect(screen.getByText('진료 대기')).toBeTruthy();
    expect(screen.getByText(/대기 순번/)).toBeTruthy();
  });
});

describe('EmergencyCtaWidget', () => {
  it('기본 상태에서 CTA 버튼 노출', () => {
    render(<EmergencyCtaWidget />);
    expect(screen.getByText('응급실 바로가기')).toBeTruthy();
    expect(screen.getByRole('button', { name: '응급 도움 받기' })).toBeTruthy();
  });

  it('CTA 클릭 시 확인 모달 노출 (119 오발신 방지)', () => {
    render(<EmergencyCtaWidget />);
    fireEvent.click(screen.getByRole('button', { name: '응급 도움 받기' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeTruthy();
    expect(dialog.getAttribute('aria-modal')).toBe('true');

    // 두 가지 주요 액션이 모두 보임
    expect(screen.getByText('원내 응급실 길 안내')).toBeTruthy();
    expect(screen.getByText('119 전화')).toBeTruthy();
    expect(screen.getByText('취소')).toBeTruthy();
  });

  it('119 링크는 tel:119로 걸림', () => {
    render(<EmergencyCtaWidget />);
    fireEvent.click(screen.getByRole('button', { name: '응급 도움 받기' }));
    const tel = screen.getByText('119 전화').closest('a');
    expect(tel?.getAttribute('href')).toBe('tel:119');
  });

  it('취소 버튼으로 모달 닫힘', () => {
    render(<EmergencyCtaWidget />);
    fireEvent.click(screen.getByRole('button', { name: '응급 도움 받기' }));
    expect(screen.queryByRole('dialog')).toBeTruthy();
    fireEvent.click(screen.getByText('취소'));
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
