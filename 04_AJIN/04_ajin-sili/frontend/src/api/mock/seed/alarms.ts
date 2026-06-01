// MSW handlers 용 알람 mock 시드.
// v4.2 M3 — 타입·SEVERITY_LABEL 은 `@/types/alarms` 로 이관. 본 파일은 mock 데이터만 보유.

import type { Alarm } from '@/types/alarms';
export type { Alarm, AlarmSeverity } from '@/types/alarms';
export { SEVERITY_LABEL } from '@/types/alarms';

export const ALARMS: Alarm[] = [
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
