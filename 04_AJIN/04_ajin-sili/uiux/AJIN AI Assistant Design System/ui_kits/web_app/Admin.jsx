// Admin.jsx — Module E: HR Admin Management (Liquid Glass)
function Admin() {
  const [tab, setTab] = React.useState('security');

  const hqStats = [
    { hq:'시스템 관리자', n:2 }, { hq:'인사본부', n:3 },
    { hq:'품질본부', n:6 }, { hq:'생산기술본부', n:5 },
    { hq:'영업본부', n:4 }, { hq:'환경안전팀', n:3 },
    { hq:'법무팀', n:2 }, { hq:'기타', n:8 },
  ];
  const totalAccounts = hqStats.reduce((a,b)=>a+b.n,0);

  const users = [
    { id:'SA-0001', name:'관리자', dept:'시스템 관리자', role:'SYS_ADMIN', lvl:6, status:'ACTIVE' },
    { id:'HR-0001', name:'인사담당', dept:'인사본부', role:'HR_ADMIN', lvl:5, status:'ACTIVE' },
    { id:'QA-0001', name:'김민수', dept:'품질보증팀', role:'TEAM_LEAD', lvl:4, status:'ACTIVE' },
    { id:'QA-0023', name:'이영희', dept:'품질보증팀', role:'EMPLOYEE', lvl:2, status:'ACTIVE' },
    { id:'PE-0008', name:'박지훈', dept:'생산기술팀', role:'MANAGER', lvl:3, status:'ACTIVE' },
    { id:'PE-0015', name:'정수영', dept:'생산기술팀', role:'EMPLOYEE', lvl:2, status:'INACTIVE' },
    { id:'SS-0003', name:'최현우', dept:'해외영업팀', role:'EMPLOYEE', lvl:2, status:'ACTIVE' },
  ];

  const securityCards = [
    { kind:'crit', title:'무차별 대입', en:'BRUTE FORCE', count:1, desc:'동일 IP 5분 내 5회 실패 → 자동 블록', detail:'203.234.55.12 · QA-0099 (존재하지 않는 사번)' },
    { kind:'warn', title:'야간 접근', en:'OFF-HOURS LOGIN', count:3, desc:'22:00~06:00 로그인 → HR_ADMIN 알림', detail:'PE-0008 · 02:14 / SS-0003 · 23:47 / 외 1건' },
    { kind:'info', title:'비활성 계정', en:'INACTIVE 90D+', count:5, desc:'90일 미접속 → 자동 비활성화 옵션', detail:'PE-0015 (112일) · QA-0044 (95일) · 외 3건' },
  ];

  const loginHistory = [
    { ts:'2026-04-26 09:23:11', id:'QA-0001', name:'김민수', ip:'10.10.5.21', ua:'Chrome/132 · macOS', ok:true },
    { ts:'2026-04-26 09:18:03', id:'PE-0008', name:'박지훈', ip:'10.10.6.44', ua:'Edge/132 · Win11', ok:true },
    { ts:'2026-04-26 02:14:55', id:'PE-0008', name:'박지훈', ip:'10.10.6.44', ua:'Edge/132 · Win11', ok:true, flag:'OFF-HOURS' },
    { ts:'2026-04-26 01:08:22', id:'QA-0099', name:'?', ip:'203.234.55.12', ua:'curl/8.4', ok:false, flag:'BRUTE' },
    { ts:'2026-04-26 01:08:18', id:'QA-0099', name:'?', ip:'203.234.55.12', ua:'curl/8.4', ok:false, flag:'BRUTE' },
    { ts:'2026-04-25 23:47:01', id:'SS-0003', name:'최현우', ip:'203.241.18.9', ua:'Safari/17 · iPad', ok:true, flag:'OFF-HOURS' },
  ];

  const features = ['검색','문서','AI','법규','설비'];
  const depts5 = ['품질보증','생산기술','해외영업','환경안전','법무'];
  const heatmap = [
    [82,68,90,40,72],[78,55,88,35,95],[60,82,72,55,15],[42,38,65,88,30],[28,22,50,72,8],
  ];
  const dau = [120,145,138,162,158,172,168,180,176,191,188,205,212,219,228,231,238,242,251,258,266,272,281,289,295,302,309];
  const dauMax = Math.max(...dau);

  const positions = [
    { n:'사원', v:120, c:'#A47148' },
    { n:'대리', v:88, c:'#C9924E' },
    { n:'과장', v:62, c:'#FCB132' },
    { n:'차장', v:42, c:'#FFCD66' },
    { n:'부장', v:17, c:'#FFE099' },
  ];
  const totalPos = positions.reduce((a,b)=>a+b.v,0);
  const tenure = [{n:'~1y',v:42},{n:'1~3y',v:78},{n:'3~5y',v:88},{n:'5~10y',v:72},{n:'10y+',v:49}];
  const tenureMax = Math.max(...tenure.map(t=>t.v));

  return (
    <div className="page lg-page" data-screen-label="E · HR Admin">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">HR ADMIN MANAGEMENT · MODULE E</div>
        <h1 className="lg-display">인사 관리</h1>
        <p className="lg-sub">RBAC L1~L6 · JWT · BCRYPT. 327명 직원의 계정·권한·보안 감사·AI 활용 분석을 통합 관리합니다.</p>
      </section>

      <div className="lg-tabs">
        {[
          { k:'security', en:'SECURITY', ko:'보안 감사' },
          { k:'users', en:'USERS', ko:'사용자' },
          { k:'create', en:'CREATE', ko:'계정 생성' },
          { k:'analytics', en:'ANALYTICS', ko:'AI 활용 분석' },
          { k:'stats', en:'HR STATS', ko:'인사 통계' },
          { k:'tools', en:'TOOLS', ko:'시스템 도구' },
        ].map(t => (
          <button key={t.k} className={'lg-tab'+(tab===t.k?' on':'')} onClick={()=>setTab(t.k)}>
            <span className="en">{t.en}</span><span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {tab === 'security' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">SECURITY AUDIT · 3종 자동 감지</div><h2 className="lg-h2">실시간 보안 감사</h2></div>
              <span className="lg-pill">최근 24시간</span>
            </div>
            <div className="lg-sec-grid">
              {securityCards.map(c => (
                <div key={c.title} className={'lg-sec '+c.kind}>
                  <div className="lg-sec-top">
                    <span className="lg-sec-dot" />
                    <span className="lg-sec-en">{c.en}</span>
                  </div>
                  <div className="lg-sec-count">{c.count}<span>건</span></div>
                  <div className="lg-sec-title">{c.title}</div>
                  <div className="lg-sec-desc">{c.desc}</div>
                  <div className="lg-sec-detail mono">{c.detail}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">LOGIN HISTORY · 상세 로그인 이력</div><h2 className="lg-h2">실패·야간 접근 추적</h2></div>
              <div className="lg-actions">
                <button className="lg-btn ghost sm">↓ CSV (UTF-8 BOM)</button>
                <button className="lg-btn ghost sm">↓ XLSX</button>
              </div>
            </div>
            <div className="lg-filter-grid" style={{gridTemplateColumns:'1fr 1fr 1fr 1fr', marginBottom:18}}>
              <div className="lg-field"><label>시작일</label><input type="date" defaultValue="2026-04-01" /></div>
              <div className="lg-field"><label>종료일</label><input type="date" defaultValue="2026-04-26" /></div>
              <div className="lg-field"><label>최대 행</label><select><option>1,000건</option><option>5,000건</option><option>10,000건</option></select></div>
              <div className="lg-field"><label>플래그</label><select><option>전체</option><option>BRUTE</option><option>OFF-HOURS</option></select></div>
            </div>
            <div className="lg-table-wrap">
              <table className="lg-table">
                <thead><tr><th>타임스탬프</th><th>사번</th><th>이름</th><th>IP</th><th>User-Agent</th><th>결과</th></tr></thead>
                <tbody>
                  {loginHistory.map((l,i) => (
                    <tr key={i}>
                      <td className="mono dim">{l.ts}</td>
                      <td className="mono">{l.id}</td>
                      <td>{l.name}</td>
                      <td className="mono dim">{l.ip}</td>
                      <td className="dim" style={{fontSize:12}}>{l.ua}</td>
                      <td>
                        {l.ok ? <span className="lg-ok">● 성공</span> : <span className="lg-err">○ 실패</span>}
                        {l.flag && <span className={'lg-flag-pill '+(l.flag==='BRUTE'?'crit':'warn')}>{l.flag}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {tab === 'users' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div><div className="lg-eyebrow">USERS · 사용자 디렉터리</div><h2 className="lg-h2">계정 {totalAccounts}개</h2></div>
            <span className="lg-pill">표시 {users.length}/33</span>
          </div>
          <div className="lg-filter-grid" style={{gridTemplateColumns:'2fr 1fr 1fr 1fr', marginBottom:18}}>
            <div className="lg-field"><label>검색</label><input placeholder="사번 / 이름 / 부서..." /></div>
            <div className="lg-field"><label>부서</label><select><option>전체</option>{hqStats.map(h=><option key={h.hq}>{h.hq}</option>)}</select></div>
            <div className="lg-field"><label>역할</label><select><option>전체</option><option>SYS_ADMIN</option><option>HR_ADMIN</option><option>TEAM_LEAD</option><option>EMPLOYEE</option></select></div>
            <div className="lg-field"><label>상태</label><select><option>ACTIVE</option><option>INACTIVE</option></select></div>
          </div>
          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead><tr><th>사번</th><th>이름</th><th>부서</th><th>역할</th><th>레벨</th><th>상태</th><th>액션</th></tr></thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id}>
                    <td className="mono">{u.id}</td>
                    <td><b>{u.name}</b></td>
                    <td className="dim">{u.dept}</td>
                    <td><span className="lg-role">{u.role}</span></td>
                    <td className="mono">L{u.lvl}</td>
                    <td>{u.status==='ACTIVE'?<span className="lg-ok">● ACTIVE</span>:<span className="dim">○ INACTIVE</span>}</td>
                    <td>
                      <button className="lg-btn ghost sm">편집</button>{' '}
                      <button className="lg-btn ghost sm">권한</button>{' '}
                      <button className="lg-btn ghost sm">잠금</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === 'create' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div><div className="lg-eyebrow">CREATE · 신규 사용자 위저드</div><h2 className="lg-h2">3단계 계정 생성</h2></div>
          </div>
          <div className="lg-wiz-steps">
            <div className="lg-wiz-step on"><span>1</span><div><b>기본 정보</b><i>BASIC</i></div></div>
            <div className="lg-wiz-line" />
            <div className="lg-wiz-step"><span>2</span><div><b>권한 설정</b><i>RBAC</i></div></div>
            <div className="lg-wiz-line" />
            <div className="lg-wiz-step"><span>3</span><div><b>인증 발급</b><i>JWT · BCRYPT</i></div></div>
          </div>
          <div className="lg-filter-grid" style={{gridTemplateColumns:'1fr 1fr', gap:18, marginTop:24}}>
            <div className="lg-field"><label>부서 · DEPT</label><select><option>품질보증팀 (QA)</option><option>생산기술팀 (PE)</option><option>해외영업팀 (SS)</option></select></div>
            <div className="lg-field"><label>사번 · ID (자동)</label><input value="QA-0024" readOnly /></div>
            <div className="lg-field"><label>이름 · NAME</label><input placeholder="홍길동" /></div>
            <div className="lg-field"><label>직급 · POSITION</label><select><option>사원</option><option>대리</option><option>과장</option><option>차장</option><option>부장</option></select></div>
            <div className="lg-field"><label>이메일 · EMAIL</label><input placeholder="hong.gd@ajin.com" /></div>
            <div className="lg-field"><label>본부 · DIVISION</label><select><option>품질본부</option><option>생산기술본부</option><option>영업본부</option></select></div>
          </div>
          <div className="lg-actions" style={{justifyContent:'flex-end', marginTop:24}}>
            <button className="lg-btn ghost">취소</button>
            <button className="lg-btn">다음 ▶</button>
          </div>
        </section>
      )}

      {tab === 'analytics' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">USAGE ANALYTICS · 활동 지표</div><h2 className="lg-h2">DAU · WAU · MAU</h2></div>
            </div>
            <div className="lg-metric-row">
              <div className="lg-metric"><span className="k">DAU</span><span className="v">309</span></div>
              <div className="lg-metric"><span className="k">WAU</span><span className="v">488</span></div>
              <div className="lg-metric"><span className="k">MAU</span><span className="v">612</span></div>
              <div className="lg-metric"><span className="k">활성률</span><span className="v">94.3%</span></div>
            </div>
          </section>

          <div className="lg-grid lg-grid-2-1">
            <section className="lg-card">
              <div className="lg-card-h">
                <div><div className="lg-eyebrow">DAU TREND · 30일</div><h2 className="lg-h2">일일 활성 사용자</h2></div>
              </div>
              <div className="lg-dau-chart">
                <svg viewBox="0 0 600 180" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="dauGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--hud-primary)" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="var(--hud-primary)" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <polyline fill="url(#dauGrad)" stroke="none"
                    points={`0,180 ${dau.map((v,i)=>`${(i/(dau.length-1))*600},${180-(v/dauMax)*150}`).join(' ')} 600,180`} />
                  <polyline fill="none" stroke="var(--hud-primary)" strokeWidth="2"
                    points={dau.map((v,i)=>`${(i/(dau.length-1))*600},${180-(v/dauMax)*150}`).join(' ')} />
                </svg>
              </div>
            </section>

            <section className="lg-card">
              <div className="lg-card-h">
                <div><div className="lg-eyebrow">ROI · 월 절감 추정</div><h2 className="lg-h2">≈ 950만 원</h2></div>
              </div>
              <div className="lg-roi-list">
                <div className="lg-roi-row"><span>절감 시간</span><b>4.0 h/일/인</b></div>
                <div className="lg-roi-row"><span>적용 인원</span><b>33명</b></div>
                <div className="lg-roi-row"><span>시간당 인건비</span><b>30,000원</b></div>
                <div className="lg-roi-row hi"><span>월 절감액</span><b>≈ 950만 원</b></div>
              </div>
              <div className="lg-roi-foot">데모용 추정 — 실 데이터 적용 시 보정 필요</div>
            </section>
          </div>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">DEPT × FEATURE HEATMAP</div><h2 className="lg-h2">부서별 기능 활용도</h2></div>
            </div>
            <div className="lg-heatmap">
              <div className="lg-hm-row head">
                <span />
                {features.map(f => <span key={f} className="lg-hm-col-h">{f}</span>)}
              </div>
              {depts5.map((d,i) => (
                <div key={d} className="lg-hm-row">
                  <span className="lg-hm-row-h">{d}</span>
                  {heatmap[i].map((v,j) => (
                    <span key={j} className="lg-hm-cell" style={{
                      background:`color-mix(in oklab, var(--hud-primary) ${v}%, transparent)`,
                      color: v>50?'var(--hud-bg)':'var(--hud-text)'
                    }}>{v}</span>
                  ))}
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {tab === 'stats' && (
        <div className="lg-grid lg-grid-2">
          <section className="lg-card">
            <div className="lg-card-h"><div><div className="lg-eyebrow">CHART 1</div><h2 className="lg-h2">본부별 인원</h2></div></div>
            <div className="lg-bars-v">
              {hqStats.map(h => (
                <div key={h.hq} className="lg-bar-v">
                  <div className="lg-bar-fill" style={{height:(h.n/8*100)+'%'}}><b>{h.n}</b></div>
                  <span className="lbl">{h.hq.replace('본부','').replace('관리자','관')}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h"><div><div className="lg-eyebrow">CHART 2</div><h2 className="lg-h2">직급별 분포</h2></div></div>
            <div className="lg-donut-wrap">
              <svg viewBox="0 0 100 100" className="lg-donut">
                {(() => {
                  let acc = 0;
                  return positions.map((p,i) => {
                    const frac = p.v/totalPos;
                    const a0 = acc*Math.PI*2 - Math.PI/2; acc += frac;
                    const a1 = acc*Math.PI*2 - Math.PI/2;
                    const r = 40, cx = 50, cy = 50;
                    const x0 = cx+r*Math.cos(a0), y0 = cy+r*Math.sin(a0);
                    const x1 = cx+r*Math.cos(a1), y1 = cy+r*Math.sin(a1);
                    const large = frac > 0.5 ? 1 : 0;
                    return <path key={i} d={`M${cx},${cy} L${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1} Z`} fill={p.c} />;
                  });
                })()}
                <circle cx="50" cy="50" r="24" fill="var(--hud-bg)" />
                <text x="50" y="48" textAnchor="middle" fontSize="7" fill="var(--hud-text-dim)">총원</text>
                <text x="50" y="60" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--hud-primary)">{totalPos}</text>
              </svg>
              <div className="lg-donut-legend">
                {positions.map(p => <div key={p.n}><i style={{background:p.c}} /><span>{p.n}</span><b>{p.v}</b></div>)}
              </div>
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h"><div><div className="lg-eyebrow">CHART 3</div><h2 className="lg-h2">근속연수 분포</h2></div></div>
            <div className="lg-bars-v">
              {tenure.map(t => (
                <div key={t.n} className="lg-bar-v">
                  <div className="lg-bar-fill blue" style={{height:(t.v/tenureMax*100)+'%'}}><b>{t.v}</b></div>
                  <span className="lbl">{t.n}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h"><div><div className="lg-eyebrow">CHART 4</div><h2 className="lg-h2">요약 지표</h2></div></div>
            <div className="lg-stat-list">
              <div className="lg-stat-row"><span>성별</span><b>남 247 (75.4%) · 여 80 (24.6%)</b></div>
              <div className="lg-stat-row"><span>본사</span><b>124명</b></div>
              <div className="lg-stat-row"><span>천안</span><b>85명</b></div>
              <div className="lg-stat-row"><span>광주</span><b>42명</b></div>
              <div className="lg-stat-row"><span>JOON INC</span><b>33명</b></div>
              <div className="lg-stat-row hi"><span>이번 분기 순증</span><b>+5명 (입 8 / 퇴 3)</b></div>
            </div>
          </section>
        </div>
      )}

      {tab === 'tools' && (
        <div className="lg-grid lg-grid-2-2">
          <section className="lg-card lg-card-tight">
            <div className="lg-eyebrow">백업 · BACKUP</div>
            <h2 className="lg-h2" style={{marginTop:6, marginBottom:12}}>통합 DB 백업</h2>
            <div className="lg-tool-desc">auth.db · audit.db · draft_versions.db · feedback.db</div>
            <button className="lg-btn full" style={{marginTop:18}}>백업 실행 ▶</button>
          </section>
          <section className="lg-card lg-card-tight">
            <div className="lg-eyebrow">복원 · RESTORE</div>
            <h2 className="lg-h2" style={{marginTop:6, marginBottom:12}}>백업 파일 복원</h2>
            <div className="lg-tool-desc">정합성 검증 후 복원 (롤백 가능)</div>
            <button className="lg-btn ghost full" style={{marginTop:18}}>파일 선택...</button>
          </section>
          <section className="lg-card lg-card-tight">
            <div className="lg-eyebrow">정합성 · INTEGRITY</div>
            <h2 className="lg-h2" style={{marginTop:6, marginBottom:12}}>DB 진단</h2>
            <div className="lg-tool-desc">SQLite VACUUM · 인덱스 재구성 · ChromaDB 재인덱싱</div>
            <button className="lg-btn ghost full" style={{marginTop:18}}>진단 실행</button>
          </section>
          <section className="lg-card lg-card-tight">
            <div className="lg-eyebrow">아카이브 · ARCHIVE</div>
            <h2 className="lg-h2" style={{marginTop:6, marginBottom:12}}>감사 로그 정리</h2>
            <div className="lg-tool-desc">90일 이상 로그 → S3 Cold Storage</div>
            <button className="lg-btn ghost full" style={{marginTop:18}}>아카이브 ▶</button>
          </section>
        </div>
      )}
    </div>
  );
}
window.Admin = Admin;
