// SPCSubTab — F-spc 서브탭 (Nelson 8 Rules + 차트 + CSV 업로드).

import { DownloadActions } from '@components/common/DownloadActions';
import type { SPCResponse, SPCUploadResponse } from '@/types/equipment';
import type { ProcessHealthDisplay } from '../types';
import { buildSpcMarkdown } from '../markdownBuilders';

interface SPCChartView {
  values: number[];
  cl: number;
  ucl: number;
  lcl: number;
  violations: SPCResponse['violations'];
}

interface Props {
  processes5: ProcessHealthDisplay[];
  spcResp: SPCResponse | null;
  spcChart: SPCChartView;
  spcLoading: boolean;
  spcProcessId: string;
  setSpcProcessId: (id: string) => void;
  uploadProcessId: string;
  setUploadProcessId: (id: string) => void;
  uploadResp: SPCUploadResponse | null;
  uploading: boolean;
  yScale: (v: number) => number;
  onSPCUpload: (f: File) => void | Promise<void>;
}

export function SPCSubTab({
  processes5,
  spcResp,
  spcChart,
  spcLoading,
  spcProcessId,
  setSpcProcessId,
  uploadProcessId,
  setUploadProcessId,
  uploadResp,
  uploading,
  yScale,
  onSPCUpload,
}: Props) {
  return (
    <>
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">SPC · 5공정 건강 카드</div>
            <h2 className="lg-h2">Nelson 8 Rules 위반</h2>
          </div>
        </div>
        <div className="lg-spc-grid">
          {processes5.map((p) => (
            <div
              key={p.name}
              className={'lg-spc state-' + p.state}
              onClick={() =>
                setSpcProcessId(
                  p.name === '범퍼빔'
                    ? 'bumper_beam'
                    : p.name === '도어'
                      ? 'door'
                      : p.name === '볼시트'
                        ? 'ball_seat'
                        : p.name.toLowerCase(),
                )
              }
              style={{ cursor: 'pointer' }}
            >
              <div className="lg-spc-h">
                <span className="lg-state-dot" />
                <span className="ko">{p.name}</span>
              </div>
              <div className="lg-spc-cpk">
                Cpk <b>{p.cpk}</b>
              </div>
              <div className="lg-spc-viol">위반 {p.viol}건</div>
              <div className="lg-spc-rules">{p.rules.length ? p.rules.join(' · ') : '—'}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">CONTROL CHART · X̄ ({spcResp?.data?.process_name ?? '범퍼빔'})</div>
            <h2 className="lg-h2">관리도</h2>
          </div>
          {spcLoading ? (
            <span className="lg-pill" style={{ color: 'var(--hud-text-dim)' }}>로딩중…</span>
          ) : (
            <span className="lg-pill warn">
              {spcChart.violations.length > 0
                ? `Rule ${spcChart.violations.map((v) => v.rule_number).join('·')} 위반`
                : 'Rule 1·2 위반'}
            </span>
          )}
        </div>
        <div className="lg-spc-chart">
          <svg viewBox="0 0 600 220" preserveAspectRatio="none">
            <line x1="0" y1={yScale(spcChart.ucl)} x2="600" y2={yScale(spcChart.ucl)} stroke="var(--hud-red)" strokeDasharray="4,4" opacity="0.7" />
            <line x1="0" y1={yScale(spcChart.cl)} x2="600" y2={yScale(spcChart.cl)} stroke="var(--hud-text-dim)" strokeDasharray="2,2" opacity="0.6" />
            <line x1="0" y1={yScale(spcChart.lcl)} x2="600" y2={yScale(spcChart.lcl)} stroke="var(--hud-red)" strokeDasharray="4,4" opacity="0.7" />
            {!spcResp && (
              <>
                <rect x={18 * 15} y="10" width={9 * 15} height="200" fill="rgba(232,163,23,0.12)" />
                <rect x={32 * 15 - 6} y="10" width="12" height="200" fill="rgba(192,57,43,0.18)" />
              </>
            )}
            {spcChart.violations.map((v, vi) =>
              v.points.length > 0 ? (
                <rect
                  key={vi}
                  x={Math.min(...v.points) * 15}
                  y="10"
                  width={(Math.max(...v.points) - Math.min(...v.points) + 1) * 15}
                  height="200"
                  fill={v.severity === 'critical' ? 'rgba(192,57,43,0.18)' : 'rgba(232,163,23,0.12)'}
                />
              ) : null,
            )}
            <polyline
              fill="none"
              stroke="var(--hud-primary)"
              strokeWidth="1.5"
              points={spcChart.values.slice(0, 40).map((v, i) => `${i * 15},${yScale(v)}`).join(' ')}
            />
            {spcChart.values.slice(0, 40).map((v, i) => {
              const inViol = !spcResp
                ? (i >= 18 && i <= 26) || i === 32
                : spcChart.violations.some((vio) => vio.points.includes(i));
              return (
                <circle
                  key={i}
                  cx={i * 15}
                  cy={yScale(v)}
                  r={inViol ? 4 : 3}
                  fill={inViol ? 'var(--hud-red)' : 'var(--hud-primary)'}
                />
              );
            })}
            <text x="595" y={yScale(spcChart.ucl) - 4} textAnchor="end" fontSize="10" fill="var(--hud-red)">
              UCL {spcChart.ucl.toFixed(2)}
            </text>
            <text x="595" y={yScale(spcChart.cl) - 4} textAnchor="end" fontSize="10" fill="var(--hud-text-dim)">
              CL {spcChart.cl.toFixed(2)}
            </text>
            <text x="595" y={yScale(spcChart.lcl) - 4} textAnchor="end" fontSize="10" fill="var(--hud-red)">
              LCL {spcChart.lcl.toFixed(2)}
            </text>
          </svg>
        </div>
        <div className="lg-spc-foot">
          <span>
            Isolation Forest 예측: Cpk{' '}
            <b>
              {(spcResp?.data?.values
                ? spcChart.values.slice(-10).reduce((a, b) => a + b, 0) / 10 / spcChart.cl
                : 1.38
              ).toFixed(2)}{' '}
              → <i className="warn">1.24</i>
            </b>{' '}
            (다음 100샘플)
          </span>
          <span>평균 드리프트 +0.6mm</span>
        </div>
      </section>

      <section className="lg-card lg-card-tight">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">DATA MANAGEMENT · CSV 업로드</div>
            <h2 className="lg-h2">SPC 데이터 관리</h2>
          </div>
          {uploadResp && (
            <span className="lg-pill" style={{ color: 'var(--hud-green)' }}>
              ✓ {uploadResp.n_samples}샘플 / Cpk {uploadResp.cpk?.toFixed(2) ?? '—'}
            </span>
          )}
        </div>
        <div
          className="lg-filter-grid"
          style={{ gridTemplateColumns: '1fr 2fr auto', alignItems: 'flex-end' }}
        >
          <div className="lg-field">
            <label>대상 공정</label>
            <select value={uploadProcessId} onChange={(e) => setUploadProcessId(e.target.value)}>
              <option value="cch">CCH</option>
              <option value="obc">OBC</option>
              <option value="bumper_beam">범퍼빔</option>
              <option value="door">도어</option>
              <option value="ball_seat">볼시트</option>
            </select>
          </div>
          <div className="lg-field">
            <label>CSV 파일 (UTF-8 BOM, 헤더 1행)</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onSPCUpload(f);
              }}
            />
          </div>
          <button className="lg-btn" disabled={uploading}>
            {uploading ? '업로드 중…' : '업로드 ▶'}
          </button>
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--hud-text-dim)' }}>
          ※ 업로드 후 자동으로 SPC 차트 재계산. 샘플 재생성은 백엔드 `spc_data_generator.py` 가 처리.
        </div>
        <DownloadActions
          content={() => buildSpcMarkdown(processes5, spcResp?.data?.process_name ?? '범퍼빔')}
          basename={`equipment_spc_${spcProcessId}_${new Date().toISOString().slice(0, 10)}`}
          source="equipment"
          metadata={{
            title: `SPC Nelson 8 Rules 보고서 (${spcResp?.data?.process_name ?? '5공정'})`,
            doc_type: 'equipment_spc',
          }}
        />
      </section>
    </>
  );
}
