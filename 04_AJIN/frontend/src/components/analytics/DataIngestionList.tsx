// Day 5++ — DATA INGESTION 5종 (ERROR_CODES, MOLD_ASSETS, SPC_PROCESS, DRAWINGS, INSPECTIONS).
// 시안의 진행률 바 패턴 — EN 라벨 + 카운터 + 가는 골드 진행률.

import type { IngestionItem } from '@api/analytics';

interface Props {
  items: IngestionItem[];
}

export function DataIngestionList({ items }: Props) {
  return (
    <ul className="ingestion-list" aria-label="Data ingestion status">
      {items.map((it) => {
        const pct = it.total > 0 ? Math.min(100, (it.current / it.total) * 100) : 0;
        const complete = it.current >= it.total;
        return (
          <li key={it.label} className="ingestion-row">
            <div className="ingestion-row__top">
              <span className="ingestion-row__label">
                <span className="label-en">{it.label}</span>
                {it.labelKo && (
                  <span
                    className="label-ko"
                    style={{ marginLeft: 6, opacity: 0.7, fontSize: '0.85em' }}
                  >
                    · {it.labelKo}
                  </span>
                )}
              </span>
              <span
                className="ingestion-row__count"
                data-complete={complete || undefined}
              >
                {it.current}/{it.total}
              </span>
            </div>
            <div className="ingestion-row__track" aria-hidden="true">
              <span
                className="ingestion-row__fill"
                style={{ width: `${pct.toFixed(1)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
