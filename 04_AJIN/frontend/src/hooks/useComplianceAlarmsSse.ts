// D 컴플라이언스 알람 SSE 스트림 (v4.2 P4).
//
// useComplianceAlarms (polling) 의 대안. 동일한 `Alarm[]` 형상 반환 →
// 호출부 변경 없이 swap 가능.
//
// EventSource 는 자동 재연결을 지원하지만 401 만료 시 client.ts 의 3-tier 가
// 동작하지 않으므로 (HTTP 헤더 인터셉트 불가), 만료 감지 시 onError → 재구독
// 흐름을 명시한다.

import { useEffect, useRef, useState } from 'react';

import type { ComplianceAlarm } from '@api/compliance';
import type { Alarm } from '@/types/alarms';

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

interface StreamPayload {
  items?: ComplianceAlarm[];
  total?: number;
  error?: string;
}

export interface UseComplianceAlarmsSseOptions {
  intervalSec?: number;
  enabled?: boolean;
  /** SSE 미지원 또는 401 만료 등으로 stream 종료 시 호출자가 polling fallback 결정 */
  onClose?: () => void;
}

/**
 * SSE 기반 D 알람 구독. EventSource 가 자동 재연결.
 * 401 발생 시 EventSource 가 errored → onClose 콜백 → 호출자가 useComplianceAlarms 로 fallback.
 */
export function useComplianceAlarmsSse(opts: UseComplianceAlarmsSseOptions = {}): Alarm[] {
  const { intervalSec = 30, enabled = true, onClose } = opts;
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!enabled) return;
    if (typeof EventSource === 'undefined') {
      onCloseRef.current?.();
      return;
    }

    const url = `/api/compliance/alarms/stream?interval=${intervalSec}`;
    const es = new EventSource(url, { withCredentials: true });

    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data) as StreamPayload;
        if (payload.error) {
          console.warn('[compliance-alarms-sse] server error:', payload.error);
          return;
        }
        if (payload.items) {
          setAlarms(payload.items.map(toAlarm));
        }
      } catch (err) {
        console.warn('[compliance-alarms-sse] parse error:', err);
      }
    };

    es.onerror = () => {
      // EventSource 자동 재연결 시도. readyState=CLOSED 면 종료 콜백.
      if (es.readyState === EventSource.CLOSED) {
        onCloseRef.current?.();
      }
    };

    return () => {
      es.close();
    };
  }, [enabled, intervalSec]);

  return alarms;
}
