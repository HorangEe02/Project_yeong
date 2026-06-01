// Day 5++ — GPU Utilization 원형 게이지 (DAY5_PLUS_HUD_PLAN Section 8-4).
// SVG circle 기반 — 외부 npm 추가 0. 토큰만 사용.

interface Props {
  value: number; // 0~100
  size?: number;
}

export function GPUGauge({ value, size = 160 }: Props) {
  const clamped = Math.max(0, Math.min(100, value));
  const r = size / 2 - 12;
  const C = 2 * Math.PI * r;
  const offset = C * (1 - clamped / 100);
  const cx = size / 2;
  const cy = size / 2;

  return (
    <div className="gpu-gauge" role="img" aria-label={`GPU ${clamped.toFixed(0)}%`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        {/* track */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="var(--hud-border)"
          strokeWidth="6"
          strokeDasharray="3 4"
        />
        {/* progress */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="var(--hud-primary)"
          strokeWidth="6"
          strokeDasharray={C}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: 'stroke-dashoffset 0.5s ease-out' }}
        />
        {/* value */}
        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="var(--hud-font)"
          fontSize={size * 0.22}
          fontWeight={700}
          fill="var(--hud-primary)"
        >
          {clamped.toFixed(0)}%
        </text>
        <text
          x={cx}
          y={cy + size * 0.18}
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="var(--hud-font)"
          fontSize="9"
          letterSpacing="0.12em"
          fill="var(--hud-text-dim)"
        >
          GPU · UTILIZATION
        </text>
      </svg>
    </div>
  );
}
