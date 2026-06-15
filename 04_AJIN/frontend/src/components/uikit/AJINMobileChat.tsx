// AJINMobileChat — iPhone 모바일 AI Chat 화면.
//
// 2026-05-28 사용자 모바일 피드백:
//   "챗봇 기능도 확인해보니 기능을 사용하지 못하고 그냥 UI만 달랑 만들어 놨네?"
//
// 이전: send() 가 navigate('/chat?prefill=...') 만 함. chat.tsx 가 isMobile
// 시점에 다시 AJINMobileChat 으로 early return → prefill 처리 코드가 실행
// 안 되어 응답 0건.
//
// 해결: AJINMobileChat 자체에 실제 chat 로직 (messages state + useSSE 직접
// 호출 + streaming 토큰 누적). chat.tsx 의 quick questions / SOP / 액션 카드
// / 비교 모드 등 복잡 기능은 모바일에서 생략 (데스크탑 진입). 핵심 챗
// (질문 → 토큰 streaming 응답) 만 모바일에서 작동.

import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowUp, ChevronLeft, MessageSquare, Sparkles } from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { buildChatUrl } from '@api/onboarding';
import { apiUrl } from '@api/baseUrl';
import { useSSE } from '@hooks/useSSE';
import type { ForceProvider } from '@/types/chat';

// 2026-05-28 — 모바일 모델 선택 (사용자 피드백: 모바일에 모델 선택 기능 없음).
// chat.tsx 의 ModelSelect (react-select 기반) 는 너무 무거움 → 모바일은 native
// select 로 단순화. localStorage 키는 chat.tsx 와 동일 → 모바일/데스크탑 일관.
const FORCE_PROVIDER_LS_KEY = 'ajin-chat-force-provider';

