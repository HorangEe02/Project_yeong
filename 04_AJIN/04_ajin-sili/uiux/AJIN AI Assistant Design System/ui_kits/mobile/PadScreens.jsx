// AJIN Tablet — iPadOS 26 split-view screens. Renders inside an IOSDevice
// frame at 1024x720 landscape (we override width/height on the device).

function PadFrame({ children, dark = true, width = 1024, height = 720 }) {
  // A simplified iPad bezel — skinnier corners than iPhone, no dynamic island.
  return (
    <div style={{
      width, height, borderRadius: 30, overflow:'hidden', position:'relative',
      background: dark ? '#000' : '#F2F2F7',
      boxShadow:'0 28px 70px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.12)',
      fontFamily:'-apple-system, system-ui, sans-serif',
      WebkitFontSmoothing:'antialiased',
    }}>
      {/* status bar */}
      <div style={{
        position:'absolute', top:0, left:0, right:0, zIndex:30,
        height:42, padding:'0 36px', display:'flex', alignItems:'center',
        justifyContent:'space-between',
        color: dark ? '#fff' : '#000',
        fontFamily:'-apple-system,"SF Pro",system-ui',
      }}>
        <span style={{fontSize:14, fontWeight:600}}>9:41 화</span>
        <div style={{display:'flex', gap:6, alignItems:'center'}}>
          <svg width="17" height="11" viewBox="0 0 17 11"><rect x="0" y="7" width="3" height="4" rx="0.6" fill="currentColor"/><rect x="4.5" y="5" width="3" height="6" rx="0.6" fill="currentColor"/><rect x="9" y="2" width="3" height="9" rx="0.6" fill="currentColor"/><rect x="13.5" y="0" width="3" height="11" rx="0.6" fill="currentColor"/></svg>
          <span style={{fontSize:12, opacity:0.7}}>5G</span>
          <svg width="24" height="11" viewBox="0 0 24 11"><rect x="0.5" y="0.5" width="20" height="10" rx="2.5" stroke="currentColor" strokeOpacity="0.4" fill="none"/><rect x="2" y="2" width="17" height="7" rx="1.5" fill="currentColor"/></svg>
        </div>
      </div>
      {children}
    </div>
  );
}

