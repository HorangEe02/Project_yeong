// 부록 K Phase 2 — G7-HR 이력서 분석 카드.

import { useState } from 'react';
import { ClipboardCheck } from 'lucide-react';
import { CardHeader, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { ResumeData } from '@api/visionTasks';

interface Props { department?: string }

export function ResumeAnalyzer({ department = '' }: Props) {
  const [r, setR] = useState<ResumeData | null>(null);
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<ClipboardCheck size={16} />} eyebrow="RESUME ANALYZER"
        title="이력서 분석 — 면접 질문 자동 생성" subtitle="이력서 PDF → 경력·강점 요약 + JD 일치도 + 맞춤 면접 질문 5개" />
      <VisionDropzone<ResumeData> task="resume" department={department}
        accept="application/pdf,image/*" hint="이력서 PDF·이미지" ctaLabel="이력서 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{r.name}</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>{r.email} · {r.phone}</div>
            </div>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--hud-primary)' }}>
              JD 일치 {r.fit_score}%
            </span>
          </div>
          <div style={{ marginTop: 10, fontSize: 10, opacity: 0.6 }}>학력</div>
          <ChipRow items={(r.education ?? []).map(e => `${e.school} · ${e.major} (${e.graduated})`)} />
          <div style={{ marginTop: 10, fontSize: 10, opacity: 0.6 }}>경력</div>
          <ChipRow items={(r.experience ?? []).map(e => `${e.company} · ${e.role} (${e.years})`)} />
          <div style={{ marginTop: 10, fontSize: 10, opacity: 0.6 }}>스킬</div>
          <ChipRow items={r.skills ?? []} />
          {r.interview_questions?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>맞춤 면접 질문</div>
              <ol style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {r.interview_questions.map((q, i) => <li key={i}>{q}</li>)}
              </ol>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
