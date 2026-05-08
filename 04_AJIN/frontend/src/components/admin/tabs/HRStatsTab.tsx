// HRStatsTab — 7 서브탭 인사 통계.
// 요약 / 본부별 / 부서별 / 직급별 / 성별 / 근속 / 본부×직급 (+해외주재)

import { useEffect, useMemo, useState } from 'react';
import {
  fetchHrGender,
  fetchHrHeadcount,
  fetchHrMatrix,
  fetchHrOverseas,
  fetchHrSummary,
  fetchHrTenure,
  type DivisionPositionMatrixResponse,
  type HeadcountResponse,
  type HRSummaryResponse,
  type OverseasResponse,
} from '@api/admin';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { HeatmapGrid } from '@components/admin/widgets/HeatmapGrid';

type SubTab = 'summary' | 'division' | 'department' | 'position' | 'gender' | 'tenure' | 'matrix' | 'overseas';

const SUB_LABELS: { key: SubTab; ko: string; en: string }[] = [
  { key: 'summary',   ko: '요약',     en: 'SUMMARY' },
  { key: 'division',  ko: '본부별',   en: 'DIVISION' },
  { key: 'department', ko: '부서별',  en: 'DEPARTMENT' },
  { key: 'position',  ko: '직급별',   en: 'POSITION' },
  { key: 'gender',    ko: '성별',     en: 'GENDER' },
  { key: 'tenure',    ko: '근속',     en: 'TENURE' },
  { key: 'matrix',    ko: '본부×직급', en: 'MATRIX' },
  { key: 'overseas',  ko: '해외주재', en: 'OVERSEAS' },
];

