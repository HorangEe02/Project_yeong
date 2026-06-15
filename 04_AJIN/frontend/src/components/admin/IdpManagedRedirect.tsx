// IdpManagedRedirect — PR-E4 (6→3 탭 통합).
// 사용자 라이프사이클(추가/수정/삭제)이 사내 IdP 로 위임되었음을 안내.
// IDP_PROVIDER 가 OIDC/SAML 활성일 때 콘솔 링크, 그 외엔 관리자 문의 fallback.

import { useEffect, useState } from 'react';
import { fetchIdPCapabilities } from '@api/auth';

interface Props {
  /** 페이지 풀스크린 모드(default true). false 면 카드 내부 안내로만 사용. */
  fullPage?: boolean;
}

export function IdpManagedRedirect({ fullPage = true }: Props) {
  const [providers, setProviders] = useState<string[] | null>(null);
  const consoleUrl =
    (import.meta.env.VITE_IDP_CONSOLE_URL as string | undefined)?.trim() || '';

  useEffect(() => {
    let cancelled = false;
    fetchIdPCapabilities().then((r) => {
      if (!cancelled) setProviders(r.providers);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const idpActive = (providers?.length ?? 0) > 0;
  const showConsoleLink = idpActive && !!consoleUrl;

  const card = (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">IDP MANAGED · 사용자는 사내 IdP에서 관리됩니다</div>
          <h2 style={{ marginTop: 8, fontSize: 18, fontWeight: 700 }}>
            사용자 추가·수정·삭제는 IT전략팀에 요청하세요
          </h2>
          <p style={{ marginTop: 10, fontSize: 13, color: 'var(--hud-text-dim)', lineHeight: 1.55 }}>
            v4.9 부터 사용자 라이프사이클은 사내 IdP(LDAP / SAML)에서 일원화되어 관리됩니다.
            <br />
            AJIN AI 콘솔에서는 캐시된 사용자 목록과 권한 매핑만 조회할 수 있으며,
            신규 입사·전배·퇴직은 IdP 관리 시스템에서 처리됩니다.
          </p>
        </div>
      </div>

      <div style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {showConsoleLink ? (
          <a
            href={consoleUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="lg-btn primary"
          >
            IdP 콘솔 열기 ↗
          </a>
        ) : (
          <span className="lg-state-pill warn">
            {idpActive ? 'IdP 콘솔 URL 미설정 — 관리자에게 문의' : '관리자에게 문의 (IT전략팀)'}
          </span>
        )}
        {providers !== null && (
          <span className="lg-state-pill" style={{ alignSelf: 'center' }}>
            활성 IdP: {idpActive ? providers!.join(' · ').toUpperCase() : 'DISABLED'}
          </span>
        )}
      </div>
    </div>
  );

  if (!fullPage) return card;

  return (
    <div className="page lg-page" data-screen-label="G · IdP Managed Redirect">
      <div className="lg-card-h" style={{ marginBottom: 18 }}>
        <div>
          <div className="lg-pill">FEATURE G · ADMIN CONSOLE</div>
          <h1 style={{ marginTop: 6, fontSize: 24, fontWeight: 700, letterSpacing: '-0.01em' }}>
            사용자 관리는 사내 IdP로 이관되었습니다
          </h1>
        </div>
      </div>
      {card}
    </div>
  );
}

export default IdpManagedRedirect;
