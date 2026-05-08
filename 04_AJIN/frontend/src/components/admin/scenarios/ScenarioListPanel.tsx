// ScenarioListPanel — 협업 시나리오 관리 표 + 신규 추가 / 편집 / 이력 / Reset.
// 사용처: SystemToolsTab 내부 + LearnTab 우상단 모달

import { useCallback, useEffect, useState } from 'react';
import {
  fetchScenarios,
  type ScenarioItem,
} from '@api/admin_scenarios';
import { fetchDepartmentTree, type DepartmentTreeResponse } from '@api/admin';
import { ScenarioEditDrawer } from './ScenarioEditDrawer';
import { ScenarioHistoryDrawer } from './ScenarioHistoryDrawer';

interface Props {
  embedded?: boolean;  // true 면 외부 카드 안에 들어가므로 hero 생략
}

function StatusPill({ item }: { item: ScenarioItem }) {
  if (!item.is_active) {
    return <span className="lg-state-pill" style={{ background: 'color-mix(in oklab, var(--hud-text) 12%, transparent)', color: 'var(--hud-text-dim)' }}>비활성</span>;
  }
  if (item.is_system_default) {
    return <span className="lg-state-pill ok">시드</span>;
  }
  return <span className="lg-state-pill warn">사용자 추가</span>;
}

export function ScenarioListPanel({ embedded = false }: Props) {
  const [items, setItems] = useState<ScenarioItem[]>([]);
  const [tree, setTree] = useState<DepartmentTreeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editTarget, setEditTarget] = useState<{ mode: 'create' | 'edit'; item: ScenarioItem | null } | null>(null);
  const [historyTarget, setHistoryTarget] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive' | 'seed' | 'custom'>('active');
  const [q, setQ] = useState('');

  const reload = useCallback(() => {
    setLoading(true);
    fetchScenarios(true)
      .then((res) => setItems(res.items))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
    fetchDepartmentTree().then(setTree).catch((e) => setError((e as Error).message));
  }, [reload]);

  const visible = items.filter((it) => {
    if (filter === 'active' && !it.is_active) return false;
    if (filter === 'inactive' && it.is_active) return false;
    if (filter === 'seed' && !it.is_system_default) return false;
    if (filter === 'custom' && it.is_system_default) return false;
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      return [it.scenario_id, it.situation, it.requesting_dept, ...it.trigger_keywords]
        .some((s) => s.toLowerCase().includes(needle));
    }
    return true;
  });

  return (
    <>
      <div className="lg-card" style={embedded ? { margin: 0 } : undefined}>
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">COLLABORATION SCENARIOS</div>
            <h2 className="lg-h2" style={{ marginTop: 4 }}>협업 시나리오 관리</h2>
            <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', marginTop: 4 }}>
              시드 5종 + 사용자 추가 시나리오. HR_ADMIN+ 만 편집 가능. 모든 변경은 이력에 기록.
            </div>
          </div>
          <button
            type="button"
            className="lg-btn"
            onClick={() => setEditTarget({ mode: 'create', item: null })}
          >
            + 신규 시나리오
          </button>
        </div>

        <div className="lg-filter-grid" style={{ gridTemplateColumns: '1fr 1fr 2fr', marginBottom: 12 }}>
          <div className="lg-field">
            <label>필터</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
              <option value="all">전체</option>
              <option value="active">활성</option>
              <option value="inactive">비활성</option>
              <option value="seed">시스템 시드</option>
              <option value="custom">사용자 추가</option>
            </select>
          </div>
          <div className="lg-field">
            <label>총</label>
            <input value={`${visible.length} / ${items.length}`} readOnly />
          </div>
          <div className="lg-field">
            <label>검색 (id / 상황 / 부서 / 키워드)</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="검색어 입력..." />
          </div>
        </div>

        {error && (
          <div className="lg-state-pill crit" style={{ display: 'inline-block', marginBottom: 10 }}>
            {error}
          </div>
        )}

        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>상황</th>
                <th>요청 부서</th>
                <th>본부 한정</th>
                <th>언어</th>
                <th>키워드</th>
                <th>상태</th>
                <th>업데이트</th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((it) => (
                <tr key={it.scenario_id}>
                  <td className="mono">{it.scenario_id}</td>
                  <td style={{ maxWidth: 300, whiteSpace: 'normal' }}>{it.situation || '—'}</td>
                  <td>{it.requesting_dept || '—'}</td>
                  <td className="dim">{it.scope_division || '전사'}</td>
                  <td className="mono">{it.lang}</td>
                  <td className="dim" style={{ maxWidth: 220, whiteSpace: 'normal' }}>
                    {it.trigger_keywords.slice(0, 3).join(' · ')}
                    {it.trigger_keywords.length > 3 && ` 외 ${it.trigger_keywords.length - 3}`}
                  </td>
                  <td><StatusPill item={it} /></td>
                  <td className="dim mono">{it.updated_at?.slice(0, 16) || '—'}</td>
                  <td>
                    <button className="lg-btn ghost sm" onClick={() => setEditTarget({ mode: 'edit', item: it })}>
                      편집
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && visible.length === 0 && (
                <tr><td colSpan={9} style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}>조건에 맞는 시나리오가 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editTarget && (
        <ScenarioEditDrawer
          mode={editTarget.mode}
          initial={editTarget.item}
          tree={tree}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            reload();
          }}
          onShowHistory={(id) => setHistoryTarget(id)}
        />
      )}

      {historyTarget && (
        <ScenarioHistoryDrawer
          scenarioId={historyTarget}
          onClose={() => setHistoryTarget(null)}
          onRestored={() => reload()}
        />
      )}
    </>
  );
}
