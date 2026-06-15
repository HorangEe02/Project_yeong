// VersionTimeline — Module B · 버전 관리 타임라인.
// B4 v4.0: 작성자별/검토자별 영속 버전 + 단일 검토자 워크플로우.
//   draft → under_review → approved / rejected
// 디자인 시스템 v3.5: lg-card-tight + lg-state-pill + 16/12 라운드.

import { useEffect, useState, useCallback } from 'react';
import {
  History,
  GitBranch,
  Send,
  Check,
  X as XIcon,
  RefreshCw,
  Eye,
} from 'lucide-react';
import {
  listDraftVersions,
  reviewDraftVersion,
  getDraftVersion,
  type VersionListItemData,
  type VersionStatus,
  type VersionReviewAction,
} from '@api/draft';
import { useToast } from '@store/toast';

interface Props {
  /** 본문에 적용할 콜백 (rollback / 검토 결과 보기). */
  onLoadVersion?: (rendered_text: string) => void;
}

const STATUS_LABEL: Record<VersionStatus, { label: string; pill: 'ok' | 'warn' | 'crit' | 'info' }> = {
  draft:        { label: '초안',     pill: 'info' },
  under_review: { label: '검토 중',  pill: 'warn' },
  approved:     { label: '승인',     pill: 'ok' },
  rejected:     { label: '반려',     pill: 'crit' },
};

type Scope = 'mine' | 'review' | 'all';

const SCOPE_TABS: { key: Scope; en: string; ko: string }[] = [
  { key: 'mine',   en: 'MINE',   ko: '내 문서' },
  { key: 'review', en: 'REVIEW', ko: '검토 요청' },
  { key: 'all',    en: 'ALL',    ko: '전체' },
];

function formatTime(s: string): string {
  if (!s) return '—';
  return s.replace('T', ' ').slice(0, 16);
}

