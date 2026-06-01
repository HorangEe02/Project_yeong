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
          <div className="mark"><img src="../../assets/ajin_symbol.svg" alt="AJIN"/></div>
          <div>
            <img
              src={`../../assets/ajin_wordmark_${theme === 'light' ? 'light' : 'dark'}.svg`}
              alt="AJIN INDUSTRIAL CO., LTD."
              style={{height: 20, display:'block', marginBottom: 2}}
            />
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
            <img
              src={`../../assets/ajin_logo_${theme === 'light' ? 'light' : 'dark'}.svg`}
              alt="AJIN INDUSTRIAL CO., LTD."
              style={{height: 56, display:'block', margin:'0 auto 14px', filter:'drop-shadow(0 12px 32px rgba(252,177,50,0.35))'}}
            />
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
        <MobShellTop greeting="화요일, 5월 13" name="안녕하세요, 김민수 책임" ts="14:23 · CST" theme="dark" />
        <div className="aj-scroll" style={{position:'relative', zIndex:3, marginTop:18}}>
          {/* App-Store-style HERO of the day */}
          <div style={{padding:'4px 12px 16px'}}>
            <div className="aj-as-hero">
              <div className="bg" />
              <div className="overlay" />
              <div className="content">
                <div className="overline">오늘의 인사이트 · STORY OF THE DAY</div>
                <div className="ttl">사출 #03 라인을<br/>지금 점검해야 합니다</div>
                <div className="sub">SPC Nelson R2 · Cpk 0.92 · 형틀 온도 +4.2°C drift</div>
                <div className="cta">
                  <div className="ico-tile"><Icons.Equipment size={20}/></div>
                  <div className="meta">
                    <div className="t">설비 AI · Equipment</div>
                    <div className="s">실시간 분석 · 14ms p95</div>
                  </div>
                  <button className="get">열기</button>
                </div>
              </div>
            </div>
          </div>
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
          <div className="aj-as-sect"><div><div className="label">MODULES · 모듈</div><h2>업무에 필요한 모든 것</h2></div><span className="more">전체</span></div>
          <div className="aj-glass aj-divlist" style={{margin:'0 12px'}}>
            <ModRow icon={<Icons.Chat size={20}/>} ko="AI 채팅" en="CHAT · NLU" meta="Streaming" />
            <ModRow icon={<Icons.Search size={20}/>} ko="문서 검색" en="SEARCH · HYBRID" meta="14ms p95" />
            <ModRow icon={<Icons.Draft size={20}/>} ko="문서 작성" en="DRAFT · GEN-AI" meta="3 templates" />
            <ModRow icon={<Icons.Compliance size={20}/>} ko="규제 모니터" en="COMPLIANCE" meta="3 critical" />
            <ModRow icon={<Icons.Equipment size={20}/>} ko="설비 AI" en="EQUIPMENT" meta="94/97" />
          </div>
          {/* Recent activity */}
          <div className="aj-as-sect"><div><div className="label">RECENT · 최근 활동</div><h2>오늘의 흐름</h2></div></div>
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

