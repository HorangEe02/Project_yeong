// 부록 K Phase 2 — G4 안전 사고 현장 사진 분석 카드.

import { useState } from 'react';
import { Siren } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { IncidentData } from '@api/visionTasks';

interface Props { department?: string }

export function IncidentSceneAnalyzer({ department = '' }: Props) {
  const [r, setR] = useState<IncidentData | null>(null);
  const sevColor = r?.severity_estimate === 'critical' ? '#dc2626'
    : r?.severity_estimate === 'major' ? '#d97706'
    : '#16a34a';
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<Siren size={16} />} eyebrow="INCIDENT ANALYZER"
        title="사고 현장 분석 — 보고서 자동 prefill" subtitle="현장 사진 → 위험 요소 + 4M 원인 + PPE 점검 + 보고서 요약" />
      <VisionDropzone<IncidentData> task="incident" department={department}
        hint="사고 현장 사진" ctaLabel="현장 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: `1px solid ${sevColor}`, background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>현장 분석</div>
            <span style={{ fontSize: 10, fontWeight: 700, color: sevColor,
              padding: '2px 8px', borderRadius: 4, border: `1px solid ${sevColor}` }}>
              {(r.severity_estimate || '').toUpperCase()}
            </span>
          </div>
          <KeyValueGrid items={[
            { k: '현장 유형', v: r.scene_type || '—' },
            { k: '보고서 요약', v: r.report_summary || '—' },
          ]} />
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 10, opacity: 0.6 }}>관찰된 위험 요소</div>
            <ChipRow items={r.observed_hazards ?? []} />
          </div>
          {r.potential_4m_causes && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>4M 원인 후보</div>
              <KeyValueGrid items={[
                { k: 'Man', v: r.potential_4m_causes.man || '—' },
                { k: 'Machine', v: r.potential_4m_causes.machine || '—' },
                { k: 'Material', v: r.potential_4m_causes.material || '—' },
                { k: 'Method', v: r.potential_4m_causes.method || '—' },
              ]} />
            </div>
          )}
          {r.immediate_actions?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>즉시 조치</div>
              <ol style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {r.immediate_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ol>
            </div>
          )}
          {r.required_ppe_missing?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6, color: '#dc2626' }}>⚠ 미착용 PPE 추정</div>
              <ChipRow items={r.required_ppe_missing} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
