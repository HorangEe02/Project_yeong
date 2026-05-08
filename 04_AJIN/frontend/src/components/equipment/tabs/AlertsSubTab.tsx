// AlertsSubTab — F-alerts 서브탭 (긴급 조치 큐).

interface Props {
  alertCount: number;
}

export function AlertsSubTab({ alertCount }: Props) {
  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">URGENT · 긴급 조치 큐</div>
          <h2 className="lg-h2">즉시 대응 필요</h2>
        </div>
        <span className="lg-pill">{alertCount}건</span>
      </div>
      <div className="lg-urg-list">
        <div className="lg-urg-row crit">
          <span className="cat">CRITICAL</span>
          <div className="body">
            <b>도장 #1</b>
            <span> · Cpk 0.89 · Nelson Rule 1·2·5 위반</span>
          </div>
          <span className="time mono">14분 전</span>
          <button className="lg-btn sm">조치</button>
        </div>
        <div className="lg-urg-row warn">
          <span className="cat">HIGH</span>
          <div className="body">
            <b>용접 #2</b>
            <span> · Cpk 1.18 · 평균 이동 감지 (Rule 2)</span>
          </div>
          <span className="time mono">32분 전</span>
          <button className="lg-btn sm">조치</button>
        </div>
        <div className="lg-urg-row warn">
          <span className="cat">HIGH</span>
          <div className="body">
            <b>MD-007 (OBC-RR)</b>
            <span> · 잔여 사이클 15,000 (XGBoost 예측 D-3)</span>
          </div>
          <span className="time mono">1시간 전</span>
          <button className="lg-btn sm">정비 예약</button>
        </div>
      </div>
    </section>
  );
}
