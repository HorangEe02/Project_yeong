// 2026-05-28 — 모바일 전용 테마 토글 chip group.
// 사용자 피드백: 모바일 페이지에 light/dark/auto 토글이 없어 일부 화면이 강제로
// 라이트(시스템관리)·다크(챗봇) 로 보임. 모든 모바일 페이지 헤더 우측에 본 컴포넌트
// 1개로 통일.
//
// 3-segment chip group. 작은 padding 으로 헤더에 inline 배치 가능.

import { Moon, Sparkles, Sun } from 'lucide-react';

import { useThemeStore, type ThemePreference } from '@store/theme';

const OPTIONS: { id: ThemePreference; icon: typeof Sun; label: string }[] = [
  { id: 'light', icon: Sun,      label: 'Light' },
  { id: 'auto',  icon: Sparkles, label: 'Auto' },
  { id: 'dark',  icon: Moon,     label: 'Dark' },
];

interface Props {
  /** compact=true 면 라벨 숨김 (아이콘만). 헤더 공간 작은 경우. */
  compact?: boolean;
}

export function MobileThemeToggle({ compact = false }: Props) {
  const preference = useThemeStore((s) => s.preference);
  const setPreference = useThemeStore((s) => s.setPreference);

  return (
    <div
      role="group"
      aria-label="테마 선택"
      style={{
        display: 'inline-flex',
        gap: 2,
        padding: 2,
        borderRadius: 999,
        background: 'rgba(127,127,127,0.12)',
        border: '1px solid rgba(127,127,127,0.20)',
      }}
    >
      {OPTIONS.map(({ id, icon: Icon, label }) => {
        const active = preference === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => setPreference(id)}
            aria-pressed={active}
            aria-label={label}
            title={label}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: compact ? 0 : 4,
              padding: compact ? '6px' : '5px 10px',
              minWidth: compact ? 28 : undefined,
              minHeight: 28,
              borderRadius: 999,
              border: 0,
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              background: active ? 'var(--aj-gold, #FCB132)' : 'transparent',
              color: active ? '#1A1004' : 'currentColor',
              opacity: active ? 1 : 0.7,
              transition: 'background 160ms ease-out, opacity 160ms ease-out',
            }}
          >
            <Icon size={12} aria-hidden />
            {!compact && <span>{label}</span>}
          </button>
        );
      })}
    </div>
  );
}
