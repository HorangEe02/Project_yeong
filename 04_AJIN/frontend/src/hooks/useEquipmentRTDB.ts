// Backend live alarm polling hook.
//
// Replaces legacy Firebase RTDB `live_alarms` reads with the Postgres-backed
// `/api/live-alarms/recent` endpoint.

import { useEffect, useState } from 'react';
import { fetchLiveAlarmsRecent, type LiveAlarmItem } from '@api/liveAlarms';
import type { RecentViolation, Severity } from '@/types/equipment';

const POLL_MS = 5000;

function normalizeSeverity(raw: string): Severity {
  const severity = raw.trim().toLowerCase();
  if (severity === 'critical') return 'critical';
  if (severity === 'high' || severity === 'warning') return 'warning';
  return 'info';
}

function normalizeTimestamp(alarm: LiveAlarmItem): number {
  const payloadTimestamp = alarm.payload.timestamp ?? alarm.payload.pushed_at;
  if (typeof payloadTimestamp === 'number') return payloadTimestamp;
  if (typeof payloadTimestamp === 'string') {
    const parsed = Number(payloadTimestamp);
    if (Number.isFinite(parsed)) return parsed;
  }

  const detectedAt = alarm.payload.detected_at;
  if (typeof detectedAt === 'string') {
    const parsed = Date.parse(detectedAt);
    if (Number.isFinite(parsed)) return parsed;
  }

  const createdAt = Date.parse(alarm.created_at);
  return Number.isFinite(createdAt) ? createdAt : Date.now();
}

function readString(payload: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
}

function readRuleNumber(payload: Record<string, unknown>): number {
  const value = payload.rule_number;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function normalize(alarm: LiveAlarmItem): RecentViolation {
  const process = readString(alarm.payload, 'process_id', 'process');
  return {
    id: alarm.id,
    process_id: process,
    process_name: readString(alarm.payload, 'process_name', 'process') || process,
    rule_number: readRuleNumber(alarm.payload),
    severity: normalizeSeverity(alarm.severity),
    message: alarm.message,
    timestamp: normalizeTimestamp(alarm),
    data_class: String(alarm.payload.data_class ?? 'real') as RecentViolation['data_class'],
    source_system: readString(alarm.payload, 'source_system', 'source') || 'live_alarms',
    source_label: readString(alarm.payload, 'source_label', 'source') || 'live_alarms',
  };
}

export function useEquipmentRTDB(): RecentViolation[] {
  const [items, setItems] = useState<RecentViolation[]>([]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const refresh = async () => {
      try {
        const res = await fetchLiveAlarmsRecent('equipment', 50);
        if (cancelled) return;
        setItems(res.alarms.map(normalize).sort((a, b) => b.timestamp - a.timestamp));
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
