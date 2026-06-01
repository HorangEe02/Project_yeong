// 부록 K Phase 3 — G8 자재 입고 검수 카드.

import { useState } from 'react';
import { PackageCheck } from 'lucide-react';
import { CardHeader, KeyValueGrid, ChipRow } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { InventoryReceiveData } from '@api/visionTasks';

interface Props { department?: string }

export function InventoryReceiveScanner({ department = '' }: Props) {
  const [r, setR] = useState<InventoryReceiveData | null>(null);
  const ok = String(r?.ok_to_receive) === 'true';
  const color = ok ? '#16a34a' : '#dc2626';
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<PackageCheck size={16} />} eyebrow="INVENTORY RECEIVE"
        title="자재 입고 검수" subtitle="입고 박스 사진 → 협력사·수량·포장 상태 1차 자동 검수" />
      <VisionDropzone<InventoryReceiveData> task="inventory-receive" department={department}
        hint="입고 자재 박스 사진" ctaLabel="입고 검수"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: `1px solid ${color}`, background: 'var(--hud-surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>1차 검수 결과</div>
            <span style={{ fontSize: 11, fontWeight: 700, color,
              padding: '2px 8px', borderRadius: 4, border: `1px solid ${color}` }}>
              {ok ? '✅ 입고 가능' : '⚠ 보류'}
            </span>
          </div>
          <KeyValueGrid items={[
            { k: '협력사', v: r.vendor || '—' },
            { k: '부품번호', v: r.part_number || '—' },
            { k: '박스 수량', v: String(r.package_count ?? '—') },
            { k: '포장 상태', v: r.package_condition || '—' },
            { k: '다음 조치', v: r.next_action || '—' },
          ]} />
          {r.visible_defects?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, opacity: 0.6, color: '#dc2626' }}>⚠ 외관 결함</div>
              <ChipRow items={r.visible_defects} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
