// 페르소나의 widget array 를 받아 병렬 fetch + 그리드 렌더.
// 각 위젯의 source 함수는 독립적으로 실패해도 다른 위젯에 영향 X (allSettled).

import { useEffect, useState } from 'react';
import type { WidgetSpec, WidgetData } from './types';
import { WidgetRenderer } from './Widgets';

interface Props {
  widgets: WidgetSpec[];
}

export function WidgetGrid({ widgets }: Props) {
  const [dataMap, setDataMap] = useState<Record<string, WidgetData | null>>({});
  const [loadingMap, setLoadingMap] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    const initLoading: Record<string, boolean> = {};
    widgets.forEach((w) => { initLoading[w.id] = true; });
    setLoadingMap(initLoading);

    const tasks = widgets.map(async (w) => {
      try {
        const result = await Promise.resolve(w.source());
        return { id: w.id, data: result, ok: true as const };
      } catch {
        return { id: w.id, data: null, ok: false as const };
      }
    });

    Promise.allSettled(tasks).then((settled) => {
      if (cancelled) return;
      const nextData: Record<string, WidgetData | null> = {};
      const nextLoading: Record<string, boolean> = {};
      settled.forEach((s) => {
        if (s.status === 'fulfilled') {
          nextData[s.value.id] = s.value.data;
          nextLoading[s.value.id] = false;
        }
      });
      setDataMap(nextData);
      setLoadingMap(nextLoading);
    });

    // 자동 갱신 (refreshSec 지정된 위젯만)
    const intervals: number[] = [];
    widgets.forEach((w) => {
      if (!w.refreshSec) return;
      const id = window.setInterval(async () => {
        try {
          const data = await Promise.resolve(w.source());
          if (!cancelled) setDataMap((prev) => ({ ...prev, [w.id]: data }));
        } catch { /* keep stale */ }
      }, w.refreshSec * 1000);
      intervals.push(id);
    });

    return () => {
      cancelled = true;
      intervals.forEach(window.clearInterval);
    };
  }, [widgets]);

  return (
    <div className="metrics-grid">
      {widgets.map((w) => (
        <WidgetRenderer
          key={w.id}
          spec={w}
          data={dataMap[w.id] ?? null}
          loading={loadingMap[w.id] ?? false}
        />
      ))}
    </div>
  );
}
