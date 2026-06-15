// P5 §7 — 자체 결재 워크플로 panel.
// 본인 결재 대기 큐 + inline approve/reject/delegate 액션.

import { useEffect, useState } from 'react';
import {
  decideApprovalStep,
  fetchMyApprovals,
  type ApprovalMyPendingResponse } from '@api/compliance';

export function ApprovalQueuePanel() {
  const [data, setData] = useState<ApprovalMyPendingResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comments, setComments] = useState<Record<number, string>>({});

  const reload = () => {
    setBusy(true);
    fetchMyApprovals()
      .then(setData)
      .catch((e) => setError((e as Error).message))
      .finally(() => setBusy(false));
  };

  useEffect(() => {
    reload();
  }, []);

  const handle = async (
    stepId: number,
    decision: 'approved' | 'rejected' | 'delegated',
  ) => {
    try {
      await decideApprovalStep(stepId, decision, comments[stepId] ?? '');
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <div className="lg-card">
        <div className="lg-pill">P5 §7 · APPROVAL QUEUE</div>
        <p style={{ marginTop: 8 }}>본인이 결재할 차례인 항목이 없습니다.</p>
      </div>
    );
  }

  return (
    <>
      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}
      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">APPROVAL QUEUE</div>
            <strong>결재 대기 ({items.length})</strong>
          </div>
        </div>
        <p style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
          AI 자문은 참고용 — 최종 결재 판단은 담당자입니다.
        </p>
        <table className="lg-table">
          <thead>
            <tr>
              <th>chain</th>
              <th>change</th>
              <th>단계</th>
              <th>역할</th>
              <th>코멘트</th>
              <th>결정</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const stepId = Number(it.id);
              return (
                <tr key={stepId}>
                  <td>#{String(it.chain_id ?? '?')} {String(it.chain_name ?? '')}</td>
                  <td>change #{String(it.change_id ?? 0)}</td>
                  <td>step {String(it.step_order ?? '?')}</td>
                  <td>{String(it.role_label ?? '')}</td>
                  <td>
                    <input
                      className="lg-input"
                      value={comments[stepId] ?? ''}
                      onChange={(e) =>
                        setComments({ ...comments, [stepId]: e.target.value })
                      }
                      placeholder="(선택) 코멘트"
                    />
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        type="button"
                        className="lg-btn primary"
                        onClick={() => handle(stepId, 'approved')}
                        disabled={busy}
                      >
                        ✓ 승인
                      </button>
                      <button
                        type="button"
                        className="lg-btn"
                        onClick={() => handle(stepId, 'rejected')}
                        disabled={busy}
                      >
                        ✗ 반려
                      </button>
                      <button
                        type="button"
                        className="lg-btn"
                        onClick={() => handle(stepId, 'delegated')}
                        disabled={busy}
                      >
                        ↪ 위임
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
