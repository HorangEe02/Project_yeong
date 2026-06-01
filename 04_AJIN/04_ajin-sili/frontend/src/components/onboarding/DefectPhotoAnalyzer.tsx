// 부록 K Phase 1 — G3 생산현장 불량품 사진 분석 카드.

import { useState } from 'react';
import { AlertOctagon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { DefectData, VisionTaskResponse } from '@api/visionTasks';

interface Props { department?: string }

export function DefectPhotoAnalyzer({ department = '' }: Props) {
  const navigate = useNavigate();
  const [result, setResult] = useState<DefectData | null>(null);

  const onResult = (resp: VisionTaskResponse<DefectData>) => {
    if (resp.data._parse_error) return;
    setResult(resp.data);
  };

  const onCreate8D = () => {
    if (!result) return;
    const prefill = `[불량 발생 — 8D Report 초안]

결함 유형: ${result.defect_type}
심각도: ${result.severity}
추정 위치: ${result.estimated_location}

원인 후보 (4M):
${(result.possible_causes ?? []).map((c, i) => `  ${i + 1}. ${c}`).join('\n')}

즉시 격리 조치 후보:
${(result.containment_actions ?? []).map((a, i) => `  ${i + 1}. ${a}`).join('\n')}

권장 8D 단계: ${result.recommended_8d_step}

위 정보 기반 D1~D8 단계 상세화하여 8D Report 작성.`;
    navigate('/draft', { state: { prefill, doc_type: '8D' } });
  };

  const sevColor = result?.severity === 'critical' ? '#dc2626'
    : result?.severity === 'major' ? '#d97706'
    : result?.severity === 'minor' ? '#16a34a'
    : 'var(--hud-text-dim)';

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader
        icon={<AlertOctagon size={16} />}
        eyebrow="DEFECT ANALYZER"
        title="불량품 사진 분석 — 8D 자동 prefill"
        subtitle="외관 결함 사진 → 유형·원인 4M 추정 → 8D Report 초안 자동 생성"
      />

      <VisionDropzone<DefectData>
        task="defect"
        department={department}
        hint="불량 부품 사진을 드래그·클릭"
        ctaLabel="결함 분석"
        onResult={onResult}
      />

      {result && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: `1px solid ${sevColor}`, background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>분석 결과</div>
            <span style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4,
              border: `1px solid ${sevColor}`, color: sevColor, fontWeight: 700,
            }}>{(result.severity || '').toUpperCase()}</span>
          </div>
          <KeyValueGrid items={[
            { k: '결함 유형', v: result.defect_type },
            { k: '추정 위치', v: result.estimated_location || '—' },
            { k: '원인 후보', v: (result.possible_causes ?? []).join(' / ') || '—' },
            { k: '격리 조치', v: (result.containment_actions ?? []).join(' / ') || '—' },
            { k: '권장 8D', v: result.recommended_8d_step },
          ]} />
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={onCreate8D} className="lg-btn primary" style={{ padding: '6px 14px' }}>
              8D Report 작성 →
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
