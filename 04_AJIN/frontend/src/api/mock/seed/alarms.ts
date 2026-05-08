// 진행 중 알람 시드 — Dashboard 빠른 액션 카드 + 우측 패널

export type AlarmSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface MockAlarm {
  id: string;
  severity: AlarmSeverity;
  title: string;
  detail: string;
  module: 'A' | 'B' | 'C' | 'D' | 'E' | 'F';
  timestamp: string;
  acknowledged: boolean;
}

export const ALARMS: MockAlarm[] = [
  {
    id: 'A-001',
    severity: 'HIGH',
    title: 'SPC OBC 위반 감지',
    detail: 'OBC 공정 Cpk 1.18 — Nelson Rule 2 (8점 연속 평균 한쪽)',
    module: 'F',
    timestamp: '2026-04-27T08:30:00+09:00',
    acknowledged: false,
  },
  {
    id: 'A-002',
    severity: 'MEDIUM',
    title: 'JST 누유',
    detail: '10번 프레스 라인 유압 누유 점검 필요',
    module: 'F',
    timestamp: '2026-04-27T07:15:00+09:00',
    acknowledged: false,
  },
  {
    id: 'A-003',
    severity: 'CRITICAL',
    title: '산안법 시행 D-30',
    detail: '프레스 안전거리 300→400mm 변경. 본사·천안1·천안2 라인 검토 필요',
    module: 'D',
    timestamp: '2026-04-27T06:00:00+09:00',
    acknowledged: false,
  },
];

export const SEVERITY_LABEL: Record<AlarmSeverity, { ko: string; en: string; color: string }> = {
  CRITICAL: { ko: '위급', en: 'CRITICAL', color: 'var(--hud-red)' },
  HIGH: { ko: '높음', en: 'HIGH', color: 'var(--hud-orange)' },
  MEDIUM: { ko: '보통', en: 'MEDIUM', color: 'var(--hud-blue)' },
  LOW: { ko: '낮음', en: 'LOW', color: 'var(--hud-green)' },
};
