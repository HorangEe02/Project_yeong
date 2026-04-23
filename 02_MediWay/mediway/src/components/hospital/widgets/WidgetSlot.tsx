import { Children, type ReactNode } from 'react';

/**
 * 홈 탭 위젯 컨테이너 — v2 §Phase 2 "위젯 수 상한 3+1" 강제.
 *
 * - 3개 필수 + 1개 선택 슬롯 = 최대 4
 * - 4개 초과 시 런타임 console.warn + 초과분 잘라냄 (프로덕션 UI 붕괴 방지)
 */
export const MAX_WIDGETS = 4;

export function WidgetSlot({ children }: { children: ReactNode }) {
  const arr = Children.toArray(children);
  let toRender = arr;
  if (arr.length > MAX_WIDGETS) {
    console.warn(
      `[WidgetSlot] 위젯 수가 ${arr.length}개입니다. v2 정책에 따라 최대 ${MAX_WIDGETS}개만 노출됩니다.`,
    );
    toRender = arr.slice(0, MAX_WIDGETS);
  }
  return (
    <div
      className="flex flex-col gap-3"
      role="list"
      aria-label="홈 위젯 목록"
    >
      {toRender.map((child, i) => (
        <div key={i} role="listitem">
          {child}
        </div>
      ))}
    </div>
  );
}
