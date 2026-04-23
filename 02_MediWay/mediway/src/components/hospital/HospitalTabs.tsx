import { useRef, type KeyboardEvent } from 'react';
import type { TabDef, TabId } from '@/types/tabs';

/**
 * 대시보드 상단 탭 네비.
 *
 * - 모바일: 가로 스크롤 (overflow-x-auto)
 * - 데스크탑: 좌측 정렬 inline
 * - 현재 탭 강조 + aria-current
 * - 링크 요소 대신 button + onClick — useSearchParams 기반이라 라우팅 X
 * - C10: 화살표 키 좌우 이동 (WAI-ARIA tabs pattern), Home/End 지원
 */
export interface HospitalTabsProps {
  tabs: TabDef[];
  activeTab: TabId;
  onChange: (id: TabId) => void;
  /** 모바일에서 overflow 될 때 6개 초과 시 "더보기" 드롭다운으로 접을지 (P2 추후 확장) */
  compactOverflow?: boolean;
}

export function HospitalTabs({ tabs, activeTab, onChange }: HospitalTabsProps) {
  const tablistRef = useRef<HTMLDivElement | null>(null);
  const idx = tabs.findIndex((t) => t.id === activeTab);

  const focusTab = (nextIdx: number) => {
    const bounded = ((nextIdx % tabs.length) + tabs.length) % tabs.length;
    const btn = tablistRef.current?.querySelector<HTMLButtonElement>(
      `#tab-${tabs[bounded].id}`,
    );
    btn?.focus();
    onChange(tabs[bounded].id);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    switch (e.key) {
      case 'ArrowRight':
        e.preventDefault();
        focusTab(idx + 1);
        break;
      case 'ArrowLeft':
        e.preventDefault();
        focusTab(idx - 1);
        break;
      case 'Home':
        e.preventDefault();
        focusTab(0);
        break;
      case 'End':
        e.preventDefault();
        focusTab(tabs.length - 1);
        break;
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-4 py-3 lg:max-w-5xl">
      <div
        ref={tablistRef}
        role="tablist"
        aria-label="병원 대시보드 탭"
        onKeyDown={onKeyDown}
        className="mx-auto inline-flex max-w-full gap-1 overflow-x-auto rounded-xl bg-surface-container-high p-1 lg:flex lg:justify-center"
      >
        {tabs.map((t) => {
          const active = t.id === activeTab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`tabpanel-${t.id}`}
              id={`tab-${t.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(t.id)}
              className={`shrink-0 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                active
                  ? 'bg-surface-container-lowest text-primary shadow-ambient'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
