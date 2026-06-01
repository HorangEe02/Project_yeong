// P4 D15 — 사수 평가 큐 panel.
// 사수 본인이 큐레이션한 학습경로의 평가 대기 list + inline review actions.

import { useEffect, useState } from 'react';
import {
  fetchMentorQueue,
  submitLearningReview,
  type LearningMentorQueueItem } from '@api/compliance';

export function MentorReviewPanel() {
  const [items, setItems] = useState<LearningMentorQueueItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState<Record<number, string>>({});

  const reload = () => {
    setBusy(true);
    fetchMentorQueue()
      .then((r) => setItems(r.items))
      .catch((e) => setError((e as Error).message))
      .finally(() => setBusy(false));
  };

  useEffect(() => {
    reload();
  }, []);

  const handleReview = async (
    progressId: number,
    verdict: 'pass' | 'redo' | 'pass_with_comment',
  ) => {
    try {
      await submitLearningReview(progressId, verdict, comment[progressId] ?? '');
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (items.length === 0) {
    return (
      <div className="lg-card">
        <div className="lg-pill">P4 D15 · MENTOR QUEUE</div>
        <p style={{ marginTop: 8 }}>평가 대기 중인 학습 진도가 없습니다.</p>
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
            <div className="lg-pill">MENTOR REVIEW QUEUE</div>
            <strong>평가 대기 ({items.length})</strong>
          </div>
        </div>
        <p style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
          AI 자문은 참고용 — 최종 판단은 담당자입니다.
        </p>
        <table className="lg-table">
          <thead>
            <tr>
              <th>신입</th>
              <th>경로</th>
              <th>주차</th>
              <th>change</th>
              <th>점수/시도</th>
              <th>코멘트</th>
              <th>평가</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id}>
                <td>{it.assignee_employee_id}</td>
                <td>{it.path_name}</td>
                <td>W{it.week}</td>
                <td>#{it.change_id}</td>
                <td>{it.quiz_score} / {it.quiz_attempts}</td>
                <td>
                  <input
                    className="lg-input"
                    value={comment[it.id] ?? ''}
                    onChange={(e) => setComment({ ...comment, [it.id]: e.target.value })}
                    placeholder="(선택) 코멘트"
                  />
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      type="button"
                      className="lg-btn primary"
                      onClick={() => handleReview(it.id, 'pass')}
                      disabled={busy}
                    >
                      ✓ 통과
                    </button>
                    <button
                      type="button"
                      className="lg-btn"
                      onClick={() => handleReview(it.id, 'pass_with_comment')}
                      disabled={busy || !(comment[it.id] ?? '').trim()}
                    >
                      ◐ 코멘트 통과
                    </button>
                    <button
                      type="button"
                      className="lg-btn"
                      onClick={() => handleReview(it.id, 'redo')}
                      disabled={busy}
                    >
                      ↻ 재시도
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
