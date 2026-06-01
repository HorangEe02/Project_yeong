// EquipmentTypeSubTab — F-equipment 서브탭 (장비 유형별 ML 신호 표).

import type { EquipRow } from '../types';

interface Props {
  equipment7: EquipRow[];
}

export function EquipmentTypeSubTab({ equipment7 }: Props) {
  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">TYPES · 장비 유형별 ML 신호</div>
          <h2 className="lg-h2">상세 진단</h2>
        </div>
      </div>
      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr>
              <th>장비</th>
              <th>상태</th>
              <th>Cpk</th>
              <th>알람</th>
              <th>ML 신호</th>
            </tr>
          </thead>
          <tbody>
            {equipment7.map((e) => (
              <tr key={e.type}>
                <td>
                  <b>{e.type}</b> <span className="dim mono">· {e.en}</span>
                </td>
                <td>
                  <span className={'lg-state-pill ' + e.state}>{e.state.toUpperCase()}</span>
                </td>
                <td className="mono">{e.cpk}</td>
                <td>{e.alarm}</td>
                <td className="dim">
                  {e.alarm > 0 ? 'Isolation Forest 이상치 + Markov 후속 위험' : '정상 범위'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
