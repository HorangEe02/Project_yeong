// Draft.jsx — Module B: Document Search & Drafting (Liquid Glass)
function Draft() {
  const [tab, setTab] = React.useState('internal');
  const [tone, setTone] = React.useState('공식적');
  const [docType, setDocType] = React.useState('PPAP');
  const [req, setReq] = React.useState('현대차 SQ팀에 PPAP Level 3 제출 안내');
  const [streaming, setStreaming] = React.useState(false);
  const [output, setOutput] = React.useState('');

  const sample = `## PPAP Level 3 제출 안내\n\n수신: 현대자동차 SQ팀\n발신: 아진산업 품질보증팀\n\n안녕하십니까. 아진산업 품질보증팀입니다.\n\n귀사 신차 양산 일정에 따라 부품번호 [부품번호] 의 PPAP Level 3 제출을 안내드립니다.\n포함 문서: PSW, FMEA, Control Plan, MSA, Capability Study, Sample.\n제출 기한: __날짜__.\n\n감사합니다.`;

  const generate = () => {
    if (streaming) return;
    setStreaming(true); setOutput('');
    let i = 0;
    const tick = () => {
      i += 6; setOutput(sample.slice(0, i));
      if (i < sample.length) setTimeout(tick, 18);
      else setStreaming(false);
    };
    setTimeout(tick, 150);
  };

  const quality = [
    { k:'구조', en:'STRUCTURE', max:25, score:24, note:'제목/수신/발신/본문/서명 ✓' },
    { k:'분량', en:'LENGTH', max:20, score:18, note:'권장 800~1500자' },
    { k:'전문성', en:'TERMINOLOGY', max:25, score:22, note:'PSW·FMEA·MSA 매칭' },
    { k:'완성도', en:'COMPLETION', max:15, score:13, note:'placeholder 1건' },
    { k:'톤', en:'TONE', max:15, score:10, note:'공식체 일관' },
  ];
  const total = quality.reduce((a,b)=>a+b.score,0);
  const grade = total>=90?'A':total>=80?'B+':total>=70?'B':'C';

  const cc = {
    required: [{name:'현대차 SQ팀',tag:'OEM'},{name:'영업1팀',tag:'내부'}],
    recommended: [{name:'품질본부장',tag:'결재'}],
    optional: [{name:'생산기술팀',tag:'참조'}],
  };

  const exports = ['DOCX','ODT','PDF','XLSX','CSV','TXT','복사'];
  const versions = [
    { v:'v3', date:'2026-04-26 09:32', sim:'94%', diff:'+12 / −4' },
    { v:'v2', date:'2026-04-25 17:08', sim:'88%', diff:'+38 / −22' },
    { v:'v1', date:'2026-04-25 11:14', sim:'—', diff:'초안 생성' },
  ];

  return (
    <div className="page lg-page" data-screen-label="B · Document Draft">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">DOCUMENT SEARCH & DRAFTING · MODULE B</div>
        <h1 className="lg-display">문서 검색 / 작성</h1>
        <p className="lg-sub">Few-shot RAG 584건 · 13종 문서 유형 · 사내 SOP·용어집·이력에서 컨텍스트를 가져와 한 번에 초안을 생성합니다.</p>
      </section>

      <div className="lg-tabs">
        {[{k:'internal',en:'INTERNAL',ko:'내부용 문서'},{k:'external',en:'EXTERNAL',ko:'외부용 문서'},{k:'history',en:'HISTORY',ko:'문서 이력'}].map(t=>(
          <button key={t.k} className={'lg-tab'+(tab===t.k?' on':'')} onClick={()=>setTab(t.k)}>
            <span className="en">{t.en}</span><span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {tab !== 'history' && (
        <div className="lg-grid lg-grid-2-1">
          <section className="lg-card">
            <div className="lg-card-h">
              <div><div className="lg-eyebrow">REQUEST · 작성 요청</div><h2 className="lg-h2">무엇을 작성할까요?</h2></div>
              <span className="lg-pill">QWEN-3.5 · SSE</span>
            </div>

            <div className="lg-field" style={{marginBottom:14}}>
              <label>요청 내용</label>
              <textarea className="lg-textarea" value={req} onChange={e=>setReq(e.target.value)} rows="3" />
            </div>

            <div className="lg-filter-grid" style={{gridTemplateColumns:'1fr 2fr auto', gap:14, alignItems:'flex-end'}}>
              <div className="lg-field">
                <label>어조 · TONE</label>
                <select value={tone} onChange={e=>setTone(e.target.value)}>
                  <option>공식적</option><option>친근함</option><option>중립</option>
                </select>
              </div>
              <div className="lg-field">
                <label>문서 유형 · 13종</label>
                <select value={docType} onChange={e=>setDocType(e.target.value)}>
                  <option>8D Report</option><option>ECN</option><option>PPAP</option><option>FMEA</option>
                  <option>MSA</option><option>SPC Report</option><option>사내 이메일</option>
                  <option>OEM 영문 이메일</option><option>회의록</option><option>주간 보고</option>
                  <option>휴가 신청서</option><option>견적서</option><option>출장 보고서</option>
                </select>
              </div>
              <button className="lg-btn" onClick={generate} disabled={streaming}>{streaming?'생성 중…':'생성 ▶'}</button>
            </div>

            <div className="lg-output-box">
              <div className="lg-output-h">
                <span>OUTPUT · 생성 결과</span>
                <span className="lg-mini">{streaming?'스트리밍 중':'완료'}</span>
              </div>
              <pre className={'lg-output'+(streaming?' streaming-cursor':'')}>{output || '생성 결과가 여기에 스트리밍됩니다.'}</pre>
              {output && (
                <div className="lg-export-row">
                  {exports.map(x => <button key={x} className="lg-chip">↓ {x}</button>)}
                </div>
              )}
            </div>
          </section>

          <aside className="lg-stack">
            <section className="lg-card lg-card-tight">
              <div className="lg-eyebrow">QUALITY · 품질 평가</div>
              <div className="lg-quality-h">
                <div className="lg-score">{total}<span>/100</span></div>
                <div className="lg-grade">{grade}</div>
              </div>
              <div className="lg-quality-bars">
                {quality.map(q => (
                  <div key={q.k} className="lg-q-row">
                    <div className="lg-q-l"><span className="ko">{q.k}</span><span className="en">{q.en}</span></div>
                    <div className="lg-q-bar"><span style={{width:(q.score/q.max*100)+'%'}} /></div>
                    <span className="lg-q-v">{q.score}<i>/{q.max}</i></span>
                  </div>
                ))}
              </div>
              <div className="lg-q-tip">개선: __날짜__ 채우기 · 분량 +120자 권장</div>
            </section>

            <section className="lg-card lg-card-tight">
              <div className="lg-eyebrow">CC · 자동 추천</div>
              {[
                {tier:'required', label:'필수', color:'red'},
                {tier:'recommended', label:'권장', color:'amber'},
                {tier:'optional', label:'선택', color:'gray'},
              ].map(t => (
                <div key={t.tier} className={'lg-cc-row tier-'+t.color}>
                  <span className="lg-cc-l">{t.label}</span>
                  <div className="lg-cc-chips">
                    {cc[t.tier].map(p => <span key={p.name} className="lg-cc-chip">{p.name}<i>{p.tag}</i></span>)}
                  </div>
                </div>
              ))}
            </section>

            <section className="lg-card lg-card-tight">
              <div className="lg-eyebrow">FEW-SHOT · RAG 컨텍스트</div>
              <div className="lg-fs-row"><span>PPAP_2025_Q4_001.docx</span><span className="lg-conf">0.91</span></div>
              <div className="lg-fs-row"><span>PPAP_2025_Q3_007.docx</span><span className="lg-conf">0.87</span></div>
              <div className="lg-fs-row"><span>PPAP_2024_BUMPER.docx</span><span className="lg-conf">0.82</span></div>
              <div className="lg-fs-foot">ChromaDB · BGE-M3 1024d · 584건</div>
            </section>
          </aside>
        </div>
      )}

      {tab === 'history' && (
        <section className="lg-card">
          <div className="lg-card-h">
            <div><div className="lg-eyebrow">HISTORY · 문서 버전</div><h2 className="lg-h2">버전 이력 · v3 → v1</h2></div>
          </div>
          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead><tr><th>버전</th><th>일시</th><th>유사도</th><th>diff</th><th></th></tr></thead>
              <tbody>
                {versions.map(v => (
                  <tr key={v.v}>
                    <td><b>{v.v}</b></td>
                    <td className="mono dim">{v.date}</td>
                    <td className="mono">{v.sim}</td>
                    <td className="mono dim">{v.diff}</td>
                    <td><button className="lg-btn ghost sm">비교</button> <button className="lg-btn ghost sm">재편집</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="lg-diff">
            <div className="lg-eyebrow" style={{marginTop:18,marginBottom:10}}>DIFF · v2 → v3</div>
            <div className="lg-diff-line add">+ 제출 기한: __날짜__.</div>
            <div className="lg-diff-line del">− 제출 기한: 추후 통보드리겠습니다.</div>
            <div className="lg-diff-line mod">~ 포함 문서: PSW, FMEA, Control Plan, MSA, Capability Study, Sample.</div>
            <div className="lg-diff-line">  안녕하십니까. 아진산업 품질보증팀입니다.</div>
          </div>
        </section>
      )}
    </div>
  );
}
window.Draft = Draft;
