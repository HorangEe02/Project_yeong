// 부록 K Phase 2 — G7-Finance 재무제표 PDF 분석 카드.

import { useState } from 'react';
import { TrendingDown } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { FinancialStatementData } from '@api/visionTasks';

interface Props { department?: string }

export function FinancialStatementAnalyzer({ department = '' }: Props) {
  const [r, setR] = useState<FinancialStatementData | null>(null);
  const ratingColor = r?.overall_rating === 'A' ? '#16a34a' :
    r?.overall_rating === 'B' ? '#d97706' :
    r?.overall_rating === 'C' ? '#ea580c' :
    r?.overall_rating === 'D' ? '#dc2626' : 'var(--hud-text-dim)';
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<TrendingDown size={16} />} eyebrow="FINANCIAL ANALYSIS"
        title="재무제표 분석 — 협력사 위험 평가" subtitle="재무제표 PDF → 부채비율·유동성·위험 신호 자동 추출" />
      <VisionDropzone<FinancialStatementData> task="financial-statement" department={department}
        accept="application/pdf" hint="재무제표 PDF" ctaLabel="재무제표 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: `1px solid ${ratingColor}`, background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{r.company}</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>회계연도: {r.fiscal_year}</div>
            </div>
            <span style={{ fontSize: 14, fontWeight: 800, color: ratingColor,
              padding: '4px 10px', borderRadius: 4, border: `1px solid ${ratingColor}` }}>
              {r.overall_rating}
            </span>
          </div>
          <KeyValueGrid items={[
            { k: '매출', v: String(r.revenue ?? '—') },
            { k: '영업이익', v: String(r.operating_profit ?? '—') },
            { k: '순이익', v: String(r.net_profit ?? '—') },
            { k: '자산총계', v: String(r.total_assets ?? '—') },
            { k: '부채총계', v: String(r.total_liabilities ?? '—') },
            { k: '자본총계', v: String(r.equity ?? '—') },
            { k: '부채비율', v: `${r.debt_ratio ?? '—'}%` },
            { k: '유동비율', v: `${r.current_ratio ?? '—'}%` },
          ]} />
          {r.risk_signals?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6, color: '#dc2626' }}>⚠ 위험 신호</div>
              <ChipRow items={r.risk_signals} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
