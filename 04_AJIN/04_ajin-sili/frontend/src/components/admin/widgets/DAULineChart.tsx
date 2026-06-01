// DAULineChart — .lg-dau-chart inline SVG line + gold gradient fill.

interface Props {
  series: { date: string; dau: number }[];
  height?: number;
}

export function DAULineChart({ series, height = 180 }: Props) {
  if (series.length === 0) {
    return <div style={{ color: 'var(--hud-text-dim)', fontSize: 13 }}>표시할 데이터가 없습니다.</div>;
  }

  const w = 600;
  const h = height;
  const max = Math.max(1, ...series.map((s) => s.dau));
  const stepX = series.length > 1 ? w / (series.length - 1) : w;
  const points = series.map((s, i) => {
    const x = i * stepX;
    const y = h - (s.dau / max) * (h - 20) - 10;
    return [x, y] as const;
  });
  const path = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const fillPath = `${path} L${w},${h} L0,${h} Z`;

  return (
    <div className="lg-dau-chart">
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="dau-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--hud-primary)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--hud-primary)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={fillPath} fill="url(#dau-grad)" />
        <path d={path} stroke="var(--hud-primary)" strokeWidth={2} fill="none" />
        {points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill="var(--hud-primary)" />
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--hud-font-mono)', fontSize: 10, color: 'var(--hud-text-dim)', marginTop: 4 }}>
        <span>{series[0]?.date ?? ''}</span>
        <span>{series.at(-1)?.date ?? ''}</span>
      </div>
    </div>
  );
}