export function VersionTimeline({ onLoadVersion }: Props) {
  const { addToast } = useToast();
  const [scope, setScope] = useState<Scope>('mine');
  const [items, setItems] = useState<VersionListItemData[]>([]);
  const [busy, setBusy] = useState(false);

  // 검토 액션 모달
  const [reviewTarget, setReviewTarget] = useState<VersionListItemData | null>(null);
  const [reviewAction, setReviewAction] = useState<VersionReviewAction>('submit');
  const [reviewerId, setReviewerId] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [reviewBusy, setReviewBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const r = await listDraftVersions(scope, '', 50);
      setItems(r.items);
    } catch (err) {
      addToast({
        type: 'error',
        message: `버전 목록 로드 실패: ${err instanceof Error ? err.message : ''}`,
      });
    } finally {
      setBusy(false);
    }
  }, [scope, addToast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleLoad = async (versionId: number) => {
    if (!onLoadVersion) return;
    try {
      const detail = await getDraftVersion(versionId);
      onLoadVersion(detail.rendered_text || '');
      addToast({ type: 'success', message: `v${detail.version_num} 본문을 편집기에 로드했습니다.` });
    } catch (err) {
      addToast({
        type: 'error',
        message: `버전 로드 실패: ${err instanceof Error ? err.message : ''}`,
      });
    }
  };

  const handleReview = async () => {
    if (!reviewTarget) return;
    if (reviewAction === 'submit' && !reviewerId.trim()) {
      addToast({ type: 'warning', message: '검토자 ID 를 입력하세요.' });
      return;
    }
    setReviewBusy(true);
    try {
      const r = await reviewDraftVersion(reviewTarget.version_id, {
        action: reviewAction,
        reviewer_id: reviewerId.trim(),
        note: reviewNote.trim(),
      });
      addToast({
        type: 'success',
        message: `v${reviewTarget.version_num} → ${STATUS_LABEL[r.new_status].label}`,
      });
      setReviewTarget(null);
      setReviewerId('');
      setReviewNote('');
      refresh();
    } catch (err) {
      addToast({
        type: 'error',
        message: `${reviewAction} 실패: ${err instanceof Error ? err.message : ''}`,
      });
    } finally {
      setReviewBusy(false);
    }
  };

  return (
    <>
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div
              className="lg-eyebrow"
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <History size={11} strokeWidth={2} /> VERSIONS · 버전 이력
            </div>
            <h2 className="lg-h2">초안 → 검토 → 승인</h2>
          </div>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={refresh}
            disabled={busy}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
            aria-label="새로고침"
          >
            <RefreshCw
              size={11}
              strokeWidth={2}
              style={busy ? { animation: 'spin 1s linear infinite' } : undefined}
            />
            새로고침
          </button>
        </div>

        {/* SCOPE TABS */}
        <div className="lg-tabs" style={{ marginBottom: 14 }}>
          {SCOPE_TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={'lg-tab' + (scope === t.key ? ' on' : '')}
              onClick={() => setScope(t.key)}
            >
              <span className="en">{t.en}</span>
              <span className="ko">{t.ko}</span>
            </button>
          ))}
        </div>

        {/* TIMELINE */}
        {busy ? (
          <div className="dim" style={{ padding: 18, textAlign: 'center', fontSize: 13 }}>
            불러오는 중…
          </div>
        ) : items.length === 0 ? (
          <div className="lg-empty" style={{ padding: 24, textAlign: 'center' }}>
            아직 저장된 버전이 없습니다. 초안을 생성하면 자동 저장됩니다.
          </div>
        ) : (
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
            {items.map((v) => {
              const st = STATUS_LABEL[v.status];
              return (
                <li
                  key={v.version_id}
                  style={{
                    padding: 12,
                    borderRadius: 12,
                    border:
                      '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
                    background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr auto',
                    gap: 12,
                    alignItems: 'center',
                  }}
                >
                  {/* 버전 번호 */}
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 2,
                      minWidth: 56,
                    }}
                  >
                    <GitBranch size={12} strokeWidth={2} style={{ color: 'var(--hud-primary)' }} />
                    <span
                      className="mono"
                      style={{
                        fontFamily: 'var(--hud-font-mono)',
                        fontSize: 13,
                        fontWeight: 700,
                        color: 'var(--hud-primary)',
                      }}
                    >
                      v{v.version_num}
                    </span>
                  </div>

                  {/* 본문 */}
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        flexWrap: 'wrap',
                      }}
                    >
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: 'var(--hud-text)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          maxWidth: 280,
                        }}
                        title={v.title}
                      >
                        {v.title || v.doc_type}
                      </span>
                      <span className={`lg-state-pill ${st.pill}`}>{st.label}</span>
                      {v.reviewer_id && (
                        <span
                          className="mono dim"
                          style={{
                            fontFamily: 'var(--hud-font-mono)',
                            fontSize: 10,
                            letterSpacing: '0.06em',
                          }}
                          title={v.reviewed_at ? `검토일: ${v.reviewed_at}` : '검토 대기'}
                        >
                          검토자 {v.reviewer_id}
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--hud-text-dim)',
                        marginTop: 4,
                        lineHeight: 1.5,
                      }}
                    >
                      {v.change_summary || '(요약 없음)'} · {formatTime(v.created_at)}
                      {v.created_by && ` · @${v.created_by}`}
                    </div>
                    {v.review_note && (
                      <div
                        style={{
                          fontSize: 11,
                          color: 'var(--hud-text-dim)',
                          marginTop: 4,
                          padding: '4px 8px',
                          borderRadius: 12,
                          background: 'color-mix(in oklab, var(--hud-text) 6%, transparent)',
                          fontStyle: 'italic',
                        }}
                      >
                        검토 메모: {v.review_note}
                      </div>
                    )}
                  </div>

                  {/* 액션 */}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {onLoadVersion && (
                      <button
                        type="button"
                        className="lg-btn ghost sm"
                        onClick={() => handleLoad(v.version_id)}
                        title="이 버전을 편집기에 로드"
                        aria-label="편집기에 로드"
                      >
                        <Eye size={11} strokeWidth={2} />
                      </button>
                    )}
                    {v.status === 'draft' && (
                      <button
                        type="button"
                        className="lg-btn ghost sm"
                        onClick={() => {
                          setReviewTarget(v);
                          setReviewAction('submit');
                          setReviewerId('');
                          setReviewNote('');
                        }}
                        title="검토 요청"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
                      >
                        <Send size={11} strokeWidth={2} /> 검토
                      </button>
                    )}
                    {v.status === 'under_review' && (
                      <>
                        <button
                          type="button"
                          className="lg-btn sm"
                          onClick={() => {
                            setReviewTarget(v);
                            setReviewAction('approve');
                            setReviewerId(v.reviewer_id);
                            setReviewNote('');
                          }}
                          title="승인"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
                        >
                          <Check size={11} strokeWidth={2} /> 승인
                        </button>
                        <button
                          type="button"
                          className="lg-btn ghost sm"
                          onClick={() => {
                            setReviewTarget(v);
                            setReviewAction('reject');
                            setReviewerId(v.reviewer_id);
                            setReviewNote('');
                          }}
                          title="반려"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                            color: 'var(--hud-red, #C0392B)',
                          }}
                        >
                          <XIcon size={11} strokeWidth={2} /> 반려
                        </button>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* 검토 액션 모달 */}
      {reviewTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="검토 액션"
          onClick={() => !reviewBusy && setReviewTarget(null)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'color-mix(in oklab, var(--hud-bg, #0A0E14) 60%, transparent)',
            backdropFilter: 'blur(4px) saturate(120%)',
            WebkitBackdropFilter: 'blur(4px) saturate(120%)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            paddingTop: '15vh',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(480px, 92vw)',
              background: 'var(--glass-bg-strong, var(--hud-surface, #111820))',
              backdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
              WebkitBackdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
              border:
                '1px solid var(--glass-border, color-mix(in oklab, var(--hud-text) 12%, transparent))',
              borderRadius: 16,
              padding: 20,
            }}
          >
            <div className="lg-eyebrow" style={{ marginBottom: 4 }}>
              {reviewAction === 'submit' && 'SUBMIT · 검토 요청'}
              {reviewAction === 'approve' && 'APPROVE · 승인'}
              {reviewAction === 'reject' && 'REJECT · 반려'}
            </div>
            <h3
              style={{
                margin: '0 0 14px',
                fontSize: 16,
                fontWeight: 600,
                color: 'var(--hud-text)',
              }}
            >
              v{reviewTarget.version_num} · {reviewTarget.title || reviewTarget.doc_type}
            </h3>

            {reviewAction === 'submit' && (
              <div className="lg-field" style={{ marginBottom: 12 }}>
                <label>검토자 ID (사번 또는 username)</label>
                <input
                  type="text"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  placeholder="예: 12345 / kim.qa"
                  disabled={reviewBusy}
                  autoFocus
                />
              </div>
            )}

            <div className="lg-field" style={{ marginBottom: 14 }}>
              <label>메모 (선택)</label>
              <textarea
                className="lg-textarea"
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
                rows={3}
                placeholder={
                  reviewAction === 'reject'
                    ? '반려 사유를 작성하세요'
                    : '검토 시 참고할 내용 (선택)'
                }
                disabled={reviewBusy}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                className="lg-btn ghost sm"
                onClick={() => setReviewTarget(null)}
                disabled={reviewBusy}
              >
                취소
              </button>
              <button
                type="button"
                className="lg-btn"
                onClick={handleReview}
                disabled={reviewBusy}
              >
                {reviewBusy ? '처리 중…' : '확정'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
