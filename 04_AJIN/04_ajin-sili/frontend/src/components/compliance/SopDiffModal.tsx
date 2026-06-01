// D4 — SOP diff modal: 변경 1건 → 영향 SOP 사이드바이사이드 diff.

import { useEffect, useState, type ReactElement } from 'react';
import { Modal } from '@components/ui/Modal';
import { fetchSopDiff, type SopDiffResponse, type SopDiffBlock } from '@api/compliance';

interface Props {
  changeId: number | null;
  changeTitle?: string;
  isOpen: boolean;
  onClose: () => void;
}

function renderDiff(blocks: SopDiffBlock[]): ReactElement {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
      <div>
        <div className="lg-eyebrow" style={{ marginBottom: 6 }}>BEFORE · 변경 전</div>
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'keep-all' }}>
          {blocks.map((b, i) => {
            if (b.op === 'equal') return <span key={i}>{b.old}</span>;
            if (b.op === 'insert') return null;
            return (
              <mark key={i} style={{ background: 'rgba(197,48,48,0.18)', color: '#c53030' }}>
                {b.old}
              </mark>
            );
          })}
        </div>
      </div>
      <div>
        <div className="lg-eyebrow" style={{ marginBottom: 6 }}>AFTER · 변경 후</div>
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'keep-all' }}>
          {blocks.map((b, i) => {
            if (b.op === 'equal') return <span key={i}>{b.new}</span>;
            if (b.op === 'delete') return null;
            return (
              <mark key={i} style={{ background: 'rgba(56,161,105,0.18)', color: '#38a169' }}>
                {b.new}
              </mark>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function SopDiffModal({ changeId, changeTitle, isOpen, onClose }: Props) {
  const [data, setData] = useState<SopDiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || changeId === null) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    fetchSopDiff(changeId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [isOpen, changeId]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl" title={`SOP 영향 분석${changeTitle ? ` — ${changeTitle}` : ''}`}>
      {loading && <div className="lg-sub" style={{ padding: 16 }}>분석 중…</div>}
      {error && <div className="lg-error" style={{ padding: 12 }}>{error}</div>}
      {data && (
        <div>
          <div className="lg-sub" style={{ marginBottom: 12 }}>
            영향 SOP {data.match_count}건 — 규제 유형 {data.regulation_type || '—'}
          </div>
          {data.affected_sops.length === 0 && (
            <div
              style={{
                padding: 16,
                border: '1px dashed var(--hud-border)',
                borderRadius: 2,
                color: 'var(--hud-text-dim)',
              }}
            >
              관련 SOP가 등록되지 않았거나 매칭이 없습니다. 사내 SOP 를{' '}
              <code>POST /api/compliance/sop</code> 로 적재해 주세요.
            </div>
          )}
          {data.affected_sops.map((sop) => (
            <div
              key={sop.sop_id}
              style={{
                marginBottom: 16,
                padding: 12,
                border: '1px solid var(--hud-border)',
                borderRadius: 2,
              }}
            >
              <div className="lg-eyebrow" style={{ marginBottom: 4 }}>
                SOP #{sop.sop_id} · {sop.dept || '—'} · v{sop.version} · {sop.match_method.toUpperCase()} 매칭
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{sop.sop_title}</div>
              <div className="lg-eyebrow" style={{ marginBottom: 4 }}>REGULATION DIFF</div>
              {renderDiff(sop.regulation_diff)}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
