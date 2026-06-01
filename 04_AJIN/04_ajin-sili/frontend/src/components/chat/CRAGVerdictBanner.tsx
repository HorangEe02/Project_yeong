// CRAG verdict 결과 표시 배너 — Phase 1 PR2 (CRAG retrieval evaluator) 의 frontend 렌더.
//
// backend onboarding chat endpoint 가 SSE 'done' 이벤트의 metadata 로
// `crag_verdict` ('correct' | 'ambiguous' | 'incorrect') + `crag_top_score`
// 를 송출 (PR #12 wiring). 본 컴포넌트는 그 값을 받아 사용자에게 시각화한다.
//
// 사용자 §11 #3 확정 정책:
// - correct → 배너 미표시 (정상 답변)
// - ambiguous → ⚠️ 황색 배너 — "출처 신뢰도 낮음" + 부서 확인 권유
// - incorrect → 🚫 적색 배너 — "사내 자료 없음" + 안내 메시지 (LLM 답변은 이미 backend 가 차단)

import type { ReactElement } from 'react';

export type CRAGVerdict = 'correct' | 'ambiguous' | 'incorrect';

export interface CRAGVerdictBannerProps {
  verdict: CRAGVerdict | undefined;
  topScore?: number;
  rationale?: string;
  /** citation_status === 'crag_blocked' 면 차단 모드. backend 가 LLM 호출 우회한 경우. */
  blocked?: boolean;
}

const STYLES: Record<CRAGVerdict, { bg: string; border: string; emoji: string; label: string }> = {
  correct: {
    bg: 'rgba(34, 197, 94, 0.10)',
    border: '#22c55e',
    emoji: '✓',
    label: '출처 매칭 양호',
  },
  ambiguous: {
    bg: 'rgba(245, 158, 11, 0.12)',
    border: '#f59e0b',
    emoji: '⚠️',
    label: '출처 신뢰도 낮음',
  },
  incorrect: {
    bg: 'rgba(239, 68, 68, 0.12)',
    border: '#ef4444',
    emoji: '🚫',
    label: '사내 자료에서 확인 불가',
  },
};

export function CRAGVerdictBanner({
  verdict,
  topScore,
  rationale,
  blocked,
}: CRAGVerdictBannerProps): ReactElement | null {
  if (!verdict || verdict === 'correct') return null;

  const style = STYLES[verdict];
  const scoreText = typeof topScore === 'number' && topScore > 0 ? ` · 적합도 ${topScore.toFixed(2)}` : '';
  const blockedHint =
    verdict === 'incorrect' && blocked
      ? '담당 부서(인사관리팀 / 안전보건팀)에 직접 문의해 주세요.'
      : '';
  const ambiguousHint =
    verdict === 'ambiguous'
      ? '답변의 정확성은 담당 부서에서 추가 확인하시기 바랍니다.'
      : '';

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        padding: '10px 14px',
        borderRadius: 10,
        background: style.bg,
        borderLeft: `3px solid ${style.border}`,
        fontSize: 13,
        margin: '12px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500 }}>
        <span aria-hidden style={{ fontSize: 16 }}>{style.emoji}</span>
        <span>{style.label}{scoreText}</span>
      </div>
      {blockedHint && (
        <div className="dim" style={{ fontSize: 12 }}>{blockedHint}</div>
      )}
      {ambiguousHint && (
        <div className="dim" style={{ fontSize: 12 }}>{ambiguousHint}</div>
      )}
      {rationale && (
        <div className="dim" style={{ fontSize: 11, fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}>
          {rationale}
        </div>
      )}
    </div>
  );
}
