import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  width?: string;
  className?: string;
  /** 모바일 자동 카드 렌더링에서 제외 (예: 헤더 없는 actions 컬럼은 별도 표시) */
  hideOnMobile?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyLabel?: string;
  loading?: boolean;
  /** 모바일에서 각 행을 커스텀 카드로 렌더 */
  mobileCard?: (row: T) => ReactNode;
  /** 모바일 카드 fallback 비활성화 (외부에서 카드 레이아웃을 별도 제공할 때) */
  disableMobileCard?: boolean;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyLabel = '항목이 없습니다',
  loading,
  mobileCard,
  disableMobileCard,
}: DataTableProps<T>) {
  const table = (
    <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-ambient">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-surface-container-high bg-surface-container-low">
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-on-surface-variant ${c.className ?? ''}`}
                  style={c.width ? { width: c.width } : undefined}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-10 text-center text-sm text-on-surface-variant"
                >
                  불러오는 중...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-10 text-center text-sm text-on-surface-variant"
                >
                  {emptyLabel}
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={rowKey(r)}
                  className="border-b border-surface-container-high/60 last:border-0 hover:bg-surface-container-low/60"
                >
                  {columns.map((c) => (
                    <td key={c.key} className={`px-4 py-3 ${c.className ?? ''}`}>
                      {c.cell(r)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  if (disableMobileCard) {
    return table;
  }

  const headerColumns = columns.filter((c) => !c.hideOnMobile && c.header);
  const actionColumns = columns.filter((c) => !c.hideOnMobile && !c.header);

  const mobile = (
    <div className="flex flex-col gap-2">
      {loading ? (
        <p className="rounded-xl bg-surface-container-lowest p-6 text-center text-sm text-on-surface-variant shadow-ambient">
          불러오는 중...
        </p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl bg-surface-container-lowest p-6 text-center text-sm text-on-surface-variant shadow-ambient">
          {emptyLabel}
        </p>
      ) : (
        rows.map((r) => (
          <div
            key={rowKey(r)}
            className="rounded-xl bg-surface-container-lowest p-4 shadow-ambient"
          >
            {mobileCard ? (
              mobileCard(r)
            ) : (
              <div className="flex flex-col gap-2">
                {headerColumns.map((c) => (
                  <div key={c.key} className="flex items-start justify-between gap-3">
                    <span className="shrink-0 text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                      {c.header}
                    </span>
                    <div className="min-w-0 flex-1 text-right text-sm">{c.cell(r)}</div>
                  </div>
                ))}
                {actionColumns.length > 0 && (
                  <div className="flex items-center justify-end gap-2 border-t border-surface-container-high/60 pt-2">
                    {actionColumns.map((c) => (
                      <div key={c.key}>{c.cell(r)}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );

  return (
    <>
      <div className="hidden lg:block">{table}</div>
      <div className="lg:hidden">{mobile}</div>
    </>
  );
}
