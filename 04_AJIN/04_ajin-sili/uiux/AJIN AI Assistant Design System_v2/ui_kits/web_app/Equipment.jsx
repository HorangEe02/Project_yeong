// Equipment.jsx — Module F: Equipment & Process AI (Liquid Glass)
function Equipment() {
  const [tab, setTab] = React.useState('overview');
  const [sub, setSub] = React.useState('overview');
  const [errQuery, setErrQuery] = React.useState('프레스에서 이상한 소리');
  const [equipFilter, setEquipFilter] = React.useState('프레스');
  const [symptom, setSymptom] = React.useState('진동');

  const metrics = [
    { v:'92%', en:'UPTIME', ko:'가동률' },
    { v:'1.42', en:'AVG Cpk', ko:'평균 공정능력' },
    { v:'3', en:'ALERTS', ko:'활성 알람' },
    { v:'720h', en:'MTBF', ko:'평균 무고장' },
    { v:'2', en:'MAINT DUE', ko:'정비 임박' },
  ];

  const equipment = [
    { type:'프레스', en:'PRESS', state:'ok', cpk:1.51, alarm:0 },
    { type:'용접', en:'WELD', state:'warn', cpk:1.18, alarm:2 },
    { type:'CNC', en:'CNC', state:'ok', cpk:1.45, alarm:0 },
    { type:'사출', en:'INJECT', state:'ok', cpk:1.38, alarm:0 },
    { type:'도장', en:'PAINT', state:'crit', cpk:0.89, alarm:1 },
    { type:'검사', en:'INSPECT', state:'ok', cpk:1.62, alarm:0 },
    { type:'컨베이어', en:'CONVEY', state:'ok', cpk:1.55, alarm:0 },
  ];

  const processes5 = [
    { name:'CCH', state:'ok', cpk:1.51, viol:0, rules:[] },
    { name:'OBC', state:'warn', cpk:1.18, viol:2, rules:['Rule 2'] },
    { name:'범퍼빔', state:'crit', cpk:0.89, viol:5, rules:['Rule 1','Rule 2','Rule 5'] },
    { name:'도어', state:'ok', cpk:1.62, viol:0, rules:[] },
    { name:'볼시트', state:'ok', cpk:1.55, viol:1, rules:['Rule 6'] },
  ];

  const mlEngines = [
    { name:'TF-IDF Error Search', state:'on', p99:'38ms', model:'sklearn 1.4' },
    { name:'Isolation Forest SPC', state:'on', p99:'87ms', model:'sklearn 1.4' },
    { name:'XGBoost Mold Lifecycle', state:'on', p99:'42ms', model:'XGBoost 2.0' },
    { name:'Markov Failure Chain', state:'on', p99:'24ms', model:'numpy' },
    { name:'Doc Quality Scorer', state:'on', p99:'18ms', model:'rule-based' },
    { name:'Reg Risk Classifier', state:'on', p99:'46ms', model:'sklearn 1.4' },
    { name:'Intent Classifier', state:'on', p99:'5ms', model:'sklearn 1.4' },
  ];

  const errResults = [
    { code:'E-101', name:'베어링 마모', sim:0.87, sev:'HIGH', count:24, mttr:'35분', cause:'윤활 부족 누적' },
    { code:'E-104', name:'가이드 핀 마모', sim:0.76, sev:'MED', count:12, mttr:'25분', cause:'냉각 라인 불량' },
    { code:'E-118', name:'클러치 슬립', sim:0.71, sev:'HIGH', count:8, mttr:'90분', cause:'디스크 마모' },
    { code:'E-122', name:'구동축 진동', sim:0.64, sev:'MED', count:18, mttr:'40분', cause:'얼라인먼트' },
    { code:'E-130', name:'전기 모터 이음', sim:0.58, sev:'LOW', count:31, mttr:'15분', cause:'고정 볼트 풀림' },
  ];

  const markovChain = [
    { code:'E-205', name:'윤활 부족', prob:0.62 },
    { code:'E-310', name:'모터 과열', prob:0.31 },
    { code:'E-407', name:'성형 불량', prob:0.18 },
  ];

  const molds = [
    { id:'MD-001', part:'CCH-FR', shots:412000, max:500000, risk:'LOW' },
    { id:'MD-007', part:'OBC-RR', shots:485000, max:500000, risk:'HIGH' },
    { id:'MD-012', part:'BUMPER', shots:280000, max:600000, risk:'LOW' },
    { id:'MD-015', part:'DOOR-IN', shots:442000, max:500000, risk:'MED' },
    { id:'MD-019', part:'볼시트', shots:188000, max:400000, risk:'LOW' },
    { id:'MD-022', part:'EV-CASE', shots:51000, max:800000, risk:'LOW' },
    { id:'MD-024', part:'CCH-RR', shots:478000, max:500000, risk:'HIGH' },
    { id:'MD-025', part:'DOOR-OUT', shots:320000, max:500000, risk:'MED' },
  ];

  const maintCost = [
    { eq:'프레스 #3', cost:1240, jobs:18 },
    { eq:'용접 #2', cost:920, jobs:14 },
    { eq:'도장 #1', cost:880, jobs:22 },
    { eq:'CNC #5', cost:640, jobs:11 },
    { eq:'컨베이어 #2', cost:410, jobs:9 },
  ];

  const spcData = [];
  for (let i=0;i<40;i++) {
    let v = 50 + Math.sin(i*0.4)*1.5 + (i*0.7%1.8 - 0.9);
    if (i >= 18 && i <= 26) v += 4;
    if (i === 32) v += 8;
    spcData.push(v);
  }
  const cl = 50, ucl = 56, lcl = 44;
  const yScale = (v) => 200 - ((v - 40) / 20) * 180;

  const symptomCats = {
    '프레스': ['이음','진동','압력 저하','성형 불량','누유','전기'],
    '용접': ['스패터','강도 부족','크랙','전류 불안','이음'],
    'CNC': ['가공면 불량','채터링','공구 마모','진동'],
    '사출': ['플래시','수축','색상 불균','쇼트샷'],
    '도장': ['오렌지필','핀홀','색차','광택 불량'],
    '검사': ['오감지','센서 불안','캘리브레이션'],
    '컨베이어': ['이음','속도 불안','벨트 슬립'],
  };

  return (
    <div className="page lg-page" data-screen-label="F · Equipment AI">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">EQUIPMENT & PROCESS AI · MODULE F</div>
        <h1 className="lg-display">설비 / 공정 AI</h1>
        <p className="lg-sub">7종 ML 엔진 · 14개 부서. SPC Nelson 8 Rules · TF-IDF 에러 검색 · XGBoost 잔여수명 · Markov 연쇄 고장 예측을 한 화면에서.</p>
      </section>

      <div className="lg-tabs">
        {[
          { k:'overview', en:'OVERVIEW', ko:'대시보드' },
          { k:'manual', en:'MANUAL & ERROR', ko:'매뉴얼 / 에러' },
          { k:'inspection', en:'INSPECTION', ko:'점검 이력' },
        ].map(t => (
          <button key={t.k} className={'lg-tab'+(tab===t.k?' on':'')} onClick={()=>setTab(t.k)}>
            <span className="en">{t.en}</span><span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="lg-subtabs">
            {[
              { k:'overview', label:'설비 개요' },
              { k:'urgent', label:'긴급 조치' },
              { k:'types', label:'장비 유형' },
              { k:'predict', label:'예측 정비' },
              { k:'spc', label:'SPC · Nelson 8' },
              { k:'ml', label:'ML 엔진' },
            ].map(s => (
              <button key={s.k} className={'lg-subtab'+(sub===s.k?' on':'')} onClick={()=>setSub(s.k)}>{s.label}</button>
            ))}
          </div>

          {sub === 'overview' && (
            <>
              <section className="lg-card">
                <div className="lg-card-h">
                  <div><div className="lg-eyebrow">METRICS · 핵심 지표</div><h2 className="lg-h2">실시간 설비 상태</h2></div>
                </div>
                <div className="lg-metric-row" style={{gridTemplateColumns:'repeat(5, 1fr)'}}>
                  {metrics.map(m => (
                    <div key={m.en} className="lg-metric">
                      <span className="k">{m.ko}</span>
                      <span className="v">{m.v}</span>
                      <span className="en mono">{m.en}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="lg-card">
                <div className="lg-card-h">
                  <div><div className="lg-eyebrow">EQUIPMENT · 7종 상태</div><h2 className="lg-h2">장비별 Cpk · 알람</h2></div>
                </div>
                <div className="lg-equip-grid">
                  {equipment.map(e => (
                    <div key={e.type} className={'lg-equip state-'+e.state}>
                      <div className="lg-equip-h">
                        <span className="ko">{e.type}</span>
                        <span className="lg-state-dot" />
                      </div>
                      <div className="lg-equip-en mono">{e.en}</div>
                      <div className="lg-equip-stat">
                        <div><i>Cpk</i><b>{e.cpk}</b></div>
                        <div><i>알람</i><b>{e.alarm}</b></div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}

          {sub === 'urgent' && (
            <section className="lg-card">
              <div className="lg-card-h">
                <div><div className="lg-eyebrow">URGENT · 긴급 조치 큐</div><h2 className="lg-h2">즉시 대응 필요</h2></div>
                <span className="lg-pill">3건</span>
              </div>
              <div className="lg-urg-list">
                <div className="lg-urg-row crit">
                  <span className="cat">CRITICAL</span>
                  <div className="body"><b>도장 #1</b><span> · Cpk 0.89 · Nelson Rule 1·2·5 위반</span></div>
                  <span className="time mono">14분 전</span>
                  <button className="lg-btn sm">조치</button>
                </div>
                <div className="lg-urg-row warn">
                  <span className="cat">HIGH</span>
                  <div className="body"><b>용접 #2</b><span> · Cpk 1.18 · 평균 이동 감지 (Rule 2)</span></div>
                  <span className="time mono">32분 전</span>
                  <button className="lg-btn sm">조치</button>
                </div>
                <div className="lg-urg-row warn">
                  <span className="cat">HIGH</span>
                  <div className="body"><b>MD-007 (OBC-RR)</b><span> · 잔여 사이클 15,000 (XGBoost 예측 D-3)</span></div>
                  <span className="time mono">1시간 전</span>
                  <button className="lg-btn sm">정비 예약</button>
                </div>
              </div>
            </section>
          )}

          {sub === 'types' && (
            <section className="lg-card">
              <div className="lg-card-h">
                <div><div className="lg-eyebrow">TYPES · 장비 유형별 ML 신호</div><h2 className="lg-h2">상세 진단</h2></div>
              </div>
              <div className="lg-table-wrap">
                <table className="lg-table">
                  <thead><tr><th>장비</th><th>상태</th><th>Cpk</th><th>알람</th><th>ML 신호</th></tr></thead>
                  <tbody>
                    {equipment.map(e => (
                      <tr key={e.type}>
                        <td><b>{e.type}</b> <span className="dim mono">· {e.en}</span></td>
                        <td><span className={'lg-state-pill '+e.state}>{e.state.toUpperCase()}</span></td>
                        <td className="mono">{e.cpk}</td>
                        <td>{e.alarm}</td>
                        <td className="dim">{e.alarm>0?'Isolation Forest 이상치 + Markov 후속 위험':'정상 범위'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {sub === 'predict' && (
            <>
              <section className="lg-card">
                <div className="lg-card-h">
                  <div><div className="lg-eyebrow">XGBoost MOLD LIFECYCLE</div><h2 className="lg-h2">금형 25기 잔여 수명</h2></div>
                  <span className="lg-pill">표시 {molds.length}/25</span>
                </div>
                <div className="lg-mold-grid">
                  {molds.map(m => {
                    const pct = m.shots/m.max;
                    const rem = m.max-m.shots;
                    return (
                      <div key={m.id} className={'lg-mold risk-'+m.risk.toLowerCase()}>
                        <div className="lg-mold-h">
                          <span className="id mono">{m.id}</span>
                          <span className={'lg-risk-pill r-'+m.risk.toLowerCase()}>{m.risk}</span>
                        </div>
                        <div className="lg-mold-part">{m.part}</div>
                        <div className="lg-mold-bar"><span style={{width:(pct*100)+'%'}} /></div>
                        <div className="lg-mold-stat"><span>{(pct*100).toFixed(0)}% 사용</span><span className="rem">잔여 {(rem/1000).toFixed(0)}k</span></div>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="lg-card">
                <div className="lg-card-h">
                  <div><div className="lg-eyebrow">MTBF · 수리 비용 TOP 5</div><h2 className="lg-h2">예측 정비 우선순위</h2></div>
                </div>
                <div className="lg-table-wrap">
                  <table className="lg-table">
                    <thead><tr><th>설비</th><th>누적 비용 (만원)</th><th>건수</th><th>다음 정비</th></tr></thead>
                    <tbody>
                      {maintCost.map((m,i) => (
                        <tr key={i}>
                          <td><b>{m.eq}</b></td>
                          <td className="mono">{m.cost.toLocaleString()}</td>
                          <td>{m.jobs}</td>
                          <td className="mono">{['D-3','D-12','D-24','D-45','D-60'][i]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}

          {sub === 'spc' && (
            <>
              <section className="lg-card">
                <div className="lg-card-h">
                  <div><div className="lg-eyebrow">SPC · 5공정 건강 카드</div><h2 className="lg-h2">Nelson 8 Rules 위반</h2></div>
                </div>
                <div className="lg-spc-grid">
                  {processes5.map(p => (
                    <div key={p.name} className={'lg-spc state-'+p.state}>
                      <div className="lg-spc-h">
                        <span className="lg-state-dot" />
                        <span className="ko">{p.name}</span>
                      </div>
                      <div className="lg-spc-cpk">Cpk <b>{p.cpk}</b></div>
                      <div className="lg-spc-viol">위반 {p.viol}건</div>
                      <div className="lg-spc-rules">{p.rules.length ? p.rules.join(' · ') : '—'}</div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="lg-card">
                <div className="lg-card-h">
                  <div><div className="lg-eyebrow">CONTROL CHART · X̄ (범퍼빔)</div><h2 className="lg-h2">관리도</h2></div>
                  <span className="lg-pill warn">Rule 1·2 위반</span>
                </div>
                <div className="lg-spc-chart">
                  <svg viewBox="0 0 600 220" preserveAspectRatio="none">
                    <line x1="0" y1={yScale(ucl)} x2="600" y2={yScale(ucl)} stroke="var(--hud-red)" strokeDasharray="4,4" opacity="0.7"/>
                    <line x1="0" y1={yScale(cl)} x2="600" y2={yScale(cl)} stroke="var(--hud-text-dim)" strokeDasharray="2,2" opacity="0.6"/>
                    <line x1="0" y1={yScale(lcl)} x2="600" y2={yScale(lcl)} stroke="var(--hud-red)" strokeDasharray="4,4" opacity="0.7"/>
                    <rect x={18*15} y="10" width={9*15} height="200" fill="rgba(232,163,23,0.12)" />
                    <rect x={32*15-6} y="10" width="12" height="200" fill="rgba(192,57,43,0.18)" />
                    <polyline fill="none" stroke="var(--hud-primary)" strokeWidth="1.5"
                      points={spcData.map((v,i)=>`${i*15},${yScale(v)}`).join(' ')} />
                    {spcData.map((v,i) => {
                      const inViol = (i>=18&&i<=26) || i===32;
                      return <circle key={i} cx={i*15} cy={yScale(v)} r={i===32?4:3} fill={inViol?'var(--hud-red)':'var(--hud-primary)'} />;
                    })}
                    <text x="595" y={yScale(ucl)-4} textAnchor="end" fontSize="10" fill="var(--hud-red)">UCL {ucl}</text>
                    <text x="595" y={yScale(cl)-4} textAnchor="end" fontSize="10" fill="var(--hud-text-dim)">CL {cl}</text>
                    <text x="595" y={yScale(lcl)-4} textAnchor="end" fontSize="10" fill="var(--hud-red)">LCL {lcl}</text>
                    <text x={22*15} y="30" fontSize="10" fill="#E8A317">RULE 2 — 9점 평균 이동</text>
                    <text x={32*15-50} y={yScale(spcData[32])-12} fontSize="10" fill="var(--hud-red)">RULE 1 — ±3σ 초과</text>
                  </svg>
                </div>
                <div className="lg-spc-foot">
                  <span>Isolation Forest 예측: Cpk <b>1.38 → <i className="warn">1.24</i></b> (다음 100샘플)</span>
                  <span>평균 드리프트 +0.6mm</span>
                </div>
              </section>
            </>
          )}

          {sub === 'ml' && (
            <section className="lg-card">
              <div className="lg-card-h">
                <div><div className="lg-eyebrow">ML ENGINES · 7종 상태</div><h2 className="lg-h2">모델 인벤토리</h2></div>
                <span className="lg-pill">7/7 ACTIVE</span>
              </div>
              <div className="lg-ml-grid">
                {mlEngines.map((m,i) => (
                  <div key={i} className="lg-ml">
                    <div className="lg-ml-h">
                      <span className="num mono">{String(i+1).padStart(2,'0')}</span>
                      <span className="lg-state-dot ok" />
                    </div>
                    <div className="lg-ml-name">{m.name}</div>
                    <div className="lg-ml-model dim">{m.model}</div>
                    <div className="lg-ml-foot">
                      <span className="mono">p99 {m.p99}</span>
                      <span className="lg-ok mono">● ON</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {tab === 'manual' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">ERROR SEARCH · TF-IDF + 동의어 79</div><h2 className="lg-h2">에러코드 자연어 검색</h2></div>
              <span className="lg-pill">이력 685건</span>
            </div>
            <div className="lg-filter-grid" style={{gridTemplateColumns:'1fr 1fr 2fr auto', alignItems:'flex-end'}}>
              <div className="lg-field">
                <label>장비</label>
                <select value={equipFilter} onChange={e=>{setEquipFilter(e.target.value); setSymptom(symptomCats[e.target.value][0]);}}>
                  {Object.keys(symptomCats).map(k => <option key={k}>{k}</option>)}
                </select>
              </div>
              <div className="lg-field">
                <label>증상</label>
                <select value={symptom} onChange={e=>setSymptom(e.target.value)}>
                  {symptomCats[equipFilter].map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div className="lg-field">
                <label>자연어 입력</label>
                <input value={errQuery} onChange={e=>setErrQuery(e.target.value)} placeholder="예: 프레스에서 이상한 소리..." />
              </div>
              <button className="lg-btn">검색 ▶</button>
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">RESULTS · 코사인 유사도 TOP 5</div><h2 className="lg-h2">매칭 에러 코드</h2></div>
            </div>
            <div className="lg-err-grid">
              {errResults.map((e,i) => (
                <div key={e.code} className={'lg-err sev-'+e.sev.toLowerCase()+(i===0?' top':'')}>
                  <div className="lg-err-h">
                    <span className="code mono">{e.code}</span>
                    <span className={'sev '+e.sev.toLowerCase()}>{e.sev}</span>
                    <span className="sim mono">코사인 {e.sim}</span>
                  </div>
                  <div className="lg-err-name">{e.name}</div>
                  <div className="lg-err-meta">
                    <span><i>이력 12개월</i><b>{e.count}건</b></span>
                    <span><i>평균 복구</i><b>{e.mttr}</b></span>
                    <span><i>주요 원인</i><b>{e.cause}</b></span>
                  </div>
                  <div className="lg-err-actions">
                    <button className="lg-btn ghost sm">조치 가이드</button>
                    <button className="lg-btn ghost sm">매뉴얼</button>
                    <button className="lg-btn ghost sm">👍</button>
                    <button className="lg-btn ghost sm">👎</button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">MARKOV CHAIN · DFS depth=3</div><h2 className="lg-h2">연쇄 고장 예측</h2></div>
            </div>
            <div className="lg-markov">
              <span className="lg-m-node start">E-101 베어링 마모</span>
              <span className="lg-m-arrow">→</span>
              <div className="lg-m-branches">
                {markovChain.map(m => (
                  <div key={m.code} className="lg-m-branch">
                    <span className="lg-m-prob">{m.prob.toFixed(2)}</span>
                    <span className="lg-m-node">{m.code} {m.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="lg-markov-foot">권장 사전 조치: 윤활 점검 → 베어링 교체 → 모터 온도 모니터링</div>
          </section>
        </>
      )}

      {tab === 'inspection' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div><div className="lg-eyebrow">INSPECTION · 점검 체크리스트</div><h2 className="lg-h2">9 템플릿 (3장비 × 3주기)</h2></div>
          </div>
          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead><tr><th>장비</th><th>주기</th><th>최근 점검</th><th>완료율</th><th>미달 항목</th><th></th></tr></thead>
              <tbody>
                <tr><td>프레스</td><td>일간</td><td className="mono dim">2026-04-26</td><td><span className="lg-ok">100%</span></td><td className="dim">—</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>프레스</td><td>주간</td><td className="mono dim">2026-04-22</td><td><span className="lg-ok">95%</span></td><td className="dim">가이드 핀 마모 측정 1건 보류</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>프레스</td><td>월간</td><td className="mono dim">2026-04-01</td><td><span className="lg-warn">88%</span></td><td className="dim">유압 누수 점검 미완</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>용접</td><td>일간</td><td className="mono dim">2026-04-26</td><td><span className="lg-ok">100%</span></td><td className="dim">—</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>용접</td><td>주간</td><td className="mono dim">2026-04-23</td><td><span className="lg-warn">82%</span></td><td className="dim">전극 마모 확인 누락</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>용접</td><td>월간</td><td className="mono dim">2026-04-05</td><td><span className="lg-ok">96%</span></td><td className="dim">—</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>CNC</td><td>일간</td><td className="mono dim">2026-04-26</td><td><span className="lg-ok">100%</span></td><td className="dim">—</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>CNC</td><td>주간</td><td className="mono dim">2026-04-22</td><td><span className="lg-ok">98%</span></td><td className="dim">—</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
                <tr><td>CNC</td><td>월간</td><td className="mono dim">2026-04-08</td><td><span className="lg-ok">94%</span></td><td className="dim">—</td><td><button className="lg-btn ghost sm">보기</button></td></tr>
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
window.Equipment = Equipment;
