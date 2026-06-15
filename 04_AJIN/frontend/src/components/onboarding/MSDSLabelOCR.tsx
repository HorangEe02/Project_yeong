// 부록 K Phase 1 — G4 안전 화학물질 라벨 OCR 카드.

import { useState } from 'react';
import { Beaker } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { MSDSLabelData, VisionTaskResponse } from '@api/visionTasks';

interface Props { department?: string }

export function MSDSLabelOCR({ department = '' }: Props) {
  const [result, setResult] = useState<MSDSLabelData | null>(null);

  const onResult = (resp: VisionTaskResponse<MSDSLabelData>) => {
    if (resp.data._parse_error) return;
    setResult(resp.data);
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader
        icon={<Beaker size={16} />}
        eyebrow="MSDS LABEL OCR"
        title="화학물질 라벨 OCR — MSDS 자동 매칭"
        subtitle="용기 라벨 사진 → GHS 분류·응급조치·PPE 자동 추출"
      />

      <VisionDropzone<MSDSLabelData>
        task="msds-label"
        department={department}
        hint="화학물질 용기 라벨 사진"
        ctaLabel="라벨 분석"
        onResult={onResult}
      />

      {result && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>제품 정보</div>
              <div style={{ fontSize: 14, fontWeight: 700, marginTop: 2 }}>{result.product_name}</div>
              <div style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>{result.manufacturer}</div>
            </div>
            <span style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4,
              border: '1px solid var(--hud-orange)', color: 'var(--hud-orange)', fontWeight: 700,
            }}>{result.hazard_category}</span>
          </div>

          <KeyValueGrid items={[
            { k: 'CAS', v: result.cas_no || '—' },
            { k: '응급조치', v: result.first_aid || '—' },
          ]} />

          {result.ghs_pictograms?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>GHS 그림문자</div>
              <ChipRow items={result.ghs_pictograms} />
            </div>
          )}

          {result.required_ppe?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>필수 PPE</div>
              <ChipRow items={result.required_ppe} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