/* ───────────────────────────────────────── 3 · SEARCH (App Store · Search form) ───────────────────────────────────────── */
function MobSearch({ theme = "dark" } = {}) {
  return (
    <div className="aj-mobile">
      <div className={"aj-screen " + theme} style={{position:'relative'}}>
        <div className={"aj-bg-grad " + theme} />
        <div className="aj-scroll" style={{paddingTop:60, position:'relative', zIndex:3, height:'100%'}}>
          {/* Large-title header (App Store style) */}
          <div className="aj-as-title">
            <div className="ttl-row">
              <h1>검색</h1>
              <div className="av">김</div>
            </div>
            <div className="aj-mono" style={{fontSize:10, marginTop:6, color:'#FCB132', letterSpacing:'0.18em'}}>HYBRID · BM25 + VECTOR</div>
          </div>
          {/* iOS search field */}
          <div style={{padding:'0 16px 18px'}}>
            <div className="aj-glass aj-search" style={{borderRadius:12, height:38, padding:'0 12px', background:'rgba(255,255,255,0.08)'}}>
              <span className="icn" style={{display:'inline-flex', opacity:0.6}}><Icons.Search size={16}/></span>
              <input placeholder="문서, SOP, ECN, 사람 검색" />
              <span className="icn" style={{color:'#FCB132', display:'inline-flex'}}><Icons.Mic size={16}/></span>
            </div>
          </div>
          {/* Categories grid (App Store Search » Browse Categories) */}
          <div className="aj-as-sect" style={{padding:'0 20px 12px'}}>
            <div>
              <div className="label">BROWSE · 카테고리</div>
              <h2>찾고 싶은 것</h2>
            </div>
          </div>
          <div className="aj-as-catgrid">
            <div className="aj-as-cat t1">
              <div className="glyph"><Icons.Doc size={28}/></div>
              <div className="lbl">표준작업서<br/><span style={{fontSize:11, fontWeight:500, opacity:0.85}}>SOP · 1,284</span></div>
            </div>
            <div className="aj-as-cat t2">
              <div className="glyph"><Icons.Documents size={26}/></div>
              <div className="lbl">설계 변경<br/><span style={{fontSize:11, fontWeight:500, opacity:0.85}}>ECN · 412</span></div>
            </div>
            <div className="aj-as-cat t3">
              <div className="glyph"><Icons.Chart size={26}/></div>
              <div className="lbl">품질·SPC<br/><span style={{fontSize:11, fontWeight:500, opacity:0.85}}>QM · 2,108</span></div>
            </div>
            <div className="aj-as-cat t4">
              <div className="glyph"><Icons.User size={26}/></div>
              <div className="lbl">조직·HR<br/><span style={{fontSize:11, fontWeight:500, opacity:0.85}}>PEOPLE · 427</span></div>
            </div>
            <div className="aj-as-cat t5">
              <div className="glyph"><Icons.Compliance size={26}/></div>
              <div className="lbl">규제·법규<br/><span style={{fontSize:11, fontWeight:500, opacity:0.85}}>REG · 64</span></div>
            </div>
            <div className="aj-as-cat t6">
              <div className="glyph"><Icons.Equipment size={26}/></div>
              <div className="lbl">설비·MES<br/><span style={{fontSize:11, fontWeight:500, opacity:0.85}}>EQP · 184</span></div>
            </div>
          </div>

          {/* Suggested results — App Store app row form */}
          <div className="aj-as-sect" style={{padding:'20px 20px 6px'}}>
            <div>
              <div className="label">SUGGESTED · 추천 결과</div>
              <h2>지금 보면 좋아요</h2>
            </div>
            <span className="more">전체 ›</span>
          </div>
          <div className="aj-glass" style={{margin:'0 12px', padding:'4px 0'}}>
            <AppRow tone="gold" icon={<Icons.Doc size={28}/>}
              ko="사출 금형 교체 SOP" sub="표준작업서 · 생산기술팀"
              iap="SOP-MOLD-005 · v3.2" badge="열기" />
            <AppRow tone="blue" icon={<Icons.Documents size={26}/>}
              ko="범퍼 백빔 BOM 변경" sub="설계 변경 · R&D"
              iap="ECN-2024-0182 · L3" badge="열기" />
            <AppRow tone="red" icon={<Icons.Chart size={26}/>}
              ko="크롬도금 표면 결함 사례" sub="품질 사례 · QA"
              iap="QM-INC-2308 · RESOLVED" badge="열기" />
          </div>

          {/* Recents (App Store search) */}
          <div className="aj-as-sect" style={{padding:'24px 20px 0'}}>
            <div>
              <div className="label">RECENT · 최근 검색</div>
              <h2>다시 보기</h2>
            </div>
            <span className="more">전체 지우기</span>
          </div>
          <div style={{margin:'4px 16px 0', borderTop:'0.5px solid rgba(255,255,255,0.08)'}}>
            <RecRow t="사출 #03 Cpk 회복 사례" />
            <RecRow t="ECN 승인 워크플로우" />
            <RecRow t="이정훈 책임 · R&D" />
            <RecRow t="EU CBAM 2단계 영향도" />
            <RecRow t="금형 #M-140 예방교체" />
          </div>
          <div style={{height:140}} />
        </div>
        <MobTabBar active="search" />
      </div>
    </div>
  );
}
function AppRow({ tone='dark', icon, ko, sub, iap, badge='GET' }) {
  return (
    <div className="aj-as-approw">
      <div className={'tile ' + tone}>{icon}</div>
      <div className="meta">
        <div className="nm">{ko}</div>
        <div className="sub">{sub}</div>
        {iap && <div className="iap">{iap}</div>}
      </div>
      <button className="get">{badge}</button>
    </div>
  );
}
function RecRow({ t }) {
  return (
    <div className="aj-as-rec">
      <span className="icn"><Icons.Search size={16}/></span>
      <span className="lbl">{t}</span>
      <span className="x"><Icons.Plus size={14} style={{transform:'rotate(45deg)'}}/></span>
    </div>
  );
}

