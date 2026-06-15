// MobNeuralScreens.jsx — Neural Expressive iPhone screens.
// Each renders a full screen body (no nav prop — own nav). Designed to live
// inside the existing IOSDevice frame at 402×874.

/* ─────────────────── 01 · LOGIN · Neural ─────────────────── */
function MobNeuralLogin({ theme = 'dark' }) {
  const isLight = theme === 'light';
  return (
    <div className={'ne-canvas' + (isLight ? ' aj-neural light' : ' aj-neural')}
         style={{ height: '100%', display: 'flex', flexDirection: 'column',
                  paddingTop: 64, padding: '64px 22px 28px' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <img
          src={`../../assets/ajin_logo_${isLight ? 'light' : 'dark'}.svg`}
          alt="AJIN INDUSTRIAL CO., LTD."
          style={{ height: 72, width: 'auto', display: 'block',
                   filter: isLight ? 'none' : 'drop-shadow(0 14px 36px rgba(252,177,50,0.32))' }}
        />
        <div className="ne-eyebrow" style={{ marginTop: 2 }}>AI ASSISTANT · v3.5</div>
        <h1 className="ne-greet" style={{ fontSize: 34, textAlign: 'center', maxWidth: 320, marginTop: 4 }}>
          안녕하세요,<br/>
          <span className="ombre">아진</span> 가족 여러분
        </h1>
        <p className="ne-body" style={{ textAlign: 'center', fontSize: 14, color: 'var(--ne-text-2)', marginTop: 4, maxWidth: 280 }}>
          제조 현장과 사무 업무를<br/>하나의 에이전트로.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="ne-pill" style={{ minHeight: 56 }}>
          <svg width="20" height="20" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.6" style={{ color: 'var(--ne-text-2)' }}>
            <rect x="3" y="5" width="16" height="12" rx="2.5"/>
            <circle cx="8" cy="11" r="2"/>
            <path d="M13 9h4M13 12h4" strokeLinecap="round"/>
          </svg>
          <input placeholder="사번" defaultValue="EMP-20260524" style={{ fontSize: 15 }} />
        </div>
        <div className="ne-pill" style={{ minHeight: 56 }}>
          <svg width="20" height="20" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.6" style={{ color: 'var(--ne-text-2)' }}>
            <rect x="4" y="9" width="14" height="10" rx="2.5"/>
            <path d="M7 9V6.5a4 4 0 018 0V9" strokeLinecap="round"/>
          </svg>
          <input type="password" placeholder="비밀번호" defaultValue="••••••••" style={{ fontSize: 15 }} />
        </div>
        <button className="ne-btn primary" style={{ height: 54, width: '100%', justifyContent: 'center', marginTop: 4, fontSize: 15 }}>
          로그인 →
        </button>
        <div className="ne-chips" style={{ justifyContent: 'center', marginTop: 6 }}>
          <button className="ne-chip" style={{ height: 32, fontSize: 12 }}><span className="dot" />SSO</button>
          <button className="ne-chip gold" style={{ height: 32, fontSize: 12 }}><span className="dot" />지문</button>
          <button className="ne-chip cyan" style={{ height: 32, fontSize: 12 }}><span className="dot" />외부</button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────── 02 · DASHBOARD · Neural ─────────────────── */
function MobNeuralDashboard({ theme = 'dark' }) {
  const isLight = theme === 'light';
  return (
    <div className={'ne-canvas' + (isLight ? ' aj-neural light' : ' aj-neural')}
         style={{ height: '100%', overflow: 'auto', paddingTop: 56, paddingBottom: 100 }}>
      <div style={{ padding: '14px 18px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <img
            src={`../../assets/ajin_logo_${isLight ? 'light' : 'dark'}.svg`}
            alt="AJIN"
            style={{ height: 22, width: 'auto', display: 'block' }}
          />
          <div className="ne-eyebrow">05.25 · 월 · 09:14</div>
        </div>
        <h1 className="ne-greet" style={{ fontSize: 32, marginTop: 12, lineHeight: 1.05 }}>
          안녕하세요,<br/>
          <span className="ombre">김지훈</span> 책임님
        </h1>
        <p className="ne-body" style={{ marginTop: 6, fontSize: 13.5 }}>
          오늘 데일리 브리프 3건이 준비됐어요.
        </p>
      </div>

      {/* Spark feed */}
      <div style={{ padding: '20px 18px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="ne-card spectrum" style={{ background: 'rgba(252,177,50,0.22)', borderColor: 'transparent', padding: 16 }}>
          <div className="ne-eyebrow" style={{ marginBottom: 6, fontSize: 9.5 }}>오전 9:14 · 데일리 브리프</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ne-text)', lineHeight: 1.3 }}>
            오늘은 가동률이 평소보다 <span className="ombre" style={{ fontWeight: 800 }}>6%</span> 높아요
          </div>
          <p className="ne-body" style={{ fontSize: 12.5, marginTop: 6 }}>
            3라인 풀가동, 1라인 셋업 완료. 일정 7건 중요 표시.
          </p>
        </div>

        <div className="ne-card spectrum" style={{ background: 'rgba(252,177,50,0.22)', borderColor: 'transparent', padding: 16 }}>
          <div className="ne-eyebrow" style={{ marginBottom: 6, fontSize: 9.5 }}>검토 대기</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ne-text)', lineHeight: 1.3 }}>
            품질 이슈 2건 — 1라인 PVC 외관
          </div>
          <p className="ne-body" style={{ fontSize: 12.5, marginTop: 6 }}>
            LOT-A2604-118 외관 0.42%. 조치안 자동 생성됨.
          </p>
        </div>

        {/* Mini KPIs row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          <div className="ne-card" style={{ padding: 12, borderRadius: 16 }}>
            <div className="ne-eyebrow" style={{ fontSize: 9 }}>가동률</div>
            <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, color: 'var(--ne-text)', letterSpacing: '-0.02em' }}>94.2<span style={{ fontSize: 12, color: 'var(--ne-text-3)' }}>%</span></div>
          </div>
          <div className="ne-card" style={{ padding: 12, borderRadius: 16 }}>
            <div className="ne-eyebrow" style={{ fontSize: 9 }}>NCR</div>
            <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, color: 'var(--ne-text)', letterSpacing: '-0.02em' }}>2</div>
          </div>
          <div className="ne-card" style={{ padding: 12, borderRadius: 16 }}>
            <div className="ne-eyebrow" style={{ fontSize: 9 }}>결재</div>
            <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, color: 'var(--ne-text)', letterSpacing: '-0.02em' }}>7</div>
          </div>
        </div>

        {/* Suggestion chips */}
        <div className="ne-chips" style={{ marginTop: 8 }}>
          <button className="ne-chip" style={{ height: 32, fontSize: 12 }}><span className="dot" />NCR 원인 분석</button>
          <button className="ne-chip gold" style={{ height: 32, fontSize: 12 }}><span className="dot" />주간보고 초안</button>
          <button className="ne-chip cyan" style={{ height: 32, fontSize: 12 }}><span className="dot" />사진으로 보고</button>
        </div>
      </div>

      {/* Floating pill composer (sticky bottom) */}
      <div style={{ position: 'absolute', bottom: 50, left: 12, right: 12 }}>
        <div className="ne-pill" style={{ minHeight: 54 }}>
          <button className="icon-btn" style={{ width: 36, height: 36 }}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M10 4v12M4 10h12"/></svg>
          </button>
          <input placeholder="AJIN에게 물어보세요…" style={{ fontSize: 14 }} />
          <button className="send icon-btn" style={{ width: 40, height: 40 }}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 10h11M10 5l5 5-5 5"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────── 04 · CHAT · Neural ─────────────────── */
function MobNeuralChat({ theme = 'dark' }) {
  const isLight = theme === 'light';
  return (
    <div className={'ne-canvas' + (isLight ? ' aj-neural light' : ' aj-neural')}
         style={{ height: '100%', display: 'flex', flexDirection: 'column',
                  paddingTop: 56 }}>

      <div className="ne-glowbar" style={{ height: '45%' }} />

      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px 200px',
                    display: 'flex', flexDirection: 'column', gap: 10 }}>

        <div style={{ marginBottom: 4, padding: '0 4px', display:'flex', alignItems:'center', justifyContent:'space-between', gap:12 }}>
          <div>
            <img
              src={`../../assets/ajin_logo_${isLight ? 'light' : 'dark'}.svg`}
              alt="AJIN"
              style={{ height: 18, width: 'auto', display: 'block', marginBottom: 8 }}
            />
            <div className="ne-eyebrow">AI ASSISTANT · 채팅</div>
            <h2 className="ne-h2" style={{ marginTop: 6, fontSize: 22 }}>
              오늘은 어떤 일을<br/>함께 할까요?
            </h2>
          </div>
        </div>

        {/* User bubble */}
        <div className="ne-card user" style={{ padding: 14, maxWidth: '78%' }}>
          <p style={{ margin: 0, fontSize: 13.5, fontWeight: 500, color: '#1A1004', lineHeight: 1.4 }}>
            NCR-2604-118 외관 불량 원인이 뭐야?
          </p>
        </div>

        {/* AI generative card */}
        <div className="ne-card spectrum" style={{ padding: 16 }}>
          <div className="ne-eyebrow" style={{ marginBottom: 6, fontSize: 9 }}>응답 · Gemini 3.5 · 1.2s</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ne-text)', letterSpacing: '-0.01em', lineHeight: 1.3 }}>
            1라인 PVC 외관에서 0.42% 불량
          </div>
          <p style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', margin: '8px 0',
                      background: '#FFE9B8',
                      WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            노즐 압력 불균일
          </p>
          <p className="ne-body" style={{ fontSize: 13, lineHeight: 1.5 }}>
            인접 LOT 대비 압력 표준편차 +14%. 오늘 야간 점검 권장.
          </p>

          <div className="ne-bars" style={{ marginTop: 10 }}>
            <div className="ne-bar" style={{ gridTemplateColumns: '78px 1fr 42px', fontSize: 11 }}>
              <span>압력 σ</span>
              <div className="track"><div className="fill" style={{ width: '78%' }} /></div>
              <span className="v" style={{ fontSize: 11 }}>+14%</span>
            </div>
            <div className="ne-bar" style={{ gridTemplateColumns: '78px 1fr 42px', fontSize: 11 }}>
              <span>결함률</span>
              <div className="track"><div className="fill" style={{ width: '42%' }} /></div>
              <span className="v" style={{ fontSize: 11 }}>0.42%</span>
            </div>
          </div>

          <div className="ne-chips" style={{ marginTop: 12 }}>
            <button className="ne-chip" style={{ height: 30, fontSize: 11 }}><span className="dot" />조치안 작성</button>
            <button className="ne-chip gold" style={{ height: 30, fontSize: 11 }}><span className="dot" />야간점검 등록</button>
          </div>
        </div>
      </div>

      {/* Pill composer */}
      <div style={{ position: 'absolute', bottom: 50, left: 12, right: 12 }}>
        <div className="ne-pill" style={{ minHeight: 54 }}>
          <button className="icon-btn" style={{ width: 36, height: 36 }}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M10 4v12M4 10h12"/></svg>
          </button>
          <input placeholder="질문 또는 사진…" style={{ fontSize: 14 }} />
          <button className="icon-btn" style={{ width: 36, height: 36 }}>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <rect x="7.5" y="3" width="5" height="9" rx="2.5"/>
              <path d="M4.5 9.5a5.5 5.5 0 0011 0M10 15v2.5"/>
            </svg>
          </button>
          <button className="send icon-btn" style={{ width: 40, height: 40 }}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 10h11M10 5l5 5-5 5"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { MobNeuralLogin, MobNeuralDashboard, MobNeuralChat });
