// ScenarioUsageStats — 협업 시나리오 사용 통계 (AnalyticsTab 통합용, Phase 3).
// /admin/scenarios/usage-stats — 인기 시나리오 + 매칭 0회 시나리오.

import { useEffect, useState } from 'react';
import { fetchScenarioUsageStats, type UsageStatsResponse } from '@api/admin_scenarios';

interface Props {
  days: number;
}

export function ScenarioUsageStats({ days }: Props) {
  const [data, setData] = useState<UsageStatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScenarioUsageStats(days)
      .then(setData)
      .catch((e) => setError((e as Error).message));
  }, [days]);

  const max = Math.max(1, ...((data?.by_scenario ?? []).map((r) => r.hits)));

  if (error) {
    return (
      <div className="lg-card">
        <div className="lg-card-h">
          <div className="lg-pill">SCENARIO USAGE</div>
        </div>
        <div className="lg-state-pill crit">{error}</div>
      </div>
    );
  }

  return (
    <div className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">SCENARIO USAGE · 협업 시나리오 사용 통계</div>
          <div style={{ marginTop: 4, fontSize: 13, color: 'var(--hud-text-dim)' }}>
            최근 {days}일 매칭 횟수 — TOP {data?.by_scenario.length ?? 0} / 매칭 0회 {data?.zero_match.length ?? 0}건
          </div>
        </div>
      </div>

      {(data?.by_scenario ?? []).length === 0 ? (
        <div className="lg-empty">아직 매칭 통계가 없습니다.</div>
      ) : (
        <div className="lg-stat-list">
          {(data?.by_scenario ?? []).slice(0, 10).map((r) => (
            <div key={r.scenario_id} className="lg-stat-row" style={{ alignItems: 'center' }}>
              <span style={{ flex: '0 0 200px' }} className="mono">{r.scenario_id}</span>
              <div style={{ flex: 1, marginRight: 12, height: 14, background: 'color-mix(in oklab, var(--hud-text) 8%, transparent)', borderRadius: 999, overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${(r.hits / max) * 100}%`,
                    background: 'linear-gradient(90deg, var(--hud-primary), color-mix(in oklab, var(--hud-primary) 50%, var(--hud-bg)))',
                  }}
                  title={`${r.scenario_id}: ${r.hits}회`}
                />
              </div>
              <b className="mono">{r.hits.toLocaleString()}회</b>
            </div>
          ))}
        </div>
      )}

      {(data?.zero_match ?? []).length > 0 && (
        <div style={{ marginTop: 18 }}>
          <div className="lg-pill" style={{ color: '#E8A317' }}>매칭 0회 — 개선 후보</div>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {(data?.zero_match ?? []).map((r) => (
              <span key={r.scenario_id} className="lg-chip" title={r.situation}>
                {r.scenario_id}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