/* ───────────────────────────────────────── iPad · Dashboard ───────────────────────────────────────── */
function PadDashboard({ theme = "dark" } = {}) {
  const items = [
    { k:'home', I: Icons.Home,       l:'Dashboard',  ko:'대시보드', on:true },
    { k:'chat', I: Icons.Chat,       l:'AI Chat',    ko:'AI 채팅' },
    { k:'srch', I: Icons.Search,     l:'Search',     ko:'검색' },
    { k:'drft', I: Icons.Draft,      l:'Draft',      ko:'문서작성' },
    { k:'cmpl', I: Icons.Compliance, l:'Compliance', ko:'규제' },
    { k:'eqpt', I: Icons.Equipment,  l:'Equipment',  ko:'설비 AI' },
    { k:'admn', I: Icons.Admin,      l:'Admin',      ko:'관리자' },
  ];
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3}}>
            {/* Sidebar */}
            <div className="rail">
              <div className="aj-brand" style={{padding:'4px 8px 14px'}}>
                <div className="mark" style={{width:32, height:32, fontSize:16}}>A</div>
                <div>
                  <div className="word" style={{fontSize:14}}>AJ<i>·</i>IN</div>
                  <div className="ko" style={{fontSize:9}}>아진산업 · v2.4</div>
                </div>
              </div>
              {items.map(it => (
                <div key={it.k} className={'rail-row' + (it.on ? ' on' : '')}>
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
                  <div style={{width:36, height:36, borderRadius:999, background:'linear-gradient(135deg,#FCB132,#B57600)', display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700, color:'#07090C'}}>김</div>
                  <div>
                    <div style={{fontSize:13, fontWeight:600}}>김민수</div>
                    <div className="aj-mono" style={{fontSize:9, opacity:0.6}}>R&D · L2</div>
                  </div>
                </div>
              </div>
            </div>
            {/* Workspace */}
            <div className="work">
              <div style={{display:'flex', alignItems:'baseline', justifyContent:'space-between', marginBottom:18}}>
                <div>
                  <div className="aj-mono" style={{fontSize:10, color:'#FCB132'}}>DASHBOARD · 화 14:23</div>
                  <h1 style={{margin:'4px 0 0', fontSize:32, fontWeight:700, letterSpacing:'-0.02em'}}>안녕하세요, 김민수 책임</h1>
                </div>
                <div className="aj-glass aj-search" style={{width:280, height:42, borderRadius:14}}>
                  <span className="icn" style={{display:'inline-flex'}}><Icons.Search size={16}/></span>
                  <input defaultValue="" placeholder="검색…" />
                  <span className="aj-mono" style={{fontSize:10, opacity:0.5, padding:'0 6px', borderRadius:5, background:'rgba(255,255,255,0.06)'}}>⌘K</span>
                </div>
              </div>
              {/* KPI strip */}
              <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:12, marginBottom:14}}>
                <Kpi k="QUERIES TODAY" v="2,847" delta="+12.4%" up />
                <Kpi k="EQUIPMENT OK" v="94/97" delta="3 alerts" />
                <Kpi k="SOP COVERAGE" v="98.2%" delta="+0.6%" up />
                <Kpi k="DRAFTS PENDING" v="14" delta="2 urgent" />
              </div>
              {/* 2-up panels */}
              <div style={{display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:12}}>
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>SPC · 사출 라인 #03</h3>
                    <span className="aj-mono" style={{fontSize:10, color:'#E8A317'}}>NELSON R2 · WARN</span>
                  </div>
                  <SparkChart />
                  <div style={{display:'flex', gap:18, marginTop:12, fontSize:12, opacity:0.7}}>
                    <span><b style={{fontFamily:'"JetBrains Mono",ui-monospace,monospace', fontSize:14, color:'#fff'}}>0.92</b> Cpk</span>
                    <span><b style={{fontFamily:'"JetBrains Mono",ui-monospace,monospace', fontSize:14, color:'#fff'}}>62.4°C</b> setpt</span>
                    <span><b style={{fontFamily:'"JetBrains Mono",ui-monospace,monospace', fontSize:14, color:'#FF7565'}}>+4.2°C</b> drift</span>
                  </div>
                </div>
                <div className="aj-glass" style={{padding:18}}>
                  <div className="aj-sect-h" style={{padding:'0 0 12px'}}>
                    <h3 style={{fontSize:11}}>Critical · 컴플라이언스</h3>
                    <span className="aj-mono" style={{fontSize:10, color:'#FF7565'}}>3 ITEMS</span>
                  </div>
                  <ComplItem ko="EU CBAM 2단계" en="D-14" tone="red" />
                  <ComplItem ko="K-ESG 공시기준" en="D-32" tone="amber" />
                  <ComplItem ko="IATF 16949 갱신" en="D-58" tone="amber" />
                </div>
              </div>
              {/* Recent */}
              <div className="aj-glass" style={{padding:18, marginTop:12}}>
                <div className="aj-sect-h" style={{padding:'0 0 8px'}}>
                  <h3 style={{fontSize:11}}>Activity · 최근</h3>
                  <span className="aj-mono" style={{fontSize:10, opacity:0.6}}>LIVE</span>
                </div>
                <div className="aj-divlist">
                  <PadActivity ts="14:18" who="설비 AI" what="사출 #03 SPC Nelson R2 발생" tag="ALERT" tone="red" />
                  <PadActivity ts="13:42" who="문서 작성" what="ECN-2024-0182 v3 초안 — 품질점수 92" tag="DRAFT" />
                  <PadActivity ts="13:05" who="컴플라이언스" what="EU CBAM Q3 보고서 자동 갱신" tag="GEN" />
                  <PadActivity ts="12:48" who="AI 채팅" what="@생산기술 SOP-MOLD-005 step 4 응답" tag="CHAT" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}
function Kpi({ k, v, delta, up }) {
  return (
    <div className="aj-glass aj-kpi" style={{padding:'14px 16px'}}>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className={'delta ' + (up ? 'up' : '')}>{delta}</div>
    </div>
  );
}
function ComplItem({ ko, en, tone }) {
  const c = tone === 'red' ? '#FF7565' : '#E8A317';
  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr auto', padding:'10px 0', borderBottom:'0.5px solid rgba(255,255,255,0.06)'}}>
      <div style={{fontSize:13, fontWeight:500}}>{ko}</div>
      <span className="aj-mono" style={{fontSize:11, color:c}}>{en}</span>
    </div>
  );
}
function PadActivity({ ts, who, what, tag, tone }) {
  const cls = tone === 'red' ? 'crit' : 'gold';
  return (
    <div style={{display:'grid', gridTemplateColumns:'56px 1fr auto', gap:10, padding:'12px 0', alignItems:'center'}}>
      <div className="aj-mono" style={{fontSize:11, opacity:0.6}}>{ts}</div>
      <div>
        <div style={{fontSize:14}}>{what}</div>
        <div style={{fontSize:11, opacity:0.55, marginTop:1}}>{who}</div>
      </div>
      <span className={'aj-status ' + cls}>{tag}</span>
    </div>
  );
}

