// showcase.tsx — 전체 기능 화면 쇼케이스.
// 실제 구현된 각 기능 라우트를 동일 출처(iframe)로 불러와 다크/라이트 모드로 한 화면에 나열한다.
// 같은 출처라 로그인 쿠키가 그대로 전달되고, ?theme=light|dark 로 각 프레임 테마를 강제한다 (App.tsx 참조).
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useThemeStore } from '@store/theme';
import { useAuthStore } from '@store/auth';
import { guestLogin } from '@api/auth';

type ShowTheme = 'dark' | 'light';

interface FeatureScreen {
  code: string;
  path: string;
  ko: string;
  en: string;
}

const FEATURES: FeatureScreen[] = [
  { code: '◈', path: '/', ko: '대시보드', en: 'DASHBOARD' },
  { code: 'A', path: '/search', ko: '인원 검색', en: 'PEOPLE SEARCH' },
  { code: 'B', path: '/draft', ko: '문서 작성', en: 'DOCUMENT DRAFT' },
  { code: 'C', path: '/chat', ko: 'AI 도우미', en: 'AI ASSISTANT' },
  { code: 'C2', path: '/onboarding', ko: '신입 가이드', en: 'ONBOARDING' },
  { code: 'D', path: '/compliance', ko: '법규 모니터', en: 'COMPLIANCE' },
  { code: 'E', path: '/equipment', ko: '설비 AI', en: 'EQUIPMENT AI' },
  { code: 'F', path: '/management', ko: '인사 관리', en: 'MANAGEMENT' },
  { code: 'P', path: '/profile', ko: '프로필', en: 'PROFILE' },
];

// 데스크톱 폭으로 렌더한 뒤 thumbnail 크기로 축소 (모바일 레이아웃으로 떨어지지 않도록).
const FRAME_W = 1440;
const FRAME_H = 900;
const SCALE = 0.46;
const THUMB_W = Math.round(FRAME_W * SCALE);
const THUMB_H = Math.round(FRAME_H * SCALE);

export function Showcase() {
  const [theme, setTheme] = useState<ShowTheme>('dark');
  const resolved = useThemeStore((s) => s.resolved());
  const [ready, setReady] = useState<boolean>(() => Boolean(useAuthStore.getState().user));
  const [isGuest, setIsGuest] = useState(false);

  // 공개 접근(로그인 안 한 심사위원/팀원) → 게스트 읽기전용 세션을 자동 발급.
  // setSession 으로 persisted store 를 채워야 같은 출처 iframe 의 RequireAuth 가 통과한다.
  // 쿠키가 준비된 뒤에야 iframe 을 로드하도록 ready 로 게이트한다.
  useEffect(() => {
    if (useAuthStore.getState().user) {
      setReady(true);
      return;
    }
    let alive = true;
    guestLogin()
      .then((data) => {
        if (!alive) return;
        useAuthStore.getState().setSession({
          employee_id: data.employee_id,
          username: data.username,
          role_name: data.role_name,
          role_level: data.role_level,
          department: data.department,
          position: data.position,
        });
        setIsGuest(true);
        setReady(true);
      })
      .catch(() => {
        if (alive) setReady(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  // 쇼케이스 페이지 자체 chrome 도 선택 테마로 표시. 떠날 때 사용자 테마로 원복.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    return () => {
      document.documentElement.setAttribute('data-theme', resolved);
    };
  }, [theme, resolved]);

  return (
    <div
      data-screen-label="Showcase"
      style={{ minHeight: '100vh', background: 'var(--hud-bg)', color: 'var(--hud-text)', display: 'flex', flexDirection: 'column' }}
    >
      <header
        style={{
          position: 'sticky', top: 0, zIndex: 10,
          display: 'flex', alignItems: 'center', gap: 16, padding: '16px 28px',
          borderBottom: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
          background: 'color-mix(in oklab, var(--hud-surface) 72%, transparent)',
          backdropFilter: 'blur(20px) saturate(140%)',
          WebkitBackdropFilter: 'blur(20px) saturate(140%)',
        }}
      >
        <div>
          <div style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)' }}>
            AJIN AI ASSISTANT · SHOWCASE
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2 }}>전체 기능 화면</div>
          {isGuest && (
            <div style={{ marginTop: 4, fontSize: 11, color: 'var(--hud-primary)', fontWeight: 600 }}>
              게스트 읽기 전용 미리보기 · 로그인 없이 열람 중
            </div>
          )}
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'inline-flex', border: '1px solid var(--hud-border)', borderRadius: 999, overflow: 'hidden' }}>
          {(['dark', 'light'] as ShowTheme[]).map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              style={{
                padding: '8px 18px', border: 0, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                background: theme === t ? 'var(--hud-primary)' : 'transparent',
                color: theme === t ? 'var(--hud-bg)' : 'var(--hud-text-dim)',
                transition: 'background 120ms ease',
              }}
            >
              {t === 'dark' ? '다크 모드' : '라이트 모드'}
            </button>
          ))}
        </div>
        <Link
          to="/"
          style={{ padding: '8px 16px', borderRadius: 999, border: '1px solid var(--hud-border)', color: 'var(--hud-text)', textDecoration: 'none', fontSize: 12 }}
        >
          ← 앱으로
        </Link>
      </header>

      <div
        style={{
          padding: 28, display: 'grid',
          gridTemplateColumns: `repeat(auto-fill, minmax(${THUMB_W}px, 1fr))`,
          gap: 28, alignItems: 'start',
        }}
      >
        {FEATURES.map((f) => (
          <figure key={f.path} style={{ margin: 0 }}>
            <div
              style={{
                position: 'relative', width: THUMB_W, height: THUMB_H, maxWidth: '100%',
                borderRadius: 14, overflow: 'hidden',
                border: '1px solid color-mix(in oklab, var(--hud-primary) 28%, transparent)',
                boxShadow: '0 18px 50px -28px rgba(0,0,0,0.5)', background: 'var(--hud-surface)',
              }}
            >
              <iframe
                title={`${f.ko} · ${theme}`}
                src={ready ? `${f.path}?theme=${theme}` : 'about:blank'}
                loading="lazy"
                style={{ width: FRAME_W, height: FRAME_H, border: 0, transform: `scale(${SCALE})`, transformOrigin: 'top left' }}
              />
              <a
                href={f.path}
                target="_blank"
                rel="noreferrer"
                style={{
                  position: 'absolute', top: 8, right: 8, padding: '4px 10px', borderRadius: 999, fontSize: 11,
                  background: 'color-mix(in oklab, var(--hud-bg) 70%, transparent)', color: 'var(--hud-text)',
                  border: '1px solid var(--hud-border)', textDecoration: 'none',
                  backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)',
                }}
              >
                ↗ 새 탭
              </a>
            </div>
            <figcaption style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span style={{ fontFamily: 'var(--hud-font-mono)', fontSize: 12, color: 'var(--hud-primary)', fontWeight: 700 }}>{f.code}</span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{f.ko}</span>
              <span style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-dim)' }}>{f.en}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
