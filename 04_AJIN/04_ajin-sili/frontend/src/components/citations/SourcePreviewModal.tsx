// SourcePreviewModal — 청크 원문 미리보기 모달.
// CITATION_UI_SPEC.md §4-4 기준.
// 역할: CitationItem.chunkText 를 강조 하이라이트와 함께 표시.
// 포커스 트랩: 모달 열림 시 닫기 버튼으로 포커스 이동 (WCAG 2.1 §2.4.3).
// ESC 키로 닫기, 배경 클릭으로 닫기.
//
// 디자인: glass modal 패턴 (REACT_MIGRATION_PLAN §1-2 "Liquid Glass" 모달 4영역 한정).
// 이모지 금지, 모서리 2px, 골드 강조선.

import { useEffect, useRef } from 'react';
import { X, ExternalLink } from 'lucide-react';
import { CitationBadge } from './CitationBadge';
import type { CitationItem } from '@api/search';

interface SourcePreviewModalProps {
  citation: CitationItem;
  onClose: () => void;
}

const DOC_TYPE_LABEL: Record<string, string> = {
  '8d_report': '8D 보고서',
  '8D Report': '8D 보고서',
  ecn: 'ECN (설계변경)',
  ECN: 'ECN (설계변경)',
  email: '이메일',
  Email: '이메일',
  meeting_note: '회의록',
  'Meeting Note': '회의록',
  ppap: 'PPAP',
  PPAP: 'PPAP',
};

function formatLastUpdated(isoDate: string): string {
  if (!isoDate) return '날짜 없음';
  return isoDate.slice(0, 10);
}

/**
 * 청크 텍스트에서 앞 280자를 강조 표시로 렌더링.
 * chunkText 전체를 하이라이트 배경으로 감싸는 단순 구현 (span-level 인용).
 */
function ChunkHighlight({ text }: { text: string }) {
  const preview = text.slice(0, 280);
  const hasMore = text.length > 280;
  return (
    <blockquote
      style={{
        margin: '0 0 12px',
        padding: '10px 14px',
        borderLeft: '3px solid var(--hud-primary, #F9A70D)',
        borderRadius: '0 2px 2px 0',
        background:
          'color-mix(in oklab, var(--hud-primary, #F9A70D) 6%, var(--hud-surface, #111820))',
        fontSize: 13,
        lineHeight: 1.65,
        color: 'var(--hud-text)',
        fontStyle: 'italic',
      }}
    >
      <mark
        style={{
          background:
            'color-mix(in oklab, var(--hud-primary, #F9A70D) 18%, transparent)',
          color: 'inherit',
          borderRadius: 2,
        }}
      >
        {preview}
      </mark>
      {hasMore && (
        <span style={{ color: 'var(--hud-text-dim)', fontStyle: 'normal' }}>
          {' '}
          ... ({text.length - 280}자 추가 내용)
        </span>
      )}
    </blockquote>
  );
}