function SparkChart() {
  // Inline SVG SPC-style mini chart
  const pts = [62.0,62.1,62.2,61.9,62.1,62.3,62.5,63.0,63.5,64.2,64.8,65.6,66.0,66.4];
  const min = 60, max = 68;
  const w = 540, h = 140;
  const x = i => 8 + (i / (pts.length - 1)) * (w - 16);
  const y = v => h - 16 - ((v - min) / (max - min)) * (h - 24);
  const path = pts.map((p,i) => (i === 0 ? 'M' : 'L') + x(i) + ',' + y(p)).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{width:'100%', height:140}}>
      <defs>
        <linearGradient id="lg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#FCB132" stopOpacity="0.45"/>
          <stop offset="100%" stopColor="#FCB132" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {/* USL/LSL */}
      <line x1="8" x2={w-8} y1={y(66.0)} y2={y(66.0)} stroke="#FF7565" strokeWidth="0.7" strokeDasharray="3 4"/>
      <line x1="8" x2={w-8} y1={y(60.0)} y2={y(60.0)} stroke="#FF7565" strokeWidth="0.7" strokeDasharray="3 4"/>
      <line x1="8" x2={w-8} y1={y(63.0)} y2={y(63.0)} stroke="rgba(255,255,255,0.18)" strokeWidth="0.6"/>
      <path d={`${path} L ${x(pts.length-1)},${h-16} L ${x(0)},${h-16} Z`} fill="url(#lg)"/>
      <path d={path} fill="none" stroke="#FCB132" strokeWidth="2"/>
      {pts.map((p,i) => (
        <circle key={i} cx={x(i)} cy={y(p)} r={i >= pts.length-3 ? 4 : 2.4}
          fill={i >= pts.length-3 ? '#FF7565' : '#FCB132'}/>
      ))}
    </svg>
  );
}

