// 부록 K Phase 3 — G10 교육 수료증 OCR 카드.

import { useState } from 'react';
import { Award } from 'lucide-react';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { CertificateData } from '@api/visionTasks';

interface Props { department?: string }

export function CertificateOCR({ department = '' }: Props) {
  const [r, setR] = useState<CertificateData | null>(null);
  const eligible = String(r?.hrd_eligible) === 'true';
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<Award size={16} />} eyebrow="CERTIFICATE OCR"
        title="교육 수료증 OCR — HRD 등록" subtitle="외부 교육 수료증 사진 → 강좌·이수일·시간 추출 + HRD 시스템 등록 가이드" />
      <VisionDropzone<CertificateData> task="certificate" department={department}
        hint="교육 수료증 사진/PDF" ctaLabel="수료증 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <KeyValueGrid items={[
            { k: '강좌명', v: r.course_name || '—' },
            { k: '발급기관', v: r.institution || '—' },
            { k: '이수일', v: r.completion_date || '—' },
            { k: '이수 시간', v: `${r.hours ?? '—'} 시간` },
            { k: '수료증 No.', v: r.certificate_no || '—' },
            { k: '수료자', v: r.recipient || '—' },
            { k: '분류', v: r.category || '—' },
            { k: 'HRD 등록', v: eligible ? '✅ 등록 가능' : '⚠ 검토 필요' },
          ]} />
        </div>
      )}
    </section>
  );
}
