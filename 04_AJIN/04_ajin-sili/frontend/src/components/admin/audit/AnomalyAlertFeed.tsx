// AnomalyAlertFeed — 7-패턴 통합 알람 카드 리스트 (PR-E5).
// 입력: AnomalyFeedResponse.items (severity DESC 정렬됨).

import type {
  AnomalyFeedItem,
  AnomalyPattern,
  AnomalySeverity,
} from '@api/admin';

interface Props {
  items: AnomalyFeedItem[];
  loading?: boolean;
}

const PATTERN_LABEL: Record<AnomalyPattern, string> = {
  brute_force: '무차별 대입',
  unusual_hour: '비정상 시간 접근',
  inactive_access: '비활성 계정 접근',
  privilege_escalation: '권한 상승 시도',
  mass_export: '대량 다운로드',
  off_hours_export: '야간 export',
  deprecated_account_active: '퇴직 계정 활동',
};

const SEVERITY_CLASS: Record<AnomalySeverity, string> = {
  CRITICAL: 'crit',
  HIGH: 'crit',
  MEDIUM: 'warn',
  LOW: 'info',
};

function severityColor(s: AnomalySeverity): string {
  switch (s) {
    case 'CRITICAL': return '#d33';
    case 'HIGH': return '#e9c244';
    case 'MEDIUM': return '#3b9eee';
    case 'LOW': return '#888';
  }
}

export function AnomalyAlertFeed({ items, loading }: Props) {
  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">REAL-TIME ANOMALY FEED · 7 PATTERNS</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
            {loading
              ? '로딩 중…'
              : items.length === 0
                ? '이상 패턴 없음 (정상)'
                : `${items.length}건 · severity DESC 정렬`}
          </div>
        </div>
      </div>
      {items.length === 0 && !loading && (
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--hud-text-dim)' }}>
          ✓ 최근 관찰 기간 내 7-패턴 모두 정상
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((it, idx) => (
          <div
            key={`${it.pattern}-${it.employee_id}-${idx}`}
            className={`lg-sec ${SEVERITY_CLASS[it.severity]}`}
            style={{ borderLeft: `4px solid ${severityColor(it.severity)}` }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  className="lg-state-pill"
                  style={{ background: severityColor(it.severity), color: '#fff' }}
                >
                  {it.severity}
                </span>
                <span style={{
                  fontSize: 10, fontFamily: 'var(--hud-font-mono)',
                  letterSpacing: '0.05em', color: 'var(--hud-text-dim)',
                }}>
                  {it.pattern.toUpperCase().replace(/_/g, ' ')}
                </span>
              </div>
              <span style={{ fontSize: 10, color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)' }}>
                {it.timestamp ? it.timestamp.slice(0, 19).replace('T', ' ') : '—'}
              </span>
            </div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{it.title}</div>
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 4 }}>
              {it.description}
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 4,
                border: '1px solid var(--hud-line)', color: 'var(--hud-text-dim)',
              }}>
                {PATTERN_LABEL[it.pattern] || it.pattern}
              </span>
              {it.employee_id && (
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 4,
                  border: '1px solid var(--hud-line)',
                  fontFamily: 'var(--hud-font-mono)',
                }}>
                  사번: {it.employee_id}
                </span>
              )}
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="lg-btn sm ghost"
                onClick={() => {
                  // 향후 PR — 계정 잠금 / 감사 로그 drill-down 액션.
                  // 현재는 placeholder (UI 만 구비).
                  window.alert(`상세: ${JSON.stringify(it.details, null, 2).slice(0, 800)}`);
                }}
              >
                상세
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
