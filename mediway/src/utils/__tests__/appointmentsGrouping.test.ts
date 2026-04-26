import { describe, it, expect } from 'vitest';
import {
  formatGroupHeader,
  FILTER_VISIBILITY_THRESHOLD,
  groupAppointments,
  groupKey,
} from '../appointmentsGrouping';
import type { AppointmentPatientIndex } from '@/types/appointment';

/** KST 자정의 epoch ms 헬퍼 — 결정적 입력 생성. */
function kstAt(y: number, m: number, d: number, h = 0, min = 0): number {
  return Date.UTC(y, m - 1, d, h - 9, min);
}

function appt(
  id: string,
  scheduledAt: number,
  department = '내과',
): AppointmentPatientIndex {
  return {
    id,
    department,
    scheduledAt,
    status: 'scheduled',
  } as AppointmentPatientIndex;
}

describe('groupKey', () => {
  const t = kstAt(2026, 4, 26, 14, 30); // 2026-04-26 14:30 KST

  it('day → YYYY-MM-DD', () => {
    expect(groupKey(t, 'day')).toBe('2026-04-26');
  });

  it('month → YYYY-MM', () => {
    expect(groupKey(t, 'month')).toBe('2026-04');
  });

  it('year → YYYY', () => {
    expect(groupKey(t, 'year')).toBe('2026');
  });

  it('월/일 한 자리 수도 zero-padding', () => {
    const t2 = kstAt(2026, 1, 5, 10, 0);
    expect(groupKey(t2, 'day')).toBe('2026-01-05');
    expect(groupKey(t2, 'month')).toBe('2026-01');
  });

  it('KST 자정 직후 vs 직전 — 일자 경계 정확', () => {
    // 2026-04-26 23:59 KST = UTC 2026-04-26 14:59 → KST 기준 그대로 26일
    const justBefore = kstAt(2026, 4, 26, 23, 59);
    // 2026-04-27 00:00 KST = UTC 2026-04-26 15:00 → KST 27일
    const justAfter = kstAt(2026, 4, 27, 0, 0);
    expect(groupKey(justBefore, 'day')).toBe('2026-04-26');
    expect(groupKey(justAfter, 'day')).toBe('2026-04-27');
  });

  it('UTC 같은 시각이라도 KST 시 단위가 일자 경계를 넘으면 다른 그룹', () => {
    // UTC 2026-04-25 16:00 = KST 2026-04-26 01:00 → 26일로 그룹화
    const utc1600 = Date.UTC(2026, 3, 25, 16, 0);
    expect(groupKey(utc1600, 'day')).toBe('2026-04-26');
  });
});

describe('formatGroupHeader', () => {
  it('day → "YYYY-MM-DD (요일)"', () => {
    // 2026-04-26 = 일요일 (검증: Date.UTC(2026, 3, 26).getUTCDay() === 0)
    expect(formatGroupHeader('2026-04-26', 'day')).toBe('2026-04-26 (일)');
  });

  it('month → "YYYY년 N월"', () => {
    expect(formatGroupHeader('2026-04', 'month')).toBe('2026년 4월');
    expect(formatGroupHeader('2026-12', 'month')).toBe('2026년 12월');
  });

  it('year → "YYYY년"', () => {
    expect(formatGroupHeader('2026', 'year')).toBe('2026년');
  });

  it('월 한 자리 수 — "1월"', () => {
    expect(formatGroupHeader('2026-01', 'month')).toBe('2026년 1월');
  });

  it('주 7개 요일 모두 매핑', () => {
    // 2026-04-20 = 월, 21=화, 22=수, 23=목, 24=금, 25=토, 26=일
    expect(formatGroupHeader('2026-04-20', 'day')).toMatch(/\(월\)/);
    expect(formatGroupHeader('2026-04-21', 'day')).toMatch(/\(화\)/);
    expect(formatGroupHeader('2026-04-22', 'day')).toMatch(/\(수\)/);
    expect(formatGroupHeader('2026-04-23', 'day')).toMatch(/\(목\)/);
    expect(formatGroupHeader('2026-04-24', 'day')).toMatch(/\(금\)/);
    expect(formatGroupHeader('2026-04-25', 'day')).toMatch(/\(토\)/);
    expect(formatGroupHeader('2026-04-26', 'day')).toMatch(/\(일\)/);
  });
});

describe('groupAppointments', () => {
  it('빈 list → 빈 그룹', () => {
    expect(groupAppointments([], 'day')).toEqual([]);
  });

  it('day 단위 — 같은 날짜 묶임', () => {
    const list = [
      appt('a1', kstAt(2026, 4, 26, 10, 0)),
      appt('a2', kstAt(2026, 4, 26, 14, 0)),
      appt('a3', kstAt(2026, 4, 27, 9, 0)),
    ];
    const groups = groupAppointments(list, 'day');
    expect(groups).toHaveLength(2);
    expect(groups[0].key).toBe('2026-04-26');
    expect(groups[0].entries).toHaveLength(2);
    expect(groups[1].key).toBe('2026-04-27');
    expect(groups[1].entries).toHaveLength(1);
  });

  it('month 단위 — 같은 달 묶임', () => {
    const list = [
      appt('a1', kstAt(2026, 4, 1, 10, 0)),
      appt('a2', kstAt(2026, 4, 30, 14, 0)),
      appt('a3', kstAt(2026, 5, 1, 9, 0)),
    ];
    const groups = groupAppointments(list, 'month');
    expect(groups.map((g) => g.key)).toEqual(['2026-04', '2026-05']);
    expect(groups[0].entries).toHaveLength(2);
  });

  it('year 단위 — 같은 년도 묶임', () => {
    const list = [
      appt('a1', kstAt(2025, 12, 31, 23, 0)),
      appt('a2', kstAt(2026, 1, 1, 1, 0)),
      appt('a3', kstAt(2026, 12, 31, 12, 0)),
    ];
    const groups = groupAppointments(list, 'year');
    expect(groups.map((g) => g.key)).toEqual(['2025', '2026']);
    expect(groups[1].entries).toHaveLength(2);
  });

  it('그룹 키 오름차순 정렬 (입력 순서 무관)', () => {
    const list = [
      appt('a1', kstAt(2026, 5, 1, 10, 0)),
      appt('a2', kstAt(2026, 4, 1, 10, 0)),
      appt('a3', kstAt(2026, 3, 1, 10, 0)),
    ];
    const groups = groupAppointments(list, 'month');
    expect(groups.map((g) => g.key)).toEqual(['2026-03', '2026-04', '2026-05']);
  });

  it('그룹 내부 scheduledAt 오름차순 정렬', () => {
    const list = [
      appt('a-late', kstAt(2026, 4, 26, 18, 0)),
      appt('a-early', kstAt(2026, 4, 26, 8, 0)),
      appt('a-mid', kstAt(2026, 4, 26, 12, 0)),
    ];
    const groups = groupAppointments(list, 'day');
    expect(groups[0].entries.map((e) => e.id)).toEqual([
      'a-early',
      'a-mid',
      'a-late',
    ]);
  });
});

describe('FILTER_VISIBILITY_THRESHOLD', () => {
  it('= 5', () => {
    expect(FILTER_VISIBILITY_THRESHOLD).toBe(5);
  });
});
