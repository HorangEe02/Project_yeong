// Day 6 Phase 3 — SPC 알람 폴링 (옵션 B).
// 5초 간격 백엔드 폴링 → 새 위반 감지 시 RTDB push + Toast + 사이드바 점멸.

import { useEffect, useRef } from 'react';
import { ref as rtdbRef, push as rtdbPush, serverTimestamp } from 'firebase/database';
import { auth, rtdb } from '@lib/firebase';
import { fetchSPCViolationsRecent } from '@api/equipment';
import { useToastStore, type ToastType } from '@store/toast';
import { useUIStore } from '@store/ui';
import { useEquipmentStore } from '@store/equipment';
import type { RecentViolation, Severity } from '@/types/equipment';

const POLL_MS = 5000;
const SEVERITY_TOAST: Record<Severity, ToastType> = {
  critical: 'error',
  warning: 'warning',
  info: 'info',
};

interface Options {
  /** 활성화 여부 (페이지 unmount 시 false) */
  enabled?: boolean;
}

export function useSPCAlarms(options: Options = {}) {
  const { enabled = true } = options;
  const lastSeenRef = useRef<number>(0);
  const seenIdsRef = useRef<Set<string>>(new Set());
  const addToast = useToastStore((s) => s.addToast);
  const incActiveAlarms = useUIStore((s) => s.incActiveAlarms);
  const appendViolation = useEquipmentStore((s) => s.appendViolation);
  const setLastSeenViolationsTs = useEquipmentStore((s) => s.setLastSeenViolationsTs);
  const lastSeenViolationsTs = useEquipmentStore((s) => s.lastSeenViolationsTs);

  useEffect(() => {
    if (!enabled) return;
    // 초기 lastSeen 은 store 의 마지막 ts 로 시작 (재진입 시 중복 알람 방지)
    lastSeenRef.current = lastSeenViolationsTs;
  }, [enabled, lastSeenViolationsTs]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const tick = async () => {
      try {
        const res = await fetchSPCViolationsRecent(lastSeenRef.current, 20);
        if (cancelled) return;
        const fresh: RecentViolation[] = [];
        for (const v of res.items) {
          if (seenIdsRef.current.has(v.id)) continue;
          seenIdsRef.current.add(v.id);
          fresh.push(v);
        }

        if (fresh.length === 0) return;

        for (const v of fresh) {
          // RTDB push (인증 + RTDB 사용 가능 시에만)
          if (auth?.currentUser && rtdb) {
            try {
              await rtdbPush(rtdbRef(rtdb, 'live_alarms'), {
                ...v,
                pushed_at: serverTimestamp(),
              });
            } catch {
              // RTDB 권한 부재 — 조용히 skip (로컬 toast 만)
            }
          }
          appendViolation(v);
          incActiveAlarms();
          addToast({
            type: SEVERITY_TOAST[v.severity],
            message: v.message,
            duration: 6000,
          });
        }

        const newTs = Date.now();
        lastSeenRef.current = newTs;
        setLastSeenViolationsTs(newTs);
      } catch {
        // 네트워크/인증 오류 — 다음 tick 에서 재시도
      }
    };

    // 초기 1회 + 5초 폴링
    void tick();
    timer = setInterval(tick, POLL_MS);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [enabled, addToast, incActiveAlarms, appendViolation, setLastSeenViolationsTs]);
}
