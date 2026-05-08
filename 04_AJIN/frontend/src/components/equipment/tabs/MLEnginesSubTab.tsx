// MLEnginesSubTab — F-ml 서브탭 (7종 ML 모델 인벤토리).

import type { MLEnginesStatusResponse } from '@/types/equipment';
import type { MLEngineDisplay } from '../types';

interface Props {
  mlList: MLEngineDisplay[];
  mlEngines: MLEnginesStatusResponse | null;
}

export function MLEnginesSubTab({ mlList, mlEngines }: Props) {
  const onlineCount = mlEngines?.online_count ?? mlList.filter((e) => e.online).length;
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
        {mlList.map((m, i) => (
          <div key={`${m.name}-${i}`} className="lg-ml">
            <div className="lg-ml-h">
              <span className="num mono">{String(i + 1).padStart(2, '0')}</span>
              <span className={`lg-state-dot ${m.online ? 'ok' : 'crit'}`} />
            </div>
            <div className="lg-ml-name">{m.name}</div>
            <div className="lg-ml-model dim">{m.model}</div>
            <div className="lg-ml-foot">
              <span className="mono">p99 {m.p99}</span>
              <span className={m.online ? 'lg-ok mono' : 'lg-err mono'}>
                ● {m.online ? 'ON' : 'OFF'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
