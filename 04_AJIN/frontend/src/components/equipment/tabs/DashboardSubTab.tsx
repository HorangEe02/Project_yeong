// DashboardSubTab — F-overview 서브탭 (실시간 설비 상태 + 7장비 카드).
// v3.8 — 7대 장비 카드에 hover tooltip + 클릭 시 하단 Drawer 상세 패널 추가 (신입 교육용).

import { useState } from 'react';
import type { OverviewResponse } from '@/types/equipment';
import type { EquipRow, MetricCard } from '../types';
import { DataClassBadge } from '@/lib/syntheticBadge';
import { EquipmentHoverCard } from '../EquipmentHoverCard';
import { EquipmentDetailDrawer } from '../EquipmentDetailDrawer';

interface Props {
  metrics: readonly MetricCard[] | MetricCard[];
  equipment7: EquipRow[];
  overview: OverviewResponse | null;
}

export function DashboardSubTab({ metrics, equipment7, overview }: Props) {
  const [selected, setSelected] = useState<EquipRow | null>(null);

  return (
    <>
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">METRICS · 핵심 지표</div>
            <h2 className="lg-h2">실시간 설비 상태</h2>
          </div>
          {overview && <span className="lg-pill">LIVE</span>}
        </div>
        <div className="lg-metric-row" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
          {metrics.map((m) => (
            <div key={m.en} className="lg-metric">
              <span className="k">{m.ko}</span>
              <span className="v">{m.v}</span>
              <span className="en mono">{m.en}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">EQUIPMENT · {equipment7.length}종 상태</div>
            <h2 className="lg-h2">장비별 Cpk · 알람</h2>
          </div>
          <span className="lg-mini" style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
            카드 hover · 클릭 시 상세 학습
          </span>
        </div>
        <div className="lg-equip-grid">
          {equipment7.map((e) => (
            <EquipmentHoverCard key={e.type} row={e} onClick={() => setSelected(e)}>
              <div className={'lg-equip state-' + e.state}>
                <div className="lg-equip-h">
                  <span className="ko">{e.type}</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <DataClassBadge dataClass={e.dataClass} sourceSystem={e.sourceSystem} />
                    <span className="lg-state-dot" />
                  </span>
                </div>
                <div className="lg-equip-en mono">{e.en}</div>
                <div className="lg-equip-stat">
                  <div>
                    <i>Cpk</i>
                    <b>{e.cpk}</b>
                  </div>
                  <div>
                    <i>알람</i>
                    <b>{e.alarm}</b>
                  </div>
                </div>
              </div>
            </EquipmentHoverCard>
          ))}
        </div>
      </section>

      <EquipmentDetailDrawer selected={selected} onClose={() => setSelected(null)} />
    </>
  );
}
