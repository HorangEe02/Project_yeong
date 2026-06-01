// 부록 K Phase 3 — G9 ESG 보고서 PDF 분석 카드.

import { useState } from 'react';
import { Leaf } from 'lucide-react';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { ESGData } from '@api/visionTasks';

interface Props { department?: string }

export function ESGReportAnalyzer({ department = '' }: Props) {
  const [r, setR] = useState<ESGData | null>(null);
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<Leaf size={16} />} eyebrow="ESG REPORT"
        title="ESG 보고서 분석" subtitle="ESG 보고서 PDF → 환경·사회·지배구조 핵심 지표 자동 추출" />
      <VisionDropzone<ESGData> task="esg" department={department}
        accept="application/pdf" hint="ESG 보고서 PDF" ctaLabel="ESG 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{r.company}</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>{r.report_year}</div>
            </div>
            <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--hud-primary)',
              padding: '4px 10px', borderRadius: 4, border: '1px solid var(--hud-primary)' }}>
              {r.rating}
            </span>
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>🌱 환경 (E)</div>
            <KeyValueGrid items={[
              { k: '탄소배출', v: `${r.environment?.carbon_emission_t ?? '—'} 톤CO2` },
              { k: '용수', v: String(r.environment?.water_use ?? '—') },
              { k: '재생에너지', v: `${r.environment?.renewable_energy_pct ?? '—'}%` },
            ]} />
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>👥 사회 (S)</div>
            <KeyValueGrid items={[
              { k: '임직원', v: String(r.social?.employees ?? '—') },
              { k: '산재', v: `${r.social?.safety_accidents ?? '—'} 건` },
              { k: '여성 임원', v: `${r.social?.diversity_pct ?? '—'}%` },
            ]} />
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>⚖ 지배구조 (G)</div>
            <KeyValueGrid items={[
              { k: '사외이사', v: `${r.governance?.board_independence_pct ?? '—'}%` },
              { k: '감사 지적', v: `${r.governance?.audit_findings ?? '—'} 건` },
            ]} />
          </div>
        </div>
      )}
    </section>
  );
}
