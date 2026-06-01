// PredictiveSubTab — F-predictive 서브탭 (XGBoost 금형 + MTBF Plotly + TOP 5).
// W5 (P1): 위험 금형 카드에 컴플라이언스 영향 / 8D 작성 액션 추가 (F→D, F→B 연계).

import { useNavigate } from 'react-router-dom';
import { ShieldAlert, FileText } from 'lucide-react';
import { PlotlyChart } from '@components/chart/PlotlyChart';
import type { Data } from 'plotly.js';
import { DownloadActions } from '@components/common/DownloadActions';
import type { MoldsResponse, MTBFResponse } from '@/types/equipment';
import type { MaintCostDisplay, MoldDisplay } from '../types';
import { buildMoldMarkdown, buildMtbfMarkdown } from '../markdownBuilders';
import { DataClassBadge } from '@/lib/syntheticBadge';

interface Props {
  molds: MoldsResponse | null;
  moldList: MoldDisplay[];
  mtbf: MTBFResponse | null;
  mtbfBar: Data[];
  maintCost: MaintCostDisplay[];
}

export function PredictiveSubTab({ molds, moldList, mtbf, mtbfBar, maintCost }: Props) {
  const navigate = useNavigate();

  const onComplianceImpact = (m: MoldDisplay) => {
    // F→D: 부품명을 컴플라이언스 검색에 prefill (compliance/search 라우트 또는 root 라우트)
    navigate('/compliance', { state: { prefillQuery: m.part, source: 'equipment.mold', mold_id: m.id } });
  };

  const onDraft8D = (m: MoldDisplay) => {
    // F→B: 금형 위험 8D Report 초안
    const rem = m.max - m.shots;
    const prefill = `[금형 ${m.id} / ${m.part}] 잔여수명 임박\n- 잔여 shots: ${rem.toLocaleString()}\n- 사용률: ${((m.shots / m.max) * 100).toFixed(1)}%\n- 리스크: ${m.risk}\n\n해당 금형 관련 8D Report 초안을 작성해 주세요.`;
    navigate('/draft', { state: { prefill, doc_type: '8D' } });
  };

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
            const risk = m.risk.toLowerCase();
            const showActions = risk === 'critical' || risk === 'warning';
            return (
              <div key={m.id} className={'lg-mold risk-' + risk}>
                <div className="lg-mold-h">
                  <span className="id mono">{m.id}</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <DataClassBadge dataClass={m.dataClass} sourceSystem={m.sourceSystem} />
                    <span className={'lg-risk-pill r-' + risk}>{m.risk}</span>
                  </span>
                </div>
                <div className="lg-mold-part">{m.part}</div>
                <div className="lg-mold-bar">
                  <span style={{ width: pct * 100 + '%' }} />
                </div>
                <div className="lg-mold-stat">
                  <span>{(pct * 100).toFixed(0)}% 사용</span>
                  <span className="rem">잔여 {(rem / 1000).toFixed(0)}k</span>
                </div>

                {/* W6 (P2) — ML 설명력: 신뢰구간 + 예측 교체일 */}
                {(m.ci || m.predictedReplaceDate || m.predictedRemaining) && (
                  <div
                    style={{
                      marginTop: 6,
                      fontSize: 10,
                      opacity: 0.7,
                      lineHeight: 1.5,
                    }}
                  >
                    {m.predictedReplaceDate && (
                      <div>📅 예측 교체일: {m.predictedReplaceDate}</div>
                    )}
                    {m.ci && (
                      <div>
                        🎯 95% CI: {(m.ci[0] / 1000).toFixed(0)}k ~ {(m.ci[1] / 1000).toFixed(0)}k shots
                      </div>
                    )}
                  </div>
                )}

                {showActions && (
                  <div
                    style={{
                      marginTop: 8,
                      display: 'flex',
                      gap: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => onComplianceImpact(m)}
                      title="컴플라이언스 영향 확인 (D)"
                      style={btnStyle}
                    >
                      <ShieldAlert size={11} />
                      컴플라이언스
                    </button>
                    <button
                      type="button"
                      onClick={() => onDraft8D(m)}
                      title="8D Report 초안 작성 (B)"
                      style={btnStyle}
                    >
                      <FileText size={11} />
                      8D Report
                    </button>
                  </div>
                )}
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

const btnStyle: React.CSSProperties = {
  padding: '4px 8px',
  fontSize: 10,
  borderRadius: 6,
  border: '1px solid var(--hud-border)',
  background: 'var(--hud-surface-2)',
  color: 'var(--hud-text)',
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
};
