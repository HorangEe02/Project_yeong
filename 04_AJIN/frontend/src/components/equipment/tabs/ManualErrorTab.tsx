// ManualErrorTab — F-manual_error 메인 탭 (3 sub-tabs: 에러코드 / 증상 / RAG).

import { useState } from 'react';
import { PlotlyChart } from '@components/chart/PlotlyChart';
import type { Data } from 'plotly.js';
import { DownloadActions } from '@components/common/DownloadActions';
import type {
  ErrorCategoriesResponse,
  ManualSearchResponse,
  MarkovResponse,
} from '@/types/equipment';
import type { ErrResultDisplay, MarkovBranchDisplay } from '../types';
import { CAUSALITY_CATEGORIES } from '../mockData';
import { buildErrSearchMarkdown } from '../markdownBuilders';

type ManualSubTab = 'codes' | 'symptoms' | 'rag';

const MANUAL_SUB_TABS: { k: ManualSubTab; label: string }[] = [
  { k: 'codes', label: '에러코드' },
  { k: 'symptoms', label: '증상 가이드' },
  { k: 'rag', label: 'AI 질의' },
];

interface Props {
  categories: ErrorCategoriesResponse | null;
  symptomCats: Record<string, string[]>;
  equipFilter: string;
  setEquipFilter: (v: string) => void;
  symptom: string;
  setSymptom: (v: string) => void;
  errQuery: string;
  setErrQuery: (v: string) => void;
  errSearching: boolean;
  onErrorSearch: () => void | Promise<void>;
  errResults: ErrResultDisplay[];
  markov: MarkovResponse | null;
  markovChain: MarkovBranchDisplay[];
  markovGraph: Data[];
  ragQuery: string;
  setRagQuery: (v: string) => void;
  manualSearching: boolean;
  onManualSearch: () => void | Promise<void>;
  manualResp: ManualSearchResponse | null;
}

