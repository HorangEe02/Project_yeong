// Day 6 Phase 3 — SPC 알람 폴링 (옵션 B).
// 5초 간격 백엔드 폴링 → 새 위반 감지 시 Toast + 사이드바 점멸.
// Firebase RTDB push 경로는 제거되었고, backend/Postgres live_alarms API가 표준 경로다.
// v4.7 Sprint 2 P0 (축 ③) — 토스트에 "메일 초안" 액션 버튼 추가.
//   클릭 시 /draft?template=spc_violation&violation_id=<id> 로 이동.

import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
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
          appendViolation(v);
          incActiveAlarms();
          // v4.7 Sprint 2 P0 (축 ③) — critical/warning 위반에 "메일 초안" 액션 부착.
          const isActionable = v.severity === 'critical' || v.severity === 'warning';
          addToast({
            type: SEVERITY_TOAST[v.severity],
            message: v.message,
            duration: 8000,
            ...(isActionable
              ? {
                  action: {
                    label: '메일 초안',
                    onClick: () => {
                      navigate(
                        `/draft?template=spc_violation&violation_id=${encodeURIComponent(v.id)}`,
                      );
                    },
                  },
                }
              : {}),
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
  }, [enabled, addToast, incActiveAlarms, appendViolation, setLastSeenViolationsTs, navigate]);
}
