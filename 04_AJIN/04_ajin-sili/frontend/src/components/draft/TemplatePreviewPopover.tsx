// TemplatePreviewPopover — Module B · 템플릿 카드 hover 미리보기.
// B1 v4.0: anchor 카드 우측/하단 적응형 위치 + 변수 리스트 + 출력 예시.
// 디자인 시스템 v3.5: glass 표면 + 16px 라운드 + lg-eyebrow.

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles, Building2 } from 'lucide-react';
import type { DocTypeMeta } from '@/types/draft';

interface Props {
  doc: DocTypeMeta;
  anchor: HTMLElement | null;
  onClose: () => void;
}

interface Position {
  top: number;
  left: number;
  side: 'right' | 'left' | 'below';
}

const POPOVER_WIDTH = 360;
const POPOVER_GAP = 8;

function computePosition(anchor: HTMLElement | null): Position {
  if (!anchor || typeof window === 'undefined') {
    return { top: 0, left: 0, side: 'right' };
  }
  const rect = anchor.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  // 우측 공간이 충분하면 우측, 아니면 좌측, 그것도 좁으면 카드 아래
  const rightSpace = vw - rect.right - POPOVER_GAP;
  const leftSpace = rect.left - POPOVER_GAP;
  const side: Position['side'] =
    rightSpace >= POPOVER_WIDTH ? 'right' : leftSpace >= POPOVER_WIDTH ? 'left' : 'below';

  let top = rect.top;
  let left = rect.right + POPOVER_GAP;
  if (side === 'left') {
    left = rect.left - POPOVER_WIDTH - POPOVER_GAP;
  } else if (side === 'below') {
    top = rect.bottom + POPOVER_GAP;
    left = rect.left;
  }

  // 화면 하단 초과 방지
  const POPOVER_MAX_HEIGHT = 480;
  if (top + POPOVER_MAX_HEIGHT > vh - 16) {
    top = Math.max(16, vh - POPOVER_MAX_HEIGHT - 16);
  }
  return { top, left, side };
}

export function TemplatePreviewPopover({ doc, anchor, onClose }: Props) {
  const [pos, setPos] = useState<Position>(() => computePosition(anchor));

  useEffect(() => {
    setPos(computePosition(anchor));
    const onResize = () => setPos(computePosition(anchor));
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', onResize, true);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onResize, true);
    };
  }, [anchor]);

  const requiredVars = (doc.var_metadata ?? []).filter((v) => v.required);
  const optionalVars = (doc.var_metadata ?? []).filter((v) => !v.required);

  return createPortal(
    <div
      role="tooltip"
      onMouseEnter={() => {/* 마우스가 popover 위면 유지 */}}
      onMouseLeave={onClose}
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        width: POPOVER_WIDTH,
        maxHeight: 480,
        overflow: 'auto',
        zIndex: 900,
        background: 'var(--glass-bg-strong, var(--hud-surface, #111820))',
        backdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
        WebkitBackdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
        border:
          '1px solid var(--glass-border, color-mix(in oklab, var(--hud-text) 12%, transparent))',
        borderRadius: 16,
        padding: 16,
        boxShadow:
          'inset 0 1px 0 var(--glass-highlight, rgba(255,255,255,0.18)), 0 24px 60px -28px rgba(0,0,0,0.4)',
      }}
    >
      <div className="lg-eyebrow" style={{ marginBottom: 4 }}>
        TEMPLATE PREVIEW · 미리보기
      </div>
      <h4
        style={{
          margin: '0 0 12px',
          fontSize: 16,
          fontWeight: 600,
          color: 'var(--hud-text)',
        }}
      >
        {doc.name_ko}
      </h4>

      {/* 부서 추천 (전체) */}
      {doc.dept_recommend && doc.dept_recommend.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}
          >
            <Building2 size={11} strokeWidth={2} /> 추천 부서
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {doc.dept_recommend.map((d) => (
              <span key={d} className="lg-tag mod" style={{ fontSize: 10 }}>
                {d}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 출력 예시 */}
      {doc.example_output && (
        <div style={{ marginBottom: 12 }}>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}
          >
            <Sparkles size={11} strokeWidth={2} /> 예시 출력
          </div>
          <div
            style={{
              padding: 10,
              borderRadius: 12,
              background: 'color-mix(in oklab, var(--hud-surface) 70%, transparent)',
              border: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
              fontSize: 12,
              lineHeight: 1.55,
              color: 'var(--hud-text-dim)',
              fontStyle: 'italic',
            }}
          >
            {doc.example_output}
          </div>
        </div>
      )}

      {/* 필수 변수 */}
      {requiredVars.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
            필수 변수 ({requiredVars.length})
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: 12 }}>
            {requiredVars.map((v) => (
              <li
                key={v.name}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '3px 0',
                }}
              >
                <span>
                  <span style={{ color: 'var(--hud-primary)', marginRight: 4 }}>★</span>
                  {v.label_ko || v.name}
                </span>
                <span
                  className="mono"
                  style={{
                    fontFamily: 'var(--hud-font-mono)',
                    fontSize: 10,
                    color: 'var(--hud-text-muted)',
                    letterSpacing: '0.04em',
                  }}
                >
                  {v.group}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 선택 변수 (요약) */}
      {optionalVars.length > 0 && (
        <div>
          <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
            선택 변수 ({optionalVars.length})
          </div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--hud-text-dim)',
              lineHeight: 1.6,
              letterSpacing: '0.02em',
            }}
          >
            {optionalVars.map((v) => v.label_ko || v.name).join(' · ')}
          </div>
        </div>
      )}
    </div>,
    document.body,
  );
}
