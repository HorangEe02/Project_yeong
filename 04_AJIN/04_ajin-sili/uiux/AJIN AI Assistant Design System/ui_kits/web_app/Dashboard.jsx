// Dashboard.jsx
function Dashboard({ onNav }) {
  const metrics = [
    { v: '329', en: 'EMPLOYEES', ko: '사원' },
    { v: '201', en: 'ERROR CODES', ko: '에러코드' },
    { v: '29', en: 'DEPARTMENTS', ko: '부서' },
    { v: '33', en: 'ACCOUNTS', ko: '테스트 계정' },
  ];
  const modules = [
    { code: 'A', key: 'search', en: 'PEOPLE SEARCH', ko: '인원 검색', notes: ['FTS5 + ChromaDB','Semantic hybrid','ML 의도 분류'] },
    { code: 'B', key: 'draft', en: 'DOCUMENT DRAFT', ko: '문서 작성', notes: ['Few-shot RAG','품질평가 5기준','7포맷 다운로드'] },
    { code: 'C', key: 'chat', en: 'AI ASSISTANT', ko: 'AI 도우미', notes: ['SSE 스트리밍','비전 (Gemma 4)','업무·교육 듀얼 모드'] },
    { code: 'D', key: 'compliance', en: 'COMPLIANCE', ko: '법규 모니터', notes: ['리스크 100점','관세 시뮬레이터','Plotly 간트차트'] },
    { code: 'E', key: 'admin', en: 'HR ADMIN', ko: '인사 관리', notes: ['6탭 인사관리','보안 감사','히트맵'] },
    { code: 'F', key: 'equipment', en: 'EQUIPMENT AI', ko: '설비 / 공정', notes: ['Nelson 8 Rules','XGBoost 잔여수명','TF-IDF 에러검색'] },
  ];
  return (
    <div className="page">
      <div className="page-h">
        <h1>대시보드</h1>
        <span className="ko">DASHBOARD · CORE OVERVIEW</span>
        <span className="grow" />
        <span className="v">v3.5 · 2026.04.26</span>
      </div>
      <div className="metrics-grid">
        {metrics.map(m => (
          <div className="metric-card" key={m.en}>
            <span className="corner-tl" /><span className="corner-br" />
            <div className="v">{m.v}</div>
            <div className="en">{m.en}</div>
            <div className="ko">{m.ko}</div>
          </div>
        ))}
      </div>
      <div className="modules-grid">
        {modules.map(m => (
          <div className="module-card" key={m.key} onClick={() => onNav(m.key)}>
            <div className="row1"><span className="code">MOD · {m.code}</span><span className="en">{m.en}</span></div>
            <div className="ko">{m.ko}</div>
            <ul>{m.notes.map(n => <li key={n}>{n}</li>)}</ul>
          </div>
        ))}
      </div>
    </div>
  );
}
window.Dashboard = Dashboard;
