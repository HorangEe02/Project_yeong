// ModelHelpPopover — H1 v4.0 · 모델 옆 ⓘ 아이콘 + 클릭 팝오버.
// 프로파일 페이지로 이동하는 "전체 비교" 링크 포함.
// 디자인 시스템 v3.5: glass 표면 + 16px 라운드 + 클릭 외부 영역 닫기.

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Info, X, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { fetchModelCatalogCached, type ModelCatalogItem } from '@api/models';
import { ModelComparisonCard } from './ModelComparisonCard';

interface Props {
  /** 현재 선택된 모델 ID. 카탈로그에서 매칭되는 카드 노출. */
  modelId: string;
  /** 비교 페이지 진입 라벨 (default: "전체 모델 비교"). */
  compareLabel?: string;
}

const POPOVER_WIDTH = 380;

interface Pos {
  top: number;
  left: number;
}

function computePos(anchor: HTMLElement | null): Pos {
  if (!anchor || typeof window === 'undefined') return { top: 0, left: 0 };
  const r = anchor.getBoundingClientRect();
  const vw = window.innerWidth;
  // 우측에 공간 충분하면 우측, 아니면 좌측 (앵커 좌측 정렬)
  let left = r.right + 8;
  if (left + POPOVER_WIDTH > vw - 16) {
    left = Math.max(16, r.left - POPOVER_WIDTH - 8);
  }
  return { top: r.top, left };
}

export function ModelHelpPopover({ modelId, compareLabel = '전체 모델 비교' }: Props) {
  const [open, setOpen] = useState(false);
  const [catalog, setCatalog] = useState<ModelCatalogItem[] | null>(null);
  const [pos, setPos] = useState<Pos>({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();

  // 카탈로그 lazy load — 첫 hover/click 시 한 번만
  useEffect(() => {
    if (!open || catalog) return;
    let cancelled = false;
    fetchModelCatalogCached()
      .then((d) => {
        if (!cancelled) setCatalog(d.items);
      })
      .catch(() => !cancelled && setCatalog([]));
    return () => {
      cancelled = true;
    };
  }, [open, catalog]);

  // 위치 계산 (열린 후 + resize 대응)
  useEffect(() => {
    if (!open) return;
    const update = () => setPos(computePos(triggerRef.current));
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open]);

  // ESC 닫기 + 외부 클릭 닫기
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const matched = useMemo(
    () => catalog?.find((m) => m.id === modelId) ?? null,
    [catalog, modelId],
  );

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`${modelId} 모델 정보`}
        className="lg-btn ghost sm"
        style={{
          padding: 4,
          minWidth: 28,
          width: 28,
          height: 28,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 999,
        }}
        title="이 모델에 대해 알아보기"
      >
        <Info size={14} strokeWidth={2} />
      </button>

      {open &&
        createPortal(
          <>
            {/* scrim — 외부 클릭 닫기 */}
            <div
              onClick={() => setOpen(false)}
              role="presentation"
              style={{
                position: 'fixed',
                inset: 0,
                zIndex: 800,
                background: 'transparent',
              }}
            />
            <div
              role="dialog"
              aria-modal="false"
              aria-label="모델 정보 팝오버"
              style={{
                position: 'fixed',
                top: pos.top,
                left: pos.left,
                width: POPOVER_WIDTH,
                maxHeight: '80vh',
                overflow: 'auto',
                zIndex: 801,
                background: 'var(--glass-bg-strong, var(--hud-surface, #111820))',
                backdropFilter:
                  'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
                WebkitBackdropFilter:
                  'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
                border:
                  '1px solid var(--glass-border, color-mix(in oklab, var(--hud-text) 12%, transparent))',
                borderRadius: 16,
                boxShadow:
                  'inset 0 1px 0 var(--glass-highlight, rgba(255,255,255,0.18)), 0 24px 60px -28px rgba(0,0,0,0.4)',
                padding: 14,
              }}
            >
              {/* 헤더 — 닫기 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 10,
                }}
              >
                <span className="lg-eyebrow" style={{ marginBottom: 0 }}>
                  MODEL HELP · 모델 도움말
                </span>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="lg-btn ghost sm"
                  aria-label="닫기"
                  style={{ padding: 4 }}
                >
                  <X size={12} strokeWidth={2} />
                </button>
              </div>

              {/* 본문 — 매칭 카드 또는 안내 */}
              {!catalog ? (
                <div
                  className="dim"
                  style={{ fontSize: 12, padding: 12, textAlign: 'center' }}
                >
                  모델 카탈로그 불러오는 중…
                </div>
              ) : matched ? (
                <ModelComparisonCard model={matched} />
              ) : (
                <div
                  className="dim"
                  style={{ fontSize: 12, padding: 12, lineHeight: 1.6 }}
                >
                  카탈로그에 등록된 모델 정보가 없습니다 (id:{' '}
                  <code style={{ fontFamily: 'var(--hud-font-mono)' }}>{modelId}</code>).
                  <br />
                  관리자가 추가 등록할 수 있습니다.
                </div>
              )}

              {/* 푸터 — 비교 페이지 진입 */}
              <div
                style={{
                  marginTop: 12,
                  paddingTop: 10,
                  borderTop: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
                  display: 'flex',
                  justifyContent: 'flex-end',
                }}
              >
                <button
                  type="button"
                  className="lg-btn ghost sm"
                  onClick={() => {
                    setOpen(false);
                    navigate('/profile/llm');
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 11,
                  }}
                >
                  {compareLabel} <ExternalLink size={10} strokeWidth={2} />
                </button>
              </div>
            </div>
          </>,
          document.body,
        )}
    </>
  );
}