export function ManualErrorTab({
  categories,
  symptomCats,
  equipFilter,
  setEquipFilter,
  symptom,
  setSymptom,
  errQuery,
  setErrQuery,
  errSearching,
  onErrorSearch,
  errResults,
  markov,
  markovChain,
  markovGraph,
  ragQuery,
  setRagQuery,
  manualSearching,
  onManualSearch,
  manualResp,
}: Props) {
  const [sub, setSub] = useState<ManualSubTab>('codes');

  return (
    <>
      <div className="lg-subtabs">
        {MANUAL_SUB_TABS.map((t) => (
          <button
            key={t.k}
            className={'lg-subtab' + (sub === t.k ? ' on' : '')}
            onClick={() => setSub(t.k)}
            type="button"
          >
            {t.label}
          </button>
        ))}
      </div>

      {sub === 'codes' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">
                  ERROR SEARCH · TF-IDF + 동의어 {categories?.total_synonyms ?? 79}
                </div>
                <h2 className="lg-h2">에러코드 자연어 검색</h2>
              </div>
              <span className="lg-pill">이력 685건</span>
            </div>
            <div
              className="lg-filter-grid"
              style={{ gridTemplateColumns: '1fr 1fr 2fr auto', alignItems: 'flex-end' }}
            >
              <div className="lg-field">
                <label>장비</label>
                <select
                  value={equipFilter}
                  onChange={(e) => {
                    setEquipFilter(e.target.value);
                    const list = symptomCats[e.target.value];
                    if (list?.length) setSymptom(list[0]);
                  }}
                >
                  {Object.keys(symptomCats).map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </div>
              <div className="lg-field">
                <label>증상 ({(symptomCats[equipFilter] ?? []).length})</label>
                <select value={symptom} onChange={(e) => setSymptom(e.target.value)}>
                  {(symptomCats[equipFilter] ?? []).map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="lg-field">
                <label>자연어 입력</label>
                <input
                  value={errQuery}
                  onChange={(e) => setErrQuery(e.target.value)}
                  placeholder="예: 프레스에서 이상한 소리..."
                />
              </div>
              <button className="lg-btn" onClick={() => void onErrorSearch()} disabled={errSearching}>
                {errSearching ? '검색중…' : '검색 ▶'}
              </button>
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">RESULTS · 코사인 유사도 TOP 5</div>
                <h2 className="lg-h2">매칭 에러 코드</h2>
              </div>
            </div>
            <div className="lg-err-grid">
              {errResults.map((e, i) => (
                <div
                  key={`${e.code}-${i}`}
                  className={'lg-err sev-' + e.sev.toLowerCase() + (i === 0 ? ' top' : '')}
                >
                  <div className="lg-err-h">
                    <span className="code mono">{e.code}</span>
                    <span className={'sev ' + e.sev.toLowerCase()}>{e.sev}</span>
                    <span className="sim mono">코사인 {e.sim.toFixed(2)}</span>
                  </div>
                  <div className="lg-err-name">{e.name}</div>
                  <div className="lg-err-meta">
                    <span>
                      <i>이력 12개월</i>
                      <b>{e.count > 0 ? `${e.count}건` : '—'}</b>
                    </span>
                    <span>
                      <i>평균 복구</i>
                      <b>{e.mttr}</b>
                    </span>
                    <span>
                      <i>주요 원인</i>
                      <b>{e.cause}</b>
                    </span>
                  </div>
                  <div className="lg-err-actions">
                    <button className="lg-btn ghost sm">조치 가이드</button>
                    <button className="lg-btn ghost sm">매뉴얼</button>
                    <button className="lg-btn ghost sm">좋아요</button>
                    <button className="lg-btn ghost sm">별로</button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">MARKOV CHAIN · DFS depth=3</div>
                <h2 className="lg-h2">연쇄 고장 예측</h2>
              </div>
              {markov?.risk_level && (
                <span className={'lg-pill ' + (markov.risk_level === 'critical' ? 'warn' : '')}>
                  {markov.risk_level.toUpperCase()}
                </span>
              )}
            </div>
            <div className="lg-markov">
              <span className="lg-m-node start">{markov?.current_code ?? 'E-101'} 베어링 마모</span>
              <span className="lg-m-arrow">→</span>
              <div className="lg-m-branches">
                {markovChain.map((m) => (
                  <div key={m.code} className="lg-m-branch">
                    <span className="lg-m-prob">{m.prob.toFixed(2)}</span>
                    <span className="lg-m-node">
                      {m.code} {m.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ width: '100%', height: 320, marginTop: 18 }}>
              <PlotlyChart
                data={markovGraph}
                layout={{
                  margin: { l: 10, r: 10, t: 10, b: 10 },
                  xaxis: {
                    visible: false,
                    showgrid: false,
                    zeroline: false,
                    showticklabels: false,
                    range: [-0.5, 2.0],
                  },
                  yaxis: {
                    visible: false,
                    showgrid: false,
                    zeroline: false,
                    showticklabels: false,
                    range: [-1.2, 1.2],
                    scaleanchor: 'x',
                    scaleratio: 1,
                  },
                  hovermode: 'closest',
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
            <div className="lg-markov-foot">
              {markov?.prevention_message ?? '권장 사전 조치: 윤활 점검 → 베어링 교체 → 모터 온도 모니터링'}
            </div>
            <DownloadActions
              content={() => buildErrSearchMarkdown(errQuery, equipFilter, symptom, errResults, markovChain)}
              basename={`equipment_error_search_${equipFilter}_${new Date().toISOString().slice(0, 10)}`}
              source="equipment"
              metadata={{
                title: `에러 검색 보고서 — ${equipFilter} (${symptom})`,
                doc_type: 'equipment_error_search',
              }}
            />
          </section>
        </>
      )}

      {sub === 'symptoms' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">
                  SYMPTOM GUIDE · {Object.values(symptomCats).flat().length} 증상
                </div>
                <h2 className="lg-h2">증상별 카테고리 ({Object.keys(symptomCats).length} 장비)</h2>
              </div>
            </div>
            <div className="lg-spc-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {Object.entries(symptomCats).map(([eq, syms]) => (
                <div key={eq} className="lg-spc state-ok">
                  <div className="lg-spc-h">
                    <span className="ko">{eq}</span>
                    <span className="dim mono" style={{ marginLeft: 'auto', fontSize: 11 }}>
                      {syms.length}
                    </span>
                  </div>
                  <div className="lg-spc-rules" style={{ marginTop: 8, lineHeight: 1.7 }}>
                    {syms.join(' · ')}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">CAUSALITY · 에러 인과 카테고리</div>
                <h2 className="lg-h2">{CAUSALITY_CATEGORIES.length} 카테고리 (70+ 인과 규칙)</h2>
              </div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {CAUSALITY_CATEGORIES.map((c) => (
                <span key={c} className="lg-chip">
                  {c}
                </span>
              ))}
            </div>
            <div style={{ marginTop: 14, fontSize: 12, color: 'var(--hud-text-dim)' }}>
              ※ 인과 규칙 예시: 유압 누수 → 압력 저하 → 성형 불량
            </div>
          </section>
        </>
      )}

      {sub === 'rag' && (
        <>
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">MANUAL RAG · LLM + ChromaDB</div>
                <h2 className="lg-h2">AI 매뉴얼 질의</h2>
              </div>
              <span className="lg-pill">{equipFilter}</span>
            </div>
            <div
              className="lg-filter-grid"
              style={{ gridTemplateColumns: '1fr 3fr auto', alignItems: 'flex-end' }}
            >
              <div className="lg-field">
                <label>장비 컨텍스트</label>
                <select value={equipFilter} onChange={(e) => setEquipFilter(e.target.value)}>
                  {Object.keys(symptomCats).map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </div>
              <div className="lg-field">
                <label>질의</label>
                <input
                  value={ragQuery}
                  onChange={(e) => setRagQuery(e.target.value)}
                  placeholder="예: 베어링 교체 절차"
                />
              </div>
              <button className="lg-btn" onClick={() => void onManualSearch()} disabled={manualSearching}>
                {manualSearching ? '검색중…' : '검색 ▶'}
              </button>
            </div>
          </section>

          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">EXCERPTS · {manualResp?.total ?? 0} 관련 발췌</div>
                <h2 className="lg-h2">매뉴얼 발췌</h2>
              </div>
            </div>
            {manualResp?.items?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {manualResp.items.map((it, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 12,
                      background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                      border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        marginBottom: 8,
                        fontSize: 11,
                        color: 'var(--hud-text-dim)',
                        fontFamily: 'var(--hud-font-mono)',
                        letterSpacing: '0.06em',
                      }}
                    >
                      <span>
                        {it.source} · p.{it.page}
                      </span>
                      <span>관련도 {(it.relevance * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--hud-text)' }}>
                      {it.content}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="lg-empty">검색 결과가 없습니다. 질의를 입력 후 검색을 실행하세요.</div>
            )}
          </section>
        </>
      )}
    </>
  );
}
