import { useState, type ReactNode } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { Skeleton } from './Skeleton';
import { useIsMobile } from '@hooks/useBreakpoint';

interface Props<T> {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  pagination?: boolean;
  pageSize?: number;
  sortable?: boolean;
  loading?: boolean;
  emptyText?: string;
  onRowClick?: (row: T) => void;
  toolbar?: ReactNode;
  /** v4.4 — 모바일(≤640px)에서 row 별 카드 렌더 함수. 미제공 시 column header×value 자동 stack. */
  mobileCard?: (row: T, index: number) => ReactNode;
}

export function DataTable<T>({
  data,
  columns,
  pagination = true,
  pageSize = 10,
  sortable = true,
  loading = false,
  emptyText = '데이터가 없습니다',
  onRowClick,
  toolbar,
  mobileCard,
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const isMobile = useIsMobile();

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: sortable ? getSortedRowModel() : undefined,
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: pagination ? getPaginationRowModel() : undefined,
    initialState: pagination ? { pagination: { pageSize } } : undefined,
  });

  if (loading) {
    return <Skeleton variant="card" count={3} />;
  }

  // v4.4 — 모바일 카드 뷰 자동 전환 (≤640px)
  if (isMobile) {
    const rows = table.getRowModel().rows;
    return (
      <div>
        {toolbar && <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'flex-end' }}>{toolbar}</div>}
        {rows.length === 0 ? (
          <div className="ui-table-empty" style={{ padding: 20, textAlign: 'center', color: 'var(--hud-text-dim)' }}>
            {emptyText}
          </div>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {rows.map((row, idx) => (
              <li
                key={row.id}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                style={{
                  borderRadius: 'var(--r-card-mobile, 14px)',
                  border: '1px solid var(--hud-border)',
                  background: 'var(--hud-surface)',
                  padding: 14,
                  cursor: onRowClick ? 'pointer' : 'default',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
              >
                {mobileCard ? (
                  mobileCard(row.original, idx)
                ) : (
                  row.getVisibleCells().map((cell) => {
                    const header = cell.column.columnDef.header;
                    const headerText = typeof header === 'string' ? header : cell.column.id;
                    return (
                      <div
                        key={cell.id}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'baseline',
                          gap: 12,
                          fontSize: 13,
                        }}
                      >
                        <span style={{ color: 'var(--hud-text-dim)', fontSize: 11, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                          {headerText}
                        </span>
                        <span style={{ color: 'var(--hud-text)', textAlign: 'right', minWidth: 0 }}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </span>
                      </div>
                    );
                  })
                )}
              </li>
            ))}
          </ul>
        )}
        {pagination && table.getPageCount() > 1 && (
          <div className="ui-table-pagination" style={{ marginTop: 10 }}>
            <span>
              {table.getState().pagination.pageIndex + 1} / {table.getPageCount()} 페이지 ·{' '}
              {table.getFilteredRowModel().rows.length}건
            </span>
            <span style={{ display: 'flex', gap: 4 }}>
              <button className="btn ghost sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
                ← 이전
              </button>
              <button className="btn ghost sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
                다음 →
              </button>
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      {toolbar && <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'flex-end' }}>{toolbar}</div>}
      <div className="ui-table-wrap">
        <table className="ui-table">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted();
                  return (
                    <th
                      key={h.id}
                      data-sortable={sortable && h.column.getCanSort()}
                      data-sorted={sorted || undefined}
                      onClick={sortable && h.column.getCanSort() ? h.column.getToggleSortingHandler() : undefined}
                    >
                      {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                      {sortable && h.column.getCanSort() && (
                        <span className="ui-sort">
                          {sorted === 'asc' ? <ChevronUp size={12} /> : sorted === 'desc' ? <ChevronDown size={12} /> : '↕'}
                        </span>
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="ui-table-empty">{emptyText}</td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  style={{ cursor: onRowClick ? 'pointer' : 'default' }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {pagination && table.getPageCount() > 1 && (
        <div className="ui-table-pagination">
          <span>
            {table.getState().pagination.pageIndex + 1} / {table.getPageCount()} 페이지 ·{' '}
            {table.getFilteredRowModel().rows.length}건
          </span>
          <span style={{ display: 'flex', gap: 4 }}>
            <button
              className="btn ghost sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              ← 이전
            </button>
            <button
              className="btn ghost sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              다음 →
            </button>
          </span>
        </div>
      )}
    </div>
  );
}
