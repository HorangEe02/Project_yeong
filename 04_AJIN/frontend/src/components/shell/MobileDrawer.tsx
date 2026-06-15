// MobileDrawer — 모바일(≤640px) 좌측 메뉴 off-canvas drawer.
//
// UI_REDESIGN_PLAN.md §3 Phase 2 (D-9 머지 목표). v3.5 디자인 시스템 모바일 shell.
//
// 동작:
//   - useUIStore.mobileNavOpen 이 true 일 때 from-left slide-in
//   - 배경 scrim 클릭 / Esc / 메뉴 항목 클릭 시 close
//   - Liquid Glass + 2px corner (Bottom Nav 와 동일 미학)
//   - 5탭 Bottom Nav 와 중복되지만 RBAC 통과한 모든 모듈 + Profile + Logout 노출
//
// 5 Bottom Nav 탭이 노출하지 않는 모듈 (Draft, Onboarding, Equipment, Admin) 접근 통로.

import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LogOut, X } from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { useUIStore } from '@store/ui';
import { isMenuVisible } from '@lib/rbac';
import { TAB_META } from '@components/shell/mobileTabs';
import { fetchLlmStatus, type LlmStatusResponse } from '@api/health';

// 2026-05-28 — Dynamic Island LLM pill 을 TopBar 모바일에서 제거 (ThemeToggle 과
// 시각 overlap) 하고 본 drawer 헤더로 이전. TopBar.tsx 의 classifyLlmStatus 와
// 같은 우선순위 규칙을 단순화한 derive 함수 — 정확한 분류 (tunnel/local/cloud)
// 대신 OLLAMA·OK / GEMINI·CLOUD / OFFLINE / CHECK 3-4 카테고리만 표시.
function deriveLlmLabel(status: LlmStatusResponse | null): { label: string; color: string } {
  if (!status) return { label: 'CHECKING…', color: 'rgba(127,127,127,0.65)' };
  const primary = status.routing?.primary_provider;
  const ollamaOk = status.ollama?.ok;
  const tunnel = status.tunnel_active || status.ollama?.is_tunnel;
  const url = String(status.ollama?.base_url ?? '');
  const isLocal = /localhost|127\.0\.0\.1|host\.docker\.internal/.test(url);
  if (ollamaOk && (primary === 'ollama' || primary === undefined)) {
    if (tunnel) return { label: 'OLLAMA · TUNNEL', color: '#4ade80' };
    if (isLocal) return { label: 'LOCAL · OLLAMA', color: '#4ade80' };
    return { label: 'OLLAMA', color: '#4ade80' };
  }
  if (primary === 'ollama' && !ollamaOk) {
    return { label: 'OLLAMA · CHECK', color: '#FCB132' };
  }
  if (status.gemini?.api_key_present) {
    return { label: 'GEMINI · CLOUD', color: '#6EB1FC' };
  }
  return { label: 'OFFLINE', color: '#f87171' };
}

const ORDER = [
  'dashboard',
  'search',
  'draft',
  'chat',
  'onboarding',
  'compliance',
  'equipment',
  'admin',
  'profile',
] as const;

