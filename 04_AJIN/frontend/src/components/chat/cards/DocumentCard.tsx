// v3.3 Phase F — DocumentCard: 문서 검색 결과 + 다운로드 액션.

import type { DocumentCardPayload } from './types';

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

interface Props {
  payload: DocumentCardPayload;
}

export function DocumentCard({ payload }: Props) {
  const items = payload.items ?? [];
  const total = payload.total ?? items.length;

  if (total === 0) {
    return (
      <div className="lg-action-card" data-kind="document">
        <div className="lg-eyebrow">DOC · 0건</div>
        <div style={{ fontSize: 13, color: 'var(--hud-text-dim)' }}>
          "{payload.query}" 에 대한 문서를 찾지 못했습니다.
        </div>
      </div>
    );
  }

  return (
    <div className="lg-action-card" data-kind="document">
      <div className="lg-eyebrow">
        DOC · {total}건 <span className="lg-meta">{payload.query}</span>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((item) => (
          <li
            key={item.doc_id || item.title}
            style={{
              padding: '10px 12px',
              borderRadius: 10,
              background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
              <strong style={{ color: 'var(--hud-text)', fontSize: 13 }}>{item.title}</strong>
              {item.doc_type && (
                <span className="lg-meta" style={{ fontSize: 10 }}>
                  {item.doc_type}
                </span>
              )}
              {typeof item.score === 'number' && item.score > 0 && (
                <span className="lg-meta" style={{ fontSize: 10 }}>
                  score {item.score.toFixed(2)}
                </span>
              )}
            </div>
            {item.snippet && (
              <p
                style={{
                  margin: '6px 0 0',
                  fontSize: 12,
                  lineHeight: 1.6,
                  color: 'var(--hud-text-dim)',
                }}
              >
                {item.snippet}
              </p>
            )}
            {item.download_url && (
              <div style={{ marginTop: 8 }}>
                <a
                  href={`${API_URL}${item.download_url}`}
                  target="_blank"
                  rel="noreferrer"
                  className="lg-btn ghost sm"
                  style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                >
                  ↓ 다운로드
                </a>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
