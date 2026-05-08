// Day 5 Phase 3 — 메시지 풍선 피드백 버튼 (👍/👎)
// RTDB 직접 push (옵션 B) + Day 3 useRTDBValue 로 누적 카운트 실시간 표시.

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRTDBValue } from '@hooks/useRTDBValue';
import { recordFeedback, type FeedbackRating } from '@api/feedback';

interface Props {
  messageId: string;
}

interface FeedbackEntry {
  user_id: string;
  rating: FeedbackRating;
  ts: number;
}

export function FeedbackActions({ messageId }: Props) {
  const { t } = useTranslation();

  const { data } = useRTDBValue<Record<string, FeedbackEntry>>(`feedback/${messageId}`);
  const [submittedRating, setSubmittedRating] = useState<FeedbackRating | null>(null);
  const [error, setError] = useState<string | null>(null);

  const counts = (() => {
    if (!data) return { up: 0, down: 0 };
    let up = 0;
    let down = 0;
    for (const v of Object.values(data)) {
      if (v?.rating === 'thumbs_up') up += 1;
      else if (v?.rating === 'thumbs_down') down += 1;
    }
    return { up, down };
  })();

  const handle = async (rating: FeedbackRating) => {
    if (submittedRating) return;
    setError(null);
    try {
      await recordFeedback(messageId, rating);
      setSubmittedRating(rating);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="feedback-actions" role="group" aria-label={t('chat.feedback.title')}>
      <button
        type="button"
        className={`feedback-btn up ${submittedRating === 'thumbs_up' ? 'active' : ''}`}
        onClick={() => handle('thumbs_up')}
        disabled={submittedRating !== null}
        aria-label={t('chat.feedback.thumbs_up')}
        title={t('chat.feedback.thumbs_up')}
      >
        <span aria-hidden>▲</span>
        <span className="feedback-count">{counts.up}</span>
      </button>
      <button
        type="button"
        className={`feedback-btn down ${submittedRating === 'thumbs_down' ? 'active' : ''}`}
        onClick={() => handle('thumbs_down')}
        disabled={submittedRating !== null}
        aria-label={t('chat.feedback.thumbs_down')}
        title={t('chat.feedback.thumbs_down')}
      >
        <span aria-hidden>▼</span>
        <span className="feedback-count">{counts.down}</span>
      </button>
      {submittedRating && (
        <span className="feedback-thanks" aria-live="polite">
          {t('chat.feedback.thanks')}
        </span>
      )}
      {error && (
        <span className="feedback-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
