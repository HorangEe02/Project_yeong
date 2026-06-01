// TopBar.jsx
function TopBar({ rightOn, onToggleRight, onLogout }) {
  return (
    <header className="topbar">
      <span className="tb-brand">◼ 아진산업 <b>AI v3.5</b></span>
      <span className="tb-pipe">│</span>
      <span className="tb-seg">환경 <b>ON-PREMISE</b></span>
      <span className="tb-pipe">·</span>
      <span className="tb-seg">인증 <b>JWT_ACTIVE</b></span>
      <span className="tb-pipe">·</span>
      <span className="tb-seg">LLM <b>QWEN 3.5</b><span className="tb-dot" /></span>
      <span className="tb-grow" />
      <span className="tb-seg">RBAC <b style={{color:'var(--hud-primary)'}}>L6 · ADMIN</b></span>
      <button className="tb-toggle" onClick={onToggleRight}>{rightOn ? 'HIDE' : 'SYS'}</button>
      <button className="tb-toggle" onClick={onLogout}>LOGOUT</button>
    </header>
  );
}
window.TopBar = TopBar;
