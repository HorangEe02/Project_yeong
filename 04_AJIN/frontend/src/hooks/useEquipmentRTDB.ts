// Day 6 Phase 3 — RTDB live_alarms 구독.
// 다른 사용자가 푸시한 알람 도 합치도록 구독 — 본선 시연 멀티 사용자 시나리오.

import { useEffect, useState } from 'react';
import { off, onValue, ref as rtdbRef } from 'firebase/database';
import { rtdb } from '@lib/firebase';
import type { RecentViolation } from '@/types/equipment';

interface RTDBAlarmEntry {
  id?: string;
  process_id?: string;
  process_name?: string;
  rule_number?: number;
  severity?: string;
  message?: string;
  timestamp?: number;
  pushed_at?: number;
}

function normalize(key: string, raw: RTDBAlarmEntry): RecentViolation | null {
  if (!raw || typeof raw !== 'object') return null;
  const sev = raw.severity ?? 'info';
  const severity = (sev === 'critical' || sev === 'warning' || sev === 'info' ? sev : 'info') as RecentViolation['severity'];
  return {
    id: raw.id ?? key,
    process_id: raw.process_id ?? '',
    process_name: raw.process_name ?? '',
    rule_number: raw.rule_number ?? 0,
    severity,
    message: raw.message ?? '',
    timestamp: raw.timestamp ?? raw.pushed_at ?? Date.now(),
  };
}

export function useEquipmentRTDB(): RecentViolation[] {
  const [items, setItems] = useState<RecentViolation[]>([]);

  useEffect(() => {
    if (!rtdb) return;
    const r = rtdbRef(rtdb, 'live_alarms');
    const unsub = onValue(
      r,
      (snap) => {
        const val = snap.val() as Record<string, RTDBAlarmEntry> | null;
        if (!val) {
          setItems([]);
          return;
        }
        const list: RecentViolation[] = [];
        for (const [key, entry] of Object.entries(val)) {
          const n = normalize(key, entry);
          if (n) list.push(n);
        }
        // 최신순 + 최대 50개
        list.sort((a, b) => b.timestamp - a.timestamp);
        setItems(list.slice(0, 50));
      },
      () => {
        // 구독 권한 거부 시 빈 리스트 유지
        setItems([]);
      },
    );

    return () => off(r, 'value', unsub);
  }, []);

  return items;
}
