// useComplianceRTDB — D 컴플라이언스 알람 hook.
//
// `useEquipmentRTDB` 와 동일 패턴 — `/api/live-alarms/recent` polling 으로
// `live_alarms` 백엔드 통로를 공유하되, `module="D"` 필드로 필터링한다.
// (백엔드: `features.compliance.d1_alert.pipeline.dispatch_compliance_alarms_to_rtdb`
//  가 alarm_aggregator → firebase_rtdb.push_alarm 체인으로 D 알람을 push 한다.)
//
// useComplianceAlarms (Phase 1) / useComplianceAlarmsSse (Phase 2) 와 별개로,
// 본 hook 은 RTDB 통합 통로 (F SPC 와 동일) 를 통과한 D 알람을 직접 구독한다.

import { useEffect, useState } from 'react';
import { fetchLiveAlarmsRecent, type LiveAlarmItem } from '@api/liveAlarms';

const POLL_MS = 5000;

export type ComplianceSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type ComplianceSource =
  | 'law_change'
  | 'dday'
  | 'impact_score'
  | 'unresolved'
  | 'trend';

export interface ComplianceRtdbAlarm {
  id: string;
  module: 'D';
  source: ComplianceSource | string;
  severity: ComplianceSeverity;
  title: string;
  detail: string;
  regulation_id: string;
  effective_date: string;
  timestamp: number;
  acknowledged: boolean;
}

function normalizeSeverity(raw: string): ComplianceSeverity {
  const v = raw.trim().toUpperCase();
  if (v === 'CRITICAL') return 'CRITICAL';
  if (v === 'HIGH') return 'HIGH';
  if (v === 'MEDIUM') return 'MEDIUM';
  if (v === 'LOW') return 'LOW';
  return 'MEDIUM';
}

function readString(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === 'string' ? value : '';
}

function normalizeTimestamp(alarm: LiveAlarmItem): number {
  const payloadTs = alarm.payload.timestamp;
  if (typeof payloadTs === 'number') return payloadTs;
  if (typeof payloadTs === 'string') {
    const parsed = Date.parse(payloadTs);
    if (Number.isFinite(parsed)) return parsed;
  }
  const created = Date.parse(alarm.created_at);
  return Number.isFinite(created) ? created : Date.now();
}

function isDModule(alarm: LiveAlarmItem): boolean {
  const module = alarm.payload.module;
  return typeof module === 'string' && module.toUpperCase() === 'D';
}

function normalize(alarm: LiveAlarmItem): ComplianceRtdbAlarm {
  return {
    id: alarm.id,
    module: 'D',
    source: readString(alarm.payload, 'source') || 'law_change',
    severity: normalizeSeverity(alarm.severity),
    title: readString(alarm.payload, 'title') || alarm.message,
    detail: readString(alarm.payload, 'detail'),
    regulation_id: readString(alarm.payload, 'regulation_id'),
    effective_date: readString(alarm.payload, 'effective_date'),
    timestamp: normalizeTimestamp(alarm),
    acknowledged: !!alarm.acknowledged_at,
  };
}

export function useComplianceRTDB(): ComplianceRtdbAlarm[] {
  const [items, setItems] = useState<ComplianceRtdbAlarm[]>([]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const refresh = async () => {
      try {
        const res = await fetchLiveAlarmsRecent('compliance', 50);
        if (cancelled) return;
        const dOnly = res.alarms.filter(isDModule).map(normalize);
        dOnly.sort((a, b) => b.timestamp - a.timestamp);
        setItems(dOnly);
      } catch {
        if (!cancelled) setItems([]);
      }
    };

    void refresh();
    timer = setInterval(refresh, POLL_MS);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  return items;
}
