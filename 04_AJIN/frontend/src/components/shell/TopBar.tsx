// TopBar — canonical uiux/web_app/TopBar.jsx 스타일 (TS port)
// Plan v3.0 — LLM 라벨 동적 표시 (TUNNEL / LOCAL / CLOUD / OFFLINE)

import { useEffect, useState } from 'react';
import { Menu } from 'lucide-react';
import { useAuthStore } from '@store/auth';
import { logout } from '@api/auth';
import { useUIStore } from '@store/ui';
import { useIsDesktop, useIsMobile } from '@hooks/useBreakpoint';
import { fetchDiagnose } from '@api/draft';
import { fetchLlmStatus, type LlmStatusResponse } from '@api/health';
import { NotificationBell } from './NotificationBell';
import { MobileThemeToggle } from '@components/uikit/MobileThemeToggle';

// PR #35 — 모바일 분기에서 페이지명 + 버전 텍스트 제거 (LLM Dynamic Island pill 과 overlap).
// PAGE_MAP / resolvePageLabel / useLocation 은 함께 제거 (dead code, tsc -b 빌드 모드에서 unused error).
// 향후 데스크탑 contextual TopBar 확장 시 별도 git history 에서 복구.

type LLMState = { label: string; color: string; tooltip: string };

const LLM_STATES: Record<string, LLMState> = {
  loading: { label: 'CHECKING…', color: 'var(--hud-text)', tooltip: '진단 호출 중' },
  tunnel:  { label: 'OLLAMA · TUNNEL', color: 'var(--hud-green, #4ade80)', tooltip: '보안 터널을 통해 Mac Ollama 사용 중' },
  local:   { label: 'LOCAL · OLLAMA', color: 'var(--hud-green, #4ade80)', tooltip: '로컬 Ollama 직접 사용' },
  ollama:  { label: 'OLLAMA',     color: 'var(--hud-green, #4ade80)', tooltip: 'Ollama 사용 중' },
  degraded:{ label: 'OLLAMA · CHECK', color: 'var(--hud-orange)', tooltip: 'Ollama primary 설정이나 도달성 확인 필요' },
  cloud:   { label: 'GEMINI · CLOUD', color: 'var(--hud-orange)', tooltip: 'Ollama 미가용으로 Gemini fallback 사용 중' },
  offline: { label: 'OFFLINE',    color: 'var(--hud-red, #f87171)', tooltip: '백엔드 연결 실패' },
  restricted: { label: 'LLM', color: 'var(--hud-text)', tooltip: '시스템 진단은 SYS_ADMIN 전용입니다' },
};

function classifyLlmStatus(status: LlmStatusResponse): LLMState {
  const primary = status.routing?.primary_provider;
  const url = String(status.ollama?.base_url ?? '');
  const isLocal = /localhost|127\.0\.0\.1|host\.docker\.internal/.test(url);
  const preferOllama = primary === 'ollama' || (primary === undefined && status.ollama?.ok);
  if (preferOllama && status.ollama?.ok && (status.tunnel_active || status.ollama.is_tunnel)) {
    return LLM_STATES.tunnel;
  }
  if (preferOllama && status.ollama?.ok && isLocal) {
    return LLM_STATES.local;
  }
  if (preferOllama && status.ollama?.ok) {
    return LLM_STATES.ollama;
  }
  if (status.ollama?.ok && primary !== 'gemini') {
    return LLM_STATES.ollama;
  }
  if (primary === 'ollama') {
    return LLM_STATES.degraded;
  }
  if (status.gemini?.api_key_present) {
    return LLM_STATES.cloud;
  }
  return LLM_STATES.offline;
}

function classifyDiagnoseFallback(diag: Awaited<ReturnType<typeof fetchDiagnose>>): LLMState {
  const url = String(diag.ollama.meta?.base_url ?? '');
  const isTunnel = /trycloudflare|cfargotunnel/i.test(url);
  const isLocal = /localhost|127\.0\.0\.1/.test(url);
  if (diag.ollama.ok && isTunnel) return LLM_STATES.tunnel;
  if (diag.ollama.ok && isLocal)  return LLM_STATES.local;
  if (diag.ollama.ok)             return LLM_STATES.ollama;
  if (diag.gemini.ok)             return LLM_STATES.cloud;
  return LLM_STATES.offline;
}

