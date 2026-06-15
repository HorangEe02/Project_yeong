// 부록 K Phase 3 — G5 R&D CAD 도면 표준 검증 카드.

import { useState } from 'react';
import { Ruler } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { CADVerifyData } from '@api/visionTasks';

interface Props { department?: string }

export function CADStandardVerifier({ department = '' }: Props) {
  const [r, setR] = useState<CADVerifyData | null>(null);
  const score = Number(r?.compliance_score ?? 0);
  const color = score >= 80 ? '#16a34a' : score >= 60 ? '#d97706' : '#dc2626';
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<Ruler size={16} />} eyebrow="CAD STANDARD"
        title="CAD 도면 표준 검증" subtitle="도면 사진/PDF → 표제란·치수·공차·재질 표준 적합도 평가" />
      <VisionDropzone<CADVerifyData> task="cad-verify" department={department}
        accept="image/*,application/pdf" hint="도면 이미지 또는 PDF" ctaLabel="표준 검증"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: `1px solid ${color}`, background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>
              {r.drawing_number} · Rev {r.revision}
            </div>
            <span style={{ fontSize: 14, fontWeight: 800, color }}>
              {score}%
            </span>
          </div>
          <KeyValueGrid items={[
            { k: '표제란', v: String(r.title_block_ok) === 'true' ? '✅ 일치' : '⚠ 불일치' },
            { k: '치수 단위', v: r.dimension_unit || '—' },
            { k: '공차 표기', v: r.tolerance_spec || '—' },
            { k: '재질 표기', v: r.material_spec || '—' },
          ]} />
          {r.violations?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6, color: '#dc2626' }}>⚠ 표준 위반</div>
              <ChipRow items={r.violations} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