export function MobileDrawer() {
  const open = useUIStore((s) => s.mobileNavOpen);
  const setOpen = useUIStore((s) => s.setMobileNavOpen);
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const navigate = useNavigate();

  // 2026-05-28 — LLM 상태 (TopBar 모바일 pill 에서 이전).
  // drawer 열린 시점에 1회 fetch — drawer 가 잠깐 열려있는 UX 라 polling 불필요.
  const [llmStatus, setLlmStatus] = useState<LlmStatusResponse | null>(null);
  useEffect(() => {
    if (!open) return;
    let alive = true;
    fetchLlmStatus()
      .then((s) => { if (alive) setLlmStatus(s); })
      .catch(() => { if (alive) setLlmStatus(null); });
    return () => { alive = false; };
  }, [open]);
  const llm = deriveLlmLabel(llmStatus);

  // Esc 키 닫기 + 첫 진입 시 body scroll lock
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, setOpen]);

  if (!open) return null;

  const visibleSlugs = ORDER.filter((slug) => isMenuVisible(slug, user));

  const handleClose = () => setOpen(false);
  const handleLogout = () => {
    clearAuth();
    setOpen(false);
    navigate('/login');
  };

  return (
    <>
      {/* Scrim — 클릭 시 닫힘 */}
      <div
        role="presentation"
        onClick={handleClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          zIndex: 60,
          animation: 'fade-in 200ms ease-out',
        }}
      />
      {/* Drawer panel */}
      <aside
        role="dialog"
        aria-label="모바일 메뉴"
        aria-modal="true"
        style={{
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          width: 'min(82vw, 320px)',
          zIndex: 70,
          background: 'color-mix(in oklab, var(--hud-surface) 92%, transparent)',
          backdropFilter: 'blur(28px) saturate(150%)',
          WebkitBackdropFilter: 'blur(28px) saturate(150%)',
          borderRight: '1px solid var(--hud-border)',
          display: 'flex',
          flexDirection: 'column',
          padding: '16px 14px calc(env(safe-area-inset-bottom, 0px) + 16px)',
          fontFamily: 'var(--hud-font)',
          animation: 'drawer-slide-in 240ms ease-out',
        }}
      >
        {/* 헤더 — brand + 닫기 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: '1px solid var(--hud-border)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span
              className="mono"
              style={{
                fontSize: 10,
                letterSpacing: '0.1em',
                color: 'var(--hud-text-dim)',
                textTransform: 'uppercase',
              }}
            >
              AJIN AI ASSISTANT
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--hud-text)' }}>
              v3.5 · {user?.username ?? '익명'}
            </span>
            {/* 2026-05-28 — Dynamic Island LLM pill 을 본 drawer 헤더로 이전 */}
            <span
              title={llm.label}
              style={{
                marginTop: 6,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                width: 'fit-content',
                padding: '4px 9px',
                borderRadius: 999,
                background: 'rgba(0,0,0,0.05)',
                border: '1px solid rgba(127,127,127,0.20)',
                fontSize: 10,
                letterSpacing: '0.08em',
                fontFamily: 'var(--hud-font-mono, ui-monospace)',
                color: 'var(--hud-text)',
                textTransform: 'uppercase',
                fontWeight: 600,
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: llm.color,
                  boxShadow: `0 0 6px ${llm.color}`,
                }}
              />
              {llm.label}
            </span>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="메뉴 닫기"
            style={{
              width: 44,
              height: 44,
              minHeight: 44,
              background: 'transparent',
              border: '1px solid var(--hud-border)',
              borderRadius: 'var(--card-radius, 2px)',
              color: 'var(--hud-text)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={20} strokeWidth={1.5} />
          </button>
        </div>

        {/* 메뉴 list */}
        <nav
          aria-label="모듈 메뉴"
          style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, overflowY: 'auto' }}
        >
          {visibleSlugs.map((slug) => {
            const meta = TAB_META[slug];
            if (!meta) return null;
            const Icon = meta.icon;
            return (
              <NavLink
                key={slug}
                to={meta.path}
                end={meta.path === '/'}
                onClick={handleClose}
                style={({ isActive }) => ({
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  minHeight: 44,
                  padding: '10px 12px',
                  borderRadius: 'var(--card-radius, 2px)',
                  background: isActive
                    ? 'color-mix(in oklab, var(--hud-primary) 12%, transparent)'
                    : 'transparent',
                  borderLeft: `3px solid ${
                    isActive ? 'var(--hud-primary)' : 'transparent'
                  }`,
                  color: isActive ? 'var(--hud-primary)' : 'var(--hud-text)',
                  textDecoration: 'none',
                  fontSize: 14,
                  fontWeight: isActive ? 600 : 500,
                  transition: 'background 180ms ease-out, color 180ms ease-out',
                })}
              >
                <Icon size={18} strokeWidth={1.5} aria-hidden />
                <span style={{ flex: 1 }}>{meta.labelKo}</span>
                <span
                  className="mono"
                  style={{
                    fontSize: 9,
                    letterSpacing: '0.08em',
                    color: 'var(--hud-text-dim)',
                    textTransform: 'uppercase',
                  }}
                >
                  {meta.labelEn}
                </span>
              </NavLink>
            );
          })}
        </nav>

        {/* 데모 · 자료 — 전체 화면 쇼케이스 / 백엔드 기술 설명 바로가기 */}
        <div
          style={{
            paddingTop: 12,
            marginTop: 12,
            borderTop: '1px solid var(--hud-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {[
            { to: '/showcase', ko: '전체 화면 쇼케이스', en: 'SHOWCASE' },
            { to: '/tech', ko: '백엔드 기술 설명', en: 'TECH' },
          ].map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              onClick={handleClose}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                minHeight: 44,
                padding: '10px 12px',
                borderRadius: 'var(--card-radius, 2px)',
                background: isActive
                  ? 'color-mix(in oklab, var(--hud-primary) 12%, transparent)'
                  : 'transparent',
                color: isActive ? 'var(--hud-primary)' : 'var(--hud-text)',
                textDecoration: 'none',
                fontSize: 14,
                fontWeight: 500,
              })}
            >
              <span style={{ flex: 1 }}>{it.ko}</span>
              <span
                className="mono"
                style={{ fontSize: 9, letterSpacing: '0.08em', color: 'var(--hud-text-dim)', textTransform: 'uppercase' }}
              >
                {it.en}
              </span>
            </NavLink>
          ))}
        </div>

        {/* 하단 — Logout */}
        <div
          style={{
            paddingTop: 12,
            marginTop: 12,
            borderTop: '1px solid var(--hud-border)',
          }}
        >
          <button
            type="button"
            onClick={handleLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              width: '100%',
              minHeight: 44,
              padding: '10px 12px',
              background: 'transparent',
              border: '1px solid var(--hud-border)',
              borderRadius: 'var(--card-radius, 2px)',
              color: 'var(--hud-text)',
              fontFamily: 'var(--hud-font)',
              fontSize: 13,
              cursor: 'pointer',
              transition: 'border-color 200ms ease-out, color 200ms ease-out',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--hud-red, #C0392B)';
              e.currentTarget.style.color = 'var(--hud-red, #C0392B)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--hud-border)';
              e.currentTarget.style.color = 'var(--hud-text)';
            }}
          >
            <LogOut size={16} strokeWidth={1.5} aria-hidden />
            <span style={{ flex: 1, textAlign: 'left' }}>로그아웃</span>
            <span
              className="mono"
              style={{ fontSize: 9, letterSpacing: '0.08em', color: 'var(--hud-text-dim)' }}
            >
              LOGOUT
            </span>
          </button>
        </div>
      </aside>
      <style>{`
        @keyframes drawer-slide-in {
          from { transform: translateX(-100%); opacity: 0.6; }
          to   { transform: translateX(0);     opacity: 1; }
        }
      `}</style>
    </>
  );
}
