// AJIN Mobile — iPhone screens (iOS 26 Liquid Glass).
// Each screen is a body that fits inside an IOSDevice frame (no nav-bar prop —
// we draw our own custom AJIN nav so we control the brand expression).

/* ───────────────────────────────────────── shared bits ───────────────────────────────────────── */
function MobileNav({ title, sub, dark = true, leading, trailing }) {
  // floating glass nav row, sits above content
  return (
    <div style={{
      position: 'absolute', top: 56, left: 0, right: 0, zIndex: 6,
      padding: '0 14px',
    }}>
      <div className="aj-glass" style={{
        height: 52, display: 'grid', gridTemplateColumns: '36px 1fr 36px',
        gap: 8, alignItems: 'center', padding: '0 12px',
      }}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'center'}}>{leading}</div>
        <div style={{textAlign:'center'}}>
          <div style={{fontSize:14,fontWeight:600,letterSpacing:'-0.01em'}}>{title}</div>
          {sub && <div className="aj-mono" style={{fontSize:9,marginTop:1}}>{sub}</div>}
        </div>
        <div style={{display:'flex',alignItems:'center',justifyContent:'center'}}>{trailing}</div>
      </div>
    </div>
  );
}

function MobShellTop({ greeting, name, ts, theme = 'dark' }) {
  return (
    <div style={{ padding: '64px 16px 0', position:'relative', zIndex:5 }}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <div className="aj-brand">
          <div className="mark">A</div>
          <div>
            <div className="word">AJ<i>·</i>IN</div>
            <div className="ko">아진산업</div>
          </div>
        </div>
        <div style={{textAlign:'right'}}>
          <div className="aj-mono" style={{fontSize:9}}>{ts}</div>
        </div>
      </div>
      {greeting && (
        <div style={{marginTop:18}}>
          <div className="aj-mono" style={{fontSize:10,opacity:0.7}}>{greeting}</div>
          <div style={{fontSize:28,fontWeight:700,letterSpacing:'-0.02em',marginTop:4}}>{name}</div>
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────────────────── 1 · LOGIN ───────────────────────────────────────── */
function MobLogin({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <div className={"aj-screen " + theme} style={{position:'relative'}}>
        <div className={"aj-bg-grad " + theme} />
        <div style={{position:'relative', zIndex:2, paddingTop: 100, height:'100%', display:'flex', flexDirection:'column'}}>
          <div style={{textAlign:'center', padding:'12px 16px 4px'}}>
            <div style={{
              width:64, height:64, borderRadius:18, margin:'0 auto 14px',
              background:'linear-gradient(135deg,#FCB132,#B57600)',
              display:'flex', alignItems:'center', justifyContent:'center',
              fontSize:32, fontWeight:800, color:'#07090C', letterSpacing:'-0.04em',
              boxShadow:'0 12px 40px -10px rgba(252,177,50,0.6)',
            }}>A</div>
            <div style={{fontWeight:800, fontSize:20, letterSpacing:'0.18em'}}>AJ·IN</div>
            <div className="aj-mono" style={{marginTop:6, color:'#FCB132'}}>AI ASSISTANT · v2.4</div>
          </div>
          <div className="aj-glass aj-login-card" style={{flex:'0 0 auto'}}>
            <div className="field">
              <label>SOCIAL ID</label>
              <input defaultValue="K-2024-0731" />
            </div>
            <div className="field">
              <label>PASSWORD</label>
              <input type="password" defaultValue="••••••••••" />
            </div>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',fontSize:12}}>
              <label style={{display:'flex',alignItems:'center',gap:8,opacity:0.8}}>
                <span style={{width:18,height:18,borderRadius:5,background:'#FCB132',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#07090C'}}><Icons.Check size={12}/></span>
                Remember me
              </label>
              <a style={{color:'#FCB132',textDecoration:'none'}}>Forgot ID</a>
            </div>
            <button className="aj-btn primary full">Sign In · 로그인</button>
            <div style={{display:'flex',alignItems:'center',gap:10,opacity:0.5}}>
              <div style={{flex:1,height:0.5,background:'rgba(255,255,255,0.16)'}}/>
              <span className="aj-mono" style={{fontSize:9}}>OR</span>
              <div style={{flex:1,height:0.5,background:'rgba(255,255,255,0.16)'}}/>
            </div>
            <button className="aj-btn ghost full">
              <Icons.Profile size={16}/> Face ID
            </button>
          </div>
          <div style={{flex:1}}/>
          <div className="aj-mono" style={{textAlign:'center',padding:'0 0 24px',fontSize:9,opacity:0.5}}>
            ISO 27001 · IATF 16949 · INTERNAL USE ONLY
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────── 2 · DASHBOARD ───────────────────────────────────────── */
function MobDashboard({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <div className={"aj-screen " + theme} style={{position:'relative'}}>
        <div className={"aj-bg-grad " + theme} />
        <MobNotificationDot />
        <MobShellTop greeting="안녕하세요" name="김민수 책임" ts="화 14:23 · CST" theme="dark" />
        <div className="aj-scroll" style={{position:'relative', zIndex:3, marginTop:18}}>
          {/* KPI strip */}
          <div className="aj-grid-2" style={{paddingBottom:6}}>
            <div className="aj-glass aj-kpi">
              <div className="k">QUERIES TODAY</div>
              <div className="v">2,847<i>req</i></div>
              <div className="delta up">+12.4% vs yest</div>
            </div>
            <div className="aj-glass aj-kpi">
              <div className="k">EQUIPMENT OK</div>
              <div className="v">94<i>/97</i></div>
              <div className="delta down">3 alerts</div>
            </div>
          </div>
          {/* Toast */}
          <div style={{padding:'12px 4px'}}>
            <div className="aj-glass aj-toast">
              <div className="icn"><Icons.Warn size={16}/></div>
              <div>
                <div className="ttl">SPC out-of-control · 사출 #03</div>
                <div className="sub">Cpk 0.92 · Nelson Rule 2</div>
              </div>
            </div>
          </div>
          {/* Modules */}
          <div className="aj-sect-h"><h3>Modules · 모듈</h3><span className="more">All</span></div>
          <div className="aj-glass aj-divlist" style={{margin:'0 12px'}}>
            <ModRow icon={<Icons.Chat size={20}/>} ko="AI 채팅" en="CHAT · NLU" meta="Streaming" />
            <ModRow icon={<Icons.Search size={20}/>} ko="문서 검색" en="SEARCH · HYBRID" meta="14ms p95" />
            <ModRow icon={<Icons.Draft size={20}/>} ko="문서 작성" en="DRAFT · GEN-AI" meta="3 templates" />
            <ModRow icon={<Icons.Compliance size={20}/>} ko="규제 모니터" en="COMPLIANCE" meta="3 critical" />
            <ModRow icon={<Icons.Equipment size={20}/>} ko="설비 AI" en="EQUIPMENT" meta="94/97" />
          </div>
          {/* Recent activity */}
          <div className="aj-sect-h"><h3>Recent · 최근 활동</h3></div>
          <div className="aj-glass aj-divlist" style={{margin:'0 12px 14px'}}>
            <ActivityRow ts="14:18" who="설비 AI" what="사출 #03 SPC 알람 발신" tag="ALERT" />
            <ActivityRow ts="13:42" who="문서 작성" what="ECN-2024-0182 초안 완료" tag="DRAFT" />
            <ActivityRow ts="13:05" who="컴플라이언스" what="EU CBAM Q3 보고서 갱신" tag="GEN" />
            <ActivityRow ts="12:48" who="AI 채팅" what="사출 SOP-005 step 4 응답" tag="CHAT" />
          </div>
          <div style={{height:120}} />
        </div>
        {/* Tab bar */}
        <MobTabBar active="home" />
      </div>
    </div>
  );
}
function MobNotificationDot() {
  // top-right tiny status dot above nav
  return null;
}
function ModRow({ icon, ko, en, meta }) {
  return (
    <div className="aj-row">
      <div className="ico">{icon}</div>
      <div>
        <div className="ko">{ko}</div>
        <div className="en">{en}</div>
      </div>
      <div className="meta" style={{display:'flex',alignItems:'center',gap:6}}>{meta}<Icons.ChevronRight size={14}/></div>
    </div>
  );
}
function ActivityRow({ ts, who, what, tag }) {
  return (
    <div style={{display:'grid', gridTemplateColumns:'52px 1fr auto', gap:10, padding:'12px 16px', alignItems:'center'}}>
      <div className="aj-mono" style={{fontSize:11, opacity:0.6}}>{ts}</div>
      <div>
        <div style={{fontSize:14, fontWeight:500}}>{what}</div>
        <div style={{fontSize:11, opacity:0.55, marginTop:1}}>{who}</div>
      </div>
      <span className="aj-status gold">{tag}</span>
    </div>
  );
}

function MobTabBar({ active = 'home' }) {
  const tabs = [
    { k: 'home',   I: Icons.Home,   l: 'HOME' },
    { k: 'search', I: Icons.Search, l: 'SEARCH' },
    { k: 'chat',   I: Icons.Chat,   l: 'CHAT' },
    { k: 'draft',  I: Icons.Draft,  l: 'DRAFT' },
    { k: 'me',     I: Icons.User,   l: 'ME' },
  ];
  return (
    <div className="aj-tabbar" style={{position:'relative', zIndex:8}}>
      {tabs.map(t => (
        <button key={t.k} className={t.k === active ? 'on' : ''}>
          <span className="icn" style={{display:'inline-flex'}}><t.I size={20}/></span>
          <span style={{fontFamily:'"JetBrains Mono",ui-monospace,monospace'}}>{t.l}</span>
        </button>
      ))}
    </div>
  );
}

/* ───────────────────────────────────────── 3 · SEARCH ───────────────────────────────────────── */
function MobSearch({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <div className={"aj-screen " + theme} style={{position:'relative'}}>
        <div className={"aj-bg-grad " + theme} />
        <div style={{paddingTop:64, position:'relative', zIndex:3, height:'100%', display:'flex', flexDirection:'column'}}>
          <div className="aj-title">
            <div className="sub">SEARCH · HYBRID BM25+VEC</div>
            <h1>문서 검색</h1>
          </div>
          {/* Search bar */}
          <div style={{padding:'4px 16px 12px'}}>
            <div className="aj-glass aj-search" style={{borderRadius:18, height:52, padding:'0 16px'}}>
              <span className="icn" style={{display:'inline-flex'}}><Icons.Search size={18}/></span>
              <input defaultValue="사출 SOP 금형 교체" />
              <span className="icn" style={{color:'#FCB132', display:'inline-flex'}}><Icons.Mic size={18}/></span>
            </div>
          </div>
          {/* Filter chips */}
          <div style={{display:'flex', gap:6, padding:'0 16px 14px', overflowX:'auto'}}>
            <span className="aj-chip gold dot">All · 전체</span>
            <span className="aj-chip">SOP</span>
            <span className="aj-chip">ECN</span>
            <span className="aj-chip">Quality</span>
            <span className="aj-chip">HR</span>
          </div>
          <div className="aj-scroll">
            {/* Result card */}
            <div className="aj-stack">
              <ResultCard
                code="SOP-MOLD-005"
                ko="사출 금형 교체 표준작업서"
                en="Mold Change Standard Procedure"
                meta="v3.2 · 2024-09-12 · 생산기술팀"
                score="98.4"
                snippet="3.2 금형 분리 시 안전핀 체결 후 크레인 인양. 반드시 2인 1조."
                tier="public"
              />
              <ResultCard
                code="ECN-2024-0182"
                ko="범퍼 백빔 BOM 변경"
                en="Bumper Back-beam BOM Update"
                meta="2024-10-08 · R&D · approved"
                score="91.7"
                snippet="HSS 590 → 780 변경. 두께 1.2 → 1.0mm. 중량 −0.8kg/대."
                tier="restricted"
              />
              <ResultCard
                code="QM-INC-2308"
                ko="크롬도금 표면 결함 사례"
                en="Chrome Plating Surface Defect Case"
                meta="2023-08-21 · QA · resolved"
                score="86.3"
                snippet="원인: pH 4.1 미달. 대책: 자동 보정 시스템 + 1h 주기 점검."
                tier="public"
              />
            </div>
            <div style={{height:120}} />
          </div>
        </div>
        <MobTabBar active="search" />
      </div>
    </div>
  );
}
function ResultCard({ code, ko, en, meta, score, snippet, tier }) {
  return (
    <div className="aj-glass" style={{padding:14, margin:'0 4px'}}>
      <div style={{display:'flex', alignItems:'center', gap:6, marginBottom:6}}>
        <span className="aj-mono" style={{fontSize:10, color:'#FCB132'}}>{code}</span>
        <span className="aj-status ok">SCORE {score}</span>
        <span className="aj-status" style={{
          marginLeft:'auto',
          background: tier === 'restricted' ? 'rgba(255,117,101,0.18)' : 'rgba(255,255,255,0.08)',
          color: tier === 'restricted' ? '#FF7565' : 'rgba(255,255,255,0.6)',
        }}>{tier === 'restricted' ? 'L3' : 'L1 PUBLIC'}</span>
      </div>
      <div style={{fontSize:16, fontWeight:600, letterSpacing:'-0.01em'}}>{ko}</div>
      <div style={{fontSize:11, opacity:0.5, marginTop:1}}>{en} · {meta}</div>
      <div style={{
        marginTop:10, padding:'10px 12px', borderRadius:12,
        background:'rgba(252,177,50,0.06)',
        borderLeft:'2px solid #FCB132',
        fontSize:13, lineHeight:1.5, opacity:0.92,
      }}>{snippet}</div>
    </div>
  );
}

/* ───────────────────────────────────────── 4 · CHAT ───────────────────────────────────────── */
function MobChat({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <div className={"aj-screen " + theme} style={{position:'relative'}}>
        <div className={"aj-bg-grad " + theme} />
        <MobileNav
          title="AI 채팅"
          sub="GEN · GROUNDED RAG"
          leading={<Icons.ChevronLeft size={18}/>}
          trailing={<Icons.More size={16}/>}
        />
        <div className="aj-scroll" style={{padding:'120px 14px 8px', position:'relative', zIndex:3, display:'flex', flexDirection:'column', gap:10}}>
          <div style={{textAlign:'center', padding:'4px 0 12px'}}>
            <span className="aj-mono" style={{fontSize:9, opacity:0.5}}>오늘 14:18 · 생산기술팀 · GROUNDED</span>
          </div>
          <div className="aj-msg user">
            <div className="meta" style={{color:'rgba(26,16,4,0.7)'}}>김민수 · 14:18</div>
            사출 #03 Cpk 0.92 떨어진 원인이 뭐야?
          </div>
          <div className="aj-msg ai">
            <div className="meta">AJIN AI · 14:18 · 4 sources</div>
            <div style={{marginBottom:8}}>최근 24h 데이터 기준, <b style={{color:'#FCB132'}}>3가지 원인</b>이 식별됩니다.</div>
            <ol style={{margin:'0 0 4px 18px', padding:0, fontSize:14, lineHeight:1.55}}>
              <li>형틀 온도 4.2°C 변동 ↑ <span style={{opacity:0.6, fontSize:11}}>(SPC R2)</span></li>
              <li>원료 lot K-2024-1031 점도 +6%</li>
              <li>금형 #M-140 사용 횟수 14k 도달</li>
            </ol>
            <div style={{marginTop:10, display:'flex', gap:6, flexWrap:'wrap'}}>
              <span className="aj-chip" style={{height:26, fontSize:11}}><Icons.Doc size={12}/> SOP-MOLD-005</span>
              <span className="aj-chip" style={{height:26, fontSize:11}}><Icons.Chart size={12}/> SPC #03</span>
            </div>
          </div>
          <div className="aj-msg user">
            <div className="meta" style={{color:'rgba(26,16,4,0.7)'}}>김민수 · 14:19</div>
            우선순위 조치는?
          </div>
          <div className="aj-msg ai">
            <div className="meta">AJIN AI · 14:19 · streaming</div>
            <b>1순위:</b> 형틀 온도 setpoint 재캘리브레이션 (15min)<br/>
            <b>2순위:</b> 금형 #M-140 예방교체 일정 — D-3<span className="streaming-cursor"/>
          </div>
          <div style={{height:30}} />
        </div>
        <div className="aj-composer" style={{position:'relative', zIndex:5}}>
          <button className="att"><Icons.Plus size={16}/></button>
          <input placeholder="메시지를 입력하세요…" />
          <button className="att"><Icons.Mic size={16}/></button>
          <button className="send"><Icons.ArrowUp size={16}/></button>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────── 5 · DRAFT ───────────────────────────────────────── */
function MobDraft({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <div className={"aj-screen " + theme} style={{position:'relative'}}>
        <div className={"aj-bg-grad " + theme} />
        <MobileNav
          title="문서 작성"
          sub="DRAFT · QUALITY 92"
          leading={<Icons.ChevronLeft size={18}/>}
          trailing={<span className="aj-mono" style={{fontSize:10, color:'#FCB132'}}>SAVE</span>}
        />
        <div className="aj-scroll" style={{padding:'120px 12px 0', position:'relative', zIndex:3}}>
          {/* Quality score card */}
          <div className="aj-glass" style={{padding:18, marginBottom:10}}>
            <div style={{display:'flex', alignItems:'baseline', gap:12, marginBottom:10}}>
              <div style={{fontSize:46, fontWeight:700, letterSpacing:'-0.03em', lineHeight:1, color:'#FCB132', fontFeatureSettings:'"tnum"'}}>92<span style={{fontSize:18, opacity:0.6, marginLeft:2}}>/100</span></div>
              <div style={{padding:'4px 10px', borderRadius:10, background:'rgba(252,177,50,0.18)', color:'#FCB132', fontWeight:700, fontSize:13}}>A · 우수</div>
            </div>
            <div style={{display:'flex', flexDirection:'column', gap:8}}>
              <Bar lbl="STRUCT" v={94} />
              <Bar lbl="CITE" v={88} />
              <Bar lbl="CLARITY" v={95} />
              <Bar lbl="COMPL" v={90} />
            </div>
          </div>
          {/* Editor preview */}
          <div className="aj-glass" style={{padding:14, marginBottom:10}}>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:8}}>
              <span className="aj-mono" style={{fontSize:9, opacity:0.6}}>ECN-2024-0182 · DRAFT</span>
              <span className="aj-mono" style={{fontSize:9, color:'#FCB132'}}>v3 · 2,418 chars</span>
            </div>
            <div style={{fontSize:14, lineHeight:1.65, whiteSpace:'pre-wrap'}}>
              <b>제목:</b> 범퍼 백빔 소재 변경 (HSS 590 → HSS 780)
              {'\n\n'}
              <b>1. 변경 사유</b>{'\n'}
              경량화 목표 −0.8 kg/대 달성 및 충돌 안전성 향상.
              {'\n\n'}
              <b>2. 기술 근거</b>{'\n'}
              R&D 시뮬 결과(Crash CAE) IIHS Small Overlap 기준 +14% 개선…
            </div>
          </div>
          {/* CC chips */}
          <div className="aj-glass" style={{padding:14, marginBottom:10}}>
            <div className="aj-mono" style={{fontSize:9, opacity:0.6, marginBottom:8}}>SUGGESTED CC · 4 PEOPLE</div>
            <div style={{display:'flex', gap:6, flexWrap:'wrap'}}>
              <CCChip n="이정훈 책임" t="R&D · 99%" tone="red" />
              <CCChip n="박서연 매니저" t="QA · 87%" tone="amber" />
              <CCChip n="장동훈 팀장" t="구매 · 76%" tone="amber" />
              <CCChip n="최유진 사원" t="설계 · 62%" tone="gray" />
            </div>
          </div>
          {/* Export */}
          <div className="aj-glass" style={{padding:'10px 12px', display:'flex', gap:6, flexWrap:'wrap', marginBottom:120}}>
            {['DOCX','PDF','HWP','MD','HTML','TXT','EML'].map(x => (
              <span key={x} className="aj-chip" style={{height:30, fontSize:11}}>{x}</span>
            ))}
          </div>
        </div>
        <div className="aj-composer" style={{position:'relative', zIndex:5}}>
          <button className="att"><Icons.Sparkle size={16}/></button>
          <input placeholder="다음 문단을 자동 작성…" />
          <button className="send"><Icons.ArrowUp size={16}/></button>
        </div>
      </div>
    </div>
  );
}
function Bar({ lbl, v }) {
  return (
    <div className="aj-q-bar">
      <div className="lbl">{lbl}</div>
      <div className="track"><i style={{width: v + '%'}}/></div>
      <div className="v">{v}</div>
    </div>
  );
}
function CCChip({ n, t, tone }) {
  const c = tone === 'red' ? '#FF7565' : tone === 'amber' ? '#E8A317' : '#D5CFC5';
  const bg = tone === 'red' ? 'rgba(255,117,101,0.14)' : tone === 'amber' ? 'rgba(232,163,23,0.14)' : 'rgba(255,255,255,0.06)';
  return (
    <span style={{
      padding:'8px 12px', borderRadius:14, background:bg, fontSize:12, lineHeight:1.3,
      display:'inline-flex', flexDirection:'column', gap:1,
    }}>
      <b style={{fontWeight:600, color:'inherit'}}>{n}</b>
      <span className="aj-mono" style={{fontSize:9, color:c}}>{t}</span>
    </span>
  );
}

Object.assign(window, {
  MobLogin, MobDashboard, MobSearch, MobChat, MobDraft, MobileNav, MobTabBar,
});
