// 부록 K Phase 3 — G3 생산현장 5S 점수 카드.

import { useState } from 'react';
import { ListChecks } from 'lucide-react';
import { CardHeader, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { FiveSData } from '@api/visionTasks';

interface Props { department?: string }

const LABELS: Record<string, string> = {
  seiri: '정리', seiton: '정돈', seiso: '청소', seiketsu: '청결', shitsuke: '습관',
};

export function FiveSScorer({ department = '' }: Props) {
  const [r, setR] = useState<FiveSData | null>(null);
  const total = Number(r?.total_score ?? 0);
  const totalColor = total >= 80 ? '#16a34a' : total >= 60 ? '#d97706' : '#dc2626';
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<ListChecks size={16} />} eyebrow="5S SCORER"
        title="작업장 5S 점수" subtitle="작업장 사진 → 5S 5축 자동 점수 (0~20 각, 총 100)" />
      <VisionDropzone<FiveSData> task="5s" department={department}
        hint="작업장·라인 사진" ctaLabel="5S 평가"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: `1px solid ${totalColor}`, background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>5S 점수</div>
            <span style={{ fontSize: 14, fontWeight: 800, color: totalColor }}>{total}/100</span>
          </div>
          {r.scores && (
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(r.scores).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ minWidth: 60, fontSize: 11 }}>{LABELS[k] || k}</span>
                  <div style={{ flex: 1, height: 6, background: 'var(--hud-surface)',
                    borderRadius: 999, overflow: 'hidden' }}>
                    <div style={{ width: `${(Number(v) / 20) * 100}%`, height: '100%',
                      background: 'var(--hud-primary)' }} />
                  </div>
                  <span style={{ minWidth: 30, fontSize: 11, textAlign: 'right' }}>{v}/20</span>
                </div>
              ))}
            </div>
          )}
          {r.strengths?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>✅ 잘 된 점</div>
              <ChipRow items={r.strengths} />
            </div>
          )}
          {r.priority_actions?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>🔧 우선 조치</div>
              <ol style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {r.priority_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ol>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
