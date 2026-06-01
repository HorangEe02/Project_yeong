// ChangeAuditTimeline — 데이터 변경 이벤트 vertical timeline (PR-E5).
// 무한 스크롤 — IntersectionObserver, 50개 단위 (AuditTimeline.tsx 패턴 참고).
// 입력: AuditDashboardResponse.change_audit

import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeAuditRow } from '@api/admin';

interface Props {
  rows: ChangeAuditRow[];
  loading?: boolean;
}

const PAGE_SIZE = 50;

const ACTION_COLOR: Record<string, string> = {
  update: '#3b9eee',
  delete: '#d33',
  grant: '#5ec97c',
  revoke: '#e9c244',
  create: '#5ec97c',
};

function actionColor(action: string): string {
  return ACTION_COLOR[action.toLowerCase()] ?? '#888';
}

function methodBadgeColor(method: string): string {
  switch (method.toUpperCase()) {
    case 'DELETE': return '#d33';
    case 'POST': return '#5ec97c';
    case 'PUT':
    case 'PATCH': return '#e9c244';
    default: return '#888';
  }
}

function statusColor(code: number): string {
  if (code >= 500) return '#d33';
  if (code >= 400) return '#e9c244';
  if (code >= 300) return '#88c';
  return '#5ec97c';
}

/** actor 첫 글자 아바타 */
function Avatar({ actor }: { actor: string }) {
  const initial = (actor || '?')[0].toUpperCase();
  return (
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: 'var(--hud-primary)',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 700,
        fontSize: 13,
        flexShrink: 0,
      }}
    >
      {initial}
    </div>
  );
}

/** action chip */
function ActionChip({ action }: { action: string }) {
  const color = actionColor(action);
  return (
    <span
      style={{
        fontSize: 10,
        padding: '2px 7px',
        borderRadius: 4,
        background: `${color}22`,
        border: `1px solid ${color}`,
        color,
        fontFamily: 'var(--hud-font-mono)',
        letterSpacing: '0.04em',
        fontWeight: 700,
        textTransform: 'uppercase',
      }}
    >
      {action}
    </span>
  );
}

export function ChangeAuditTimeline({ rows, loading }: Props) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // IntersectionObserver — 하단 감시 → 페이지 추가 로드
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisibleCount((c) => Math.min(c + PAGE_SIZE, rows.length));
        }
      },
      { threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [rows.length]);

  // rows 변경 시 visibleCount 리셋
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [rows]);

  const visible = useMemo(() => rows.slice(0, visibleCount), [rows, visibleCount]);

  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">CHANGE AUDIT TIMELINE</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
            {loading
              ? '로딩 중…'
              : rows.length === 0
                ? '변경 이벤트 없음'
                : `${rows.length}건 · ${visibleCount < rows.length ? `${visibleCount}/${rows.length} 표시 중` : '전체'}`}
          </div>
        </div>
      </div>

      {!loading && rows.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--hud-text-dim)', fontSize: 13 }}>
          해당 기간 데이터 변경 이벤트가 없습니다.
        </div>
      )}

      {visible.length > 0 && (
        <div style={{ position: 'relative', paddingLeft: 20 }}>
          {/* 세로 타임라인 선 */}
          <div
            style={{
              position: 'absolute',
              left: 36,
              top: 0,
              bottom: 0,
              width: 2,
              background: 'var(--hud-line)',
            }}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {visible.map((row, i) => (
              <div
                key={`${row.timestamp}-${row.actor}-${i}`}
                style={{
                  display: 'flex',
                  gap: 14,
                  alignItems: 'flex-start',
                  padding: '10px 0',
                  position: 'relative',
                }}
              >
                {/* Avatar (타임라인 선 위) */}
                <div style={{ position: 'relative', zIndex: 1 }}>
                  <Avatar actor={row.actor_name || row.actor} />
                </div>

                {/* 내용 */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* 상단: actor + timestamp + status */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 5 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>
                      {row.actor_name || row.actor}
                    </span>
                    {row.actor_role && (
                      <span
                        style={{
                          fontSize: 10,
                          padding: '1px 6px',
                          borderRadius: 4,
                          border: '1px solid var(--hud-line)',
                          color: 'var(--hud-text-dim)',
                          fontFamily: 'var(--hud-font-mono)',
                        }}
                      >
                        {row.actor_role}
                      </span>
                    )}
                    <ActionChip action={row.action} />
                    <span
                      style={{
                        marginLeft: 'auto',
                        fontSize: 10,
                        color: 'var(--hud-text-dim)',
                        fontFamily: 'var(--hud-font-mono)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {row.timestamp.slice(0, 19).replace('T', ' ')}
                    </span>
                  </div>

                  {/* 엔드포인트 + 메서드 + 상태 코드 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
                    <span
                      style={{
                        fontSize: 10,
                        padding: '1px 6px',
                        borderRadius: 3,
                        background: `${methodBadgeColor(row.method)}22`,
                        border: `1px solid ${methodBadgeColor(row.method)}`,
                        color: methodBadgeColor(row.method),
                        fontFamily: 'var(--hud-font-mono)',
                        fontWeight: 700,
                      }}
                    >
                      {row.method}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: 'var(--hud-font-mono)',
                        color: 'var(--hud-text-dim)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: 400,
                      }}
                    >
                      {row.endpoint}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        padding: '1px 6px',
                        borderRadius: 3,
                        background: `${statusColor(row.status_code)}22`,
                        color: statusColor(row.status_code),
                        fontFamily: 'var(--hud-font-mono)',
                        fontWeight: 600,
                        border: `1px solid ${statusColor(row.status_code)}`,
                      }}
                    >
                      {row.status_code}
                    </span>
                  </div>

                  {/* detail (before/after diff 요약) */}
                  {row.detail && (
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--hud-text-dim)',
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid var(--hud-line)',
                        borderRadius: 4,
                        padding: '4px 8px',
                        fontFamily: 'var(--hud-font-mono)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        maxHeight: 80,
                        overflow: 'hidden',
                      }}
                    >
                      {row.detail.length > 240 ? `${row.detail.slice(0, 240)}…` : row.detail}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* IntersectionObserver sentinel */}
          <div ref={sentinelRef} style={{ height: 1 }} />
        </div>
      )}

      {visibleCount < rows.length && (
        <div style={{ textAlign: 'center', padding: '8px 0', fontSize: 12, color: 'var(--hud-text-dim)' }}>
          스크롤하여 더 불러오기 ({rows.length - visibleCount}건 남음)
        </div>
      )}
    </div>
  );
}
