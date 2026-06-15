// ios-frame.jsx — Refined device frame (v2).
// Original AJIN-style implementation. Inspired by community iPhone 17 / AIR
// reference assets — bezel ratios + radii only, no Apple system UI replicated.
//
// Exports: IOSDevice, IOSStatusBar, IOSGlassPill, IOSList, IOSListRow,
//          IOSKeyboard, IOSNavBar
//
// New in v2:
//  • Realistic 4-layer bezel: outer rim → ring → glass → screen
//  • Subtle screen reflection sheen (toggleable per Tweaks)
//  • Dynamic Island variants: pill | wide | minimal
//  • Status bar — Korean date variant + accurate signal/wifi/battery glyphs
//  • Home indicator — refined width + opacity per theme
//  • Keyboard — slightly softer keys, better light-mode contrast
//
// Tweaks integration (read from window.__AJIN_TWEAKS_FRAME if present):
//   { bezelHi, bezelTone, island, sheen, reflect, statusTime, statusLocale }

(function () {
  // ─────────────────────────────────────────────────────────────
  // Status bar
  // ─────────────────────────────────────────────────────────────
  function IOSStatusBar({ dark = false, time, locale = 'en' }) {
    const c = dark ? '#fff' : '#000';
    const t = time || (locale === 'ko' ? '9:41' : '9:41');
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '21px 34px 17px 32px', boxSizing: 'border-box',
        position: 'relative', zIndex: 20, width: '100%', height: 54,
      }}>
        {/* time */}
        <div style={{
          minWidth: 60, height: 22, display: 'flex', alignItems: 'center',
          fontFamily: '-apple-system, "SF Pro", system-ui', fontWeight: 590,
          fontSize: 17, lineHeight: '22px', color: c, letterSpacing: '-0.01em',
        }}>{t}</div>
        {/* indicators */}
        <div style={{
          minWidth: 90, height: 22, display: 'flex', alignItems: 'center',
          justifyContent: 'flex-end', gap: 6.5,
        }}>
          <svg width="19" height="12" viewBox="0 0 19 12">
            <rect x="0" y="7.5" width="3.2" height="4.5" rx="0.7" fill={c}/>
            <rect x="4.8" y="5" width="3.2" height="7" rx="0.7" fill={c}/>
            <rect x="9.6" y="2.5" width="3.2" height="9.5" rx="0.7" fill={c}/>
            <rect x="14.4" y="0" width="3.2" height="12" rx="0.7" fill={c}/>
          </svg>
          <svg width="16" height="12" viewBox="0 0 16 12">
            <path d="M8 3C10.2 3 12.2 3.9 13.6 5.3L14.6 4.3C12.9 2.5 10.6 1.4 8 1.4C5.4 1.4 3.1 2.5 1.4 4.3L2.4 5.3C3.8 3.9 5.8 3 8 3Z" fill={c}/>
            <path d="M8 6.4C9.3 6.4 10.4 6.9 11.3 7.7L12.3 6.7C11.1 5.6 9.6 4.9 8 4.9C6.4 4.9 4.9 5.6 3.7 6.7L4.7 7.7C5.6 6.9 6.7 6.4 8 6.4Z" fill={c}/>
            <circle cx="8" cy="10" r="1.5" fill={c}/>
          </svg>
          <svg width="27" height="13" viewBox="0 0 27 13">
            <rect x="0.5" y="0.5" width="23" height="12" rx="3.5"
                  stroke={c} strokeOpacity="0.4" fill="none" strokeWidth="1"/>
            <rect x="2" y="2" width="20" height="9" rx="2" fill={c}/>
            <path d="M24.8 4.2V8.8C25.7 8.5 26.3 7.7 26.3 6.5C26.3 5.3 25.7 4.5 24.8 4.2Z"
                  fill={c} fillOpacity="0.4"/>
          </svg>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Liquid glass pill — blur + tint + shine (re-exported)
  // ─────────────────────────────────────────────────────────────
  function IOSGlassPill({ children, dark = false, style = {} }) {
    return (
      <div style={{
        height: 44, minWidth: 44, borderRadius: 9999,
        position: 'relative', overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: dark
          ? '0 2px 6px rgba(0,0,0,0.35), 0 6px 16px rgba(0,0,0,0.2)'
          : '0 1px 3px rgba(0,0,0,0.07), 0 3px 10px rgba(0,0,0,0.06)',
        ...style,
      }}>
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 9999,
          backdropFilter: 'blur(14px) saturate(180%)',
          WebkitBackdropFilter: 'blur(14px) saturate(180%)',
          background: dark ? 'rgba(120,120,128,0.28)' : 'rgba(255,255,255,0.5)',
        }} />
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 9999,
          boxShadow: dark
            ? 'inset 1.5px 1.5px 1px rgba(255,255,255,0.15), inset -1px -1px 1px rgba(255,255,255,0.08)'
            : 'inset 1.5px 1.5px 1px rgba(255,255,255,0.7), inset -1px -1px 1px rgba(255,255,255,0.4)',
          border: dark ? '0.5px solid rgba(255,255,255,0.15)' : '0.5px solid rgba(0,0,0,0.06)',
        }} />
        <div style={{
          position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', padding: '0 4px',
        }}>{children}</div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Nav bar (kept for backward-compat with PadScreens)
  // ─────────────────────────────────────────────────────────────
  function IOSNavBar({ title = 'Title', dark = false, trailingIcon = true }) {
    const muted = dark ? 'rgba(255,255,255,0.6)' : '#404040';
    const text = dark ? '#fff' : '#000';
    const pillIcon = (c) => (
      <IOSGlassPill dark={dark}>
        <div style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{c}</div>
      </IOSGlassPill>
    );
    return (
      <div style={{ display:'flex', flexDirection:'column', gap:10,
                    paddingTop:62, paddingBottom:10, position:'relative', zIndex:5 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 16px' }}>
          {pillIcon(
            <svg width="12" height="20" viewBox="0 0 12 20" fill="none" style={{ marginLeft: -1 }}>
              <path d="M10 2L2 10l8 8" stroke={muted} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          {trailingIcon && pillIcon(
            <svg width="22" height="6" viewBox="0 0 22 6">
              <circle cx="3" cy="3" r="2.5" fill={muted}/>
              <circle cx="11" cy="3" r="2.5" fill={muted}/>
              <circle cx="19" cy="3" r="2.5" fill={muted}/>
            </svg>
          )}
        </div>
        <div style={{ padding:'0 16px', fontFamily:'-apple-system, system-ui',
                      fontSize:34, fontWeight:700, lineHeight:'41px', color:text, letterSpacing:0.4 }}>{title}</div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // List
  // ─────────────────────────────────────────────────────────────
  function IOSListRow({ title, detail, icon, chevron = true, isLast = false, dark = false }) {
    const text = dark ? '#fff' : '#000';
    const sec = dark ? 'rgba(235,235,245,0.6)' : 'rgba(60,60,67,0.6)';
    const ter = dark ? 'rgba(235,235,245,0.3)' : 'rgba(60,60,67,0.3)';
    const sep = dark ? 'rgba(84,84,88,0.65)' : 'rgba(60,60,67,0.12)';
    return (
      <div style={{
        display:'flex', alignItems:'center', minHeight:52, padding:'0 16px', position:'relative',
        fontFamily:'-apple-system, system-ui', fontSize:17, letterSpacing:-0.43,
      }}>
        {icon && <div style={{ width:30, height:30, borderRadius:7, background:icon, marginRight:12, flexShrink:0 }} />}
        <div style={{ flex:1, color:text }}>{title}</div>
        {detail && <span style={{ color:sec, marginRight:6 }}>{detail}</span>}
        {chevron && (
          <svg width="8" height="14" viewBox="0 0 8 14" style={{ flexShrink:0 }}>
            <path d="M1 1l6 6-6 6" stroke={ter} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
        {!isLast && <div style={{ position:'absolute', bottom:0, right:0, left:icon ? 58 : 16, height:0.5, background:sep }} />}
      </div>
    );
  }

  function IOSList({ header, children, dark = false }) {
    const hc = dark ? 'rgba(235,235,245,0.6)' : 'rgba(60,60,67,0.6)';
    const bg = dark ? '#1C1C1E' : '#fff';
    return (
      <div>
        {header && <div style={{ fontFamily:'-apple-system, system-ui', fontSize:13, color:hc,
                                  textTransform:'uppercase', padding:'8px 36px 6px', letterSpacing:-0.08 }}>{header}</div>}
        <div style={{ background:bg, borderRadius:26, margin:'0 16px', overflow:'hidden' }}>{children}</div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Dynamic Island variants
  // ─────────────────────────────────────────────────────────────
  function DynamicIsland({ variant = 'pill' }) {
    const styles = {
      pill:    { width: 126, height: 37, borderRadius: 24 },   // standard
      wide:    { width: 142, height: 38, borderRadius: 24 },   // iPhone 17 Pro look
      minimal: { width: 110, height: 34, borderRadius: 22 },   // iPhone AIR thinner
    };
    const s = styles[variant] || styles.pill;
    return (
      <div style={{
        position:'absolute', top: 11, left:'50%', transform:'translateX(-50%)',
        width: s.width, height: s.height, borderRadius: s.borderRadius,
        background: '#000', zIndex: 50,
        // micro-detail: extremely subtle inner specular near top edge
        boxShadow: 'inset 0 0.5px 0 rgba(255,255,255,0.04)',
      }}>
        {/* hint of the camera + sensor — very subtle */}
        <div style={{ position:'absolute', right: 14, top:'50%', transform:'translateY(-50%)',
                      width: 8, height: 8, borderRadius:99, background:'#0c0c10',
                      boxShadow:'inset 0 0 0 1px rgba(80,90,110,0.35), inset 0 0 4px rgba(0,0,0,0.9)' }} />
        <div style={{ position:'absolute', right: 30, top:'50%', transform:'translateY(-50%)',
                      width: 4, height: 4, borderRadius:99, background:'#080a0e',
                      boxShadow:'inset 0 0 0 0.5px rgba(120,130,150,0.25)' }} />
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Device frame v2 — realistic bezel
  // ─────────────────────────────────────────────────────────────
  function IOSDevice({
    children, width = 402, height = 874, dark = false,
    title, keyboard = false,
    island = 'pill',      // 'pill' | 'wide' | 'minimal'
    bezelTone = 'titanium', // 'titanium' | 'space' | 'natural'
    bezelHi = true,       // top/edge highlights on
    sheen = true,         // diagonal screen sheen
    reflect = true,       // bottom screen reflection
  }) {
    // Bezel palettes — narrow, intentional
    const bezels = {
      titanium: {
        outer: 'linear-gradient(135deg, #1a1a1d 0%, #2a2a2e 30%, #1a1a1d 60%, #383838 100%)',
        ring:  'linear-gradient(135deg, #3a3a3f 0%, #1c1c20 50%, #2e2e34 100%)',
      },
      space: {
        outer: 'linear-gradient(135deg, #0e0e10 0%, #1c1c22 40%, #0a0a0c 100%)',
        ring:  'linear-gradient(135deg, #25252c 0%, #0e0e12 50%, #1c1c22 100%)',
      },
      natural: {
        outer: 'linear-gradient(135deg, #c4b8a4 0%, #d8cdb8 40%, #ada196 100%)',
        ring:  'linear-gradient(135deg, #e6ddc9 0%, #b2a692 50%, #d4c8b3 100%)',
      },
    };
    const bz = bezels[bezelTone] || bezels.titanium;

    // The given width/height are the SCREEN dimensions (AJIN UI canvas).
    // Bezel layers add padding OUTSIDE that — so existing screens still fit
    // exactly as before.
    const bezelPad = 7; // 4px outer frame + 3px ring = visual thickness
    const outerW = width + bezelPad * 2;
    const outerH = height + bezelPad * 2;

    return (
      <div style={{
        width: outerW, height: outerH, position: 'relative',
        fontFamily: '-apple-system, system-ui, sans-serif',
        WebkitFontSmoothing: 'antialiased',
        // Layer 1 — outer frame (titanium / space gray look)
        padding: 4,
        borderRadius: 56,
        background: bz.outer,
        boxShadow:
          // resting shadow on canvas
          '0 50px 100px -20px rgba(0,0,0,0.4), 0 30px 60px -30px rgba(0,0,0,0.3),' +
          // crisp edge
          '0 0 0 0.5px rgba(0,0,0,0.6)',
      }}>
        {/* Layer 2 — inner bezel ring */}
        <div style={{
          width: '100%', height: '100%',
          borderRadius: 52,
          background: bz.ring,
          padding: 3,
          boxShadow:
            // top highlight — catches "light" from above
            (bezelHi ? 'inset 0 1px 0 rgba(255,255,255,0.12),' : '') +
            'inset 0 0 0 0.5px rgba(0,0,0,0.6)',
          position: 'relative', overflow: 'hidden',
        }}>
          {/* extra micro-highlight bands on left/right curves — gives the rim "shape" */}
          {bezelHi && (
            <>
              <div style={{ position:'absolute', top: 80, left: -1, width: 2, height: outerH - 200,
                            background:'linear-gradient(180deg, transparent, rgba(255,255,255,0.06), transparent)',
                            pointerEvents:'none' }}/>
              <div style={{ position:'absolute', top: 80, right: -1, width: 2, height: outerH - 200,
                            background:'linear-gradient(180deg, transparent, rgba(255,255,255,0.06), transparent)',
                            pointerEvents:'none' }}/>
            </>
          )}

          {/* Layer 3 — screen surface (where the UI lives) */}
          <div style={{
            width: width, height: height,
            borderRadius: 48,
            overflow: 'hidden', position: 'relative',
            background: dark ? '#000' : '#F2F2F7',
            boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.85)',
          }}>
            {/* Dynamic island */}
            <DynamicIsland variant={island} />

            {/* Status bar — absolute */}
            <div style={{ position:'absolute', top:0, left:0, right:0, zIndex:10 }}>
              <IOSStatusBar dark={dark} />
            </div>

            {/* App content */}
            <div style={{ height:'100%', display:'flex', flexDirection:'column' }}>
              {title !== undefined && <IOSNavBar title={title} dark={dark} />}
              <div style={{ flex:1, overflow:'auto', position:'relative' }}>{children}</div>
              {keyboard && <IOSKeyboard dark={dark} />}
            </div>

            {/* Layer 4a — diagonal screen sheen (very subtle) */}
            {sheen && (
              <div style={{
                position:'absolute', inset:0, pointerEvents:'none', zIndex: 65,
                background:
                  'linear-gradient(115deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0) 22%, rgba(255,255,255,0) 78%, rgba(255,255,255,0.04) 100%)',
                mixBlendMode: 'screen',
              }}/>
            )}
            {/* Layer 4b — bottom screen reflection */}
            {reflect && (
              <div style={{
                position:'absolute', left:0, right:0, bottom:0, height:140, pointerEvents:'none', zIndex: 65,
                background: 'linear-gradient(0deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0) 100%)',
                mixBlendMode: 'screen',
              }}/>
            )}

            {/* Home indicator */}
            <div style={{
              position:'absolute', bottom:0, left:0, right:0, zIndex:60, height:34,
              display:'flex', justifyContent:'center', alignItems:'flex-end',
              paddingBottom:8, pointerEvents:'none',
            }}>
              <div style={{
                width:139, height:5, borderRadius:100,
                background: dark ? 'rgba(255,255,255,0.78)' : 'rgba(0,0,0,0.28)',
              }} />
            </div>
          </div>
        </div>

        {/* Side buttons — tiny visual details on the bezel */}
        <SideButtons height={height} tone={bezelTone}/>
      </div>
    );
  }

  function SideButtons({ height, tone }) {
    const dark = tone !== 'natural';
    const col = dark
      ? 'linear-gradient(180deg, #0a0a0c, #1c1c22 50%, #0a0a0c)'
      : 'linear-gradient(180deg, #a89a82, #c4b8a4 50%, #a89a82)';
    const shadow = dark
      ? 'inset 0 0.5px 0 rgba(255,255,255,0.06), 0 0 0 0.5px rgba(0,0,0,0.5)'
      : 'inset 0 0.5px 0 rgba(255,255,255,0.3), 0 0 0 0.5px rgba(120,100,70,0.4)';
    // Left side: action btn + vol up + vol down
    // Right side: camera control + power
    return (
      <>
        <div style={{ position:'absolute', left:-2, top:130, width:3, height:32, borderRadius:1, background:col, boxShadow:shadow }}/>
        <div style={{ position:'absolute', left:-2, top:178, width:3, height:60, borderRadius:1, background:col, boxShadow:shadow }}/>
        <div style={{ position:'absolute', left:-2, top:250, width:3, height:60, borderRadius:1, background:col, boxShadow:shadow }}/>
        <div style={{ position:'absolute', right:-2, top:180, width:3, height:90, borderRadius:1, background:col, boxShadow:shadow }}/>
        <div style={{ position:'absolute', right:-2, top:290, width:3, height:44, borderRadius:1, background:col, boxShadow:shadow }}/>
      </>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Keyboard — Liquid Glass (refined)
  // ─────────────────────────────────────────────────────────────
  function IOSKeyboard({ dark = false }) {
    const glyph = dark ? 'rgba(255,255,255,0.78)' : '#3a3a3a';
    const sugg  = dark ? 'rgba(255,255,255,0.7)'  : '#222';
    const keyBg = dark ? 'rgba(255,255,255,0.20)' : 'rgba(255,255,255,0.92)';
    const sepBg = dark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';

    const icons = {
      shift: <svg width="19" height="17" viewBox="0 0 19 17"><path d="M9.5 1L1 9.5h4.5V16h8V9.5H18L9.5 1z" fill={glyph}/></svg>,
      del:   <svg width="23" height="17" viewBox="0 0 23 17"><path d="M7 1h13a2 2 0 012 2v11a2 2 0 01-2 2H7l-6-7.5L7 1z" fill="none" stroke={glyph} strokeWidth="1.6" strokeLinejoin="round"/><path d="M10 5l7 7M17 5l-7 7" stroke={glyph} strokeWidth="1.6" strokeLinecap="round"/></svg>,
      ret:   <svg width="20" height="14" viewBox="0 0 20 14"><path d="M18 1v6H4m0 0l4-4M4 7l4 4" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>,
    };

    const key = (content, { w, flex, ret, fs = 25, k } = {}) => (
      <div key={k} style={{
        height: 42, borderRadius: 8.5,
        flex: flex ? 1 : undefined, width: w, minWidth: 0,
        background: ret ? '#0a84ff' : keyBg,
        boxShadow: ret
          ? '0 1px 0 rgba(0,0,0,0.2), inset 0 0.5px 0 rgba(255,255,255,0.3)'
          : (dark
              ? '0 1px 0 rgba(0,0,0,0.12), inset 0 0.5px 0 rgba(255,255,255,0.1)'
              : '0 1px 0 rgba(0,0,0,0.08), inset 0 0.5px 0 rgba(255,255,255,0.7)'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: '-apple-system, "SF Compact", system-ui',
        fontSize: fs, fontWeight: 458, color: ret ? '#fff' : glyph,
      }}>{content}</div>
    );

    const row = (keys, pad = 0) => (
      <div style={{ display: 'flex', gap: 6.5, justifyContent: 'center', padding: `0 ${pad}px` }}>
        {keys.map(l => key(l, { flex: true, k: l }))}
      </div>
    );

    return (
      <div style={{
        position: 'relative', zIndex: 15, borderRadius: 27, overflow: 'hidden',
        padding: '11px 0 2px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        boxShadow: dark
          ? '0 -2px 20px rgba(0,0,0,0.09)'
          : '0 -1px 6px rgba(0,0,0,0.02), 0 -3px 20px rgba(0,0,0,0.014)',
      }}>
        {/* base */}
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 27,
          backdropFilter: 'blur(18px) saturate(180%)',
          WebkitBackdropFilter: 'blur(18px) saturate(180%)',
          background: dark ? 'rgba(40,40,46,0.55)' : 'rgba(208,210,217,0.62)',
        }} />
        {/* specular */}
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 27,
          boxShadow: dark
            ? 'inset 0 0.5px 0 rgba(255,255,255,0.12)'
            : 'inset 0 0.5px 0 rgba(255,255,255,0.7), inset 0 -0.5px 0 rgba(0,0,0,0.05)',
          border: dark ? '0.5px solid rgba(255,255,255,0.10)' : '0.5px solid rgba(0,0,0,0.05)',
          pointerEvents: 'none',
        }} />

        {/* autocorrect bar */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'center',
                      padding: '8px 22px 13px', width: '100%', boxSizing: 'border-box', position: 'relative' }}>
          {['"라인"', '라인', '오늘'].map((w, i) => (
            <React.Fragment key={i}>
              {i > 0 && <div style={{ width: 1, height: 25, background: sepBg, opacity: 0.6 }} />}
              <div style={{ flex: 1, textAlign: 'center',
                            fontFamily: '-apple-system, system-ui', fontSize: 17,
                            color: sugg, letterSpacing: -0.43, lineHeight: '22px' }}>{w}</div>
            </React.Fragment>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 13,
                      padding: '0 6.5px', width: '100%', boxSizing: 'border-box', position: 'relative' }}>
          {row(['ㅂ','ㅈ','ㄷ','ㄱ','ㅅ','ㅛ','ㅕ','ㅑ','ㅐ','ㅔ'])}
          {row(['ㅁ','ㄴ','ㅇ','ㄹ','ㅎ','ㅗ','ㅓ','ㅏ','ㅣ'], 20)}
          <div style={{ display: 'flex', gap: 14.25, alignItems: 'center' }}>
            {key(icons.shift, { w: 45, k: 'shift' })}
            <div style={{ display: 'flex', gap: 6.5, flex: 1 }}>
              {['ㅋ','ㅌ','ㅊ','ㅍ','ㅠ','ㅜ','ㅡ'].map(l => key(l, { flex: true, k: l }))}
            </div>
            {key(icons.del, { w: 45, k: 'del' })}
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {key('한/영', { w: 80, fs: 14, k: 'lang' })}
            {key('', { flex: true, k: 'space' })}
            {key(icons.ret, { w: 80, ret: true, k: 'ret' })}
          </div>
        </div>

        <div style={{ height: 56, width: '100%', position: 'relative' }} />
      </div>
    );
  }

  Object.assign(window, {
    IOSDevice, IOSStatusBar, IOSGlassPill, IOSList, IOSListRow, IOSKeyboard, IOSNavBar,
  });
})();
