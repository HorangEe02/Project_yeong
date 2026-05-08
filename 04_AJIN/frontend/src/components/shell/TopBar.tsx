// TopBar — canonical uiux/web_app/TopBar.jsx 스타일 (TS port)
// Plan v3.0 — LLM 라벨 동적 표시 (DOCKER / LOCAL / CLOUD / OFFLINE)

import { useEffect, useState } from 'react';
import { useAuthStore } from '@store/auth';
import { useUIStore } from '@store/ui';
import { fetchDiagnose } from '@api/draft';

type LLMState = { label: string; color: string; tooltip: string };

const LLM_STATES: Record<string, LLMState> = {
  loading: { label: 'CHECKING…', color: 'var(--hud-text)', tooltip: '진단 호출 중' },
  docker:  { label: '🐳 DOCKER',  color: 'var(--hud-green, #4ade80)', tooltip: 'Docker Tunnel(Cloudflare) 통해 Mac Ollama 사용 중' },
  local:   { label: 'LOCAL · OLLAMA', color: 'var(--hud-green, #4ade80)', tooltip: '로컬 Ollama 직접 사용' },
  ollama:  { label: 'OLLAMA',     color: 'var(--hud-green, #4ade80)', tooltip: 'Ollama 사용 중' },
  cloud:   { label: 'GEMINI · CLOUD', color: 'var(--hud-orange)', tooltip: 'Gemini 2.5 Pro 클라우드 모드 (Mac Ollama 미연결)' },
  offline: { label: 'OFFLINE',    color: 'var(--hud-red, #f87171)', tooltip: '백엔드 연결 실패' },
};

function classifyLLM(diag: Awaited<ReturnType<typeof fetchDiagnose>>): LLMState {
  const url = String(diag.ollama.meta?.base_url ?? '');
  const isTunnel = /trycloudflare|cfargotunnel/i.test(url);
  const isLocal = /localhost|127\.0\.0\.1/.test(url);
  if (diag.ollama.ok && isTunnel) return LLM_STATES.docker;
  if (diag.ollama.ok && isLocal)  return LLM_STATES.local;
  if (diag.ollama.ok)             return LLM_STATES.ollama;
  if (diag.gemini.ok)             return LLM_STATES.cloud;
  return LLM_STATES.offline;
}

export function TopBar() {
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const rightOpen = useUIStore((s) => s.rightPanelOpen);
  const toggleRight = useUIStore((s) => s.toggleRightPanel);

  const roleLabel = user
    ? `L${user.role_level} · ${user.role_name?.toUpperCase() ?? 'USER'}`
    : 'L0 · GUEST';

  // Plan v3.0 — LLM 상태 동적 표시 (mount + 30초 polling, 탭 비활성 시 멈춤)
  const [llm, setLlm] = useState<LLMState>(LLM_STATES.loading);
  useEffect(() => {
    let cancelled = false;
    const update = async () => {
      if (cancelled || (typeof document !== 'undefined' && document.hidden)) return;
      try {
        const d = await fetchDiagnose();
        if (!cancelled) setLlm(classifyLLM(d));
      } catch {
        if (!cancelled) setLlm(LLM_STATES.offline);
      }
    };
    void update();
    const id = window.setInterval(() => void update(), 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <header className="topbar">
      <span className="tb-brand">
        ◼ 아진산업 <b>AI v3.5</b>
      </span>
      <span className="tb-pipe">│</span>
      <span className="tb-seg">
        환경 <b>ON-PREMISE</b>
      </span>
      <span className="tb-pipe">·</span>
      <span className="tb-seg">
        인증 <b>{user ? 'JWT_ACTIVE' : 'JWT_INACTIVE'}</b>
      </span>
      <span className="tb-pipe">·</span>
      <span className="tb-seg" title={llm.tooltip}>
        LLM <b style={{ color: llm.color }}>{llm.label}</b>
        <span className="tb-dot" style={{ background: llm.color }} />
      </span>
      <span className="tb-grow" />
      <span className="tb-seg">
        RBAC <b style={{ color: 'var(--hud-primary)' }}>{roleLabel}</b>
      </span>
      <button className="tb-toggle" onClick={toggleRight} title="Toggle right panel">
        {rightOpen ? 'HIDE' : 'SYS'}
      </button>
      <button className="tb-toggle" onClick={() => clearAuth()} title="Sign out">
        LOGOUT
      </button>
    </header>
  );
}
