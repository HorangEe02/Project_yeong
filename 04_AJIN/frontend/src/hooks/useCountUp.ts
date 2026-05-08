// 메트릭 카운트업 애니메이션 (0.6초 + reduced-motion 존중)

import { useEffect, useState } from 'react';

interface Options {
  durationMs?: number;
  startValue?: number;
}

export function useCountUp(target: number, opts: Options = {}): number {
  const { durationMs = 600, startValue = 0 } = opts;
  const [value, setValue] = useState(startValue);

  useEffect(() => {
    // reduced-motion 존중
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    if (prefersReduced) {
      setValue(target);
      return;
    }

    const start = performance.now();
    const begin = startValue;
    const delta = target - begin;
    let raf = 0;

    const tick = (now: number) => {
      const elapsed = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - elapsed, 3); // ease-out cubic
      setValue(Math.round(begin + delta * eased));
      if (elapsed < 1) {
        raf = requestAnimationFrame(tick);
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return value;
}
