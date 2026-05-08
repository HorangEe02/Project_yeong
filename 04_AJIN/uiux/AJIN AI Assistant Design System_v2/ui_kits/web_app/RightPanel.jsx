// RightPanel.jsx
function RightPanel() {
  const r = 36, c = 2 * Math.PI * r, gpu = 0.42;
  return (
    <aside className="right-panel">
      <div className="sb-h"><span>SYSTEM ANALYTICS <span className="ko">시스템 분석</span></span><span className="pill" style={{color:'#7FD89E'}}>REALTIME ●</span></div>
      <div className="gauge">
        <svg viewBox="0 0 96 96">
          <circle cx="48" cy="48" r={r} fill="none" stroke="var(--hud-border)" strokeWidth="6" />
          <circle cx="48" cy="48" r={r} fill="none" stroke="var(--hud-primary)" strokeWidth="6" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1-gpu)} transform="rotate(-90 48 48)" style={{filter:'drop-shadow(0 0 6px var(--hud-primary))'}} />
          <text x="48" y="50" textAnchor="middle" dominantBaseline="middle" fontSize="20" fontWeight="700" fill="var(--hud-primary)" fontFamily="Pretendard, sans-serif">42%</text>
        </svg>
        <span className="lbl">GPU · UTILIZATION</span>
      </div>
      <div className="metric-row">
        <div className="metric-mini"><span className="k">LATENCY</span><span className="v">124<small style={{fontSize:11,color:'var(--hud-text-dim)'}}>ms</small></span></div>
        <div className="metric-mini"><span className="k">QPS</span><span className="v">8.4<small style={{fontSize:11,color:'var(--hud-text-dim)'}}>k</small></span></div>
      </div>
      <div className="sb-section">
        <div className="sb-h"><span>DATA INGESTION <span className="ko">데이터 수집</span></span></div>
        {[
          { k: 'ERROR_CODES', v: '201/201', p: 1 },
          { k: 'MOLD_ASSETS', v: '25/25', p: 1 },
          { k: 'SPC_PROCESS', v: '5/5', p: 1 },
          { k: 'DRAWINGS', v: '418/418', p: 1 },
          { k: 'INSPECTIONS', v: '64/72', p: 0.89 },
        ].map(r => (
          <div className="ingest-row" key={r.k}>
            <div className="top"><span>{r.k}</span><b>{r.v}</b></div>
            <div className="bar"><span style={{width: `${r.p*100}%`}} /></div>
          </div>
        ))}
      </div>
    </aside>
  );
}
window.RightPanel = RightPanel;
