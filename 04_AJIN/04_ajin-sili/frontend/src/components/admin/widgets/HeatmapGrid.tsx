// HeatmapGrid — .lg-heatmap 형태의 부서×기능 또는 본부×직급 히트맵.
// 셀 강도는 column 별 max 대비 비율로 계산.

interface Props {
  rows: string[];
  cols: string[];
  matrix: Record<string, Record<string, number>>;
  rowLabel?: string;
  colLabel?: string;
}

export function HeatmapGrid({ rows, cols, matrix, rowLabel = '항목', colLabel = '컬럼' }: Props) {
  if (rows.length === 0 || cols.length === 0) {
    return <div style={{ color: 'var(--hud-text-dim)', fontSize: 13 }}>표시할 데이터가 없습니다.</div>;
  }

  const max = Math.max(
    1,
    ...rows.flatMap((r) => cols.map((c) => matrix[r]?.[c] ?? 0)),
  );

  const gridTemplate = `120px repeat(${cols.length}, minmax(48px, 1fr))`;

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: gridTemplate, gap: 4, minWidth: cols.length * 48 + 130 }}>
        <div style={{ fontFamily: 'var(--hud-font-mono)', fontSize: 9, letterSpacing: '0.14em', color: 'var(--hud-text-dim)', textTransform: 'uppercase', alignSelf: 'end', paddingBottom: 4 }}>
          {rowLabel} \ {colLabel}
        </div>
        {cols.map((c) => (
          <div
            key={c}
            style={{
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 11,
              color: 'var(--hud-text-dim)',
              textAlign: 'center',
              padding: '4px 2px',
              borderBottom: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            }}
          >
            {c}
          </div>
        ))}
        {rows.map((r) => (
          <div key={r} style={{ display: 'contents' }}>
            <div style={{ fontSize: 12, color: 'var(--hud-text)', padding: '6px 4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {r}
            </div>
            {cols.map((c) => {
              const v = matrix[r]?.[c] ?? 0;
              const ratio = v / max;
              const bg = `color-mix(in oklab, var(--hud-primary) ${Math.round(ratio * 80)}%, transparent)`;
              const text = ratio > 0.5 ? 'var(--hud-bg)' : 'var(--hud-text)';
              return (
                <div
                  key={`${r}-${c}`}
                  title={`${r} × ${c}: ${v}`}
                  style={{
                    background: bg,
                    color: text,
                    fontSize: 11,
                    fontFamily: 'var(--hud-font-mono)',
                    textAlign: 'center',
                    padding: '6px 2px',
                    borderRadius: 4,
                    minHeight: 28,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {v || ''}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
