// 부록 K Phase 2 — G8 구매 발주서 OCR 카드.

import { useState } from 'react';
import { ClipboardList } from 'lucide-react';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { POData } from '@api/visionTasks';

interface Props { department?: string }

export function POScanner({ department = '' }: Props) {
  const [r, setR] = useState<POData | null>(null);
  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader icon={<ClipboardList size={16} />} eyebrow="PURCHASE ORDER"
        title="발주서 OCR — ERP 등록 가이드" subtitle="발주서 사진/PDF → 부품·수량·단가 표 자동 추출" />
      <VisionDropzone<POData> task="po" department={department}
        accept="application/pdf,image/*" hint="발주서 PDF·사진" ctaLabel="발주서 분석"
        onResult={(resp) => !resp.data._parse_error && setR(resp.data)} />
      {r && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <KeyValueGrid items={[
            { k: '발주번호', v: r.po_number || '—' },
            { k: '협력사', v: r.vendor || '—' },
            { k: '발행일', v: r.issued_date || '—' },
            { k: '납기', v: r.delivery_date || '—' },
            { k: '총액', v: String(r.total_amount ?? '—') },
            { k: '결제 조건', v: r.payment_terms || '—' },
            { k: '납품지', v: r.delivery_location || '—' },
          ]} />
          {r.items?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>부품 리스트</div>
              <table style={{ width: '100%', marginTop: 6, fontSize: 11, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--hud-border)' }}>
                    <th style={{ textAlign: 'left', padding: 4 }}>부품번호</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>부품명</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>수량</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>단가</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>합계</th>
                  </tr>
                </thead>
                <tbody>
                  {r.items.map((it, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--hud-border)' }}>
                      <td style={{ padding: 4 }}>{it.part_number}</td>
                      <td style={{ padding: 4 }}>{it.name}</td>
                      <td style={{ padding: 4, textAlign: 'right' }}>{it.qty}</td>
                      <td style={{ padding: 4, textAlign: 'right' }}>{it.unit_price?.toLocaleString?.() ?? it.unit_price}</td>
                      <td style={{ padding: 4, textAlign: 'right' }}>{it.total?.toLocaleString?.() ?? it.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
