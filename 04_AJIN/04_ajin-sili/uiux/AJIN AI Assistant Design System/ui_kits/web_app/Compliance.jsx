// Compliance.jsx — Module D: Compliance Monitoring (Liquid Glass)
function Compliance() {
  const [tab, setTab] = React.useState('updates');
  const [tariff, setTariff] = React.useState(25);

  const scenarios = [
    { id:'safety', title:'산안법 안전거리', score:85, cat:'CRITICAL', dday:30, en:'KOSHA SAFETY DISTANCE',
      desc:'프레스 안전거리 300mm → 400mm 변경', risk:{fin:30,pos:28,urg:27},
      sites:['본사 프레스 라인 3개소'], depts:['생산기술팀','환경안전팀'] },
    { id:'tariff', title:'트럼프 관세', score:78, cat:'HIGH', dday:90, en:'US TARIFF SIMULATOR',
      desc:'美 25% 관세 → JOON INC 공급 원가 영향', risk:{fin:35,pos:22,urg:21},
      sites:['JOON INC (USA)','본사 수출'], depts:['해외영업팀','구매팀'] },
    { id:'reach', title:'REACH 신규 SVHC', score:52, cat:'MEDIUM', dday:180, en:'EU REACH SVHC',
      desc:'EU 신규 우려물질 등재 → 부품 재인증', risk:{fin:18,pos:16,urg:18},
      sites:['천안 1공장','광주 도장'], depts:['품질보증팀','환경안전팀'] },
  ];

  const crawlers = [
    { id:1, name:'ISO Crawler', target:'ISO 14001 / 45001', last:'04-26 02:15', changes:1 },
    { id:2, name:'MSDS Crawler', target:'화학물질안전보건자료', last:'04-26 02:20', changes:0 },
    { id:3, name:'EU Regulation', target:'REACH · RoHS · ELV', last:'04-26 02:25', changes:3 },
    { id:4, name:'Domestic Law', target:'산안법 · 화관법 · 환경법', last:'04-26 02:30', changes:2 },
    { id:5, name:'OEM Quality', target:'IATF 16949 · PPAP · FMEA', last:'04-26 02:35', changes:1 },
    { id:6, name:'APQP Crawler', target:'APQP 단계별 요구사항', last:'04-26 02:40', changes:0 },
    { id:7, name:'Carbon ESG', target:'탄소 배출 / ESG 지표', last:'04-26 02:45', changes:2 },
    { id:8, name:'EV Battery', target:'EV 배터리 (UN R100)', last:'04-26 02:50', changes:1 },
    { id:9, name:'Global Trade', target:'관세 · FTA · 무역 규제', last:'04-26 02:55', changes:2 },
  ];
  const totalChanges = crawlers.reduce((a,b)=>a+b.changes,0);

  const items = [
    { type:'수정', name:'ISO 14001 § 6.1.2 환경측면 식별', date:'04-25', status:'pending' },
    { type:'신규', name:'EU REACH 신규 SVHC 등재 (PFAS 계열 3종)', date:'04-24', status:'pending' },
    { type:'신규', name:'美 자동차 부품 추가 관세 검토', date:'04-23', status:'confirmed' },
    { type:'수정', name:'산안법 시행규칙 개정 — 안전거리 300→400mm', date:'04-22', status:'pending' },
  ];

  const items6 = [
    { name:'CCH', base:320 }, { name:'OBC', base:280 },
    { name:'범퍼빔', base:180 }, { name:'도어', base:240 },
    { name:'볼시트', base:90 }, { name:'EV 배터리 케이스', base:410 },
  ];
  const totalImpact = items6.reduce((a,it)=>a+(it.base*tariff/100),0);

  const plants = [
    { name:'본사 (대구)', type:'HQ', certs:['IATF 16949'], domestic:true },
    { name:'천안 1공장', type:'프레스', certs:['ISO 14001'], domestic:true },
    { name:'천안 2공장', type:'용접', certs:['IATF 16949'], domestic:true },
    { name:'광주 도장', type:'도장', certs:['ISO 45001'], domestic:true },
    { name:'울산', type:'CNC', certs:['IATF 16949'], domestic:true },
    { name:'아산', type:'사출', certs:[], domestic:true },
    { name:'평택', type:'검사', certs:[], domestic:true },
    { name:'인천 R&D', type:'R&D', certs:[], domestic:true },
    { name:'경주', type:'금형', certs:[], domestic:true },
    { name:'창원', type:'컨베이어', certs:[], domestic:true },
    { name:'부산', type:'자재', certs:[], domestic:true },
    { name:'서울 본부', type:'OFFICE', certs:[], domestic:true },
    { name:'JOON INC (USA)', type:'북미', certs:['IATF 16949'], domestic:false },
    { name:'AJIN MEXICO', type:'중남미', certs:[], domestic:false },
    { name:'AJIN INDIA', type:'아시아', certs:[], domestic:false },
    { name:'AJIN POLAND', type:'유럽', certs:['ISO 14001'], domestic:false },
    { name:'AJIN CHINA', type:'아시아', certs:[], domestic:false },
    { name:'AJIN SLOVAKIA', type:'유럽', certs:[], domestic:false },
    { name:'AJIN BRAZIL', type:'중남미', certs:[], domestic:false },
  ];

  return (
    <div className="page lg-page" data-screen-label="D · Compliance">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">COMPLIANCE MONITORING · MODULE D</div>
        <h1 className="lg-display">법규 / 규정 모니터링</h1>
        <p className="lg-sub">9개 크롤러 · 7개 부서 RBAC · 24시간 자동 감지. 산안법·REACH·관세·IATF 16949 — 글로벌 19개 사업장의 컴플라이언스를 실시간으로 추적합니다.</p>
      </section>

      <div className="lg-tabs">
        {[
          { k:'updates', en:'UPDATES', ko:'법규 업데이트' },
          { k:'monitor', en:'MONITOR', ko:'영향 분석' },
          { k:'sites', en:'SITES', ko:'사업장' },
          { k:'docs', en:'DOCS', ko:'법규 문서' },
        ].map(t => (
          <button key={t.k} className={'lg-tab'+(tab===t.k?' on':'')} onClick={()=>setTab(t.k)}>
            <span className="en">{t.en}</span><span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {tab === 'updates' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">SCENARIOS · TOP 3</div><h2 className="lg-h2">규제 현황 시나리오</h2></div>
              <span className="lg-pill">위험도 점수 100점 기준</span>
            </div>
            <div className="lg-scen-grid">
              {scenarios.map(s => (
                <div key={s.id} className={'lg-scen cat-'+s.cat.toLowerCase()}>
                  <div className="lg-scen-top">
                    <span className="cat">{s.cat}</span>
                    <span className="dday">D-{s.dday}</span>
                  </div>
                  <div className="lg-scen-score">{s.score}<span>/100</span></div>
                  <div className="lg-scen-title">{s.title}</div>
                  <div className="lg-scen-en">{s.en}</div>
                  <div className="lg-scen-desc">{s.desc}</div>
                  <div className="lg-scen-risk">
                    <span><i>재무</i><b>{s.risk.fin}</b><u>/40</u></span>
                    <span><i>가능성</i><b>{s.risk.pos}</b><u>/30</u></span>
                    <span><i>긴급</i><b>{s.risk.urg}</b><u>/30</u></span>
                  </div>
                  <div className="lg-scen-meta">
                    <div><span className="ko">영향</span> {s.sites.join(', ')}</div>
                    <div><span className="ko">대응</span> {s.depts.join(' · ')}</div>
                  </div>
                  <button className="lg-btn full">시뮬레이션 ▶</button>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">CRAWLERS · 9개</div><h2 className="lg-h2">크롤러 실행 현황</h2></div>
              <div className="lg-actions">
                <button className="lg-btn ghost">RUN ALL</button>
                <button className="lg-btn">RUN SELECTED</button>
              </div>
            </div>
            <div className="lg-crawl-grid">
              {crawlers.map(c => (
                <div key={c.id} className="lg-crawl">
                  <div className="lg-crawl-h">
                    <span className="num">{String(c.id).padStart(2,'0')}</span>
                    <span className="lg-dot ok" />
                  </div>
                  <div className="lg-crawl-name">{c.name}</div>
                  <div className="lg-crawl-target">{c.target}</div>
                  <div className="lg-crawl-foot">
                    <span className="mono dim">{c.last}</span>
                    {c.changes ? <span className="lg-chg">{c.changes}건</span> : <span className="dim">—</span>}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">CHANGE DETECTOR · 변경 감지</div><h2 className="lg-h2">신규·수정 사항</h2></div>
              <div className="lg-actions">
                <span className="lg-pill">총 {totalChanges}건</span>
              </div>
            </div>
            <div className="lg-metric-row">
              <div className="lg-metric"><span className="k">총 변경</span><span className="v">{totalChanges}</span></div>
              <div className="lg-metric"><span className="k">신규</span><span className="v">3</span></div>
              <div className="lg-metric"><span className="k">수정</span><span className="v">7</span></div>
              <div className="lg-metric warn"><span className="k">미확인</span><span className="v">3</span></div>
            </div>
            <div className="lg-table-wrap">
              <table className="lg-table">
                <thead><tr><th>유형</th><th>법규 / 규정</th><th>일자</th><th></th></tr></thead>
                <tbody>
                  {items.map((it,i) => (
                    <tr key={i}>
                      <td><span className={'lg-tag '+(it.type==='신규'?'new':'mod')}>{it.type}</span></td>
                      <td>{it.name}</td>
                      <td className="mono dim">{it.date}</td>
                      <td>
                        {it.status==='pending'
                          ? <button className="lg-btn ghost sm">확인</button>
                          : <span className="lg-ok">✓ 처리됨</span>}
                        {' '}<button className="lg-btn ghost sm">상세</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">TARIFF SIMULATOR · 관세</div><h2 className="lg-h2">美 관세율 시나리오</h2></div>
              <span className="lg-pill">JOON INC · 북미 공급분</span>
            </div>
            <div className="lg-tariff-control">
              <div>
                <div className="lg-eyebrow">관세율 조정</div>
                <div className="lg-tariff-val">{tariff}<i>%</i></div>
              </div>
              <input className="lg-range" type="range" min="0" max="50" step="1" value={tariff} onChange={e=>setTariff(+e.target.value)} />
              <div className="lg-tariff-impact">
                <div className="lg-eyebrow">월 추가 부담 추정</div>
                <div className="lg-tariff-val accent">{Math.round(totalImpact)}<i>억</i></div>
              </div>
            </div>
            <div className="lg-tariff-bars">
              {items6.map(it => {
                const impact = it.base*tariff/100;
                return (
                  <div key={it.name} className="lg-tariff-row">
                    <span className="lbl">{it.name}</span>
                    <div className="lg-tariff-bar">
                      <span className="base" style={{width:(it.base/410*70)+'%'}} />
                      <span className="add" style={{width:(impact/410*70)+'%'}} />
                    </div>
                    <span className="val mono">기준 {it.base}억 <i>+{Math.round(impact)}</i></span>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}

      {tab === 'monitor' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">DEADLINE TIMELINE · D-DAY</div><h2 className="lg-h2">대응 마감 타임라인</h2></div>
            </div>
            <div className="lg-timeline">
              {scenarios.map(s => (
                <div key={s.id} className={'lg-tl-row cat-'+s.cat.toLowerCase()}>
                  <span className="lg-tl-name">{s.title}</span>
                  <div className="lg-tl-bar">
                    <span className="lg-tl-fill" style={{width:Math.max(5,100-s.dday/2)+'%'}} />
                    <span className="lg-tl-d">D-{s.dday}</span>
                  </div>
                  <span className="lg-tl-cat">{s.cat}</span>
                </div>
              ))}
              <div className="lg-tl-row cat-low">
                <span className="lg-tl-name">IATF 16949 정기 감사</span>
                <div className="lg-tl-bar"><span className="lg-tl-fill" style={{width:'15%'}} /><span className="lg-tl-d">D-220</span></div>
                <span className="lg-tl-cat">LOW</span>
              </div>
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">IMPACT NETWORK · 영향 관계도</div><h2 className="lg-h2">규제 → 시설 → 부서</h2></div>
              <div className="lg-net-legend">
                <span><i className="d-reg" />규제 3</span>
                <span><i className="d-site" />시설 3</span>
                <span><i className="d-dept" />부서 4</span>
              </div>
            </div>
            <div className="lg-impact-net">
              <svg viewBox="0 0 800 320" preserveAspectRatio="xMidYMid meet">
                <line x1="120" y1="60" x2="380" y2="160" stroke="var(--hud-primary)" strokeWidth="1.5" opacity="0.5" />
                <line x1="120" y1="60" x2="380" y2="240" stroke="var(--hud-primary)" strokeWidth="1.5" opacity="0.5" />
                <line x1="120" y1="160" x2="380" y2="80" stroke="#6FB1FC" strokeWidth="1.5" opacity="0.5" />
                <line x1="120" y1="160" x2="380" y2="160" stroke="#6FB1FC" strokeWidth="1.5" opacity="0.5" />
                <line x1="120" y1="260" x2="380" y2="240" stroke="#A47148" strokeWidth="1.5" opacity="0.5" />
                <line x1="380" y1="80" x2="640" y2="60" stroke="var(--hud-text-dim)" strokeWidth="1" opacity="0.4" />
                <line x1="380" y1="160" x2="640" y2="160" stroke="var(--hud-text-dim)" strokeWidth="1" opacity="0.4" />
                <line x1="380" y1="160" x2="640" y2="220" stroke="var(--hud-text-dim)" strokeWidth="1" opacity="0.4" />
                <line x1="380" y1="240" x2="640" y2="280" stroke="var(--hud-text-dim)" strokeWidth="1" opacity="0.4" />
                <g className="reg">
                  <circle cx="120" cy="60" r="26" /><text x="120" y="65" textAnchor="middle">산안법</text>
                  <circle cx="120" cy="160" r="26" /><text x="120" y="165" textAnchor="middle">관세</text>
                  <circle cx="120" cy="260" r="26" /><text x="120" y="265" textAnchor="middle">REACH</text>
                </g>
                <g className="site">
                  <rect x="350" y="56" width="60" height="48" rx="10" /><text x="380" y="85" textAnchor="middle">본사</text>
                  <rect x="350" y="136" width="60" height="48" rx="10" /><text x="380" y="165" textAnchor="middle">JOON</text>
                  <rect x="350" y="216" width="60" height="48" rx="10" /><text x="380" y="245" textAnchor="middle">천안</text>
                </g>
                <g className="dept">
                  <circle cx="640" cy="60" r="26" /><text x="640" y="65" textAnchor="middle">생기</text>
                  <circle cx="640" cy="160" r="26" /><text x="640" y="165" textAnchor="middle">해영</text>
                  <circle cx="640" cy="220" r="26" /><text x="640" y="225" textAnchor="middle">구매</text>
                  <circle cx="640" cy="280" r="26" /><text x="640" y="285" textAnchor="middle">환안</text>
                </g>
              </svg>
            </div>
          </section>
        </>
      )}

      {tab === 'sites' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div><div className="lg-eyebrow">SITES · 19 LOCATIONS</div><h2 className="lg-h2">국내 12 + 해외 7</h2></div>
            <div className="lg-actions">
              <span className="lg-pill">전체</span>
              <button className="lg-btn ghost sm">국내</button>
              <button className="lg-btn ghost sm">해외</button>
            </div>
          </div>
          <div className="lg-sites-grid">
            {plants.map(p => (
              <div key={p.name} className={'lg-site '+(p.domestic?'dom':'ovs')}>
                <div className="lg-site-h">
                  <span className="flag">{p.domestic?'국내':'해외'}</span>
                  <span className="type">{p.type}</span>
                </div>
                <div className="lg-site-name">{p.name}</div>
                <div className="lg-site-certs">
                  {p.certs.length ? p.certs.map(c => <span key={c} className="cert">{c}</span>) : <span className="cert ghost">—</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {tab === 'docs' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div><div className="lg-eyebrow">DOCS · 법규 문서 라이브러리</div><h2 className="lg-h2">출처별 원문 / 개정안</h2></div>
          </div>
          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead><tr><th>문서</th><th>출처</th><th>버전</th><th>다운로드</th></tr></thead>
              <tbody>
                <tr><td>산안법 시행규칙 개정안</td><td className="dim">고용노동부</td><td className="mono">2026.04</td><td><button className="lg-btn ghost sm">DOCX</button> <button className="lg-btn ghost sm">PDF</button></td></tr>
                <tr><td>REACH SVHC 등재 후보 리스트 v28</td><td className="dim">ECHA</td><td className="mono">2026.04</td><td><button className="lg-btn ghost sm">DOCX</button> <button className="lg-btn ghost sm">PDF</button></td></tr>
                <tr><td>美 자동차부품 232조 관세 검토안</td><td className="dim">USTR</td><td className="mono">2026.03</td><td><button className="lg-btn ghost sm">DOCX</button> <button className="lg-btn ghost sm">PDF</button></td></tr>
                <tr><td>IATF 16949 Sanctioned Interpretations</td><td className="dim">IATF</td><td className="mono">2026.01</td><td><button className="lg-btn ghost sm">DOCX</button> <button className="lg-btn ghost sm">PDF</button></td></tr>
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
window.Compliance = Compliance;
