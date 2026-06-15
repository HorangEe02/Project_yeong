// v4.7 Feature E Phase 1 — 외부 IdP 로그인 버튼
//
// 백엔드의 GET /auth/idp/capabilities 를 호출해 활성 IdP 만 버튼으로 표시.
// IDP_PROVIDER=disabled 인 환경에서는 컴포넌트 자체가 null 반환 → UI 무영향.

import { useEffect, useState } from 'react';
import { fetchIdPCapabilities } from '@api/auth';

const PROVIDER_META: Record<string, { label: string; logo?: string }> = {
  oidc: { label: 'SSO 로그인 (OIDC)' },
  saml: { label: 'SSO 로그인 (SAML)' },
};

interface Props {
  /** 로그인 후 돌아갈 경로 (기본 /) */
  nextUrl?: string;
}

export function IdPLoginButtons({ nextUrl = '/' }: Props) {
  const [providers, setProviders] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchIdPCapabilities().then((r) => {
      if (!cancelled) setProviders(r.providers);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // 로딩 또는 비활성 — UI 무영향
  if (providers === null || providers.length === 0) return null;

  const redirectProviders = providers.filter((p) => p === 'oidc' || p === 'saml');
  if (redirectProviders.length === 0) return null;

  const safeNext = nextUrl.startsWith('/') && !nextUrl.startsWith('//') ? nextUrl : '/';

  // baseURL 는 client.ts 에서 /api 보장. 백엔드 redirect 경로가 절대 URL 이어야
  // 하므로 window.location.origin 기반으로 조립.
  const makeUrl = (provider: string) =>
    `/api/auth/idp/${provider}/login?next_url=${encodeURIComponent(safeNext)}`;

  return (
    <div style={{ marginTop: 16 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          margin: '12px 0',
          color: 'var(--hud-text-dim)',
          fontSize: 11,
          letterSpacing: '0.1em',
        }}
      >
        <div style={{ flex: 1, height: 1, background: 'var(--hud-border, #2a2a2a)' }} />
        <span>OR</span>
        <div style={{ flex: 1, height: 1, background: 'var(--hud-border, #2a2a2a)' }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {redirectProviders.map((p) => {
          const meta = PROVIDER_META[p] ?? { label: `${p.toUpperCase()} 로그인` };
          return (
            <a
              key={p}
              href={makeUrl(p)}
              className="btn ghost"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '10px 14px',
                textDecoration: 'none',
                fontSize: 13,
                letterSpacing: '0.03em',
              }}
              data-testid={`idp-login-${p}`}
            >
              {meta.label}
            </a>
          );
        })}
      </div>
    </div>
  );
}
