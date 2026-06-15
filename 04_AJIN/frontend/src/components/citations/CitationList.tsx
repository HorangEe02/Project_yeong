// CitationList — 챗봇 응답 하단 출처 목록.
// CITATION_UI_SPEC.md §4-3 기준.
// 역할: CitationItem 배열을 받아 DocumentCitation 컴포넌트 목록으로 렌더.
// 3건 초과 시 "펼치기" 토글 (HUD 디자인: 점선 구분선 + 영한 헤더 패턴).
// SourcePreviewModal 상태를 내부에서 관리 (모달 오픈 소유권).

import { useState } from 'react';
import { DocumentCitation } from './DocumentCitation';
import { SourcePreviewModal } from './SourcePreviewModal';
import type { CitationItem } from '@api/search';

interface CitationListProps {
  citations: CitationItem[];
  /** 접기 전 표시할 최대 항목 수 (기본 3) */
  initialLimit?: number;
}

export function CitationList({
  citations,
  initialLimit = 3,
}: CitationListProps) {
  const [expanded, setExpanded] = useState(false);
  const [previewTarget, setPreviewTarget] = useState<CitationItem | null>(null);

  if (!citations.length) return null;

  const visible = expanded ? citations : citations.slice(0, initialLimit);
  const hasMore = citations.length > initialLimit;

  return (
    <>
      <section aria-label="출처 목록" style={{ marginTop: 16 }}>
        {/* 섹션 헤더 — 영한 병기 패턴 (WEB_DESIGN_SPECIFICATION §3-5) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingBottom: 8,
            borderBottom: '1px solid var(--hud-border)',
            marginBottom: 8,
          }}
        >
          <span
            className="lg-eyebrow"
            style={{ fontSize: 11, letterSpacing: '0.1em', marginBottom: 0 }}
          >
            CITATIONS · 출처 {citations.length}건
          </span>
          {hasMore && (
            <button
              type="button"
              className="lg-btn ghost sm"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              style={{ fontSize: 10, letterSpacing: '0.06em' }}
            >
              {expanded
                ? '접기 ▲'
                : `+${citations.length - initialLimit}건 더보기 ▼`}
            </button>
          )}
        </div>

        {/* 출처 목록 */}
        <ol
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
          aria-label={`출처 ${visible.length}건`}
        >
          {visible.map((citation, i) => (
            <li key={citation.id ?? i}>
              <DocumentCitation
                index={i + 1}
                citation={citation}
                onOpenPreview={setPreviewTarget}
              />
            </li>
          ))}
        </ol>

        {/* 점선 구분선 (WEB_DESIGN_SPECIFICATION §6-5) */}
        <div
          style={{
            marginTop: 12,
            borderTop:
              '1px dashed color-mix(in oklab, var(--hud-text) 12%, transparent)',
          }}
          aria-hidden="true"
        />
        <p
          style={{
            margin: '8px 0 0',
            fontSize: 10,
            color: 'var(--hud-text-dim)',
            fontFamily: 'var(--hud-font-mono, monospace)',
            letterSpacing: '0.06em',
          }}
        >
          NOTICE · AI 답변은 위 출처를 기반으로 생성됩니다. 중요 사안은 원본 문서를 직접 확인하세요.
        </p>
      </section>

      {/* SourcePreviewModal — CitationList 가 소유 */}
      {previewTarget && (
        <SourcePreviewModal
          citation={previewTarget}
          onClose={() => setPreviewTarget(null)}
        />
      )}
    </>
  );
}
