// Tab6to3Notice — PR-E4 첫 진입 1회 안내 모달.
// 6 탭(사용자/아이디 생성/AI 활용 분석/검색 분석/...) → 3 탭(계정 위임/보안 알림/시스템 헬스).
// localStorage 키로 1회만 노출. "다시 보지 않기" 클릭 시 저장.

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'ajin-admin-v4.9-tab-notice-seen';

export function Tab6to3Notice() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) !== 'true') {
        setOpen(true);
      }
    } catch {
      // localStorage 미가용 환경 — 노출하지 않음(반복 노출 방지가 더 중요)
    }
  }, []);

  if (!open) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      // 저장 실패해도 세션 내에서는 닫음
    }
    setOpen(false);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="tab6to3-notice-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={dismiss}
    >
      <div
        className="lg-card"
        style={{ maxWidth: 560, width: '100%', cursor: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="lg-pill">ADMIN CONSOLE · v4.9 NOTICE</div>
        <h2
          id="tab6to3-notice-title"
          style={{ marginTop: 10, fontSize: 18, fontWeight: 700, letterSpacing: '-0.01em' }}
        >
          관리자 콘솔이 3 탭으로 단순화되었습니다
        </h2>
        <p style={{ marginTop: 8, fontSize: 13, color: 'var(--hud-text-dim)', lineHeight: 1.55 }}>
          기존 6 탭은 다음과 같이 이관되었습니다. 기능 자체는 모두 유지됩니다.
        </p>

        <ul style={{ marginTop: 12, paddingLeft: 18, fontSize: 13, lineHeight: 1.7 }}>
          <li>
            <b>사용자 추가</b> → 사내 IdP (LDAP/SAML) — IT전략팀 요청
          </li>
          <li>
            <b>사용자 목록</b> → 계정 위임 탭 (캐시 기반 조회)
          </li>
          <li>
            <b>검색 분석</b> → <code>/search/analytics</code>
          </li>
          <li>
            <b>사용 분석 (HR)</b> → 설비 → KPI 대시보드 (<code>/equipment?cat=stats</code>)
          </li>
        </ul>

        <div
          style={{
            marginTop: 16,
            display: 'flex',
            gap: 8,
            justifyContent: 'flex-end',
          }}
        >
          <button type="button" className="lg-btn primary" onClick={dismiss}>
            다시 보지 않기
          </button>
        </div>
      </div>
    </div>
  );
}

export default Tab6to3Notice;
