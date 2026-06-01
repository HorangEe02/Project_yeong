// BottomTabBar — 모바일(≤640px) 하단 탭 네비게이션 (v4.5 동적).
//
// v4.5: 페르소나 매트릭스 + 사용자 override prefs (서버 user_prefs).
// 구조: [DRAFT(B)] [CHAT(C)] [HOME] [동적1] [동적2]
// 잠긴 모듈은 표시 안 됨 (resolveMobileTabs 가 RBAC 통과만 반환).
// 5탭 미달 시 마지막 슬롯에 "더보기" 안내 → 햄버거 Drawer 열림.

import { useMemo } from 'react';
import { Menu as MenuIcon } from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { useAuthStore } from '@store/auth';
import { useUIStore } from '@store/ui';
import { useMobileTabPrefs } from '@hooks/useMobileTabPrefs';
import { resolveMobileTabs } from '@components/shell/mobileTabs';

export function BottomTabBar() {
  const user = useAuthStore((s) => s.user);
  const prefs = useMobileTabPrefs();
  const toggleMobileNav = useUIStore((s) => s.toggleMobileNav);

  const { tabs, emptySlots } = useMemo(
    () => resolveMobileTabs(user, { override: prefs.override, customSlots: prefs.customSlots }),
    [user, prefs.override, prefs.customSlots],
  );

  // 5번째 슬롯 — 빈 슬롯이 있으면 More 자리. 슬롯 = tabs.length + 1 (더보기 차지 1)
  const showMore = emptySlots > 0;
  const totalCols = Math.min(5, tabs.length + (showMore ? 1 : 0));

  return (
    <nav
      role="tablist"
      aria-label="모바일 핵심 메뉴"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        display: 'grid',
        gridTemplateColumns: `repeat(${totalCols}, 1fr)`,
        height: 'var(--bottom-nav-h, 60px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        borderTop: '1px solid var(--hud-border)',
        backdropFilter: 'blur(24px) saturate(140%)',
        WebkitBackdropFilter: 'blur(24px) saturate(140%)',
        background: 'color-mix(in oklab, var(--hud-surface) 82%, transparent)',
        fontFamily: 'var(--hud-font)',
      }}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <NavLink
            key={tab.path}
            to={tab.path}
            end={tab.path === '/'}
            role="tab"
            aria-label={`${tab.labelEn} · ${tab.labelKo}`}
            style={({ isActive }) => ({
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              color: isActive ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
              textDecoration: 'none',
              transition: 'color 180ms ease-out',
              minHeight: 44,
              padding: '6px 4px',
            })}
          >
            {({ isActive }) => (
              <>
                <Icon size={20} strokeWidth={isActive ? 2 : 1.5} aria-hidden />
                <span style={{ fontSize: 11, fontWeight: isActive ? 700 : 500 }}>
                  {tab.labelKo}
                </span>
                <span style={{ fontSize: 8, letterSpacing: '0.08em', opacity: 0.7 }}>
                  {tab.labelEn}
                </span>
              </>
            )}
          </NavLink>
        );
      })}
      {showMore && (
        <button
          type="button"
          role="tab"
          aria-label="더 많은 메뉴 열기"
          onClick={toggleMobileNav}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
            background: 'transparent',
            border: 'none',
            color: 'var(--hud-text-dim)',
            cursor: 'pointer',
            minHeight: 44,
            padding: '6px 4px',
            fontFamily: 'var(--hud-font)',
          }}
        >
          <MenuIcon size={20} strokeWidth={1.5} aria-hidden />
          <span style={{ fontSize: 11, fontWeight: 500 }}>더보기</span>
          <span style={{ fontSize: 8, letterSpacing: '0.08em', opacity: 0.7 }}>MORE</span>
        </button>
      )}
    </nav>
  );
}