export function TopBar() {
  const user = useAuthStore((s) => s.user);
  const rightOpen = useUIStore((s) => s.rightPanelOpen);
  const toggleRight = useUIStore((s) => s.toggleRightPanel);
  const toggleMobileNav = useUIStore((s) => s.toggleMobileNav);
  const mobileNavOpen = useUIStore((s) => s.mobileNavOpen);
  // v4.4 — 데스크탑(>1024px) 외에는 햄버거 노출
  const isDesktop = useIsDesktop();
  // v4.4 — 모바일(≤640px)은 Design System v2 contextual TopBar
  const isMobile = useIsMobile();
  // PR #35 — 모바일 분기에서 pageLabel 텍스트 제거 (LLM pill overlap).
  // useLocation / resolvePageLabel / PAGE_LABELS 는 file-level declaration 으로 유지
  // (향후 데스크탑 contextual TopBar 확장 시 재사용 가능, tsc top-level 은 unused 미경고).

  const roleLabel = user
    ? `L${user.role_level} · ${user.role_name?.toUpperCase() ?? 'USER'}`
    : 'L0 · GUEST';

  // SYS 패널 / HIDE 토글은 관리자(L5+ SYS_ADMIN/HR_ADMIN) 전용.
  const isAdmin = (user?.role_level ?? 0) >= 5;

  // Plan v3.0 — LLM 상태 동적 표시 (mount + 30초 polling, 탭 비활성 시 멈춤)
  const [llm, setLlm] = useState<LLMState>(LLM_STATES.loading);
  useEffect(() => {
    if (!isAdmin) {
      setLlm(LLM_STATES.restricted);
      return;
    }

    let cancelled = false;
    const update = async () => {
      if (cancelled || (typeof document !== 'undefined' && document.hidden)) return;
      try {
        const status = await fetchLlmStatus();
        if (!cancelled) setLlm(classifyLlmStatus(status));
      } catch {
        try {
          const d = await fetchDiagnose();
          if (!cancelled) setLlm(classifyDiagnoseFallback(d));
        } catch {
          if (!cancelled) setLlm(LLM_STATES.offline);
        }
      }
    };
    void update();
    const id = window.setInterval(() => void update(), 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [isAdmin]);

  // v4.4 — 모바일 contextual TopBar: 햄버거 + 페이지명/부제 + 알림 + iOS Dynamic Island pill
  if (isMobile) {
    return (
      <header
        className="topbar topbar-mobile"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '0 var(--safe-x, 16px)',
          height: 'var(--top-bar-height, 56px)',
          borderBottom: '1px solid var(--hud-border)',
          background: 'var(--hud-surface)',
          position: 'sticky',
          top: 0,
          zIndex: 30,
        }}
      >
        {/* 2026-05-28 — Dynamic Island LLM pill 제거 (ThemeToggle 과 시각 overlap).
            LLM 상태는 햄버거 → MobileDrawer 헤더로 이전 (사용자 피드백). */}

        <button
          type="button"
          onClick={toggleMobileNav}
          aria-label="메뉴 열기"
          aria-expanded={mobileNavOpen}
          aria-controls="left-sidebar"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 44,
            height: 44,
            border: 'none',
            background: 'transparent',
            color: 'var(--hud-text)',
            cursor: 'pointer',
          }}
        >
          <Menu size={22} aria-hidden />
        </button>
        {/* 중앙 spacer — pageLabel + v3.5 텍스트 제거 (iOS Dynamic Island LLM pill 과 시각 overlap).
            LLM pill 이 position:fixed 로 상단 중앙에 위치, 햄버거↔알람 좌우 sticky 유지. */}
        <div style={{ flex: 1 }} aria-hidden />
        {/* 2026-05-28 — 모바일 헤더 우측에 다크/라이트 토글 (사용자 모바일 피드백).
            compact=true 로 아이콘만, NotificationBell 좌측 배치. */}
        <MobileThemeToggle compact />
        {user ? (
          <NotificationBell />
        ) : (
          <span style={{ width: 44 }} aria-hidden />
        )}
      </header>
    );
  }

  return (
    <header className="topbar">
      {!isDesktop && (
        <button
          type="button"
          className="tb-hamburger"
          onClick={toggleMobileNav}
          aria-label="메뉴 열기"
          aria-expanded={mobileNavOpen}
          aria-controls="left-sidebar"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 40,
            height: 40,
            marginRight: 6,
            border: '1px solid var(--hud-border)',
            background: 'transparent',
            color: 'var(--hud-text)',
            borderRadius: 4,
            cursor: 'pointer',
          }}
        >
          <Menu size={20} aria-hidden />
        </button>
      )}
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
      {user && <NotificationBell />}
      <span className="tb-seg">
        RBAC <b style={{ color: 'var(--hud-primary)' }}>{roleLabel}</b>
      </span>
      {isAdmin && (
        <button className="tb-toggle" onClick={toggleRight} title="Toggle right panel">
          {rightOpen ? 'HIDE' : 'SYS'}
        </button>
      )}
      <button className="tb-toggle" onClick={() => void logout()} title="Sign out">
        LOGOUT
      </button>
    </header>
  );
}
