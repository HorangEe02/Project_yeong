// ModelComparisonCard — H1 v4.0 · 단일 모델 정보 카드.
// size·speed·quality 막대 + 한국어 요약 + best_for 칩.
// 디자인 시스템 v3.5: lg-card-tight + lg-pill + lg-tag + 16/12 라운드.

import { Image as ImageIcon, Languages, Sparkles, Zap, Award, ChevronRight } from 'lucide-react';
import type { ModelCatalogItem, ModelSpeed, ModelQuality } from '@api/models';

interface Props {
  model: ModelCatalogItem;
  /** 카드 우상단 추천 배지 표시 (특정 컨텍스트에서 추천된 모델). */
  recommended?: boolean;
  /** 현재 선택된 모델인지 (강조 outline). */
  selected?: boolean;
  /** 카드 클릭 시 호출 (선택). 미제공 시 비활성. */
  onSelect?: (id: string) => void;
}

const SPEED_BARS: Record<ModelSpeed, number> = { fast: 5, medium: 3, slow: 2 };
const QUALITY_BARS: Record<ModelQuality, number> = { good: 3, high: 4, very_high: 5 };

const FEATURE_LABEL: Record<string, string> = {
  draft: '초안',
  onboarding: '온보딩',
  search: '검색',
  compliance: '규제',
  equipment: '설비',
  admin: '관리',
};

function Bar({ value, max = 5 }: { value: number; max?: number }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }} aria-hidden>
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          style={{
            display: 'inline-block',
            width: 6,
            height: 10,
            borderRadius: 999,
            background:
              i < value
                ? 'var(--hud-primary)'
                : 'color-mix(in oklab, var(--hud-text) 8%, transparent)',
          }}
        />
      ))}
    </span>
  );
}

export function ModelComparisonCard({ model, recommended, selected, onSelect }: Props) {
  const interactive = typeof onSelect === 'function';
  const speedBar = SPEED_BARS[model.speed] ?? 3;
  const qualityBar = QUALITY_BARS[model.quality] ?? 3;

  return (
    <div
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={interactive ? () => onSelect!(model.id) : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect!(model.id);
              }
            }
          : undefined
      }
      className="lg-card lg-card-tight"
      style={{
        marginBottom: 0,
        cursor: interactive ? 'pointer' : 'default',
        outline: selected
          ? '2px solid var(--hud-primary)'
          : '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
        outlineOffset: selected ? -2 : 0,
        transition: 'all 0.15s ease',
      }}
    >
      {/* 헤더 — eyebrow + 추천 배지 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          marginBottom: 6,
        }}
      >
        <span className="lg-eyebrow" style={{ marginBottom: 0 }}>
          MODEL · 모델 정보
        </span>
        {recommended && (
          <span
            className="lg-state-pill ok"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
          >
            <Award size={9} strokeWidth={2} /> 추천
          </span>
        )}
      </div>

      {/* 제목 + 모델 ID */}
      <h3
        style={{
          margin: '0 0 4px',
          fontSize: 16,
          fontWeight: 600,
          color: 'var(--hud-text)',
          letterSpacing: '-0.01em',
        }}
      >
        {model.display}
      </h3>
      <div
        className="mono"
        style={{
          fontFamily: 'var(--hud-font-mono)',
          fontSize: 10,
          letterSpacing: '0.1em',
          color: 'var(--hud-text-muted)',
          marginBottom: 10,
        }}
      >
        {model.id}
      </div>

      {/* 태그 칩 */}
      {model.tags_ko.length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 10 }}>
          {model.tags_ko.map((t) => (
            <span key={t} className="lg-pill" style={{ fontSize: 10 }}>
              {t}
            </span>
          ))}
          {model.vision && (
            <span
              className="lg-tag mod"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
            >
              <ImageIcon size={10} strokeWidth={2} /> 비전
            </span>
          )}
          <span
            className="lg-tag mod"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
          >
            <Languages size={10} strokeWidth={2} /> {model.lang === 'korean' ? '한국어' : '다국어'}
          </span>
        </div>
      )}

      {/* size / speed / quality 메트릭 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          gap: '4px 10px',
          fontSize: 11,
          color: 'var(--hud-text-dim)',
          marginBottom: 10,
        }}
      >
        <span>Size</span>
        <span style={{ fontFamily: 'var(--hud-font-mono)' }}>{model.size_gb} GB</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
          <Zap size={10} strokeWidth={2} /> Speed
        </span>
        <span><Bar value={speedBar} /></span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
          <Sparkles size={10} strokeWidth={2} /> Quality
        </span>
        <span><Bar value={qualityBar} /></span>
      </div>

      {/* 한 줄 요약 */}
      {model.summary_ko && (
        <p
          style={{
            margin: '0 0 10px',
            fontSize: 12,
            lineHeight: 1.55,
            color: 'var(--hud-text)',
          }}
        >
          {model.summary_ko}
        </p>
      )}

      {/* 이럴 때 / 피하기 */}
      {(model.use_when_ko || model.avoid_when_ko) && (
        <div
          style={{
            paddingTop: 10,
            borderTop: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            fontSize: 11,
            lineHeight: 1.5,
          }}
        >
          {model.use_when_ko && (
            <div>
              <span style={{ color: 'var(--hud-green, #2D8A4E)', fontWeight: 600 }}>
                ✓ 이럴 때
              </span>{' '}
              <span style={{ color: 'var(--hud-text-dim)' }}>{model.use_when_ko}</span>
            </div>
          )}
          {model.avoid_when_ko && (
            <div>
              <span style={{ color: 'var(--hud-red, #C0392B)', fontWeight: 600 }}>
                ✗ 피하기
              </span>{' '}
              <span style={{ color: 'var(--hud-text-dim)' }}>{model.avoid_when_ko}</span>
            </div>
          )}
        </div>
      )}

      {/* 추천 기능 칩 */}
      {model.best_for.length > 0 && (
        <div
          style={{
            marginTop: 10,
            paddingTop: 10,
            borderTop: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
          }}
        >
          <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
            추천 기능
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {model.best_for.map((b) => (
              <span key={b} className="lg-tag" style={{ fontSize: 10 }}>
                {FEATURE_LABEL[b] ?? b}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 선택 인디케이터 */}
      {interactive && (
        <div
          style={{
            marginTop: 10,
            display: 'flex',
            justifyContent: 'flex-end',
            fontSize: 11,
            color: selected ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
            fontFamily: 'var(--hud-font-mono)',
            letterSpacing: '0.08em',
          }}
        >
          {selected ? '선택됨' : '선택'} <ChevronRight size={11} strokeWidth={2} />
        </div>
      )}
    </div>
  );
}
