// AJIN iPad — Module screens (Search · Draft · Compliance · Admin · Equipment)
// Reuses PadFrame, aj-pad, aj-glass, aj-mono, aj-chip primitives.

/* ─────────────── Shared rail used by all module pads ─────────────── */
function PadRail({ active, theme = "dark" }) {
  const items = [
    { k:'home', I: Icons.Home,       l:'Dashboard',  ko:'대시보드' },
    { k:'chat', I: Icons.Chat,       l:'AI Chat',    ko:'AI 채팅' },
    { k:'srch', I: Icons.Search,     l:'Search',     ko:'검색' },
    { k:'drft', I: Icons.Draft,      l:'Draft',      ko:'문서작성' },
    { k:'cmpl', I: Icons.Compliance, l:'Compliance', ko:'규제' },
    { k:'eqpt', I: Icons.Equipment,  l:'Equipment',  ko:'설비 AI' },
    { k:'admn', I: Icons.Admin,      l:'Admin',      ko:'관리자' },
  ];
  return (
    <div className="rail">
      <div className="aj-brand" style={{padding:'4px 8px 14px'}}>
        <div className="mark" style={{width:36, height:36}}>
          <img src="../../assets/ajin_symbol.svg" alt="AJIN"/>
        </div>
        <div>
          <img
            src={`../../assets/ajin_wordmark_${theme === 'light' ? 'light' : 'dark'}.svg`}
            alt="AJIN INDUSTRIAL CO., LTD."
            style={{height: 18, display:'block', marginBottom: 2}}
          />
          <div className="ko" style={{fontSize:9}}>아진산업 · v2.4</div>
        </div>
      </div>
      {items.map(it => (
        <div key={it.k} className={'rail-row' + (it.k === active ? ' on' : '')}>
          <div className="icn"><it.I size={16}/></div>
          <div>
            <div style={{fontWeight:600, fontSize:14}}>{it.ko}</div>
            <div className="aj-mono" style={{fontSize:9, opacity:0.7, marginTop:1}}>{it.l}</div>
          </div>
        </div>
      ))}
      <div style={{flex:1}} />
      <div className="aj-glass" style={{padding:12, borderRadius:14}}>
        <div style={{display:'flex', alignItems:'center', gap:10}}>
          <div style={{width:36, height:36, borderRadius:999, background:'#FCB132', display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700, color:'#07090C'}}>김</div>
          <div>
            <div style={{fontSize:13, fontWeight:600}}>김민수</div>
            <div className="aj-mono" style={{fontSize:9, opacity:0.6}}>R&D · L2</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PadHeader({ kicker, title, right }) {
  // App Store-style large title (iPad)
  return (
    <div className="as-pad-h" style={{marginBottom:18}}>
      <div>
        <div className="label">{kicker}</div>
        <h2>{title}</h2>
      </div>
      <div style={{display:'flex', alignItems:'center', gap:10}}>{right}</div>
    </div>
  );
}

/* ─────────────── iPad · Search (조직도 + 인원검색) ─────────────── */
function PadSearch({ theme = "dark" } = {}) {
  const depts = [
    { k:'mgmt', ko:'경영지원', en:'Management', n:48, on:false },
    { k:'qual', ko:'품질본부', en:'Quality',     n:62, on:true },
    { k:'prod', ko:'생산기술', en:'Production',  n:118, on:false },
    { k:'sales',ko:'영업본부', en:'Sales',       n:54, on:false },
    { k:'rnd',  ko:'R&D 센터', en:'R&D',         n:97, on:false },
    { k:'esh',  ko:'환경안전', en:'EHS',         n:48, on:false },
  ];
  const teams = ['QA · 품질보증', 'QC · 검사', 'SQE · 협력사품질', 'CQE · 고객품질', '계측 · METROLOGY'];
  const people = [
    { k:'kim', n:'김민수', t:'책임 · L2', tm:'QA · 품질보증', email:'kim.ms@ajin.co.kr', ph:'010-2841-3920', tag:'ON SITE' },
    { k:'lee', n:'이진우', t:'사원 · L1', tm:'QC · 검사',     email:'lee.jw@ajin.co.kr', ph:'010-9128-2920', tag:'ON SITE' },
    { k:'par', n:'박서연', t:'선임 · L1', tm:'SQE · 협력사',   email:'park.sy@ajin.co.kr', ph:'010-5471-0042', tag:'WFH' },
    { k:'cho', n:'조현민', t:'책임 · L3', tm:'CQE · 고객',     email:'cho.hm@ajin.co.kr', ph:'010-7012-1185', tag:'OUT' },
    { k:'jng', n:'정유나', t:'사원 · L1', tm:'QA · 품질보증',  email:'jung.yn@ajin.co.kr', ph:'010-3304-7758', tag:'ON SITE' },
  ];
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3}}>
            <PadRail active="srch" theme={theme} />
            <div className="work">
              <PadHeader
                kicker="DIRECTORY · 인원 검색"
                title="아진산업 조직도"
                right={(
                  <div className="aj-glass aj-search" style={{width:300, height:42, borderRadius:14}}>
                    <span className="icn" style={{display:'inline-flex'}}><Icons.Search size={16}/></span>
                    <input defaultValue="QA 차장" placeholder="이름, 직급, 부서" />
                    <span className="aj-mono" style={{fontSize:10, opacity:0.5, padding:'0 6px', borderRadius:5, background:'rgba(255,255,255,0.06)'}}>⌘K</span>
                  </div>
                )}
              />

              {/* CEO + 6 dept node row */}
              <div className="aj-glass" style={{padding:18, marginBottom:12}}>
                <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                  <h3 style={{fontSize:11}}>본부 · DIVISIONS</h3>
                  <span className="aj-mono" style={{fontSize:10, opacity:0.6}}>6 본부 · 19 팀 · 427명</span>
                </div>
                <div style={{display:'flex', justifyContent:'center', marginBottom:14}}>
                  <div className="aj-glass" style={{padding:'10px 22px', borderRadius:999, fontSize:13}}>
                    <span className="aj-mono" style={{fontSize:10, color:'#FCB132', marginRight:8}}>CEO</span>
                    대표이사 윤영석
                  </div>
                </div>
                <div style={{display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:10}}>
                  {depts.map(d => (
                    <div key={d.k} className={'aj-glass' + (d.on ? ' on-gold' : '')} style={{padding:12, borderRadius:12, textAlign:'center', cursor:'pointer'}}>
                      <div className="aj-mono" style={{fontSize:9, opacity:0.6}}>{d.en.toUpperCase()}</div>
                      <div style={{fontSize:13, fontWeight:600, marginTop:4}}>{d.ko}</div>
                      <div className="aj-mono" style={{fontSize:11, marginTop:6, color: d.on ? '#FCB132' : 'inherit', opacity: d.on ? 1 : 0.5}}>{d.n}명</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 2-up: team chips · directory list */}
              <div style={{display:'grid', gridTemplateColumns:'1fr 1.4fr', gap:12}}>
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>품질본부 · TEAMS</h3>
                    <span className="aj-mono" style={{fontSize:10, color:'#FCB132'}}>62명</span>
                  </div>
                  <div style={{display:'flex', flexWrap:'wrap', gap:8}}>
                    {teams.map((t,i) => (
                      <span key={i} className={'aj-chip' + (i === 0 ? ' gold' : '')} style={{height:30, fontSize:12}}>{t}</span>
                    ))}
                  </div>
                  <div style={{marginTop:18}}>
                    <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginBottom:10}}>FILTERS · 필터</div>
                    <div style={{display:'grid', gap:8}}>
                      {[
                        ['직급', '전체 · 사원 · 선임 · 책임 · 수석'],
                        ['직군', '엔지니어 · 사무 · 현장'],
                        ['상태', '재직 · 휴직 · 출장'],
                      ].map(([k,v],i) => (
                        <div key={i} className="aj-glass" style={{padding:'10px 12px', borderRadius:10, display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                          <div className="aj-mono" style={{fontSize:10, opacity:0.6}}>{k}</div>
                          <div style={{fontSize:12}}>{v}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 8px'}}>
                    <h3 style={{fontSize:11}}>QA · 품질보증 — 12명</h3>
                    <span className="aj-mono" style={{fontSize:10, opacity:0.6}}>이름순 ↓</span>
                  </div>
                  <div className="aj-divlist">
                    {people.map(p => (
                      <div key={p.k} style={{display:'grid', gridTemplateColumns:'40px 1fr auto', gap:12, padding:'12px 0', alignItems:'center'}}>
                        <div style={{width:40, height:40, borderRadius:999, background:'rgba(255,255,255,0.08)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:600}}>{p.n[0]}</div>
                        <div>
                          <div style={{fontSize:14, fontWeight:500}}>{p.n} <span className="aj-mono" style={{fontSize:11, opacity:0.55, marginLeft:6}}>{p.t}</span></div>
                          <div className="aj-mono" style={{fontSize:11, opacity:0.55, marginTop:2}}>{p.tm} · {p.email}</div>
                        </div>
                        <span className={'aj-status ' + (p.tag === 'ON SITE' ? 'gold' : p.tag === 'OUT' ? 'crit' : '')}>{p.tag}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}

/* ─────────────── iPad · Draft (문서 작성) ─────────────── */
function PadDraft({ theme = "dark" } = {}) {
  const docs = [
    { t:'ECN-2024-0182 v3', sub:'사출 #03 setpt 변경', score:92, on:true },
    { t:'8D-2024-0455',     sub:'납품 #K-1031 점도 편차', score:78 },
    { t:'CAPA-2024-0301',   sub:'금형 #M-140 마모', score:84 },
    { t:'PPAP-2024-0112',   sub:'고객 LG·신규 부품', score:96 },
    { t:'안전 일일 점검 v8', sub:'템플릿', score:null },
  ];
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3}}>
            <PadRail active="drft" theme={theme} />
            <div className="work">
              <PadHeader
                kicker="DRAFT · 문서 작성"
                title="ECN-2024-0182 v3"
                right={(
                  <div style={{display:'flex', gap:8}}>
                    <span className="aj-chip" style={{height:34}}><Icons.Documents size={14}/> 가져오기</span>
                    <span className="aj-chip gold dot" style={{height:34}}>품질 92 · 자동저장</span>
                  </div>
                )}
              />
              <div style={{display:'grid', gridTemplateColumns:'240px 1fr 280px', gap:12}}>
                {/* Document list */}
                <div className="aj-glass" style={{padding:14}}>
                  <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginBottom:10}}>DOCUMENTS · 14</div>
                  <div style={{display:'grid', gap:6}}>
                    {docs.map((d,i) => (
                      <div key={i} className={'aj-glass' + (d.on ? ' on-gold' : '')} style={{padding:'10px 12px', borderRadius:10}}>
                        <div style={{fontSize:13, fontWeight:600}}>{d.t}</div>
                        <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginTop:2}}>{d.sub}</div>
                        {d.score !== null && (
                          <div className="aj-mono" style={{fontSize:10, marginTop:4, color: d.score >= 90 ? '#4FB774' : d.score >= 80 ? '#E8A317' : '#FF7565'}}>QA SCORE · {d.score}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                {/* Editor */}
                <div className="aj-glass" style={{padding:18}}>
                  <div style={{display:'flex', gap:6, marginBottom:12, flexWrap:'wrap'}}>
                    {['H1','H2','B','I','U','• List','1. List','〔 〕','/cite'].map((b,i) => (
                      <span key={i} className="aj-chip" style={{height:28, fontSize:11, padding:'0 10px'}}>{b}</span>
                    ))}
                  </div>
                  <div style={{borderTop:'0.5px solid rgba(255,255,255,0.08)', paddingTop:14, fontSize:13.5, lineHeight:1.7}}>
                    <div className="aj-mono" style={{fontSize:10, color:'#FCB132', marginBottom:8}}>ENGINEERING CHANGE NOTICE</div>
                    <h2 style={{fontSize:18, margin:'0 0 10px'}}>사출 #03 형틀 온도 setpoint 변경 (62 → 65°C)</h2>
                    <div style={{opacity:0.85}}>
                      본 ECN은 최근 24시간 내 사출 라인 #03의 Cpk 0.92 저하에 대응하기 위해 발행됩니다. SPC 데이터는 Nelson Rule 2 위반(연속 9 point 평균선 이탈)을 보였으며, R&D 분석 결과 원료 lot K-2024-1031의 점도 변동(+6%)이 주요 원인으로 식별되었습니다.<br/><br/>
                      <b style={{color:'#FCB132'}}>제안 조치:</b> 형틀 온도 setpoint를 <span style={{background:'rgba(252,177,50,0.18)', padding:'2px 6px', borderRadius:4}}>62.4°C → 65.0°C</span>로 상향 조정. 변경 후 24h 내 Cpk 1.33 이상 회복을 검증합니다.<br/><br/>
                      <b style={{color:'#FCB132'}}>근거 자료:</b><br/>
                      - SOP-MOLD-005 (rev. C, 2024-09)<br/>
                      - SPC chart #03 / 2024-10-12 ~ 2024-10-19<br/>
                      - Lot K-2024-1031 COA<span className="streaming-cursor"/>
                    </div>
                  </div>
                </div>
                {/* Inspector */}
                <div className="aj-glass" style={{padding:14}}>
                  <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginBottom:10}}>INSPECTOR · 검토</div>
                  <div style={{display:'grid', gap:8, marginBottom:14}}>
                    {[
                      ['SOP 일관성',  '4 / 4', '#4FB774'],
                      ['수치 검증',   '3 / 3', '#4FB774'],
                      ['용어 표준',   '2 / 3', '#E8A317'],
                      ['승인 필요',   '품질이사 · QA장', '#FCB132'],
                    ].map(([k,v,c],i) => (
                      <div key={i} style={{display:'flex', justifyContent:'space-between', fontSize:12}}>
                        <span style={{opacity:0.7}}>{k}</span>
                        <span className="aj-mono" style={{fontSize:11, color:c}}>{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginBottom:8}}>인용 · 4</div>
                  <div style={{display:'grid', gap:6}}>
                    {[
                      'SOP-MOLD-005 (§4.2)',
                      'SPC chart #03',
                      'Lot K-2024-1031 COA',
                      '품질이사 회의록 10/15',
                    ].map((c,i) => (
                      <span key={i} className="aj-chip" style={{height:28, fontSize:11, justifyContent:'flex-start'}}>
                        <Icons.Doc size={13}/> {c}
                      </span>
                    ))}
                  </div>
                  <button className="btn primary" style={{width:'100%', marginTop:14, height:38, fontSize:12}}>승인 요청 보내기</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}

/* ─────────────── iPad · Compliance (규제 모니터링) ─────────────── */
function PadCompliance({ theme = "dark" } = {}) {
  const items = [
    { ko:'EU CBAM 2단계',    en:'EU·탄소국경조정', d:14, tone:'red',   src:'EUR-Lex 2024/3215', upd:'10/14 03:12' },
    { ko:'K-ESG 공시기준',   en:'금융위·ESG 공시', d:32, tone:'amber', src:'금융위 2024-217',   upd:'10/12 11:08' },
    { ko:'IATF 16949 갱신',  en:'자동차 품질',      d:58, tone:'amber', src:'IATF Notice 2024-7', upd:'10/11 21:47' },
    { ko:'화관법 시행령',    en:'유해화학물질',     d:104, tone:'green', src:'법제처 1124호',     upd:'10/09 14:30' },
    { ko:'중대재해처벌법 가이드', en:'중대재해', d:142, tone:'green', src:'고용노동부 2024-65', upd:'10/05 18:22' },
  ];
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3}}>
            <PadRail active="cmpl" theme={theme} />
            <div className="work">
              <PadHeader
                kicker="COMPLIANCE · 규제 모니터링"
                title="진행 중 12 · 임박 3"
                right={(
                  <div style={{display:'flex', gap:6}}>
                    <span className="aj-chip gold dot" style={{height:32}}>실시간</span>
                    <span className="aj-chip" style={{height:32}}>크롤러 8 · ON</span>
                  </div>
                )}
              />
              {/* KPI strip */}
              <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:12}}>
                <Kpi k="ACTIVE WATCH" v="12" delta="3 임박" />
                <Kpi k="SOURCES" v="64" delta="+4 this wk" up />
                <Kpi k="ALERTS · 7d" v="38" delta="+12.4%" up />
                <Kpi k="AUTO-DRAFTS" v="9" delta="2 검토 중" />
              </div>
              <div style={{display:'grid', gridTemplateColumns:'1fr 1.4fr', gap:12}}>
                {/* Source crawlers */}
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>SOURCES · 크롤러</h3>
                    <span className="aj-mono" style={{fontSize:10, color:'#4FB774'}}>8 / 8 ONLINE</span>
                  </div>
                  {[
                    ['EUR-Lex',          'EU 법령',      '03:12', '#4FB774'],
                    ['금융위',           'K-ESG',        '11:08', '#4FB774'],
                    ['IATF',             '자동차 품질',   '21:47', '#4FB774'],
                    ['법제처',           '국내 법령',    '14:30', '#4FB774'],
                    ['고용노동부',        '안전·산업',     '18:22', '#4FB774'],
                    ['환경부',           '환경 규제',    '09:54', '#E8A317'],
                  ].map((r,i) => (
                    <div key={i} style={{display:'grid', gridTemplateColumns:'1fr auto auto', gap:8, padding:'10px 0', borderBottom:'0.5px solid rgba(255,255,255,0.06)', alignItems:'center'}}>
                      <div>
                        <div style={{fontSize:13, fontWeight:500}}>{r[0]}</div>
                        <div className="aj-mono" style={{fontSize:10, opacity:0.55, marginTop:2}}>{r[1]}</div>
                      </div>
                      <span className="aj-mono" style={{fontSize:10, opacity:0.6}}>{r[2]}</span>
                      <span style={{width:8, height:8, borderRadius:999, background:r[3]}}/>
                    </div>
                  ))}
                </div>
                {/* Items table */}
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>WATCH · 모니터링 항목</h3>
                    <span className="aj-mono" style={{fontSize:10, opacity:0.6}}>D-DAY ↑</span>
                  </div>
                  <div className="aj-divlist">
                    {items.map((it,i) => {
                      const c = it.tone === 'red' ? '#FF7565' : it.tone === 'amber' ? '#E8A317' : '#4FB774';
                      return (
                        <div key={i} style={{display:'grid', gridTemplateColumns:'1fr auto', gap:10, padding:'12px 0'}}>
                          <div>
                            <div style={{fontSize:14, fontWeight:600, display:'flex', alignItems:'center', gap:8}}>
                              <span style={{width:6, height:6, borderRadius:999, background:c}}/>
                              {it.ko}
                            </div>
                            <div className="aj-mono" style={{fontSize:10, opacity:0.55, marginTop:3}}>{it.en} · {it.src} · {it.upd}</div>
                          </div>
                          <div style={{textAlign:'right'}}>
                            <div className="aj-mono" style={{fontSize:14, fontWeight:700, color:c}}>D-{it.d}</div>
                            <div className="aj-mono" style={{fontSize:9, opacity:0.55}}>{it.tone === 'red' ? '즉시' : it.tone === 'amber' ? '계획' : '관찰'}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}

/* ─────────────── iPad · Admin (관리자/보안) ─────────────── */
function PadAdmin({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3}}>
            <PadRail active="admn" theme={theme} />
            <div className="work">
              <PadHeader
                kicker="ADMIN · 인사·보안"
                title="조직 · 권한 · 감사"
                right={(
                  <div style={{display:'flex', gap:6}}>
                    {['보안','권한','감사'].map((t,i) => (
                      <span key={i} className={'aj-chip' + (i === 0 ? ' gold dot' : '')} style={{height:32}}>{t}</span>
                    ))}
                  </div>
                )}
              />
              {/* KPI */}
              <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:12}}>
                <Kpi k="USERS" v="427" delta="+3 this wk" up />
                <Kpi k="ROLES" v="14" delta="2 pending" />
                <Kpi k="MFA COVER" v="98.4%" delta="+1.2%" up />
                <Kpi k="AUDITS · 30d" v="1,284" delta="0 critical" up />
              </div>
              <div style={{display:'grid', gridTemplateColumns:'1.3fr 1fr', gap:12}}>
                {/* Permissions matrix */}
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>PERMISSIONS · 권한 매트릭스</h3>
                    <span className="aj-mono" style={{fontSize:10, opacity:0.6}}>RBAC v2</span>
                  </div>
                  <div style={{display:'grid', gridTemplateColumns:'1.4fr repeat(5, 1fr)', gap:6, fontSize:11}}>
                    <div className="aj-mono" style={{opacity:0.5}}>ROLE \ MODULE</div>
                    {['검색','채팅','문서','규제','설비'].map(m => (
                      <div key={m} className="aj-mono" style={{opacity:0.5, textAlign:'center'}}>{m}</div>
                    ))}
                    {[
                      ['L1 · 사원',     [1,1,0,1,0]],
                      ['L2 · 책임',     [1,1,1,1,1]],
                      ['L3 · 팀장',     [1,1,1,2,2]],
                      ['L4 · 부서장',   [1,1,2,2,2]],
                      ['QA · 품질',     [1,2,2,2,1]],
                      ['EHS · 안전',    [1,1,1,1,2]],
                      ['IT · 시스템',   [2,2,2,2,2]],
                    ].map((row,i) => (
                      <React.Fragment key={i}>
                        <div style={{padding:'10px 0', borderTop:'0.5px solid rgba(255,255,255,0.05)', fontSize:13, fontWeight:500}}>{row[0]}</div>
                        {row[1].map((v,j) => (
                          <div key={j} style={{borderTop:'0.5px solid rgba(255,255,255,0.05)', padding:'10px 0', display:'flex', justifyContent:'center'}}>
                            {v === 0 && <span style={{width:6, height:6, borderRadius:999, background:'rgba(255,255,255,0.18)'}}/>}
                            {v === 1 && <span style={{width:18, height:18, borderRadius:5, border:'1px solid rgba(252,177,50,0.5)', display:'flex', alignItems:'center', justifyContent:'center', color:'#FCB132'}}><Icons.Check size={11}/></span>}
                            {v === 2 && <span style={{width:18, height:18, borderRadius:5, background:'#FCB132', display:'flex', alignItems:'center', justifyContent:'center', color:'#07090C'}}><Icons.Check size={11}/></span>}
                          </div>
                        ))}
                      </React.Fragment>
                    ))}
                  </div>
                  <div style={{display:'flex', gap:14, marginTop:14, fontSize:11, opacity:0.7}}>
                    <span style={{display:'flex', alignItems:'center', gap:6}}><span style={{width:18, height:18, borderRadius:5, border:'1px solid rgba(252,177,50,0.5)'}}/>READ</span>
                    <span style={{display:'flex', alignItems:'center', gap:6}}><span style={{width:18, height:18, borderRadius:5, background:'#FCB132'}}/>WRITE</span>
                    <span style={{display:'flex', alignItems:'center', gap:6}}><span style={{width:6, height:6, borderRadius:999, background:'rgba(255,255,255,0.18)'}}/>NONE</span>
                  </div>
                </div>
                {/* Audit log */}
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>AUDIT LOG · 감사</h3>
                    <span className="aj-mono" style={{fontSize:10, color:'#4FB774'}}>0 CRITICAL</span>
                  </div>
                  <div className="aj-divlist">
                    {[
                      ['14:18', '김민수', 'ECN-2024-0182 v3 발행', 'WRITE', 'ok'],
                      ['13:42', '이진우', 'SPC #03 chart 열람', 'READ',  'ok'],
                      ['13:05', 'system', '컴플라이언스 자동 갱신', 'GEN',  'ok'],
                      ['12:48', '박서연', 'Lot K-2024-1031 COA 다운로드', 'EXP', 'ok'],
                      ['12:14', 'IT',     'L3 → L4 권한 승급 (조현민)', 'ROLE', 'pend'],
                      ['11:39', 'system', 'MFA 미설정 1건 알림', 'WARN', 'warn'],
                    ].map((r,i) => (
                      <div key={i} style={{display:'grid', gridTemplateColumns:'48px 1fr auto', gap:10, padding:'10px 0', alignItems:'center'}}>
                        <span className="aj-mono" style={{fontSize:10, opacity:0.55}}>{r[0]}</span>
                        <div>
                          <div style={{fontSize:13}}>{r[2]}</div>
                          <div className="aj-mono" style={{fontSize:10, opacity:0.55, marginTop:2}}>{r[1]} · {r[3]}</div>
                        </div>
                        <span className={'aj-status ' + (r[4] === 'warn' ? 'crit' : r[4] === 'pend' ? 'gold' : '')}>
                          {r[4] === 'warn' ? 'WARN' : r[4] === 'pend' ? 'PEND' : 'OK'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}

/* ─────────────── iPad · Equipment (설비 AI / SPC) ─────────────── */
function PadEquipment({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3}}>
            <PadRail active="eqpt" theme={theme} />
            <div className="work">
              <PadHeader
                kicker="EQUIPMENT · 설비 AI"
                title="현장 모니터링 · 생산 1공장"
                right={(
                  <div style={{display:'flex', gap:6}}>
                    {['SPC','금형','이상감지','ML 예측'].map((t,i) => (
                      <span key={i} className={'aj-chip' + (i === 0 ? ' gold dot' : '')} style={{height:32}}>{t}</span>
                    ))}
                  </div>
                )}
              />
              {/* Status grid */}
              <div style={{display:'grid', gridTemplateColumns:'repeat(8, 1fr)', gap:8, marginBottom:12}}>
                {[
                  {n:'#01', s:'ok'}, {n:'#02', s:'ok'}, {n:'#03', s:'warn'}, {n:'#04', s:'ok'},
                  {n:'#05', s:'ok'}, {n:'#06', s:'ok'}, {n:'#07', s:'ok'}, {n:'#08', s:'crit'},
                  {n:'#09', s:'ok'}, {n:'#10', s:'ok'}, {n:'#11', s:'ok'}, {n:'#12', s:'ok'},
                  {n:'#13', s:'ok'}, {n:'#14', s:'ok'}, {n:'#15', s:'warn'}, {n:'#16', s:'ok'},
                ].map((m,i) => {
                  const c = m.s === 'ok' ? '#4FB774' : m.s === 'warn' ? '#E8A317' : '#FF7565';
                  return (
                    <div key={i} className="aj-glass" style={{padding:'10px 8px', borderRadius:10, textAlign:'center', borderColor: m.s !== 'ok' ? c : undefined, borderStyle:'solid', borderWidth:m.s !== 'ok' ? 1 : 0.5}}>
                      <div className="aj-mono" style={{fontSize:11, fontWeight:600}}>사출 {m.n}</div>
                      <div style={{width:8, height:8, borderRadius:999, background:c, margin:'6px auto 0'}}/>
                    </div>
                  );
                })}
              </div>
              <div style={{display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:12}}>
                {/* SPC chart */}
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 8px'}}>
                    <div>
                      <h3 style={{fontSize:11}}>SPC · 사출 라인 #03 · 형틀 온도 (°C)</h3>
                      <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginTop:4}}>윈도우 24h · 샘플 144개 · USL 66 · LSL 60</div>
                    </div>
                    <span className="aj-mono" style={{fontSize:10, color:'#E8A317'}}>NELSON R2 · WARN</span>
                  </div>
                  <SparkChart />
                  <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:14, marginTop:14, fontSize:12}}>
                    {[
                      ['Cpk',   '0.92',  '#FF7565'],
                      ['Setpt', '62.4°C','#fff'],
                      ['Mean',  '64.8°C','#FCB132'],
                      ['Drift', '+4.2°C','#FF7565'],
                    ].map(([k,v,c],i) => (
                      <div key={i}>
                        <div className="aj-mono" style={{fontSize:9, opacity:0.5, letterSpacing:'0.18em'}}>{k.toUpperCase()}</div>
                        <div className="aj-mono" style={{fontSize:18, color:c, marginTop:3}}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* ML predictions / mold life */}
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>ML PREDICTIONS · 잔여 수명</h3>
                    <span className="aj-mono" style={{fontSize:10, color:'#FCB132'}}>3 ALERT</span>
                  </div>
                  {[
                    ['#M-140 사출', '14,012/15,000', 93, 'D-3', '#FF7565'],
                    ['#M-088 사출', '8,420/12,000',  70, 'D-21','#E8A317'],
                    ['#M-015 사출', '5,210/15,000',  35, 'D-90','#4FB774'],
                    ['#M-202 검사', '2,101/8,000',   26, 'D-128','#4FB774'],
                  ].map((r,i) => (
                    <div key={i} style={{padding:'10px 0', borderBottom:'0.5px solid rgba(255,255,255,0.06)'}}>
                      <div style={{display:'flex', justifyContent:'space-between', fontSize:13, marginBottom:6}}>
                        <span style={{fontWeight:500}}>{r[0]}</span>
                        <span className="aj-mono" style={{fontSize:11, color:r[4]}}>{r[3]}</span>
                      </div>
                      <div style={{display:'flex', alignItems:'center', gap:10}}>
                        <div style={{flex:1, height:6, background:'rgba(255,255,255,0.06)', borderRadius:99, overflow:'hidden'}}>
                          <div style={{width:r[2]+'%', height:'100%', background:r[4]}}/>
                        </div>
                        <span className="aj-mono" style={{fontSize:10, opacity:0.6, minWidth:80, textAlign:'right'}}>{r[1]}</span>
                      </div>
                    </div>
                  ))}
                  <button className="btn primary" style={{width:'100%', marginTop:14, height:38, fontSize:12}}>예방교체 워크플로 · #M-140</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}

Object.assign(window, { PadSearch, PadDraft, PadCompliance, PadAdmin, PadEquipment });
