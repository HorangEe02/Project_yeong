// Login.jsx
function Login({ onLogin }) {
  const [id, setId] = React.useState('EMP-20260426');
  const [pw, setPw] = React.useState('');
  const checks = [
    { k: '8자 이상', ok: pw.length >= 8 },
    { k: '대문자', ok: /[A-Z]/.test(pw) },
    { k: '소문자', ok: /[a-z]/.test(pw) },
    { k: '숫자', ok: /\d/.test(pw) },
    { k: '특수문자', ok: /[^A-Za-z0-9]/.test(pw) },
    { k: '연속 3회 금지', ok: !/(.)\1\1/.test(pw) },
  ];
  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand">
          <img className="mark" src="../../assets/ajin_symbol.svg" alt="" style={{width:64,height:64,filter:'drop-shadow(0 0 14px rgba(252,177,50,0.35))'}} />
          <div className="name">AJIN INDUSTRY</div>
          <div className="sub">AI ASSISTANT</div>
          <div className="ver">v3.5 // KNU SILLI 2026</div>
        </div>
        <div className="field">
          <span className="lbl">사원번호 · EMPLOYEE ID</span>
          <input value={id} onChange={e => setId(e.target.value)} />
        </div>
        <div className="field">
          <span className="lbl">비밀번호 · PASSWORD</span>
          <input type="password" value={pw} onChange={e => setPw(e.target.value)} placeholder="••••••••" />
        </div>
        <div className="policy">
          {checks.map(c => <span key={c.k} className={c.ok ? 'ok' : 'no'}>{c.k}</span>)}
        </div>
        <button className="btn primary full" onClick={onLogin}>로그인 · SIGN IN</button>
        <div style={{textAlign:'center',marginTop:14,fontSize:11,color:'var(--hud-text-muted)',fontFamily:'var(--hud-font-mono)',letterSpacing:'0.08em'}}>5회 실패 시 30분 잠금 · LOCKOUT 30M</div>
      </div>
    </div>
  );
}
window.Login = Login;
