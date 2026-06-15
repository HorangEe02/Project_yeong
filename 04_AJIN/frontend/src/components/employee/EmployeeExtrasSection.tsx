// EmployeeExtrasSection — Module A · 인사 부가 정보 권한 분기 표시.
// 디자인 시스템 v3.5: lg-eyebrow / lg-state-pill / lg-pill + 12·16 radii.
//   - 권한 부족(DENIED) → 안내 박스만 (state-pill warn)
//   - PARTIAL → 직속부하만
//   - FULL → 모두

import { useEffect, useState } from 'react';
import { Briefcase, Users, ClipboardCheck, Lock } from 'lucide-react';
import {
  fetchEmployeeExtras,
  type EmployeeExtras,
} from '@api/employeeExtras';

interface Props {
  employeeId: string;
}

const BOX: React.CSSProperties = {
  border: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
  borderRadius: 12,
  padding: 12,
  background: 'color-mix(in oklab, var(--hud-surface) 40%, transparent)',
};

function fmtKrw(v: number): string {
  if (!v) return '0원';
  return v.toLocaleString('ko-KR') + '원';
}

export function EmployeeExtrasSection({ employeeId }: Props) {
  const [extras, setExtras] = useState<EmployeeExtras | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    fetchEmployeeExtras(employeeId)
      .then((d) => {
        if (!cancelled) setExtras(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : '로드 실패');
      })
      .finally(() => !cancelled && setBusy(false));
    return () => {
      cancelled = true;
    };
  }, [employeeId]);

  if (busy) {
    return (
      <div
        style={{
          padding: 14,
          fontSize: 12,
          textAlign: 'center',
          color: 'var(--hud-text-dim)',
        }}
      >
        부가 정보 불러오는 중…
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          ...BOX,
          borderColor:
            'color-mix(in oklab, var(--hud-red, #C0392B) 50%, transparent)',
          color: 'var(--hud-red, #C0392B)',
          fontSize: 12,
        }}
      >
        부가 정보 로드 실패 — {error}
      </div>
    );
  }

  if (!extras) return null;

  if (extras.permission === 'DENIED') {
    return (
      <div
        style={{
          ...BOX,
          borderStyle: 'dashed',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
        }}
      >
        <Lock
          size={14}
          strokeWidth={2}
          style={{
            marginTop: 2,
            color: 'var(--hud-orange, #E8A317)',
            flexShrink: 0,
          }}
        />
        <div style={{ flex: 1 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 6,
            }}
          >
            <span className="lg-eyebrow" style={{ marginBottom: 0 }}>
              EXTRAS · 권한 부족
            </span>
            <span className="lg-state-pill warn">RESTRICTED</span>
          </div>
          <div
            style={{
              fontSize: 12,
              lineHeight: 1.7,
              color: 'var(--hud-text-dim)',
            }}
          >
            {extras.reason ||
              '권한이 부족하여 부가 정보를 표시할 수 없습니다.'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <span className="lg-eyebrow" style={{ marginBottom: 0 }}>
          EXTRAS · 부가 정보
        </span>
        <span
          className={`lg-state-pill ${extras.permission === 'FULL' ? 'ok' : 'warn'}`}
        >
          {extras.permission === 'FULL' ? 'FULL · 전체' : 'PARTIAL · 부분'}
        </span>
      </div>

      {/* APPROVALS — FULL 만 */}
      {extras.permission === 'FULL' && extras.approvals && (
        <div style={BOX}>
          <div
            className="lg-eyebrow"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <ClipboardCheck size={12} strokeWidth={2} /> 결재 현황 (최근 30일)
          </div>
          <div
            style={{
              display: 'flex',
              gap: 16,
              fontSize: 13,
              color: 'var(--hud-text)',
            }}
          >
            <span>
              대기 <b style={{ color: 'var(--hud-orange, #E8A317)' }}>{extras.approvals.pending}</b>
            </span>
            <span>
              승인 <b style={{ color: 'var(--hud-green, #2D8A4E)' }}>{extras.approvals.approved_30d}</b>
            </span>
            <span>
              반려 <b style={{ color: 'var(--hud-red, #C0392B)' }}>{extras.approvals.rejected_30d}</b>
            </span>
          </div>
        </div>
      )}

      {/* TRIPS — FULL 만 */}
      {extras.permission === 'FULL' && extras.trips.length > 0 && (
        <div>
          <div
            className="lg-eyebrow"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <Briefcase size={12} strokeWidth={2} /> 출장 이력 ({extras.trips.length})
          </div>
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            {extras.trips.map((t) => (
              <li
                key={t.trip_id}
                style={{ ...BOX, padding: 10, fontSize: 12 }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 8,
                  }}
                >
                  <b style={{ color: 'var(--hud-text)' }}>{t.destination}</b>
                  <span
                    className="mono"
                    style={{
                      fontFamily: 'var(--hud-font-mono)',
                      fontSize: 11,
                      letterSpacing: '0.06em',
                      color: 'var(--hud-text-dim)',
                    }}
                  >
                    {t.started_on} ~ {t.ended_on}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 11,
                    marginTop: 4,
                    color: 'var(--hud-text-dim)',
                  }}
                >
                  {t.purpose} · {fmtKrw(t.cost_krw)}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* DIRECT REPORTS — FULL / PARTIAL */}
      {extras.direct_reports.length > 0 && (
        <div>
          <div
            className="lg-eyebrow"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <Users size={12} strokeWidth={2} /> 직속 부하 ({extras.direct_reports.length})
          </div>
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            {extras.direct_reports.map((r) => (
              <li
                key={r.employee_id}
                style={{
                  ...BOX,
                  padding: '8px 12px',
                  borderStyle: 'dashed',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                  fontSize: 12,
                }}
              >
                <span>
                  <b style={{ color: 'var(--hud-text)' }}>{r.name}</b>{' '}
                  <span style={{ color: 'var(--hud-text-dim)' }}>· {r.position}</span>
                </span>
                <span style={{ color: 'var(--hud-text-dim)' }}>{r.department}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
