// LeftSidebar.jsx
const MODULES = [
  { code: 'A', key: 'search', en: '인원 검색', icon: 'Employee' },
  { code: 'B', key: 'draft', en: '문서 작성', icon: 'Documents' },
  { code: 'C', key: 'chat', en: 'AI 도우미', icon: 'Onboarding' },
  { code: 'D', key: 'compliance', en: '법규 모니터', icon: 'Compliance' },
  { code: 'E', key: 'admin', en: '인사 관리', icon: 'Admin' },
  { code: 'F', key: 'equipment', en: '설비 AI', icon: 'Equipment' },
];

function LeftSidebar({ active, onNav, theme, onTheme, streaming }) {
  return (
    <aside className="sidebar">
      <div className="sb-brand">
        <div className="row">
          <img src="../../assets/ajin_symbol.svg" alt="" width="32" height="32" />
          <div>
            <div className="name">AJIN INDUSTRY</div>
            <div className="sub">AI ASSISTANT</div>
          </div>
        </div>
        <div className="ver">v3.5 // KNU SILLI 2026</div>
      </div>

      <div className="sb-user">
        <div className="who">
          <span className="name">김아진 / KIM A.J.</span>
          <span className="role">품질보증팀 · L6 ADMIN</span>
        </div>
        <div className="actions">
          <button className="btn"><Icons.Profile size={12} /> PROFILE</button>
          <button className="btn"><Icons.Logout size={12} /> LOGOUT</button>
        </div>
      </div>

      <button className={'module-btn' + (active==='dashboard'?' active':'')} onClick={() => onNav('dashboard')}>
        <span className="glyph"><Icons.Dashboard size={14} /></span>
        <span className="label">DASHBOARD</span>
        <span className="ko">대시보드</span>
      </button>

      <div className="sb-section">
        <div className="sb-h"><span>THEME <span className="ko">테마</span></span></div>
        <div className="theme-row">
          {['light','dark','auto'].map(t => (
            <button key={t} className={theme===t?'on':''} onClick={() => onTheme(t)}>{t.toUpperCase()}</button>
          ))}
        </div>
        {theme==='auto' && <div className="theme-cap">AUTO · 06–18 LIGHT / 18–06 DARK</div>}
      </div>

      <div className="sb-section">
        <div className="sb-h"><span>CORE MODULES <span className="ko">핵심 모듈</span></span></div>
        {MODULES.map(m => {
          const I = Icons[m.icon];
          return (
            <button key={m.key} className={'module-btn' + (active===m.key?' active':'')} onClick={() => !streaming && onNav(m.key)} disabled={streaming}>
              <span className="glyph">{I && <I size={14} />}</span>
              <span className="label">{m.code}. {streaming && active===m.key ? '(응답 생성 중...)' : m.en.toUpperCase()}</span>
            </button>
          );
        })}
      </div>

      <div className="sb-section">
        <div className="sb-h"><span>SYSTEM REGISTRY <span className="ko">시스템 등록</span></span><span className="pill">29 ●</span></div>
        <div className="log-line"><span className="tag">[DEPT]</span> 29 / 29 <span className="dot">●</span></div>
        <div className="log-line"><span className="tag">[ACCT]</span> 33 / 33 <span className="dot">●</span></div>
      </div>

      <div className="sb-section">
        <div className="sb-h"><span>SECURITY LOG <span className="ko">보안 로그</span></span></div>
        <div className="log-line"><span className="tag">[AUTH]</span> JWT_ACTIVE <span className="dot">●</span> OK</div>
        <div className="log-line"><span className="tag">[RBAC]</span> L6 ADMIN</div>
        <div className="log-line"><span className="tag">[SYNC]</span> ChromaDB <span className="dot">●</span></div>
        <div className="log-line"><span className="tag">[LLM]</span> QWEN-3.5 124ms</div>
      </div>

      <div className="sb-footer">AJIN INDUSTRY // ON-PREMISE AI<br/>FastAPI · Streamlit · Ollama</div>
    </aside>
  );
}
window.LeftSidebar = LeftSidebar;
