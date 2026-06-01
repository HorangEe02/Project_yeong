// Search.jsx — Module A: Org Chart & Employee Directory (Liquid Glass)
function Search() {
  const [hq, setHq] = React.useState('전체');
  const [team, setTeam] = React.useState('전체');
  const [pos, setPos] = React.useState('전체');
  const [gender, setGender] = React.useState('전체');
  const [plant, setPlant] = React.useState('전체');
  const [q, setQ] = React.useState('');
  const [selectedHq, setSelectedHq] = React.useState(null); // for org diagram drill

  // ── 조직도 데이터 ──────────────────────────────────────────
  const org = [
    { hq: '경영지원본부', n: 58, color: 'oklch(72% 0.14 60)', teams: [
      { team: '인사팀', n: 14 }, { team: '재무팀', n: 18 },
      { team: '법무팀', n: 8 },  { team: '구매팀', n: 18 },
    ]},
    { hq: '품질본부', n: 92, color: 'oklch(76% 0.16 75)', teams: [
      { team: '품질보증팀', n: 42 }, { team: '품질관리팀', n: 28 }, { team: '검사팀', n: 22 },
    ]},
    { hq: '생산기술본부', n: 138, color: 'oklch(70% 0.13 50)', teams: [
      { team: '생산기술팀', n: 48 }, { team: '금형팀', n: 32 },
      { team: '정비팀', n: 38 },     { team: '프레스팀', n: 20 },
    ]},
    { hq: '영업본부', n: 64, color: 'oklch(74% 0.12 220)', teams: [
      { team: '국내영업팀', n: 24 }, { team: '해외영업팀', n: 28 }, { team: '영업기획팀', n: 12 },
    ]},
    { hq: 'R&D본부', n: 47, color: 'oklch(72% 0.10 280)', teams: [
      { team: '연구개발팀', n: 22 }, { team: '설계팀', n: 18 }, { team: '시작팀', n: 7 },
    ]},
    { hq: '환경안전본부', n: 28, color: 'oklch(68% 0.14 145)', teams: [
      { team: '환경안전팀', n: 16 }, { team: '시설관리팀', n: 12 },
    ]},
  ];

  const totalN = org.reduce((a,b)=>a+b.n,0);
  const positions = ['사원','대리','과장','차장','부장','이사','상무','전무'];
  const plants = ['본사 (대구)','천안 1공장','천안 2공장','광주 도장','울산','아산','평택','경주','창원','인천 R&D','JOON INC (USA)','AJIN POLAND','AJIN INDIA'];

  // ── 인원 데이터 (representative sample, 24명) ─────────────────
  const peopleAll = [
    { id:'QA-0001', name:'김민수', g:'남', hq:'품질본부', team:'품질보증팀', pos:'차장', ext:'1234', mobile:'010-2341-5678', email:'minsu.kim@ajin.com', plant:'본사 (대구)' },
    { id:'QA-0007', name:'이서연', g:'여', hq:'품질본부', team:'품질보증팀', pos:'대리', ext:'1238', mobile:'010-3415-2876', email:'sy.lee@ajin.com', plant:'본사 (대구)' },
    { id:'QA-0023', name:'박정호', g:'남', hq:'품질본부', team:'품질관리팀', pos:'과장', ext:'1252', mobile:'010-9871-2245', email:'jh.park@ajin.com', plant:'천안 1공장' },
    { id:'QA-0035', name:'정수영', g:'여', hq:'품질본부', team:'검사팀', pos:'사원', ext:'1265', mobile:'010-7654-3210', email:'sy.jung@ajin.com', plant:'본사 (대구)' },
    { id:'PE-0008', name:'박지훈', g:'남', hq:'생산기술본부', team:'생산기술팀', pos:'과장', ext:'2105', mobile:'010-4422-1188', email:'jh2.park@ajin.com', plant:'본사 (대구)' },
    { id:'PE-0019', name:'최유진', g:'여', hq:'생산기술본부', team:'생산기술팀', pos:'대리', ext:'2117', mobile:'010-2233-7766', email:'yj.choi@ajin.com', plant:'본사 (대구)' },
    { id:'PE-0033', name:'한승우', g:'남', hq:'생산기술본부', team:'금형팀', pos:'차장', ext:'2160', mobile:'010-5566-8899', email:'sw.han@ajin.com', plant:'경주' },
    { id:'PE-0045', name:'임지현', g:'여', hq:'생산기술본부', team:'정비팀', pos:'사원', ext:'2210', mobile:'010-3344-9988', email:'jh.lim@ajin.com', plant:'천안 2공장' },
    { id:'PE-0057', name:'오성민', g:'남', hq:'생산기술본부', team:'프레스팀', pos:'부장', ext:'2280', mobile:'010-9988-1122', email:'sm.oh@ajin.com', plant:'본사 (대구)' },
    { id:'SS-0003', name:'최현우', g:'남', hq:'영업본부', team:'해외영업팀', pos:'차장', ext:'3304', mobile:'010-1122-3344', email:'hw.choi@ajin.com', plant:'JOON INC (USA)' },
    { id:'SS-0012', name:'윤하늘', g:'여', hq:'영업본부', team:'국내영업팀', pos:'과장', ext:'3315', mobile:'010-4455-7788', email:'hn.yoon@ajin.com', plant:'본사 (대구)' },
    { id:'SS-0024', name:'강도윤', g:'남', hq:'영업본부', team:'영업기획팀', pos:'대리', ext:'3328', mobile:'010-6677-2233', email:'dy.kang@ajin.com', plant:'본사 (대구)' },
    { id:'HR-0001', name:'이영희', g:'여', hq:'경영지원본부', team:'인사팀', pos:'부장', ext:'4001', mobile:'010-1010-1010', email:'yh.lee@ajin.com', plant:'본사 (대구)' },
    { id:'HR-0004', name:'송민재', g:'남', hq:'경영지원본부', team:'인사팀', pos:'대리', ext:'4014', mobile:'010-2020-3030', email:'mj.song@ajin.com', plant:'본사 (대구)' },
    { id:'FN-0009', name:'장다은', g:'여', hq:'경영지원본부', team:'재무팀', pos:'과장', ext:'4108', mobile:'010-3030-4040', email:'de.jang@ajin.com', plant:'본사 (대구)' },
    { id:'PR-0014', name:'배현수', g:'남', hq:'경영지원본부', team:'구매팀', pos:'차장', ext:'4221', mobile:'010-4040-5050', email:'hs.bae@ajin.com', plant:'본사 (대구)' },
    { id:'LG-0002', name:'문혜린', g:'여', hq:'경영지원본부', team:'법무팀', pos:'과장', ext:'4302', mobile:'010-5050-6060', email:'hl.moon@ajin.com', plant:'본사 (대구)' },
    { id:'RD-0005', name:'권태원', g:'남', hq:'R&D본부', team:'연구개발팀', pos:'부장', ext:'5005', mobile:'010-6060-7070', email:'tw.kwon@ajin.com', plant:'인천 R&D' },
    { id:'RD-0011', name:'조예린', g:'여', hq:'R&D본부', team:'설계팀', pos:'차장', ext:'5018', mobile:'010-7070-8080', email:'yr.cho@ajin.com', plant:'인천 R&D' },
    { id:'RD-0019', name:'노건우', g:'남', hq:'R&D본부', team:'시작팀', pos:'사원', ext:'5034', mobile:'010-8080-9090', email:'gw.noh@ajin.com', plant:'인천 R&D' },
    { id:'EH-0003', name:'서지원', g:'여', hq:'환경안전본부', team:'환경안전팀', pos:'과장', ext:'6003', mobile:'010-9090-1010', email:'jw.seo@ajin.com', plant:'본사 (대구)' },
    { id:'EH-0008', name:'홍재민', g:'남', hq:'환경안전본부', team:'환경안전팀', pos:'대리', ext:'6011', mobile:'010-1212-3434', email:'jm.hong@ajin.com', plant:'천안 1공장' },
    { id:'FA-0005', name:'유나경', g:'여', hq:'환경안전본부', team:'시설관리팀', pos:'사원', ext:'6024', mobile:'010-3434-5656', email:'ng.yoo@ajin.com', plant:'광주 도장' },
    { id:'PE-0072', name:'전상현', g:'남', hq:'생산기술본부', team:'정비팀', pos:'대리', ext:'2240', mobile:'010-5656-7878', email:'sh.jeon@ajin.com', plant:'울산' },
  ];

  const teamsForHq = hq === '전체' ? [] : (org.find(o=>o.hq===hq)?.teams||[]);

  const filtered = peopleAll.filter(p => {
    if (hq !== '전체' && p.hq !== hq) return false;
    if (team !== '전체' && p.team !== team) return false;
    if (pos !== '전체' && p.pos !== pos) return false;
    if (gender !== '전체' && p.g !== gender) return false;
    if (plant !== '전체' && p.plant !== plant) return false;
    if (q.trim()) {
      const s = q.toLowerCase();
      if (!(p.name.toLowerCase().includes(s) || p.id.toLowerCase().includes(s) ||
            p.email.toLowerCase().includes(s) || p.team.includes(q) || p.hq.includes(q))) return false;
    }
    return true;
  });

  const reset = () => { setHq('전체'); setTeam('전체'); setPos('전체'); setGender('전체'); setPlant('전체'); setQ(''); setSelectedHq(null); };

  return (
    <div className="page lg-page" data-screen-label="A · Org & Directory">
      {/* Hero */}
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">EMPLOYEE DIRECTORY · MODULE A</div>
        <h1 className="lg-display">조직도 / 인원 검색</h1>
        <p className="lg-sub">아진산업 6개 본부 · 19개 팀 · {totalN}명. 본부와 팀을 선택해 부서별 체계와 인원 정보를 한눈에 확인하세요.</p>
      </section>

      {/* 조직도 다이어그램 */}
      <section className="lg-card lg-orgchart">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">ORG CHART · 조직도</div>
            <h2 className="lg-h2">본부 → 팀 구조</h2>
          </div>
          <div className="lg-pill">총 {totalN}명 · 6 HQ · 19 TEAMS</div>
        </div>

        <div className="org-diagram">
          <div className="org-ceo">
            <div className="org-node-glass ceo">
              <div className="org-node-eyebrow">CEO · 대표이사</div>
              <div className="org-node-title">AJIN INDUSTRY</div>
              <div className="org-node-sub">아진산업 주식회사 · {totalN}명</div>
            </div>
          </div>
          <svg className="org-connectors" viewBox="0 0 1200 60" preserveAspectRatio="none">
            <path d="M600,0 V20 M100,60 V40 H1100 V40 M100,40 V60 M300,40 V60 M500,40 V60 M700,40 V60 M900,40 V60 M1100,40 V60 M600,20 V40" stroke="oklch(70% 0.02 80 / 0.4)" strokeWidth="1" fill="none" />
          </svg>
          <div className="org-hq-row">
            {org.map(b => (
              <button key={b.hq} className={'org-node-glass hq' + (selectedHq===b.hq?' active':'') + (hq===b.hq?' selected':'')}
                onClick={()=>{setSelectedHq(selectedHq===b.hq?null:b.hq); setHq(b.hq); setTeam('전체');}}>
                <span className="org-accent" style={{background:b.color}} />
                <div className="org-node-eyebrow">{b.teams.length} TEAMS</div>
                <div className="org-node-title">{b.hq}</div>
                <div className="org-node-sub">{b.n}명</div>
              </button>
            ))}
          </div>
          {selectedHq && (
            <div className="org-team-row">
              <div className="org-team-label">└ {selectedHq} 산하 팀</div>
              <div className="org-team-chips">
                {org.find(o=>o.hq===selectedHq).teams.map(t => (
                  <button key={t.team} className={'org-team-chip'+(team===t.team?' on':'')} onClick={()=>setTeam(t.team)}>
                    <span className="t-name">{t.team}</span>
                    <span className="t-count">{t.n}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 필터 */}
      <section className="lg-card lg-filters">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">FILTERS · 분류 검색</div>
            <h2 className="lg-h2">부서 / 직급별 필터</h2>
          </div>
          <button className="lg-btn ghost" onClick={reset}>초기화</button>
        </div>
        <div className="lg-filter-grid">
          <div className="lg-field">
            <label>본부</label>
            <select value={hq} onChange={e=>{setHq(e.target.value); setTeam('전체'); setSelectedHq(e.target.value==='전체'?null:e.target.value);}}>
              <option>전체</option>
              {org.map(o => <option key={o.hq}>{o.hq}</option>)}
            </select>
          </div>
          <div className="lg-field">
            <label>팀</label>
            <select value={team} onChange={e=>setTeam(e.target.value)} disabled={hq==='전체'}>
              <option>전체</option>
              {teamsForHq.map(t => <option key={t.team}>{t.team}</option>)}
            </select>
          </div>
          <div className="lg-field">
            <label>직급</label>
            <select value={pos} onChange={e=>setPos(e.target.value)}>
              <option>전체</option>
              {positions.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className="lg-field">
            <label>성별</label>
            <select value={gender} onChange={e=>setGender(e.target.value)}>
              <option>전체</option><option>남</option><option>여</option>
            </select>
          </div>
          <div className="lg-field">
            <label>사업장</label>
            <select value={plant} onChange={e=>setPlant(e.target.value)}>
              <option>전체</option>
              {plants.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className="lg-field grow">
            <label>이름 / 사번 / 이메일</label>
            <input type="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="검색어 입력..." />
          </div>
        </div>
      </section>

      {/* 인원 표 */}
      <section className="lg-card lg-table-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">DIRECTORY · 인원 정보</div>
            <h2 className="lg-h2">{filtered.length}명 검색됨 <span className="lg-h2-sub">/ 전체 {peopleAll.length}명 표시</span></h2>
          </div>
          <div className="lg-actions">
            <button className="lg-btn ghost">↓ CSV</button>
            <button className="lg-btn ghost">↓ XLSX</button>
            <button className="lg-btn">+ 컬럼</button>
          </div>
        </div>

        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>사번</th><th>이름</th><th>성별</th><th>본부 / 팀</th><th>직급</th>
                <th>내선</th><th>휴대전화</th><th>이메일</th><th>사업장</th><th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan="10" className="lg-empty">조건에 맞는 인원이 없습니다. 필터를 조정해 보세요.</td></tr>
              ) : filtered.map(p => (
                <tr key={p.id}>
                  <td className="mono dim">{p.id}</td>
                  <td>
                    <div className="lg-person">
                      <span className="lg-avatar">{p.name.slice(-2)}</span>
                      <span className="lg-name">{p.name}</span>
                    </div>
                  </td>
                  <td><span className={'lg-gender g-'+(p.g==='남'?'m':'f')}>{p.g}</span></td>
                  <td>
                    <div className="lg-deptcol">
                      <span className="hq-tag">{p.hq.replace('본부','')}</span>
                      <span className="team-tag">{p.team}</span>
                    </div>
                  </td>
                  <td><span className="lg-pos">{p.pos}</span></td>
                  <td className="mono">#{p.ext}</td>
                  <td className="mono dim">{p.mobile}</td>
                  <td className="lg-email"><a href={'mailto:'+p.email}>{p.email}</a></td>
                  <td className="dim">{p.plant}</td>
                  <td><button className="lg-btn ghost sm">↗</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
window.Search = Search;