function loadForceProvider(): ForceProvider | null {
  try {
    const raw = localStorage.getItem(FORCE_PROVIDER_LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ForceProvider;
    if (parsed && typeof parsed.provider === 'string' && typeof parsed.model === 'string') {
      return parsed;
    }
  } catch {
    // fall through
  }
  return null;
}

interface MobileModelOption {
  provider: 'ollama' | 'gemini';
  id: string;
  label: string;
  available: boolean;
  blocked?: boolean;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  text: string;
  t: string;
  streaming?: boolean;
  src?: string;
  latency?: string;
}

const STARTER_PROMPTS = [
  { id: 'sop', ko: '사출 #03 SOP 알려줘' },
  { id: 'ecn', ko: 'ECN-2024-0182 요약' },
  { id: 'spc', ko: 'Cpk 분석 — 라인 #03' },
  { id: 'reg', ko: 'CBAM Q3 보고서 가이드' },
] as const;

function nowHM(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function AJINMobileChat() {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const location = useLocation();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [err, setErr] = useState<string | null>(null);

  // 2026-05-28 — 모델 선택 state (localStorage 영속, chat.tsx 와 동일 키)
  const [forceProvider, setForceProvider] = useState<ForceProvider | null>(loadForceProvider);
  const [modelOptions, setModelOptions] = useState<MobileModelOption[]>([]);
  useEffect(() => {
    try {
      if (forceProvider) {
        localStorage.setItem(FORCE_PROVIDER_LS_KEY, JSON.stringify(forceProvider));
      } else {
        localStorage.removeItem(FORCE_PROVIDER_LS_KEY);
      }
    } catch {
      // ignore
    }
  }, [forceProvider]);
  // 백엔드에서 사용 가능한 모델 옵션 1회 fetch
  useEffect(() => {
    let alive = true;
    fetch(apiUrl('/models/llm-options?feature=chat'), { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!alive || !data?.options) return;
        const opts: MobileModelOption[] = (data.options as MobileModelOption[]).filter((o) => o.available && !o.blocked);
        setModelOptions(opts);
      })
      .catch(() => {
        // 백엔드 미가용 시 빈 목록 — '자동' 만 노출
      });
    return () => { alive = false; };
  }, []);

  const activeIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sentPrefillRef = useRef(false);

  const sse = useSSE({
    onToken: (chunk) => {
      const id = activeIdRef.current;
      if (!id) return;
      setMessages((arr) => arr.map((m) => (m.id === id ? { ...m, text: m.text + chunk } : m)));
    },
    onMetadata: (meta) => {
      const id = activeIdRef.current;
      if (!id) return;
      const src = typeof meta.source === 'string' ? meta.source : undefined;
      const latency = typeof meta.latency === 'string' ? meta.latency : undefined;
      setMessages((arr) =>
        arr.map((m) => (m.id === id ? { ...m, src: src ?? m.src, latency: latency ?? m.latency } : m)),
      );
    },
    onDone: (final) => {
      const id = activeIdRef.current;
      if (!id) return;
      const lat =
        typeof final.latency_ms === 'number'
          ? `${final.latency_ms}ms`
          : typeof final.latency === 'string'
            ? final.latency
            : undefined;
      setMessages((arr) =>
        arr.map((m) => (m.id === id ? { ...m, streaming: false, latency: lat ?? m.latency } : m)),
      );
      activeIdRef.current = null;
    },
    onError: (msg) => {
      const id = activeIdRef.current;
      setErr(msg);
      if (id) {
        setMessages((arr) =>
          arr.map((m) => (m.id === id ? { ...m, streaming: false, text: m.text || `(오류) ${msg}` } : m)),
        );
      }
      activeIdRef.current = null;
    },
  });

  const busy = sse.isStreaming;

  // auto-scroll on new message
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, sse.isStreaming]);

  // ?prefill=... query param 처리 (1회만)
  useEffect(() => {
    if (sentPrefillRef.current) return;
    const params = new URLSearchParams(location.search);
    const prefill = params.get('prefill');
    if (prefill && prefill.trim()) {
      sentPrefillRef.current = true;
      sendQuery(prefill.trim());
      window.history.replaceState({}, '', location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  function sendQuery(q: string) {
    if (!q.trim() || busy) return;
    setErr(null);

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', text: q, t: nowHM() };
    const aiId = `a-${Date.now() + 1}`;
    const aiMsg: ChatMessage = { id: aiId, role: 'ai', text: '', t: nowHM(), streaming: true };
    activeIdRef.current = aiId;
    setMessages((arr) => [...arr, userMsg, aiMsg]);
    setInput('');

    void sse.start({
      url: buildChatUrl(),
      body: {
        query: q,
        mode: 'work',
        department: user?.department ?? null,
        language: 'ko',
        // 2026-05-28 — 모바일 모델 선택 적용 (chat.tsx 와 동일 페이로드 형식)
        force_provider: forceProvider ? [forceProvider.provider, forceProvider.model] : null,
      },
    });
  }

  const handleSend = () => sendQuery(input.trim());
  const handleStarter = (q: string) => sendQuery(q);

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div
        className="aj-screen dark"
        style={{ position: 'relative', display: 'flex', flexDirection: 'column', height: '100vh' }}
      >
        <div className="aj-bg-grad dark" />

        {/* Top bar */}
        <div
          style={{
            position: 'relative',
            zIndex: 3,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '14px 16px 4px',
          }}
        >
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="뒤로"
            style={{
              width: 36,
              height: 36,
              borderRadius: 999,
              background: 'transparent',
              border: '1px solid rgba(127,127,127,0.25)',
              color: 'currentColor',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ChevronLeft size={18} aria-hidden />
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="aj-mono" style={{ fontSize: 10, opacity: 0.6, letterSpacing: '0.1em' }}>
              AI ASSISTANT · CHAT
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, marginTop: 2 }}>AJIN 챗봇</div>
          </div>
          <span
            className="aj-chip"
            style={{
              fontSize: 10,
              padding: '4px 9px',
              background: busy ? 'rgba(252,177,50,0.18)' : 'rgba(79,183,116,0.18)',
              border: `1px solid ${busy ? 'rgba(252,177,50,0.4)' : 'rgba(79,183,116,0.4)'}`,
              color: 'inherit',
            }}
          >
            {busy ? 'STREAMING' : 'ON-LINE'}
          </span>
        </div>

        {/* Scrollable messages — padding-bottom 충분히 (composer ~120 + BottomTabBar 60 + 여유 30) */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            position: 'relative',
            zIndex: 3,
            padding: '12px 14px calc(env(safe-area-inset-bottom, 0px) + 210px)',
          }}
        >
          {/* Empty state */}
          {messages.length === 0 && (
            <>
              <div style={{ padding: '8px 4px 16px' }}>
                <div className="aj-mono" style={{ fontSize: 10, opacity: 0.55 }}>
                  <Sparkles size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                  AJIN AI · 데일리 어시스턴트
                </div>
                <h1
                  style={{
                    fontSize: 26,
                    fontWeight: 700,
                    margin: '8px 0 4px',
                    letterSpacing: '-0.018em',
                  }}
                >
                  안녕하세요,
                  <br />
                  <span style={{ color: 'var(--aj-gold, #FCB132)' }}>
                    {user?.username ?? '시스템관리자'}
                  </span>
                  님
                </h1>
                <div style={{ fontSize: 13, opacity: 0.65 }}>
                  SOP / ECN / 품질 / 법규 / 설비 — 무엇이든 물어보세요.
                </div>
              </div>
              <div className="aj-glass" style={{ padding: 14, marginBottom: 14, borderRadius: 14 }}>
                <div className="aj-mono" style={{ fontSize: 10, opacity: 0.55, marginBottom: 6 }}>
                  AI · 방금
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                  현장 표준작업서, 설계 변경통보, SPC 분석, 법규 모니터까지 — 사내 데이터로 즉시
                  답변드립니다. 아래 빠른 시작을 누르거나 직접 입력해 주세요.
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {STARTER_PROMPTS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleStarter(p.ko)}
                    disabled={busy}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '10px 14px',
                      borderRadius: 999,
                      background: 'rgba(127,127,127,0.08)',
                      border: '1px solid rgba(127,127,127,0.20)',
                      color: 'inherit',
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: busy ? 'wait' : 'pointer',
                      textAlign: 'left',
                      fontFamily: 'inherit',
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 999,
                        background: 'var(--aj-gold, #FCB132)',
                      }}
                    />
                    {p.ko}
                  </button>
                ))}
              </div>
            </>
          )}

          {/* Messages */}
          {messages.map((m) => (
            <div key={m.id} style={{ marginBottom: 12 }}>
              {m.role === 'user' ? (
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div
                    style={{
                      maxWidth: '82%',
                      padding: '10px 14px',
                      borderRadius: 18,
                      background: 'var(--aj-gold, #FCB132)',
                      color: '#1A1004',
                      fontSize: 14,
                      fontWeight: 500,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {m.text}
                  </div>
                </div>
              ) : (
                <div className="aj-glass" style={{ padding: '12px 14px', borderRadius: 14 }}>
                  <div className="aj-mono" style={{ fontSize: 10, opacity: 0.55, marginBottom: 6 }}>
                    AI · {m.t}
                    {m.streaming ? ' · STREAMING' : ''}
                    {m.src ? ` · ${m.src}` : ''}
                    {m.latency ? ` · ${m.latency}` : ''}
                  </div>
                  <div
                    style={{
                      fontSize: 14,
                      lineHeight: 1.55,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {m.text || (m.streaming ? '…' : '')}
                  </div>
                </div>
              )}
            </div>
          ))}

          {err && (
            <div
              className="aj-glass"
              style={{ padding: 10, fontSize: 12, color: '#FF7565', marginTop: 8 }}
            >
              연결 오류: {err}
            </div>
          )}
        </div>

        {/* Fixed composer — 2026-05-28 (재수정 v3, PR #48 후속):
            이전 sticky: Shell <main> 의 height 가 자식 .aj-mobile(minHeight:100vh)
            만큼 자라 main border-box bottom 이 viewport.bottom 보다 아래로 overflow.
            sticky 가 main padding-box bottom 기준 stick → composer 가 viewport 밖
            영역에 위치 → main overflow:hidden 으로 row 2 잘려 BottomTabBar 와 겹침.
            (iPhone 14 Pro Max 에서 row 2 완전 가려짐, 12 Pro 에서 부분 가려짐 — viewport
            가 클수록 overflow 양 커짐.)
            정확한 fix: viewport 기준 position:fixed 로 BottomTabBar 바로 위 고정.
            zIndex 51 (BottomTabBar 50 위). messages padding-bottom 210 그대로 충분. */}
        <div
          className="aj-composer"
          style={{
            position: 'fixed',
            left: 0,
            right: 0,
            bottom: 'calc(env(safe-area-inset-bottom, 0px) + var(--bottom-nav-h, 60px))',
            zIndex: 51,
            padding: '8px 14px 12px',
            background: 'linear-gradient(to top, var(--hud-bg) 80%, transparent)',
          }}
        >
          {/* 2026-05-28 (재수정 v3) — composer pill 2-row + theme-aware glass.
              이전: hard-coded rgba(10,14,24,0.65) 다크색 → 라이트 모드 부적합.
              지금: var(--glass-bg-strong) / var(--glass-border) / var(--glass-shadow)
              토큰 사용. 다크 = hud-surface 80%, 라이트 = white 80%, 자동 매핑.
              maxWidth 640 + margin auto 로 큰 viewport (태블릿 등) 에서 가운데 정렬. */}
          <div
            className="ne-pill aj-glass"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              padding: '8px 12px',
              borderRadius: 24,
              background: 'var(--glass-bg-strong)',
              border: '1px solid var(--glass-border)',
              backdropFilter: 'blur(24px) saturate(180%)',
              WebkitBackdropFilter: 'blur(24px) saturate(180%)',
              boxShadow:
                '0 22px 60px -20px var(--glass-shadow), 0 4px 14px -6px var(--glass-shadow)',
              maxWidth: 640,
              marginLeft: 'auto',
              marginRight: 'auto',
            }}
          >
            {/* Row 1 — input + send */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 44 }}>
              <MessageSquare
                size={16}
                aria-hidden
                style={{ color: 'var(--hud-text-dim)', flexShrink: 0 }}
              />
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={busy ? '응답 받는 중…' : '물어보세요'}
                disabled={busy}
                style={{
                  flex: 1,
                  minWidth: 0,
                  background: 'transparent',
                  border: 0,
                  outline: 0,
                  padding: '0 4px',
                  color: 'var(--hud-text)',
                  fontSize: 16,
                  fontWeight: 500,
                  letterSpacing: '-0.01em',
                }}
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || busy}
                className="send"
                aria-label="전송"
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 999,
                  background: input.trim() && !busy ? '#FFD78A' : 'rgba(255,215,138,0.4)',
                  color: '#1A1004',
                  border: 0,
                  cursor: input.trim() && !busy ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow:
                    input.trim() && !busy
                      ? '0 8px 22px -8px rgba(252,177,50,0.75)'
                      : 'none',
                  transition: 'background 200ms ease-out, box-shadow 200ms ease-out',
                  flexShrink: 0,
                }}
              >
                <ArrowUp size={16} aria-hidden />
              </button>
            </div>
            {/* Row 2 — model selector (자동 chip + native select)
                2026-05-28 v3 — border-top / chip 비활성 색상 theme-aware 토큰화. */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '0 2px',
                borderTop: '1px solid var(--hud-border-light)',
                paddingTop: 6,
              }}
            >
              <button
                type="button"
                onClick={() => setForceProvider(null)}
                aria-pressed={forceProvider === null}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '3px 10px',
                  borderRadius: 999,
                  background:
                    forceProvider === null ? 'var(--hud-primary-dim)' : 'var(--hud-surface-2)',
                  border: `1px solid ${
                    forceProvider === null ? 'rgba(252,177,50,0.50)' : 'var(--hud-border-light)'
                  }`,
                  color: forceProvider === null ? 'var(--aj-gold, #FCB132)' : 'inherit',
                  fontFamily: 'inherit',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
                title="자동 라우팅 (백엔드 LLMRouter 가 모델 결정)"
              >
                자동
              </button>
              <select
                value={forceProvider ? `${forceProvider.provider}::${forceProvider.model}` : ''}
                onChange={(e) => {
                  const v = e.target.value;
                  if (!v) {
                    setForceProvider(null);
                    return;
                  }
                  const [provider, model] = v.split('::');
                  setForceProvider({ provider, model });
                }}
                disabled={busy || modelOptions.length === 0}
                style={{
                  flex: 1,
                  minWidth: 0,
                  background: 'transparent',
                  border: 0,
                  outline: 0,
                  color: 'var(--hud-text-dim)',
                  fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                  fontSize: 11,
                  fontWeight: 600,
                  textAlign: 'right',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  cursor: busy || modelOptions.length === 0 ? 'not-allowed' : 'pointer',
                  appearance: 'none',
                  WebkitAppearance: 'none',
                  padding: '4px 4px',
                  direction: 'rtl', // 긴 옵션 라벨이 잘릴 때 오른쪽 (모델 이름) 우선 표시
                }}
              >
                <option value="" style={{ direction: 'ltr' }}>
                  {modelOptions.length === 0 ? '모델 자동 ▾' : '모델 선택 ▾'}
                </option>
                {modelOptions.map((o) => (
                  <option
                    key={`${o.provider}::${o.id}`}
                    value={`${o.provider}::${o.id}`}
                    style={{ direction: 'ltr' }}
                  >
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AJINMobileChat;
