// TemplateCard — Module B · 템플릿 선택 카드.
// B1 v4.0: hover 시 미리보기 팝오버 + 가이드 + 부서 추천 배지.
// 디자인 시스템 v3.5: lg-card-tight + lg-pill + lg-tag + 16px 라운드.

import { useState, useRef, useEffect } from 'react';
import { Building2, FileText, Clock, ChevronRight, Star } from 'lucide-react';
import type { DocTypeMeta } from '@/types/draft';
import { TemplatePreviewPopover } from './TemplatePreviewPopover';

interface Props {
  doc: DocTypeMeta;
  selected: boolean;
  onSelect: (doc: DocTypeMeta) => void;
  // 부록 4 — F-fav 즐겨찾기 / F-rec 추천
  isFavorited?: boolean;
  onToggleFavorite?: (id: string) => void;
  recommended?: boolean;
  // 부록 6 — P4-1 부서 추천 / P4-3 개인 CF
  deptRecommended?: boolean;
  personalPick?: boolean;
}

const CATEGORY_LABEL: Record<string, string> = {
  internal: '사내',
  external: '외부',
};

export function TemplateCard({
  doc,
  selected,
  onSelect,
  isFavorited = false,
  onToggleFavorite,
  recommended = false,
  deptRecommended = false,
  personalPick = false,
}: Props) {
  const [hover, setHover] = useState(false);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // hover 0.4s 후 popover 자동 노출 — 너무 빠르면 거슬리고, 너무 느리면 답답
  useEffect(() => {
    if (!hover) {
      setPopoverOpen(false);
      return;
    }
    const t = setTimeout(() => setPopoverOpen(true), 400);
    return () => clearTimeout(t);
  }, [hover]);

  const requiredCount = doc.var_metadata?.filter((v) => v.required).length ?? doc.required_fields.length;
  const totalCount = doc.var_metadata?.length ?? doc.required_fields.length;

  return (
    <div
      ref={cardRef}
      role="button"
      tabIndex={0}
      onClick={() => onSelect(doc)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(doc);
        }
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      className="lg-card lg-card-tight"
      style={{
        position: 'relative',
        cursor: 'pointer',
        marginBottom: 0,
        outline: selected
          ? '2px solid var(--hud-primary)'
          : recommended
          ? '2px solid #d69e2e'
          : '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
        outlineOffset: selected || recommended ? -2 : 0,
        background: selected
          ? 'color-mix(in oklab, var(--hud-primary) 8%, transparent)'
          : recommended
          ? 'rgba(214,158,46,0.06)'
          : 'color-mix(in oklab, var(--hud-surface) 60%, transparent)',
        transition: 'all 0.15s ease',
      }}
      title={doc.usage_hint || doc.name_ko}
    >
      {/* 부록 4 — F-fav ☆/★ 토글 (우상단) */}
      {onToggleFavorite && (
        <button
          type="button"
          aria-label={isFavorited ? '즐겨찾기 해제' : '즐겨찾기'}
          onClick={(e) => {
            e.stopPropagation();
            onToggleFavorite(doc.id);
          }}
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            background: 'transparent',
            border: 'none',
            padding: 4,
            cursor: 'pointer',
            color: isFavorited ? '#d69e2e' : 'var(--hud-text-dim)',
            zIndex: 2,
          }}
          title={isFavorited ? '즐겨찾기 해제' : '즐겨찾기 추가'}
        >
          <Star
            size={14}
            strokeWidth={2}
            fill={isFavorited ? '#d69e2e' : 'none'}
          />
        </button>
      )}

      {/* 부록 4 — F-rec 추천 배지 (좌상단 영역) */}
      {recommended && !selected && (
        <div
          style={{
            position: 'absolute',
            top: -8,
            left: 12,
            padding: '1px 8px',
            background: '#d69e2e',
            color: '#1a1a1a',
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: '0.1em',
            borderRadius: 2,
            textTransform: 'uppercase',
            zIndex: 2,
          }}
        >
          추천
        </div>
      )}

      {/* 부록 6 — P4-1 팀 표준 / P4-3 자주 사용 배지 (좌상단 stacked) */}
      {(deptRecommended || personalPick) && !recommended && (
        <div
          style={{
            position: 'absolute',
            top: -8,
            left: 12,
            display: 'flex',
            gap: 4,
            zIndex: 2,
          }}
        >
          {deptRecommended && (
            <div
              style={{
                padding: '1px 6px',
                background: '#4FB774',
                color: '#1a1a1a',
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '0.1em',
                borderRadius: 2,
                textTransform: 'uppercase',
              }}
              title="내 부서가 자주 쓰는 템플릿"
            >
              팀 표준
            </div>
          )}
          {personalPick && (
            <div
              style={{
                padding: '1px 6px',
                background: 'rgba(214,158,46,0.6)',
                color: '#1a1a1a',
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '0.1em',
                borderRadius: 2,
                textTransform: 'uppercase',
              }}
              title="내가 자주 쓰는 템플릿"
            >
              자주
            </div>
          )}
        </div>
      )}
      {/* 헤더 — category + 추천 부서 첫 1개 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          marginBottom: 8,
        }}
      >
        <span className="lg-pill">{CATEGORY_LABEL[doc.category] ?? doc.category}</span>
        {doc.dept_recommend && doc.dept_recommend.length > 0 && (
          <span
            className="lg-tag mod"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
            title={`추천 부서: ${doc.dept_recommend.join(', ')}`}
          >
            <Building2 size={10} strokeWidth={2} /> {doc.dept_recommend[0]}
            {doc.dept_recommend.length > 1 ? ` +${doc.dept_recommend.length - 1}` : ''}
          </span>
        )}
      </div>

      {/* 제목 (한글) + 영문 부제 */}
      <h3
        style={{
          margin: '0 0 4px',
          fontSize: 16,
          lineHeight: 1.3,
          fontWeight: 600,
          color: 'var(--hud-text)',
          letterSpacing: '-0.01em',
        }}
      >
        {doc.name_ko}
      </h3>
      <div
        style={{
          fontFamily: 'var(--hud-font-mono)',
          fontSize: 10,
          letterSpacing: '0.1em',
          color: 'var(--hud-text-dim)',
          textTransform: 'uppercase',
          marginBottom: 10,
        }}
      >
        {doc.name_en || doc.id}
      </div>

      {/* 가이드 라인 — usage_hint */}
      {doc.usage_hint && (
        <p
          style={{
            margin: '0 0 10px',
            fontSize: 12,
            lineHeight: 1.55,
            color: 'var(--hud-text-dim)',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {doc.usage_hint}
        </p>
      )}

      {/* 메타 — 변수 수 / 모델 / 시간 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          paddingTop: 8,
          borderTop: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
          fontFamily: 'var(--hud-font-mono)',
          fontSize: 10,
          letterSpacing: '0.06em',
          color: 'var(--hud-text-dim)',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <FileText size={11} strokeWidth={2} />
          필수 {requiredCount}/{totalCount}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <Clock size={11} strokeWidth={2} />
          ~30s
        </span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 2 }}>
          {selected ? '선택됨' : '선택'} <ChevronRight size={11} strokeWidth={2} />
        </span>
      </div>

      {/* hover popover — 카드 우측에 절대 위치 */}
      {popoverOpen && doc.example_output && (
        <TemplatePreviewPopover
          doc={doc}
          anchor={cardRef.current}
          onClose={() => setPopoverOpen(false)}
        />
      )}
    </div>
  );
}
