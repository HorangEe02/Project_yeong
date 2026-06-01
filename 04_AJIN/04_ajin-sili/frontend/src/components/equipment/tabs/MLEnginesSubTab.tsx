// MLEnginesSubTab — F-ml 서브탭 (7종 ML 모델 인벤토리).
// W1 (P1): 각 엔진 카드에 한국어 설명 + ⓘ tooltip 추가 — 신입사원이 5초 안에 의미 파악.

import { useState } from 'react';
import { Info } from 'lucide-react';
import type { MLEnginesStatusResponse } from '@/types/equipment';
import type { MLEngineDisplay } from '../types';

// 엔진 이름(or model)별 한국어 설명. 키 매칭은 case-insensitive substring.
const ENGINE_HINTS: { match: string; label: string; detail: string }[] = [
  {
    match: 'tf-idf error',
    label: 'TF-IDF 에러 검색',
    detail: '에러 685건의 자연어 설명에서 키워드 가중치 기반 유사 사례 검색. SPC 위반 발생 시 과거 같은 패턴의 조치 이력을 빠르게 찾는 데 사용.',
  },
  {
    match: 'isolation forest',
    label: 'Isolation Forest SPC',
    detail: 'SPC 측정값의 원시값·차분·이동평균 편차·이동표준편차·Z-score 특성으로 이상치를 감지하고 Cpk 추세와 결합해 조기 경보에 사용.',
  },
  {
    match: 'xgboost',
    label: 'XGBoost 금형 수명',
    detail: '금형 사용률·불량률·보전횟수·소재/부하 계수·SPC 이상률 등 10개 특성으로 잔여 shots와 교체 예정일을 산출.',
  },
  {
    match: 'markov',
    label: 'Markov 연쇄',
    detail: '에러 코드 간 전이 확률 행렬. 1차 발생 코드로부터 다음 단계 고장(예: E2103 → E3115)을 예측해 캐스케이드 차단 조치.',
  },
  {
    match: 'mtbf',
    label: 'MTBF 예측',
    detail: '수리 이력의 평균 고장 간격과 계절 패턴을 계산해 다음 정비 시점, 주의 설비, 누적 비용 상위 설비를 산출.',
  },
  {
    match: 'causality',
    label: '인과 규칙',
    detail: '에러 코드 카테고리 간 원인/후속 조치 규칙을 제공하고 Markov 예측의 전이 시퀀스 생성을 보강.',
  },
  {
    match: 'manual',
    label: '매뉴얼 검색/RAG',
    detail: '설비 매뉴얼 인덱스가 있으면 벡터 검색을 사용하고, 경량 배포에서는 로컬 매뉴얼 텍스트 검색으로 안전하게 폴백.',
  },
];

function findHint(name: string, model: string) {
  const blob = `${name} ${model}`.toLowerCase();
  return ENGINE_HINTS.find((h) => blob.includes(h.match));
}

interface Props {
  mlList: MLEngineDisplay[];
  mlEngines: MLEnginesStatusResponse | null;
}

export function MLEnginesSubTab({ mlList, mlEngines }: Props) {
  const onlineCount = mlEngines?.online_count ?? mlList.filter((e) => e.online).length;
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">ML ENGINES · {mlList.length}종 상태</div>
          <h2 className="lg-h2">모델 인벤토리</h2>
        </div>
        <span className="lg-pill">
          {onlineCount}/{mlList.length} ACTIVE
        </span>
      </div>
      <div className="lg-ml-grid">
        {mlList.map((m, i) => {
          const hint = findHint(m.name, m.model);
          const open = openIdx === i;
          const state = m.status ?? (m.online ? 'online' : 'offline');
          const stateClass = state === 'online' ? 'ok' : state === 'warning' ? 'warn' : 'crit';
          const stateLabel = state === 'online' ? 'ON' : state === 'warning' ? 'WARN' : 'OFF';
          return (
            <div key={`${m.name}-${i}`} className="lg-ml" style={{ position: 'relative' }}>
              <div className="lg-ml-h">
                <span className="num mono">{String(i + 1).padStart(2, '0')}</span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  {hint && (
                    <button
                      type="button"
                      onClick={() => setOpenIdx(open ? null : i)}
                      title={hint.label + ' 설명 보기'}
                      aria-label={hint.label + ' 설명 보기'}
                      style={{
                        background: open
                          ? 'color-mix(in oklab, var(--hud-primary) 18%, transparent)'
                          : 'transparent',
                        border: 'none',
                        color: 'var(--hud-text-dim)',
                        cursor: 'pointer',
                        padding: 2,
                        borderRadius: 4,
                        display: 'inline-flex',
                      }}
                    >
                      <Info size={14} aria-hidden="true" />
                    </button>
                  )}
                  <span className={`lg-state-dot ${stateClass}`} />
                </div>
              </div>
              <div className="lg-ml-name">{m.name}</div>
              <div className="lg-ml-model dim">{m.model}</div>
              <div className="lg-ml-foot">
                <span className="mono">p99 {m.p99}</span>
                <span className={`lg-ml-state ${stateClass} mono`}>
                  ● {stateLabel}
                </span>
              </div>

              {open && hint && (
                <div
                  style={{
                    marginTop: 10,
                    padding: 10,
                    borderRadius: 8,
                    border: '1px solid color-mix(in oklab, var(--hud-primary) 30%, transparent)',
                    background: 'color-mix(in oklab, var(--hud-primary) 6%, transparent)',
                    fontSize: 11,
                    lineHeight: 1.55,
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>{hint.label}</div>
                  <div style={{ opacity: 0.85 }}>{hint.detail}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