/* ───────────────────────────────────────── iPad · Chat ───────────────────────────────────────── */
function PadChat({ theme = "dark" } = {}) {
  const convos = [
    { t:'사출 #03 Cpk 분석', sub:'14:18 · streaming', on:true },
    { t:'ECN-2024-0182 검토', sub:'13:42 · 4 sources' },
    { t:'EU CBAM 2단계', sub:'어제 · 12 sources' },
    { t:'금형 #M-140 교체', sub:'어제' },
    { t:'안전사고 trend', sub:'10/08' },
  ];
  return (
    <div className="aj-mobile">
      <PadFrame dark={theme === "dark"}>
        <div className={"aj-screen " + theme} style={{height:'100%', position:'relative'}}>
          <div className={"aj-bg-grad " + theme} />
          <div className={"aj-pad " + theme} style={{position:'relative', zIndex:3, gridTemplateColumns:'320px 1fr'}}>
            {/* Convo list rail */}
            <div className="rail" style={{padding:'68px 14px 14px'}}>
              <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 6px 12px'}}>
                <div className="aj-mono" style={{fontSize:10, color:'#FCB132'}}>CONVERSATIONS</div>
                <span style={{display:'inline-flex', opacity:0.6, cursor:'pointer'}}><Icons.Plus size={18}/></span>
              </div>
              <div className="aj-glass aj-search" style={{height:36, padding:'0 12px', marginBottom:10}}>
                <span className="icn" style={{display:'inline-flex'}}><Icons.Search size={14}/></span>
                <input placeholder="대화 검색" />
              </div>
              {convos.map((c,i) => (
                <div key={i} className={'rail-row' + (c.on ? ' on' : '')} style={{display:'block', padding:'10px 12px'}}>
                  <div style={{fontSize:14, fontWeight:500}}>{c.t}</div>
                  <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginTop:2}}>{c.sub}</div>
                </div>
              ))}
            </div>
            {/* Chat workspace */}
            <div style={{display:'grid', gridTemplateRows:'auto 1fr auto', height:'100%', padding:'56px 0 0', position:'relative'}}>
              {/* Header */}
              <div style={{padding:'16px 28px 14px', borderBottom:'0.5px solid rgba(255,255,255,0.06)'}}>
                <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
                  <div>
                    <div style={{fontSize:18, fontWeight:600}}>사출 #03 Cpk 분석</div>
                    <div className="aj-mono" style={{fontSize:10, opacity:0.6, marginTop:2}}>GROUNDED · 4 SOURCES · 생산기술팀</div>
                  </div>
                  <div style={{display:'flex', gap:6}}>
                    <span className="aj-chip">@생산기술</span>
                    <span className="aj-chip gold dot">RAG ON</span>
                  </div>
                </div>
              </div>
              {/* Messages */}
              <div style={{padding:'18px 28px', overflowY:'auto', display:'flex', flexDirection:'column', gap:12}}>
                <div className="aj-msg user" style={{maxWidth:'70%'}}>
                  <div className="meta" style={{color:'rgba(26,16,4,0.7)'}}>김민수 · 14:18</div>
                  사출 #03 Cpk 0.92 떨어진 원인이 뭐야? 최근 24시간 데이터 기준으로 알려줘.
                </div>
                <div className="aj-msg ai" style={{maxWidth:'78%'}}>
                  <div className="meta">AJIN AI · 14:18 · 4 sources cited</div>
                  <div style={{marginBottom:10}}>최근 24h 데이터 기준 <b style={{color:'#FCB132'}}>3가지 주요 원인</b>이 식별됩니다:</div>
                  <ol style={{margin:'0 0 8px 18px', padding:0, fontSize:14, lineHeight:1.7}}>
                    <li>형틀 온도 setpoint <b style={{color:'#FCB132'}}>62.4°C → 66.6°C</b> drift (Nelson Rule 2)</li>
                    <li>원료 lot K-2024-1031 점도 <b>+6%</b> 변동</li>
                    <li>금형 #M-140 사용 횟수 <b>14,000회</b> 도달 (수명 임박)</li>
                  </ol>
                  <div style={{marginTop:12, display:'flex', gap:6, flexWrap:'wrap'}}>
                    <span className="aj-chip" style={{height:28, fontSize:11}}><Icons.Doc size={13}/> SOP-MOLD-005</span>
                    <span className="aj-chip" style={{height:28, fontSize:11}}><Icons.Chart size={13}/> SPC #03 chart</span>
                    <span className="aj-chip" style={{height:28, fontSize:11}}><Icons.Documents size={13}/> Lot K-2024-1031 COA</span>
                    <span className="aj-chip" style={{height:28, fontSize:11}}><Icons.Equipment size={13}/> #M-140 maintenance log</span>
                  </div>
                </div>
                <div className="aj-msg user" style={{maxWidth:'70%'}}>
                  <div className="meta" style={{color:'rgba(26,16,4,0.7)'}}>김민수 · 14:19</div>
                  우선순위별 조치 방안을 정리해줘.
                </div>
                <div className="aj-msg ai" style={{maxWidth:'78%'}}>
                  <div className="meta">AJIN AI · 14:19 · streaming</div>
                  <div style={{display:'grid', gap:6, fontSize:14, lineHeight:1.6}}>
                    <div><b style={{color:'#FF7565'}}>1순위 (즉시):</b> 형틀 온도 setpoint 재캘리브레이션 — 예상 15분</div>
                    <div><b style={{color:'#E8A317'}}>2순위 (D-3):</b> 금형 #M-140 예방교체 — 백업 #M-140B 가용</div>
                    <div><b style={{color:'#4FB774'}}>3순위 (D-7):</b> Lot K-2024-1031 잔량 소진 후 신규 lot 적용<span className="streaming-cursor"/></div>
                  </div>
                </div>
              </div>
              {/* Composer */}
              <div style={{padding:'14px 28px 18px', borderTop:'0.5px solid rgba(255,255,255,0.06)'}}>
                <div className="aj-composer" style={{margin:0}}>
                  <button className="att"><Icons.Plus size={16}/></button>
                  <input placeholder="메시지를 입력하거나 슬래시 명령을 사용하세요…" />
                  <button className="att"><Icons.Mic size={16}/></button>
                  <button className="send"><Icons.ArrowUp size={16}/></button>
                </div>
                <div style={{display:'flex', gap:6, marginTop:10}}>
                  <span className="aj-chip" style={{height:28, fontSize:11}}>/sop</span>
                  <span className="aj-chip" style={{height:28, fontSize:11}}>/draft</span>
                  <span className="aj-chip" style={{height:28, fontSize:11}}>/spc</span>
                  <span className="aj-chip" style={{height:28, fontSize:11}}>/cite</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </PadFrame>
    </div>
  );
}

Object.assign(window, { PadDashboard, PadChat, PadFrame });
