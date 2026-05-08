// ScenarioHistoryDrawer — 협업 시나리오 변경 이력 + 1-click 복구.

import { useEffect, useState } from 'react';
import {
  fetchScenarioHistory,
  restoreScenarioVersion,
  type ScenarioHistoryEntry,
} from '@api/admin_scenarios';

interface Props {
  scenarioId: string;
  onClose: () => void;
  onRestored: () => void;
}

const ACTION_LABEL: Record<string, string> = {
  create: '생성',
  update: '수정',
  reset: '기본값 복구',
  deactivate: '비활성화',
  restore: '버전 복구',
};

export function ScenarioHistoryDrawer({ scenarioId, onClose, onRestored }: Props) {
  const [rows, setRows] = useState<ScenarioHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string>('');

  const reload = () => {
    setLoading(true);
    fetchScenarioHistory(scenarioId, 50)
      .then((res) => setRows(res.history))
      .catch((e) => setMsg(`이력 로드 실패: ${(e as Error).message}`))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioId]);

  const handleRestore = async (historyId: number) => {
    if (!confirm(`이 시점으로 복구하시겠습니까? (history #${historyId})`)) return;
    setBusy(historyId);
    setMsg('');
    try {
      await restoreScenarioVersion(scenarioId, historyId);
      setMsg('복구 완료');
      onRestored();
      reload();
    } catch (e) {
      setMsg(`복구 실패: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="변경 이력"
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 'min(520px, 100vw)',
        zIndex: 70,
        background: 'color-mix(in oklab, var(--hud-surface) 94%, transparent)',
        backdropFilter: 'blur(20px) saturate(140%)',
        borderLeft: '1px solid color-mix(in oklab, var(--hud-text) 14%, transparent)',
        boxShadow: '-12px 0 40px rgba(0,0,0,0.35)',
        overflowY: 'auto',
        padding: '22px 22px 32px',
      }}
    >
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">HISTORY · {scenarioId}</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 6 }}>변경 이력</div>
        </div>
        <button type="button" className="lg-btn ghost sm" onClick={onClose}>
          닫기
        </button>
      </div>

      {msg && (
        <div className={msg.includes('실패') ? 'lg-state-pill crit' : 'lg-state-pill ok'} style={{ display: 'inline-block', marginBottom: 12 }}>
          {msg}
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--hud-text-dim)' }}>로딩 중…</div>
      ) : rows.length === 0 ? (
        <div className="lg-empty">변경 이력이 없습니다.</div>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {rows.map((h) => (
            <li
              key={h.id}
              className="lg-card lg-card-tight"
              style={{ margin: 0, padding: '12px 14px' }}
            >
              <div className="lg-card-h" style={{ marginBottom: 6, paddingBottom: 6 }}>
                <div>
                  <span className="lg-role">{ACTION_LABEL[h.action] ?? h.action}</span>
                  <span className="dim mono" style={{ marginLeft: 8, fontSize: 11 }}>
                    #{h.id} · {h.changed_at}
                  </span>
                </div>
                {(h.action === 'update' || h.action === 'restore' || h.action === 'reset') && (
                  <button
                    type="button"
                    className="lg-btn ghost sm"
                    disabled={busy === h.id}
                    onClick={() => handleRestore(h.id)}
                  >
                    {busy === h.id ? '복구중…' : '이 버전으로 복구'}
                  </button>
                )}
              </div>
              <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
                <b>by</b> {h.changed_by || '—'}
                {h.action === 'update' && (
                  <>
                    {' · 변경 필드: '}
                    {Object.keys(h.after).filter((k) => JSON.stringify(h.before[k]) !== JSON.stringify(h.after[k])).join(', ') || '없음'}
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