/* ───────────────────────────────────────── 4 · CHAT (App Store · Today form) ───────────────────────────────────────── */
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
        <div className="aj-scroll" style={{paddingTop:120, position:'relative', zIndex:3}}>
          {/* Today-style story card up top */}
          <div className="aj-as-story" style={{background:'#3A2510'}}>
            <div className="ovr"/>
            <div className="stack">
              <div>
                <div className="eyebrow">GROUNDED · 4 SOURCES</div>
                <h2>사출 #03 Cpk 0.92<br/>회복 시나리오</h2>
              </div>
              <div className="bottom">
                <div className="tile"><Icons.Chat size={22}/></div>
                <div>
                  <div className="nm">AJIN AI · v2.4</div>
                  <div className="sub">14:18 · STREAMING</div>
                </div>
                <button className="get">OPEN</button>
              </div>
            </div>
          </div>
        </div>
        <div className="aj-scroll" style={{padding:'8px 14px 8px', position:'relative', zIndex:3, display:'flex', flexDirection:'column', gap:10, marginTop:-10}}>
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

/* ───────────────────────────────────────── 5 · DRAFT (App Store · App detail form) ───────────────────────────────────────── */
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
        <div className="aj-scroll" style={{padding:'108px 0 0', position:'relative', zIndex:3}}>
          {/* App-Store "App detail" header — icon, title, subtitle, GET */}
          <div className="aj-as-approw" style={{padding:'16px 20px 14px'}}>
            <div className="tile gold" style={{width:88, height:88, borderRadius:20, fontSize:34}}>
              <Icons.Draft size={40}/>
            </div>
            <div className="meta" style={{marginLeft:4}}>
              <div className="nm" style={{fontSize:18}}>ECN-2024-0182</div>
              <div className="sub" style={{fontSize:13, opacity:0.7, whiteSpace:'normal'}}>사출 #03 setpoint 변경 · v3</div>
              <div className="iap" style={{marginTop:4}}>DRAFT · 2,418 CHARS</div>
            </div>
            <button className="get solid">SUBMIT</button>
          </div>
          {/* Stats strip — like App Store ratings/age/category row */}
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', padding:'10px 20px 18px', gap:8, borderBottom:'0.5px solid rgba(255,255,255,0.08)'}}>
            <div style={{textAlign:'center'}}>
              <div className="aj-mono" style={{fontSize:9, opacity:0.55, letterSpacing:'0.18em'}}>QUALITY</div>
              <div style={{fontSize:18, fontWeight:800, color:'#FCB132', marginTop:4, fontFeatureSettings:'"tnum"'}}>92<span style={{fontSize:11, opacity:0.6}}>/100</span></div>
              <div className="stars" style={{display:'flex', justifyContent:'center', gap:1, color:'#FCB132', marginTop:2, fontSize:11}}>★★★★★</div>
            </div>
            <div style={{textAlign:'center', borderLeft:'0.5px solid rgba(255,255,255,0.08)', borderRight:'0.5px solid rgba(255,255,255,0.08)'}}>
              <div className="aj-mono" style={{fontSize:9, opacity:0.55, letterSpacing:'0.18em'}}>TIER</div>
              <div style={{fontSize:18, fontWeight:800, marginTop:4}}>L3</div>
              <div className="aj-mono" style={{fontSize:9, opacity:0.5, marginTop:2}}>RESTRICTED</div>
            </div>
            <div style={{textAlign:'center'}}>
              <div className="aj-mono" style={{fontSize:9, opacity:0.55, letterSpacing:'0.18em'}}>OWNER</div>
              <div style={{fontSize:18, fontWeight:800, marginTop:4}}>R&D</div>
              <div className="aj-mono" style={{fontSize:9, opacity:0.5, marginTop:2}}>이정훈 책임</div>
            </div>
          </div>
          {/* Quality score breakdown */}
          <div className="aj-as-sect" style={{padding:'14px 20px 8px'}}>
            <div><div className="label">QUALITY · 품질 점수</div><h2>4개 항목 검사</h2></div>
          </div>
          <div className="aj-glass" style={{padding:16, margin:'0 16px 14px'}}>
            <div style={{display:'flex', flexDirection:'column', gap:8}}>
              <Bar lbl="STRUCT" v={94} />
              <Bar lbl="CITE" v={88} />
              <Bar lbl="CLARITY" v={95} />
              <Bar lbl="COMPL" v={90} />
            </div>
          </div>
          {/* Screenshot strip — preview of doc & related charts */}
          <div className="aj-as-sect" style={{padding:'8px 20px 8px'}}>
            <div><div className="label">PREVIEW · 미리보기</div><h2>스크린샷</h2></div>
            <span className="more">전체 ›</span>
          </div>
          <div className="aj-as-shots">
            <div className="shot">
              <div className="head"><span>ECN-2024-0182</span><span style={{color:'#FCB132'}}>v3</span></div>
              <div className="ttl">사출 #03 setpoint 62→65°C</div>
              <div className="body">SPC Nelson Rule 2 위반 · 원료 lot K-2024-1031 점도 +6%</div>
              <div className="aj-mono" style={{fontSize:9, opacity:0.55, marginTop:'auto'}}>§1. 변경 사유</div>
            </div>
            <div className="shot" style={{background:'rgba(252,177,50,0.18)', borderColor:'rgba(252,177,50,0.25)'}}>
              <div className="head" style={{color:'#FCB132'}}><span>SPC · #03</span><span>R2</span></div>
              <div className="ttl">Cpk 0.92 → 1.42</div>
              <div style={{flex:1, display:'flex', alignItems:'flex-end', gap:2}}>
                {[40,52,46,58,32,28,30,34,38,72,84,76,80,88].map((h,i)=>(
                  <div key={i} style={{flex:1, height:`${h}%`, background:i<9?'#FF7565':'#FCB132', borderRadius:2, opacity:0.85}}/>
                ))}
              </div>
            </div>
            <div className="shot">
              <div className="head"><span>CITES · 4</span><span>VERIFIED</span></div>
              <div className="ttl">근거 자료</div>
              <div className="body">SOP-MOLD-005 § 4.2<br/>SPC chart #03<br/>Lot COA K-2024-1031</div>
            </div>
          </div>
          {/* Editor preview */}
          <div className="aj-glass" style={{padding:14, margin:'0 16px 12px'}}>
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
          {/* Suggested CC — App Store "Ratings & Reviews" form */}
          <div className="aj-as-sect" style={{padding:'14px 20px 6px'}}>
            <div><div className="label">SUGGESTED CC · 4 PEOPLE</div><h2>리뷰어 추천</h2></div>
            <span className="more">전체 ›</span>
          </div>
          <div className="aj-as-review">
            <div className="head">
              <div className="av">이</div>
              <div>
                <div className="nm">이정훈 책임</div>
                <div className="aj-mono" style={{fontSize:10, opacity:0.55}}>R&D · 99% MATCH</div>
              </div>
              <div className="ts">PRIMARY</div>
            </div>
            <div className="body">사출 라인 변경 ECN의 1차 승인자. 동일 라인 직전 ECN(0179, 0166)의 발행자입니다.</div>
            <div style={{display:'flex', gap:6, marginTop:10, flexWrap:'wrap'}}>
              <CCChip n="박서연 매니저" t="QA · 87%" tone="amber" />
              <CCChip n="장동훈 팀장" t="구매 · 76%" tone="amber" />
              <CCChip n="최유진 사원" t="설계 · 62%" tone="gray" />
            </div>
          </div>
          {/* Export — Information row style */}
          <div className="aj-as-sect" style={{padding:'4px 20px 6px'}}>
            <div><div className="label">EXPORT · 내보내기</div><h2>지원 포맷</h2></div>
          </div>
          <div className="aj-glass" style={{padding:'10px 12px', margin:'0 16px 120px', display:'flex', gap:6, flexWrap:'wrap'}}>
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
