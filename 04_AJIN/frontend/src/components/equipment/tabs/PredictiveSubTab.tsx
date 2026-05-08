// PredictiveSubTab — F-predictive 서브탭 (XGBoost 금형 + MTBF Plotly + TOP 5).

import { PlotlyChart } from '@components/chart/PlotlyChart';
import type { Data } from 'plotly.js';
import { DownloadActions } from '@components/common/DownloadActions';
import type { MoldsResponse, MTBFResponse } from '@/types/equipment';
import type { MaintCostDisplay, MoldDisplay } from '../types';
import { buildMoldMarkdown, buildMtbfMarkdown } from '../markdownBuilders';

interface Props {
  molds: MoldsResponse | null;
  moldList: MoldDisplay[];
  mtbf: MTBFResponse | null;
  mtbfBar: Data[];
  maintCost: MaintCostDisplay[];
}

export function PredictiveSubTab({ molds, moldList, mtbf, mtbfBar, maintCost }: Props) {
  return (
    <>
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">XGBoost MOLD LIFECYCLE</div>
            <h2 className="lg-h2">금형 {molds?.total ?? 25}기 잔여 수명</h2>
          </div>
          <span className="lg-pill">
            표시 {moldList.length}/{molds?.total ?? 25}
          </span>
        </div>
        <div className="lg-mold-grid">
          {moldList.map((m) => {
            const pct = m.shots / m.max;
            const rem = m.max - m.shots;
            return (
              <div key={m.id} className={'lg-mold risk-' + m.risk.toLowerCase()}>
                <div className="lg-mold-h">
                  <span className="id mono">{m.id}</span>
                  <span className={'lg-risk-pill r-' + m.risk.toLowerCase()}>{m.risk}</span>
                </div>
                <div className="lg-mold-part">{m.part}</div>
                <div className="lg-mold-bar">
                  <span style={{ width: pct * 100 + '%' }} />
                </div>
                <div className="lg-mold-stat">
                  <span>{(pct * 100).toFixed(0)}% 사용</span>
                  <span className="rem">잔여 {(rem / 1000).toFixed(0)}k</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">MTBF · 수리 비용 분포</div>
            <h2 className="lg-h2">설비별 비용 + 수리 건수 ({mtbf?.items?.length ?? 15}대)</h2>
          </div>
          <span className="lg-pill">{mtbf?.machines_attention ?? 0}대 점검 필요</span>
        </div>
        <div style={{ width: '100%', height: 360 }}>
          <PlotlyChart
            data={mtbfBar}
            layout={{
              margin: { l: 60, r: 60, t: 30, b: 80 },
              xaxis: { tickangle: -30, automargin: true },
              yaxis: { title: { text: '비용 (만원)', standoff: 10 } },
              yaxis2: {
                title: { text: '수리 건수', standoff: 10 },
                overlaying: 'y',
                side: 'right',
                showgrid: false,
              },
              barmode: 'group',
              bargap: 0.3,
              legend: { orientation: 'h', x: 0, y: -0.25 },
              hovermode: 'x unified',
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">MTBF · 수리 비용 TOP 5</div>
            <h2 className="lg-h2">예측 정비 우선순위</h2>
          </div>
          {mtbf?.seasonal_message && (
            <span className="lg-pill" style={{ color: 'var(--hud-text-dim)' }}>
              {mtbf.seasonal_message}
            </span>
          )}
        </div>
        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>설비</th>
                <th>누적 비용 (만원)</th>
                <th>건수</th>
                <th>다음 정비</th>
              </tr>
            </thead>
            <tbody>
              {maintCost.map((m, i) => (
                <tr key={`${m.eq}-${i}`}>
                  <td>
                    <b>{m.eq}</b>
                  </td>
                  <td className="mono">{m.cost.toLocaleString()}</td>
                  <td>{m.jobs}</td>
                  <td className="mono">{m.next}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <DownloadActions
          content={() =>
            buildMtbfMarkdown(maintCost, mtbf?.machines_attention) +
            '\n\n---\n\n' +
            buildMoldMarkdown(moldList, molds?.total ?? 25)
          }
          basename={`equipment_predictive_${new Date().toISOString().slice(0, 10)}`}
          source="equipment"
          metadata={{ title: '예측정비 보고서 (MTBF + 금형 잔여 수명)', doc_type: 'equipment_predictive' }}
        />
      </section>
    </>
  );
}
