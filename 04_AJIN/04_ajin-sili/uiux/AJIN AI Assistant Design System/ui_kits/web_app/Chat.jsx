// Chat.jsx — Module C: AI Work Assistant (Liquid Glass)
function Chat({ streaming, setStreaming }) {
  const [mode, setMode] = React.useState('교육');
  const [dept, setDept] = React.useState('생산기술팀');
  const [input, setInput] = React.useState('');
  const [view, setView] = React.useState('sop');
  const [sopStep, setSopStep] = React.useState(0);
  const [msgs, setMsgs] = React.useState([
    { role:'user', text:'프레스 트라이 SOP 알려줘', t:'09:23' },
    { role:'ai', t:'09:23', meta:{src:'SOP_GUIDE', conf:'—', latency:'0ms'},
      text:'프레스 트라이 SOP를 단계별로 안내드립니다. 좌측 SOP 패널에서 7단계를 확인하세요. 각 단계 학습 종료 시 4지선다 퀴즈가 자동 생성됩니다.', sop:'press_try' },
  ]);

  const sopSteps = [
    { n:1, title:'금형 점검', items:['금형 표면 균열 확인','가이드 핀 마모 측정','냉각 라인 누수 점검'], warn:'마모 0.3mm 초과 시 즉시 교체' },
    { n:2, title:'재료 준비', items:['소재 두께 측정','코일 정렬 확인','윤활제 도포'], warn:'두께 편차 ±0.05mm 이내' },
    { n:3, title:'클램프 / 압력', items:['클램프 압력 설정','슬라이드 위치 조정','안전 인터록 점검'], warn:'안전거리 400mm 준수 (산안법 개정)' },
    { n:4, title:'시운전 1회', items:['저속 1샷 진행','치수 확인','소음/진동 청각 점검'], warn:'이상음 즉시 정지' },
    { n:5, title:'치수 측정', items:['주요 치수 5개소 측정','GD&T 검증','SPC 기록 입력'], warn:'Cpk 1.33 미만 시 조정' },
    { n:6, title:'연속 트라이 50샷', items:['50샷 연속 가공','전수 검사','Nelson Rule 모니터링'], warn:'Rule 2 (9점 평균이동) 발생 시 정지' },
    { n:7, title:'승인 / 기록', items:['최종 보고서 작성','품질팀 승인','양산 이관'], warn:'8D 발행 대비 이력 보관' },
  ];

  const collabScenarios = [
    { trig:'품질팀에서 8D 올려달라는데?', dept:'품질보증팀', steps:'1) 8D 양식 → 2) 5-Why → 3) 영구조치 → 4) OEM 회신', deadline:'14일' },
    { trig:'설계 변경 요청 왔어', dept:'설계팀', steps:'1) ECN 발행 → 2) 영향평가 → 3) PPAP 재제출 → 4) 양산 적용일', deadline:'7일' },
    { trig:'Cpk 1.0 떨어졌어', dept:'SPC', steps:'1) Nelson Rule 진단 → 2) 시정조치 → 3) 재측정 → 4) 보고서', deadline:'24시간' },
  ];

  const quickQuestions = [
    '프레스 트라이 SOP 알려줘',
    '품질팀에서 8D 올려달라는데?',
    '용접 검사 절차',
    '에러코드 E-101',
    '김민수 부장 어디?',
    'SPC 상태',
  ];

  const quizQ = {
    q:'Step 3 — 산안법 개정에 따른 프레스 안전거리 기준은?',
    options:[
      { k:'A', t:'200mm', ok:false },
      { k:'B', t:'300mm (기존)', ok:false },
      { k:'C', t:'400mm (개정)', ok:true },
      { k:'D', t:'500mm', ok:false },
    ],
    related:3,
    explain:'2026년 산안법 시행규칙 개정으로 프레스 안전거리는 300→400mm로 강화되었습니다. (D-30 시행)',
  };

  const send = () => {
    if (!input.trim() || streaming) return;
    const q = input;
    const isError = /(에러|코드|E-?\d)/i.test(q);
    const isPerson = /(부장|차장|어디|담당자)/i.test(q);
    const isSpc = /(spc|cpk|관리도|nelson)/i.test(q);
    setMsgs(m => [...m, { role:'user', text:q, t:'09:24' }]);
    setInput('');
    if (mode === '업무' && (isError || isPerson || isSpc)) {
      setMsgs(m => [...m, {
        role:'ai', t:'09:24',
        meta:{ src: isError?'ERROR_DB':isPerson?'PEOPLE_SEARCH':'SPC_DASHBOARD', conf:'99%', latency: isError?'12ms':isPerson?'8ms':'15ms' },
        text: isError ? 'E-101 베어링 마모 · HIGH · 평균 복구 35분 · 이력 24건. Markov 후속: E-205 윤활부족 (0.62) → E-310 모터과열 (0.31).' :
              isPerson ? '김민수 차장 · 품질보증팀 · 본사 · 내선 1234 · minsu.kim@ajin.com' :
              '5공정 Cpk: CCH 1.51 ● / OBC 1.18 ⚠ / 범퍼빔 0.89 ⛔ Rule 1·2·5 / 도어 1.62 ● / 볼시트 1.55 ●',
        action:true,
      }]);
      return;
    }
    setStreaming(true);
    setMsgs(m => [...m, { role:'ai', text:'', streaming:true, t:'09:24', meta:{src:'QWEN-3.5', conf:'—', latency:'...'} }]);
    const reply = mode === '교육'
      ? '교육 모드(컨텍스트 3,000자)로 답변드립니다. "'+dept+'" 부서 컨텍스트와 사내 SOP·용어집 297항목을 결합해 단계별로 설명합니다. 학습 종료 시 4지선다 퀴즈가 자동 생성됩니다.'
      : '업무 모드(컨텍스트 2,000자)로 즉답드립니다. 핵심 절차 + 양식 위치 + 마감 기한을 간결하게 안내합니다.';
    let i = 0;
    const tick = () => {
      i += 4;
      setMsgs(m => { const c=[...m]; c[c.length-1] = {...c[c.length-1], text: reply.slice(0,i)}; return c; });
      if (i < reply.length) setTimeout(tick, 25);
      else {
        setStreaming(false);
        setMsgs(m => { const c=[...m]; c[c.length-1] = {...c[c.length-1], streaming:false, meta:{src:'QWEN-3.5', conf:'88%', latency:'124ms · 41 t/s'}}; return c; });
      }
    };
    setTimeout(tick, 200);
  };

  return (
    <div className="page lg-page lg-chat-page" data-screen-label="C · AI Chat">
      <section className="lg-hero lg-hero-chat">
        <div className="lg-hero-eyebrow">AI WORK ASSISTANT · MODULE C</div>
        <div className="lg-chat-hero-row">
          <div>
            <h1 className="lg-display">AI 업무 도우미</h1>
            <p className="lg-sub">QWEN-3.5 · 의도 분류 5ms · SOP 8종 · 협업 5종 시나리오. 교육/업무 듀얼 모드로 부서 맞춤 답변을 제공합니다.</p>
          </div>
          <div className="lg-chat-hero-ctrl">
            <div className="lg-field">
              <label>부서 컨텍스트</label>
              <select value={dept} onChange={e=>setDept(e.target.value)}>
                <option>품질보증팀</option><option>생산기술팀</option><option>해외영업팀</option>
                <option>환경안전팀</option><option>법무팀</option><option>구매팀</option><option>인사팀</option>
              </select>
            </div>
            <div className="lg-mode-seg">
              {['교육','업무'].map(m => (
                <button key={m} className={mode===m?'on':''} onClick={()=>setMode(m)}>
                  <b>{m}</b>
                  <i>{m==='교육'?'3,000자':'2,000자'}</i>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="lg-card lg-quick-card">
        <div className="lg-eyebrow">QUICK · {dept} 추천 질문</div>
        <div className="lg-quick-chips">
          {quickQuestions.map(q => (
            <button key={q} className="lg-quick-chip" onClick={()=>setInput(q)}>{q}</button>
          ))}
        </div>
      </section>

      <div className="lg-grid lg-grid-1-2">
        <section className="lg-card lg-card-tight lg-side-card">
          <div className="lg-side-tabs">
            {[{k:'sop',l:'SOP 8'},{k:'collab',l:'협업 5'},{k:'quiz',l:'퀴즈'}].map(s => (
              <button key={s.k} className={view===s.k?'on':''} onClick={()=>setView(s.k)}>{s.l}</button>
            ))}
          </div>

          {view==='sop' && (
            <>
              <div className="lg-sop-h">
                <div className="lg-eyebrow">SOP · 프레스 트라이</div>
                <div className="lg-sop-progress-row">
                  <span>Step {sopStep+1}/7</span>
                  <div className="lg-sop-progress"><span style={{width:((sopStep+1)/7*100)+'%'}} /></div>
                </div>
              </div>
              <div className="lg-sop-step">
                <div className="lg-sop-title">Step {sopSteps[sopStep].n} — {sopSteps[sopStep].title}</div>
                <ul className="lg-sop-items">
                  {sopSteps[sopStep].items.map(it => <li key={it}>{it}</li>)}
                </ul>
                <div className="lg-sop-warn">⚠ {sopSteps[sopStep].warn}</div>
              </div>
              <div className="lg-sop-actions">
                <button className="lg-btn ghost sm" disabled={sopStep===0} onClick={()=>setSopStep(s=>Math.max(0,s-1))}>◀ 이전</button>
                <button className="lg-btn sm" onClick={()=>setSopStep(s=>Math.min(6,s+1))} disabled={sopStep===6}>다음 ▶</button>
                <button className="lg-btn ghost sm" onClick={()=>setView('quiz')}>퀴즈</button>
              </div>
              <div className="lg-sop-list">
                <div className="lg-eyebrow" style={{marginBottom:8}}>SOP 8종</div>
                {['금형 교체','용접 검사','CNC 가공','8D Report 작성','ECN 발행','SPC 분석','PPAP 제출','안전 점검'].map((s,i) => (
                  <div key={s} className={'lg-sop-item'+(i===0?' on':'')}>
                    <span className="num mono">{String(i+1).padStart(2,'0')}</span>
                    <span>{s}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {view==='collab' && (
            <>
              <div className="lg-eyebrow">협업 시나리오 5종</div>
              <h3 className="lg-h2" style={{fontSize:18, marginTop:6, marginBottom:14}}>트리거 → 부서 → 절차</h3>
              {collabScenarios.map(s => (
                <div key={s.trig} className="lg-collab-card">
                  <div className="lg-collab-trig">"{s.trig}"</div>
                  <div className="lg-collab-dept">→ {s.dept}</div>
                  <div className="lg-collab-steps">{s.steps}</div>
                  <div className="lg-collab-dl mono">⏱ {s.deadline}</div>
                </div>
              ))}
            </>
          )}

          {view==='quiz' && (
            <>
              <div className="lg-eyebrow">QUIZ · 자동 생성</div>
              <h3 className="lg-h2" style={{fontSize:17, marginTop:6, marginBottom:14, lineHeight:1.4}}>{quizQ.q}</h3>
              <div className="lg-quiz-opts">
                {quizQ.options.map(o => (
                  <button key={o.k} className={'lg-quiz-opt'+(o.ok?' ok':'')}>
                    <span className="qk mono">{o.k}</span>
                    <span className="qt">{o.t}</span>
                    {o.ok && <span className="qbadge">정답 ✓</span>}
                  </button>
                ))}
              </div>
              <div className="lg-quiz-explain">{quizQ.explain}</div>
              <div className="lg-sop-actions">
                <button className="lg-btn ghost sm" onClick={()=>{setSopStep(quizQ.related-1); setView('sop');}}>↩ Step {quizQ.related} 다시</button>
                <button className="lg-btn sm">다음 문제 ▶</button>
              </div>
            </>
          )}
        </section>

        <section className="lg-card lg-chat-stream-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-eyebrow">CHAT · {dept.toUpperCase()}-{mode.toUpperCase()}</div>
              <h2 className="lg-h2">세션 #A47-2026</h2>
            </div>
            <span className="lg-pill">● LIVE</span>
          </div>

          <div className="lg-chat-stream">
            {msgs.map((m, i) => (
              <div key={i} className={'lg-bubble '+m.role+(m.action?' action':'')}>
                {m.meta && (
                  <div className="lg-bubble-meta">
                    <span><b>{m.role==='user'?'YOU · 김아진':'AI'}</b></span>
                    <span className="src mono">{m.meta.src}</span>
                    <span className="dim">신뢰도 {m.meta.conf}</span>
                    {m.meta.latency && <span className="dim mono">· {m.meta.latency}</span>}
                    <span className="ts mono dim">{m.t}</span>
                  </div>
                )}
                <div className={'lg-bubble-body'+(m.streaming?' streaming-cursor':'')}>{m.text}</div>
                {m.role==='ai' && !m.streaming && !m.action && (
                  <div className="lg-bubble-actions">
                    <button className="lg-btn ghost sm">↓ DOCX</button>
                    <button className="lg-btn ghost sm">↓ XLSX</button>
                    <button className="lg-btn ghost sm">↓ CSV</button>
                    <button className="lg-btn ghost sm">↓ TXT</button>
                    <button className="lg-btn ghost sm">👍</button>
                    <button className="lg-btn ghost sm">👎</button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="lg-chat-meta-bar">
            <span>토큰 <b>{mode==='교육'?'420':'248'}</b>/{mode==='교육'?'3,000':'2,000'}</span>
            <span>·</span>
            <span>컨텍스트 <b>6턴</b></span>
            <span>·</span>
            <span>모델 <b>QWEN-3.5</b></span>
            <span>·</span>
            <span>의도 분류 <b>5ms</b></span>
          </div>

          <div className="lg-composer">
            <button className="lg-att">📎</button>
            <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()}
              placeholder={streaming?'AI가 응답을 생성하고 있습니다...':'질문을 입력하세요... (PDF/DOCX/이미지 첨부 가능, 최대 20MB)'} disabled={streaming} />
            <button className="lg-btn lg-send" onClick={send} disabled={streaming}>전송 ↑</button>
          </div>
        </section>
      </div>
    </div>
  );
}
window.Chat = Chat;
