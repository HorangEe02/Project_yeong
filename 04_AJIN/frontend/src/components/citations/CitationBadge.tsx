// CitationBadge — 신뢰도 점수 시각화 배지.
// CITATION_UI_SPEC.md §4-1 기준.
// 디자인 시스템 v3.5: 이모지 금지, 상태 글리프(●) + semantic 색상 사용.
//
// confidence >= 0.90 → hud-green  (#2D8A4E)  VERIFIED · 검증됨
// confidence 0.70~   → hud-orange (#E8A317)  PROBABLE · 추정
// confidence < 0.70  → hud-red    (#C0392B)  UNVERIFIED · 미검증

interface CitationBadgeProps {
  /** 0~1 정규화된 신뢰도 (RRF score) */
  confidence: number;
  /** 점수 숫자 표시 여부 (기본 true) */
  showScore?: boolean;
  /** compact 모드 — 글자 크기 축소 (기본 false) */
  compact?: boolean;
}

type ConfidenceTier = 'verified' | 'probable' | 'unverified';

function getTier(confidence: number): ConfidenceTier {
  if (confidence >= 0.9) return 'verified';
  if (confidence >= 0.7) return 'probable';
  return 'unverified';
}

const TIER_CONFIG: Record<
  ConfidenceTier,
  { colorVar: string; label: string; labelKo: string }
> = {
  verified: {
    colorVar: 'var(--hud-green, #2D8A4E)',
    label: 'VERIFIED',
    labelKo: '검증됨',
  },
  probable: {
    colorVar: 'var(--hud-orange, #E8A317)',
    label: 'PROBABLE',
    labelKo: '추정',
  },
  unverified: {
    colorVar: 'var(--hud-red, #C0392B)',
    label: 'UNVERIFIED',
    labelKo: '미검증',
  },
};

export function CitationBadge({
  confidence,
  showScore = true,
  compact = false,
}: CitationBadgeProps) {
  const tier = getTier(confidence);
  const { colorVar, label, labelKo } = TIER_CONFIG[tier];
  const fontSize = compact ? 10 : 11;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontFamily: 'var(--hud-font-mono, monospace)',
        fontSize,
        letterSpacing: '0.08em',
        color: colorVar,
      }}
      aria-label={`출처 신뢰도: ${labelKo} (${(confidence * 100).toFixed(0)}%)`}
      title={`신뢰도 ${(confidence * 100).toFixed(1)}% · ${labelKo}`}
    >
      {/* 디자인 시스템 상태 글리프 — 이모지 금지 */}
      <span aria-hidden="true">&#9679;</span>
      <span>
        {label} · {labelKo}
      </span>
      {showScore && (
        <span style={{ opacity: 0.75 }}>
          {(confidence * 100).toFixed(0)}%
        </span>
      )}
    </span>
  );
}
