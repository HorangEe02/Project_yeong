// AnalyticsTab — AI 활용 분석 (DAU + 부서별 사용량 + 부서×기능 히트맵 + ROI).

import { useEffect, useMemo, useState } from 'react';
import {
  fetchAnalyticsDau,
  fetchAnalyticsHeatmap,
  fetchAnalyticsRoi,
  fetchAnalyticsUsage,
  type AnalyticsUsageResponse,
  type DauResponse,
  type HeatmapResponse,
  type RoiResponse,
} from '@api/admin';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { DAULineChart } from '@components/admin/widgets/DAULineChart';
import { HeatmapGrid } from '@components/admin/widgets/HeatmapGrid';
import { ScenarioUsageStats } from '@components/admin/widgets/ScenarioUsageStats';

function buildAnalyticsMd(usage: AnalyticsUsageResponse | null, roi: RoiResponse | null): string {
  const lines = ['# AI 활용 분석 + ROI 보고서', ''];
  if (usage) {
    lines.push(`기간: 최근 ${usage.days}일`, '', '## 기능별 사용 횟수', '');
    lines.push('| 기능 | 이름 | 횟수 |', '|---|---|---|');
    for (const f of usage.by_feature) lines.push(`| ${f.feature} | ${f.name} | ${f.count} |`);
  }
  if (roi) {
    lines.push('', '## ROI 추정', '',
      `- 총 사용 횟수: ${roi.total_uses}`,
      `- 절감 시간: ${roi.total_saved_hours} 시간`,
      `- 환산 절감: ${roi.saved_cost_display}`,
    );
  }
  return lines.join('\n');
}

export function AnalyticsTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);
  const [days, setDays] = useState(30);
  const [usage, setUsage] = useState<AnalyticsUsageResponse | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [dau, setDau] = useState<DauResponse | null>(null);
  const [roi, setRoi] = useState<RoiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (myLevel < 4) return;
    Promise.all([
      fetchAnalyticsUsage(days),
      fetchAnalyticsHeatmap(days),
      fetchAnalyticsDau(days),
      fetchAnalyticsRoi(days),
    ])
      .then(([u, h, d, r]) => {
        setUsage(u);
        setHeatmap(h);
        setDau(d);
        setRoi(r);
      })
      .catch((e) => setError((e as Error).message));
  }, [myLevel, days]);

  const peakDau = useMemo(() => Math.max(0, ...(dau?.series.map((s) => s.dau) ?? [])), [dau]);
  const totalDau = useMemo(() => (dau?.series.reduce((a, s) => a + s.dau, 0) ?? 0), [dau]);
  const featMax = Math.max(1, ...(usage?.by_feature ?? []).map((f) => f.count));

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>AI 활용 분석은 HR_ADMIN(L4) 이상에게만 노출됩니다.</p>
      </div>
    );
  }

  return (
    <>
      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">AI USAGE · ROI</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              api_audit_log + login_history 기반 활용 분석
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <div className="lg-field" style={{ minWidth: 130 }}>
              <label>기간</label>
              <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>최근 7일</option>
                <option value={30}>최근 30일</option>
                <option value={90}>최근 90일</option>
              </select>
            </div>
            <DownloadActions source="admin" basename="ajin-analytics" content={() => buildAnalyticsMd(usage, roi)} />
          </div>
        </div>

        <div className="lg-metric-row">
          <div className="lg-metric">
            <div className="k">DAU PEAK</div>
            <div className="v">{peakDau.toLocaleString()}</div>
            <div className="en">최대 일일 사용자</div>
          </div>
          <div className="lg-metric">
            <div className="k">총 활동</div>
            <div className="v">{totalDau.toLocaleString()}</div>
            <div className="en">기간 내 누적 로그인</div>
          </div>
          <div className="lg-metric">
            <div className="k">총 사용 횟수</div>
            <div className="v">{(roi?.total_uses ?? 0).toLocaleString()}</div>
            <div className="en">API 호출 합계</div>
          </div>
          <div className="lg-metric">
            <div className="k">절감 환산</div>
            <div className="v" style={{ color: 'var(--hud-primary)' }}>{roi?.saved_cost_display ?? '—'}</div>
            <div className="en">{roi?.total_saved_hours ?? 0} 시간 절감</div>
          </div>
        </div>
      </div>

      <div className="lg-grid lg-grid-2-1">
        <div className="lg-card">
          <div className="lg-card-h">
            <div className="lg-pill">DAILY ACTIVE USERS</div>
          </div>
          <DAULineChart series={dau?.series ?? []} />
        </div>

        <div className="lg-card">
          <div className="lg-card-h">
            <div className="lg-pill">기능별 사용량</div>
          </div>
          <div className="lg-bars-v" style={{ height: 200 }}>
            {(usage?.by_feature ?? []).map((f) => (
              <div key={f.feature} className="lg-bar-v">
                <div
                  className="lg-bar-fill"
                  style={{ height: `${Math.max(4, (f.count / featMax) * 100)}%` }}
                  title={`${f.name}: ${f.count}회`}
                >
                  {f.count > 0 && <b>{f.count}</b>}
                </div>
                <div className="lbl">{f.feature}<br />{f.name}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="lg-card">
        <div className="lg-card-h">
          <div className="lg-pill">부서 × 기능 히트맵</div>
        </div>
        <HeatmapGrid
          rows={heatmap?.departments ?? []}
          cols={heatmap?.features ?? []}
          matrix={heatmap?.matrix ?? {}}
          rowLabel="부서"
          colLabel="기능"
        />
      </div>

      <ScenarioUsageStats days={days} />

      <div className="lg-card">
        <div className="lg-card-h">
          <div className="lg-pill">ROI 추정</div>
        </div>
        <div className="lg-roi-list">
          <div className="lg-roi-row hi">
            <span>월간 절감액 환산</span>
            <b>{roi?.saved_cost_display ?? '0원'}</b>
          </div>
          <div className="lg-roi-row">
            <span>총 사용 횟수</span>
            <b>{(roi?.total_uses ?? 0).toLocaleString()}회</b>
          </div>
          <div className="lg-roi-row">
            <span>총 절감 시간</span>
            <b>{roi?.total_saved_hours ?? 0} 시간</b>
          </div>
          {Object.entries(roi?.per_feature ?? {}).map(([k, v]) => (
            <div key={k} className="lg-roi-row">
              <span>{k} · {v.name}</span>
              <b>{v.count}회 · {v.saved_min}분 절감</b>
            </div>
          ))}
        </div>
        <div className="lg-roi-foot">
          기준: 연봉 5,000만원 / 12개월 / 월 160시간 시급으로 환산. 기능별 수동 처리 시간(분) 가정값 적용.
        </div>
      </div>
    </>
  );
}
