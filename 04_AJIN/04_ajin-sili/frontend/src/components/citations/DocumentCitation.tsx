// DocumentCitation — 클릭 가능한 출처 인용 배지.
// CITATION_UI_SPEC.md §4-2 기준.
// 역할: 제목 + 페이지 + 날짜 + CitationBadge 를 한 행에 표시.
// 클릭 시 SourcePreviewModal 을 부모에게 위임 (onOpenPreview 콜백).
//
// 디자인 패턴: lg-card-tight 내부 dashed border-left + lg-eyebrow 영한 라벨.
// 근거: WEB_DESIGN_SPECIFICATION.md §6-3 (쿼리 결과 카드 출처 행 패턴).

import { FileText } from 'lucide-react';
import { CitationBadge } from './CitationBadge';
import type { CitationItem } from '@api/search';

interface DocumentCitationProps {
  /** 인용 번호 (각주 스타일 — 챗봇 응답에서 [1], [2] 에 대응) */
  index: number;
  citation: CitationItem;
  /** 클릭 시 SourcePreviewModal 을 열도록 부모에게 위임 */
  onOpenPreview: (citation: CitationItem) => void;
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
  return isoDate.slice(0, 10); // YYYY-MM-DD
}

export function DocumentCitation({
  index,
  citation,
  onOpenPreview,
}: DocumentCitationProps) {
  const typeLabel = DOC_TYPE_LABEL[citation.docType] ?? citation.docType ?? 'DOC';
  const dateStr = formatLastUpdated(citation.lastUpdated);

  return (
    <button
      type="button"
      className="lg-btn ghost sm"
      onClick={() => onOpenPreview(citation)}
      aria-label={`[${index}] ${citation.documentTitle} 출처 미리보기 열기`}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        width: '100%',
        textAlign: 'left',
        borderLeft: '3px solid var(--hud-primary, #F9A70D)',
        borderRadius: '0 2px 2px 0',
        padding: '8px 12px',
        background:
          'color-mix(in oklab, var(--hud-primary, #F9A70D) 5%, transparent)',
        cursor: 'pointer',
      }}
    >
      {/* 인용 번호 */}
      <span
        style={{
          fontFamily: 'var(--hud-font-mono, monospace)',
          fontSize: 11,
          color: 'var(--hud-primary, #F9A70D)',
          letterSpacing: '0.08em',
          minWidth: 20,
          paddingTop: 1,
        }}
        aria-hidden="true"
      >
        [{index}]
      </span>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 상단 행: eyebrow 라벨 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 4,
          }}
        >
          <span className="lg-pill" style={{ fontSize: 10 }}>
            {typeLabel}
          </span>
          {citation.department && (
            <span
              style={{
                fontFamily: 'var(--hud-font-mono, monospace)',
                fontSize: 10,
                color: 'var(--hud-text-dim)',
                letterSpacing: '0.06em',
              }}
            >
              {citation.department}
            </span>
          )}
          {citation.status && (
            <span
              style={{
                fontFamily: 'var(--hud-font-mono, monospace)',
                fontSize: 10,
                color:
                  citation.status === '완료'
                    ? 'var(--hud-green, #2D8A4E)'
                    : citation.status === '진행중'
                      ? 'var(--hud-orange, #E8A317)'
                      : 'var(--hud-text-dim)',
                letterSpacing: '0.06em',
              }}
            >
              &#9679; {citation.status}
            </span>
          )}
        </div>

        {/* 문서 제목 */}
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--hud-text)',
            lineHeight: 1.35,
            marginBottom: 4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          <FileText
            size={12}
            strokeWidth={2}
            style={{ marginRight: 6, opacity: 0.6, verticalAlign: 'middle' }}
            aria-hidden="true"
          />
          {citation.documentTitle}
          {citation.pageNumber != null && (
            <span
              style={{
                fontFamily: 'var(--hud-font-mono, monospace)',
                fontSize: 10,
                color: 'var(--hud-text-dim)',
                marginLeft: 8,
                fontWeight: 400,
              }}
            >
              p.{citation.pageNumber}
            </span>
          )}
        </div>

        {/* 하단 행: 날짜 + 신뢰도 배지 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--hud-font-mono, monospace)',
              fontSize: 10,
              color: 'var(--hud-text-dim)',
              letterSpacing: '0.06em',
            }}
          >
            {dateStr}
          </span>
          <CitationBadge confidence={citation.confidence} compact />
        </div>
      </div>
    </button>
  );
}
