// SecurityAlertCard — .lg-sec.{crit|warn|info} 마크업.

interface Props {
  kind: 'crit' | 'warn' | 'info';
  en: string;
  title: string;
  count: number;
  desc: string;
  detail?: string;
}

export function SecurityAlertCard({ kind, en, title, count, desc, detail }: Props) {
  return (
    <div className={`lg-sec ${kind}`}>
      <div className="lg-sec-top">
        <span className="lg-sec-dot" />
        <span className="lg-sec-en">{en}</span>
      </div>
      <div className="lg-sec-count">
        {count}
        <span>건</span>
      </div>
      <div className="lg-sec-title">{title}</div>
      <div style={{ fontSize: 13, color: 'var(--hud-text-dim)' }}>{desc}</div>
      {detail && (
        <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)', marginTop: 6 }}>
          {detail}
        </div>
      )}
    </div>
  );
}