function HorizontalBars({ rows, label }: { rows: { label: string; count: number }[]; label: string }) {
  if (rows.length === 0) return <div style={{ color: 'var(--hud-text-dim)' }}>표시할 데이터가 없습니다.</div>;
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="lg-stat-list">
      {rows.map((r) => (
        <div key={r.label} className="lg-stat-row" style={{ alignItems: 'center' }}>
          <span style={{ flex: '0 0 140px' }}>{r.label}</span>
          <div style={{ flex: 1, marginRight: 12, height: 14, background: 'color-mix(in oklab, var(--hud-text) 8%, transparent)', borderRadius: 999, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${(r.count / max) * 100}%`,
                background: 'linear-gradient(90deg, var(--hud-primary), color-mix(in oklab, var(--hud-primary) 50%, var(--hud-bg)))',
              }}
              title={`${r.label}: ${r.count} ${label}`}
            />
          </div>
          <b className="mono">{r.count.toLocaleString()}</b>
        </div>
      ))}
    </div>
  );
}

export function HRStatsTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);
  const [sub, setSub] = useState<SubTab>('summary');
  const [summary, setSummary] = useState<HRSummaryResponse | null>(null);
  const [headcount, setHeadcount] = useState<Record<string, HeadcountResponse | null>>({});
  const [gender, setGender] = useState<Record<string, number> | null>(null);
  const [tenure, setTenure] = useState<{ range: string; count: number }[] | null>(null);
  const [matrix, setMatrix] = useState<DivisionPositionMatrixResponse | null>(null);
  const [overseas, setOverseas] = useState<OverseasResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (myLevel < 3) return;
    fetchHrSummary().then(setSummary).catch((e) => setError((e as Error).message));
  }, [myLevel]);

  useEffect(() => {
    if (myLevel < 3) return;
    const cached = headcount[sub];
    const loaders: Record<SubTab, () => Promise<void>> = {
      summary: async () => {},
      division: async () => {
        if (!cached) {
          const data = await fetchHrHeadcount('division');
          setHeadcount((p) => ({ ...p, division: data }));
        }
      },
      department: async () => {
        if (!cached) {
          const data = await fetchHrHeadcount('department');
          setHeadcount((p) => ({ ...p, department: data }));
        }
      },
      position: async () => {
        if (!cached) {
          const data = await fetchHrHeadcount('position');
          setHeadcount((p) => ({ ...p, position: data }));
        }
      },
      gender: async () => {
        if (!gender) setGender((await fetchHrGender()).distribution);
      },
      tenure: async () => {
        if (!tenure) setTenure((await fetchHrTenure()).rows);
      },
      matrix: async () => {
        if (!matrix) setMatrix(await fetchHrMatrix());
      },
      overseas: async () => {
        if (!overseas) setOverseas(await fetchHrOverseas());
      },
    };
    loaders[sub]().catch((e) => setError((e as Error).message));
  }, [sub, myLevel, headcount, gender, tenure, matrix, overseas]);

  const genderTotal = useMemo(() => Object.values(gender ?? {}).reduce((a, b) => a + b, 0), [gender]);

  if (myLevel < 3) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>인사 통계는 TEAM_LEAD(L3) 이상에게 노출됩니다.</p>
      </div>
    );
  }

  const buildMd = (): string => {
    const lines = [`# 인사 통계 — ${SUB_LABELS.find((s) => s.key === sub)?.ko}`, ''];
    if (sub === 'summary' && summary) {
      lines.push(`총 인원: ${summary.total}`, `본부 수: ${summary.divisions}`, `부서 수: ${summary.departments}`, `사업장 수: ${summary.plants}`, `팀장: ${summary.leaders}`);
    } else if ((sub === 'division' || sub === 'department' || sub === 'position') && headcount[sub]) {
      const rows = headcount[sub]!.rows;
      lines.push('| 항목 | 인원 |', '|---|---|');
      for (const r of rows) lines.push(`| ${r.label} | ${r.count} |`);
    } else if (sub === 'gender' && gender) {
      lines.push('| 구분 | 인원 |', '|---|---|');
      for (const [k, v] of Object.entries(gender)) lines.push(`| ${k || '미지정'} | ${v} |`);
    } else if (sub === 'tenure' && tenure) {
      lines.push('| 근속 | 인원 |', '|---|---|');
      for (const r of tenure) lines.push(`| ${r.range} | ${r.count} |`);
    } else if (sub === 'overseas' && overseas) {
      lines.push('| 이름 | 직급 | 부서 | 주재지 |', '|---|---|---|---|');
      for (const r of overseas.rows) lines.push(`| ${r.name} | ${r.position} | ${r.department} | ${r.overseas_assignment} |`);
    }
    return lines.join('\n');
  };

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
            <div className="lg-pill">HR STATISTICS</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              employees.db (329명) 기반 7+1 통계
            </div>
          </div>
          <DownloadActions source="admin" basename="ajin-hr-stats" content={buildMd} />
        </div>

        <div className="lg-subtabs">
          {SUB_LABELS.map((s) => (
            <button
              key={s.key}
              className={`lg-subtab ${sub === s.key ? 'on' : ''}`}
              onClick={() => setSub(s.key)}
              type="button"
            >
              {s.ko}
              <span style={{ fontFamily: 'var(--hud-font-mono)', fontSize: 9, marginLeft: 6, opacity: 0.7 }}>{s.en}</span>
            </button>
          ))}
        </div>

        {sub === 'summary' && (
          <div className="lg-metric-row">
            <div className="lg-metric"><div className="k">총 인원</div><div className="v">{summary?.total.toLocaleString() ?? '—'}</div><div className="en">ACTIVE EMPLOYEES</div></div>
            <div className="lg-metric"><div className="k">본부</div><div className="v">{summary?.divisions ?? '—'}</div><div className="en">DIVISIONS</div></div>
            <div className="lg-metric"><div className="k">부서</div><div className="v">{summary?.departments ?? '—'}</div><div className="en">DEPARTMENTS</div></div>
            <div className="lg-metric"><div className="k">사업장</div><div className="v">{summary?.plants ?? '—'}</div><div className="en">PLANTS</div></div>
          </div>
        )}

        {(sub === 'division' || sub === 'department' || sub === 'position') && (
          <HorizontalBars
            rows={(headcount[sub]?.rows ?? []).map((r) => ({ label: r.label, count: r.count }))}
            label="명"
          />
        )}

        {sub === 'gender' && gender && (
          <div className="lg-stat-list">
            {Object.entries(gender).map(([k, v]) => (
              <div key={k} className="lg-stat-row">
                <span>{k || '미지정'}</span>
                <b>{v.toLocaleString()}명 ({genderTotal > 0 ? ((v / genderTotal) * 100).toFixed(1) : '0'}%)</b>
              </div>
            ))}
          </div>
        )}

        {sub === 'tenure' && tenure && (
          <HorizontalBars rows={tenure.map((t) => ({ label: t.range, count: t.count }))} label="명" />
        )}

        {sub === 'matrix' && matrix && (
          <HeatmapGrid
            rows={matrix.divisions}
            cols={matrix.positions}
            matrix={matrix.matrix}
            rowLabel="본부"
            colLabel="직급"
          />
        )}

        {sub === 'overseas' && (
          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead>
                <tr>
                  <th>이름</th>
                  <th>직급</th>
                  <th>부서</th>
                  <th>주재지</th>
                </tr>
              </thead>
              <tbody>
                {(overseas?.rows ?? []).map((r) => (
                  <tr key={`${r.name}-${r.overseas_assignment}`}>
                    <td>{r.name}</td>
                    <td>{r.position}</td>
                    <td>{r.department}</td>
                    <td>{r.overseas_assignment}</td>
                  </tr>
                ))}
                {(!overseas || overseas.rows.length === 0) && (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}>
                      해외주재 인원이 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
