// v3.3 Phase F — DraftCard: 초안 작성 카드 (Module B 진입 링크).

import type { DraftCardPayload } from './types';

interface Props {
  payload: DraftCardPayload;
  onOpen?: (url: string) => void; // navigate(url) — chat.tsx 에서 useNavigate 주입
}

const DOC_TYPE_LABEL: Record<string, string> = {
  '8d_report': '8D Report',
  ecn: 'ECN',
  ppap: 'PPAP',
  email_internal: '사내 이메일',
  report: '보고서',
  draft: '문서 초안',
};

export function DraftCard({ payload, onOpen }: Props) {
  const handleOpen = () => {
    if (!payload.full_view_url) return;
    if (onOpen) {
      onOpen(payload.full_view_url);
    } else {
      window.location.assign(payload.full_view_url);
    }
  };

  const typeLabel = DOC_TYPE_LABEL[payload.doc_type] ?? payload.doc_type ?? '초안';

  return (
    <div className="lg-action-card" data-kind="draft">
      <div className="lg-eyebrow">
        DRAFT · <span className="lg-meta">{typeLabel}</span>
      </div>
      <div style={{ fontSize: 13, color: 'var(--hud-text)', fontWeight: 600 }}>
        {payload.title}
      </div>
      {payload.markdown_preview && (
        <pre
          style={{
            margin: 0,
            padding: '10px 12px',
            borderRadius: 8,
            background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
            border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            fontSize: 12,
            lineHeight: 1.65,
            color: 'var(--hud-text-dim)',
            fontFamily: 'var(--hud-font-sans)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {payload.markdown_preview}
        </pre>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          type="button"
          className="lg-btn sm"
          onClick={handleOpen}
          disabled={!payload.full_view_url}
        >
          Module B 로 열기 →
        </button>
      </div>
    </div>
  );
}
