// DocumentResultCard — Module A · 문서 검색 결과 카드.
// 디자인 시스템 v3.5: lg-card-tight + lg-pill + lg-btn ghost sm + 영문 eyebrow + 한글 본문.
// 24px/16px/12px/999px tier 만 사용, 6/4/3 px radii 금지. 이모지 금지.

import { useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import type { DocSearchResultItem } from '@api/search';
import { getFeedbackFor, pushFeedback } from '@lib/searchHistory';

interface Props {
  item: DocSearchResultItem;
  query: string;
  tokens: string[];
  snippet: string;
  onSelect: (item: DocSearchResultItem) => void;
}

const DOC_TYPE_LABEL: Record<string, string> = {
  '8d_report': '8D 보고서',
  ecn: 'ECN (설계변경)',
  email: '이메일',
  meeting_note: '회의록',
  ppap: 'PPAP',
};

function highlight(text: string, tokens: string[]): React.ReactNode {
  if (!tokens.length || !text) return text;
  const pattern = new RegExp(`(${tokens.map(escapeReg).join('|')})`, 'gi');
  const parts = text.split(pattern);
  return parts.map((p, i) =>
    pattern.test(p) ? (
      <mark key={i} className="lg-hl">
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

function escapeReg(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function formatScore(score: number): string {
  if (!Number.isFinite(score)) return '—';
  return score.toFixed(2);
}

function formatDate(metadata: Record<string, unknown>): string | null {
  const raw =
    (metadata?.['date'] as string) ??
    (metadata?.['created_at'] as string) ??
    (metadata?.['updated_at'] as string) ??
    null;
  if (!raw) return null;
  return raw.toString().slice(0, 10);
}

export function DocumentResultCard({ item, query, tokens, snippet, onSelect }: Props) {
  const docTypeLabel = DOC_TYPE_LABEL[item.doc_type] ?? item.doc_type ?? 'DOC';
  const date = formatDate(item.metadata ?? {});
  const author = (item.metadata?.['author'] as string) ?? null;
  const department = (item.metadata?.['department'] as string) ?? null;

  // 피드백 상태 (이전 피드백 복원)
  const [feedback, setFeedback] = useState<'helpful' | 'unhelpful' | null>(null);
  useEffect(() => {
    const prev = getFeedbackFor(query, item.doc_id);
    setFeedback(prev ? (prev.helpful ? 'helpful' : 'unhelpful') : null);
  }, [query, item.doc_id]);

  const handleFeedback = (helpful: boolean) => {
    pushFeedback({
      query,
      docId: item.doc_id,
      docTitle: item.title,
      helpful,
    });
    setFeedback(helpful ? 'helpful' : 'unhelpful');
  };

  return (
    <div
      role="button"
      tabIndex={0}
      className="lg-card lg-card-tight"
      onClick={() => onSelect(item)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(item);
        }
      }}
      title={`${item.title} 상세 보기`}
      style={{ cursor: 'pointer', marginBottom: 0 }}
    >
      {/* HEADER ROW — type pill + part + date + score */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 8,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="lg-pill">{docTypeLabel}</span>
          {item.part_name && <span className="lg-tag mod">{item.part_name}</span>}
          {date && (
            <span
              className="mono"
              style={{
                fontFamily: 'var(--hud-font-mono)',
                fontSize: 11,
                color: 'var(--hud-text-dim)',
                letterSpacing: '0.06em',
              }}
            >
              {date}
            </span>
          )}
        </div>
        <span
          className="mono"
          style={{
            fontFamily: 'var(--hud-font-mono)',
            fontSize: 11,
            color: 'var(--hud-text-dim)',
            letterSpacing: '0.08em',
          }}
          title={`RRF score ${item.score}`}
        >
          RRF · {formatScore(item.score)}
        </span>
      </div>

      {/* TITLE */}
      <h3
        style={{
          margin: '0 0 6px',
          fontSize: 17,
          lineHeight: 1.35,
          fontWeight: 600,
          letterSpacing: '-0.01em',
          color: 'var(--hud-text)',
        }}
      >
        {highlight(item.title || '(제목 없음)', tokens)}
      </h3>

      {/* SNIPPET */}
      {snippet && (
        <p
          style={{
            margin: 0,
            fontSize: 13,
            lineHeight: 1.6,
            color: 'var(--hud-text-dim)',
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {highlight(snippet, tokens)}
        </p>
      )}

      {/* META FOOTER */}
      {(author || department) && (
        <div
          style={{
            marginTop: 10,
            fontSize: 11,
            color: 'var(--hud-text-dim)',
            display: 'flex',
            gap: 14,
            flexWrap: 'wrap',
            letterSpacing: '0.02em',
          }}
        >
          {author && <span>작성자 · {author}</span>}
          {department && <span>부서 · {department}</span>}
          <span
            className="mono"
            style={{ fontFamily: 'var(--hud-font-mono)', opacity: 0.7 }}
          >
            ID · {item.doc_id || '—'}
          </span>
        </div>
      )}

      {/* FEEDBACK ROW — dashed separator, 아이콘 only buttons (lg-btn ghost sm 패턴) */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          marginTop: 14,
          paddingTop: 10,
          borderTop:
            '1px dashed color-mix(in oklab, var(--hud-text) 12%, transparent)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span
          className="lg-eyebrow"
          style={{ fontSize: 10, marginBottom: 0 }}
        >
          FEEDBACK · 도움 여부
        </span>
        <button
          type="button"
          className={`lg-btn ${feedback === 'helpful' ? '' : 'ghost'} sm`}
          onClick={() => handleFeedback(true)}
          aria-pressed={feedback === 'helpful'}
          title="도움됨"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <ThumbsUp size={11} strokeWidth={2} />
          도움됨
        </button>
        <button
          type="button"
          className="lg-btn ghost sm"
          onClick={() => handleFeedback(false)}
          aria-pressed={feedback === 'unhelpful'}
          title="도움 안 됨"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            color:
              feedback === 'unhelpful'
                ? 'var(--hud-red, #C0392B)'
                : undefined,
            borderColor:
              feedback === 'unhelpful'
                ? 'color-mix(in oklab, var(--hud-red, #C0392B) 40%, transparent)'
                : undefined,
          }}
        >
          <ThumbsDown size={11} strokeWidth={2} />
          부적합
        </button>
        {feedback && (
          <span
            className="mono"
            style={{
              marginLeft: 'auto',
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.12em',
              color: 'var(--hud-text-dim)',
            }}
          >
            RECORDED · 기록됨
          </span>
        )}
      </div>
    </div>
  );
}
