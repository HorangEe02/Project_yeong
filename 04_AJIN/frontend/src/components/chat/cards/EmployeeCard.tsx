// v3.3 Phase F — EmployeeCard: 인사 검색 결과 (가시성 매트릭스 적용).
// 비인증 시 auth_required=true → 로그인 안내 카드로 폴백.

import type { EmployeeCardPayload, EmployeeItem } from './types';

interface Props {
  payload: EmployeeCardPayload;
  onLoginClick?: () => void; // 비인증 시 /login 으로 navigate
}

function visibilityChip(level: 'FULL' | 'PARTIAL') {
  const isFull = level === 'FULL';
  const color = isFull ? 'var(--hud-green)' : 'var(--hud-orange)';
  return (
    <span
      style={{
        padding: '2px 8px',
        borderRadius: 999,
        fontFamily: 'var(--hud-font-mono)',
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: '0.08em',
        color,
        background: `color-mix(in oklab, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in oklab, ${color} 30%, transparent)`,
      }}
      title={isFull ? '같은 부서 — 전체 정보' : '타 부서 — 일부 정보 마스킹'}
    >
      {level}
    </span>
  );
}

function EmployeeRow({ item }: { item: EmployeeItem }) {
  return (
    <li
      style={{
        padding: '10px 12px',
        borderRadius: 10,
        background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
        border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13, color: 'var(--hud-text)' }}>{item.name}</strong>
        <span className="lg-meta">{item.department} · {item.position}</span>
        {visibilityChip(item.visibility)}
      </div>
      <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {item.contact.extension && <span>내선 {item.contact.extension}</span>}
        {item.contact.email && <span>{item.contact.email}</span>}
        {item.contact.phone && <span>{item.contact.phone}</span>}
        {!item.contact.extension && !item.contact.email && !item.contact.phone && (
          <span style={{ opacity: 0.6 }}>연락처 비공개</span>
        )}
      </div>
    </li>
  );
}

export function EmployeeCard({ payload, onLoginClick }: Props) {
  // 비인증 폴백
  if (payload.auth_required) {
    return (
      <div className="lg-action-card" data-kind="employee">
        <div className="lg-eyebrow">PEOPLE · LOGIN REQUIRED</div>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--hud-text-dim)', lineHeight: 1.6 }}>
          인사 검색은 로그인 후 이용할 수 있습니다.
          <br />
          가시성 매트릭스에 따라 같은 부서는 전체 정보, 타 부서는 일부 마스킹된 결과를 노출합니다.
        </p>
        <button type="button" className="lg-btn sm" onClick={onLoginClick}>
          로그인 →
        </button>
      </div>
    );
  }

  const items = payload.items ?? [];

  if (items.length === 0) {
    return (
      <div className="lg-action-card" data-kind="employee">
        <div className="lg-eyebrow">PEOPLE · 0건</div>
        <div style={{ fontSize: 13, color: 'var(--hud-text-dim)' }}>
          "{payload.query}" 검색 결과가 없습니다.
        </div>
      </div>
    );
  }

  return (
    <div className="lg-action-card" data-kind="employee">
      <div className="lg-eyebrow">
        PEOPLE · {payload.total}건
        {payload.truncated && payload.total > items.length ? (
          <span className="lg-meta" style={{ marginLeft: 6 }}>
            (상위 {items.length}건 표시)
          </span>
        ) : null}{' '}
        <span className="lg-meta">{payload.query}</span>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((item, idx) => (
          <EmployeeRow key={`${item.name}-${idx}`} item={item} />
        ))}
      </ul>
    </div>
  );
}
