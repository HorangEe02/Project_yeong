// D 컴플라이언스 실시간 알람 — polling 훅 (v4.2 Phase 2).
//
// Option B 패턴: 백엔드는 GET /compliance/alarms/recent 만 노출, 프론트엔드가 60초 폴링.
// 결과를 dashboard.tsx 의 `Alarm` 형상으로 변환해 SPC(F) 알람과 한 배열로 통합.

import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchComplianceAlarms, type ComplianceAlarm } from '@api/compliance';
import type { Alarm } from '@/types/alarms';

const DEFAULT_POLL_MS = 60_000;

function toAlarm(a: ComplianceAlarm): Alarm {
  return {
    id: a.id,
    severity: a.severity,
    title: a.title,
    detail: a.detail,
    module: 'D',
    timestamp: a.timestamp,
    acknowledged: a.acknowledged,
  };
}

export interface UseComplianceAlarmsOptions {
  pollMs?: number;
  enabled?: boolean;
}

/**
 * 60초 간격으로 D 컴플라이언스 알람을 폴링.
 * 401 만료는 `client.ts` 의 3-tier auto-recovery 가 처리.
 *
 * @returns Alarm[] — dashboard.tsx 의 알람 통합 배열에 그대로 concat 가능
 */
export function useComplianceAlarms(opts: UseComplianceAlarmsOptions = {}): Alarm[] {
  const { pollMs = DEFAULT_POLL_MS, enabled = true } = opts;
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const inflightRef = useRef(false);

  const load = useCallback(async () => {
    if (inflightRef.current) return;
    inflightRef.current = true;
    try {
      const res = await fetchComplianceAlarms(0, 50);
      setAlarms(res.items.map(toAlarm));
    } catch (err) {
      // 폴링 — 일시 실패는 console.warn 만 (UI 토스트는 useOnlineStatus 가 담당)
      console.warn('[compliance-alarms] poll failed:', err instanceof Error ? err.message : err);
    } finally {
      inflightRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    void load();
    const id = window.setInterval(() => { void load(); }, pollMs);
    return () => window.clearInterval(id);
  }, [enabled, load, pollMs]);

  return alarms;
}