export function SourcePreviewModal({
  citation,
  onClose,
}: SourcePreviewModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const typeLabel =
    DOC_TYPE_LABEL[citation.docType] ?? citation.docType ?? 'DOC';

  // 포커스 트랩 — 모달 열림 시 닫기 버튼으로 이동 (WCAG 2.4.3)
  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  // ESC 키 닫기 (WCAG 2.1.1)
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    /* 배경 오버레이 */
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${citation.documentTitle} 출처 미리보기`}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(10, 14, 20, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* 모달 패널 */}
      <div
        style={{
          background: 'var(--hud-surface, #111820)',
          border: '1px solid var(--hud-border, #2A2520)',
          borderTop: '2px solid var(--hud-primary, #F9A70D)',
          borderRadius: 2,
          width: '100%',
          maxWidth: 620,
          maxHeight: '80vh',
          overflowY: 'auto',
          padding: 24,
          boxShadow:
            '0 0 30px rgba(249,167,13,0.12), 0 24px 48px rgba(0,0,0,0.48)',
        }}
      >
        {/* 헤더 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 12,
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: '1px solid var(--hud-border)',
          }}
        >
          <div style={{ minWidth: 0 }}>
            {/* eyebrow */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 8,
              }}
            >
              <span className="lg-pill" style={{ fontSize: 10 }}>
                {typeLabel}
              </span>
              <span
                className="lg-eyebrow"
                style={{ fontSize: 10, marginBottom: 0 }}
              >
                SOURCE PREVIEW · 원문 미리보기
              </span>
            </div>
            {/* 제목 */}
            <h2
              style={{
                margin: 0,
                fontSize: 16,
                fontWeight: 700,
                color: 'var(--hud-text)',
                lineHeight: 1.3,
              }}
            >
              {citation.documentTitle}
              {citation.pageNumber != null && (
                <span
                  style={{
                    fontFamily: 'var(--hud-font-mono, monospace)',
                    fontSize: 11,
                    fontWeight: 400,
                    color: 'var(--hud-text-dim)',
                    marginLeft: 10,
                  }}
                >
                  p.{citation.pageNumber}
                </span>
              )}
            </h2>
          </div>

          {/* 닫기 버튼 */}
          <button
            ref={closeRef}
            type="button"
            className="lg-btn ghost sm"
            onClick={onClose}
            aria-label="미리보기 닫기"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              flexShrink: 0,
            }}
          >
            <X size={14} strokeWidth={2} aria-hidden="true" />
            <span>닫기</span>
          </button>
        </div>

        {/* 메타데이터 행 */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 16,
            marginBottom: 16,
            fontFamily: 'var(--hud-font-mono, monospace)',
            fontSize: 11,
            color: 'var(--hud-text-dim)',
            letterSpacing: '0.06em',
          }}
        >
          <span>
            ID ·{' '}
            <strong style={{ color: 'var(--hud-text)' }}>{citation.id}</strong>
          </span>
          {citation.department && (
            <span>
              부서 ·{' '}
              <strong style={{ color: 'var(--hud-text)' }}>
                {citation.department}
              </strong>
            </span>
          )}
          <span>
            갱신 ·{' '}
            <strong style={{ color: 'var(--hud-text)' }}>
              {formatLastUpdated(citation.lastUpdated)}
            </strong>
          </span>
          {citation.status && (
            <span
              style={{
                color:
                  citation.status === '완료'
                    ? 'var(--hud-green, #2D8A4E)'
                    : citation.status === '진행중'
                      ? 'var(--hud-orange, #E8A317)'
                      : undefined,
              }}
            >
              상태 · <strong>{citation.status}</strong>
            </span>
          )}
          <CitationBadge confidence={citation.confidence} compact />
        </div>

        {/* 점수 상세 (선택 — bm25/vector 표시) */}
        {(citation.bm25Score != null || citation.vectorScore != null) && (
          <div
            style={{
              display: 'flex',
              gap: 20,
              marginBottom: 16,
              fontFamily: 'var(--hud-font-mono, monospace)',
              fontSize: 10,
              color: 'var(--hud-text-dim)',
              letterSpacing: '0.08em',
            }}
          >
            <span>
              RRF SCORE · {(citation.confidence * 100).toFixed(1)}%
            </span>
            {citation.bm25Score != null && (
              <span>BM25 · {citation.bm25Score.toFixed(4)}</span>
            )}
            {citation.vectorScore != null && (
              <span>VECTOR · {citation.vectorScore.toFixed(4)}</span>
            )}
          </div>
        )}

        {/* 청크 하이라이트 */}
        <div style={{ marginBottom: 16 }}>
          <p
            className="lg-eyebrow"
            style={{ fontSize: 10, marginBottom: 8 }}
          >
            MATCHED CHUNK · 매칭된 청크 원문
          </p>
          {citation.chunkText ? (
            <ChunkHighlight text={citation.chunkText} />
          ) : (
            <p
              style={{
                fontSize: 13,
                color: 'var(--hud-text-dim)',
                fontStyle: 'italic',
              }}
            >
              청크 원문을 불러올 수 없습니다. 백엔드 응답에 content 필드를 확인하세요.
            </p>
          )}
        </div>

        {/* 경고 문구 */}
        <div
          role="note"
          style={{
            padding: '8px 12px',
            border:
              '1px solid color-mix(in oklab, var(--hud-orange, #E8A317) 40%, transparent)',
            borderRadius: 2,
            background:
              'color-mix(in oklab, var(--hud-orange, #E8A317) 5%, transparent)',
            fontSize: 11,
            color: 'var(--hud-orange, #E8A317)',
            letterSpacing: '0.04em',
            lineHeight: 1.6,
          }}
        >
          NOTICE · 이 청크에서 AI 답변이 생성되었습니다.
          중요 의사결정 전 원본 문서를 반드시 직접 확인하세요.
        </div>

        {/* 원본 문서 이동 링크 (선택 — sourceRef 가 URL 형태일 때) */}
        {citation.sourceRef && citation.sourceRef.startsWith('http') && (
          <div style={{ marginTop: 14, textAlign: 'right' }}>
            <a
              href={citation.sourceRef}
              target="_blank"
              rel="noopener noreferrer"
              className="lg-btn ghost sm"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 11,
              }}
              aria-label={`${citation.documentTitle} 원본 문서 새 탭에서 열기`}
            >
              <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
              OPEN SOURCE · 원본 열기
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
