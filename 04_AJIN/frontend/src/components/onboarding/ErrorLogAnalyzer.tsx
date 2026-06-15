// 부록 K Phase 3 — G7-IT 에러 로그 스크린샷 분석 카드.

import { useState } from 'react';
import { Bug } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { ErrorLogData } from '@api/visionTasks';

interface Props { department?: string }

export function ErrorLogAnalyzer({ department = '' }: Props) {
  const [r, setR] = useState<ErrorLogData | null>(null);
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<Bug size={16} />} eyebrow="ERROR LOG"
        title="에러 로그 분석 — 원인 + 해결 가이드" subtitle="에러 화면 스크린샷 → 원인 추정·해결 방안·KB 키워드" />
      <VisionDropzone<ErrorLogData> task="error-log" department={department}
        hint="에러 화면/로그 스크린샷" ctaLabel="에러 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <KeyValueGrid items={[
            { k: '에러 메시지', v: r.error_message || '—' },
            { k: '분류', v: r.category || '—' },
            { k: '원인 추정', v: r.likely_cause || '—' },
          ]} />
          {r.stack_excerpt && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>스택 트레이스</div>
              <pre style={{ fontSize: 10, padding: 8, borderRadius: 6,
                background: 'var(--hud-surface)', overflow: 'auto', maxHeight: 120 }}>
                {r.stack_excerpt}
              </pre>
            </div>
          )}
          {r.fix_suggestions?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>해결 방안</div>
              <ol style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {r.fix_suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            </div>
          )}
          {r.related_kb_keywords?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6 }}>KB 검색 키워드</div>
              <ChipRow items={r.related_kb_keywords} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
