// 부록 K Phase 2 — G9 법무 계약서 PDF 분석 카드.

import { useState } from 'react';
import { ScrollText } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { ContractData } from '@api/visionTasks';

interface Props { department?: string }

export function ContractAnalyzer({ department = '' }: Props) {
  const [r, setR] = useState<ContractData | null>(null);
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<ScrollText size={16} />} eyebrow="CONTRACT ANALYZER"
        title="계약서 분석 — 10 체크리스트" subtitle="계약서 PDF/사진 → 핵심 조항 추출 + 위험 조항 자동 표시" />
      <VisionDropzone<ContractData> task="contract" department={department}
        accept="application/pdf,image/*" hint="계약서 PDF 또는 사진" ctaLabel="계약서 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>핵심 조항</div>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--hud-primary)' }}>
              체크리스트 {r.checklist_score}/10
            </span>
          </div>
          <KeyValueGrid items={[
            { k: '당사자', v: (r.parties ?? []).join(' · ') || '—' },
            { k: '기간', v: r.duration || '—' },
            { k: '대금 조건', v: r.payment_terms || '—' },
            { k: '품질 보증', v: r.warranty || '—' },
            { k: '지적재산권', v: r.ip_clause || '—' },
            { k: '준거법', v: r.governing_law || '—' },
            { k: '불가항력', v: r.force_majeure || '—' },
            { k: '해지 조건', v: r.termination || '—' },
            { k: '하자 보수', v: r.defect_warranty || '—' },
            { k: '비밀유지', v: r.confidentiality || '—' },
          ]} />
          {r.risk_flags?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6, color: '#dc2626' }}>⚠ 위험 조항</div>
              <ChipRow items={r.risk_flags} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
