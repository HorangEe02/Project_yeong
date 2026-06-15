// 부록 K Phase 1 — G7-Finance 영수증·세금계산서 OCR 카드.

import { useState } from 'react';
import { Receipt } from 'lucide-react';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { ReceiptData, VisionTaskResponse } from '@api/visionTasks';

interface Props { department?: string }

function toKRW(v: number | string): string {
  const n = typeof v === 'number' ? v : Number(String(v).replace(/[^\d.-]/g, ''));
  if (!isFinite(n)) return String(v);
  return n.toLocaleString('ko-KR') + ' 원';
}

export function ReceiptOCR({ department = '' }: Props) {
  const [result, setResult] = useState<ReceiptData | null>(null);

  const onResult = (resp: VisionTaskResponse<ReceiptData>) => {
    if (resp.data._parse_error) return;
    setResult(resp.data);
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader
        icon={<Receipt size={16} />}
        eyebrow="RECEIPT OCR"
        title="영수증·세금계산서 OCR — 회계 분개 자동 생성"
        subtitle="영수증·세금계산서 사진 → 금액·항목·분개 자동 추출"
      />

      <VisionDropzone<ReceiptData>
        task="receipt"
        department={department}
        accept="image/*,application/pdf"
        hint="영수증 사진 또는 세금계산서 PDF"
        ctaLabel="영수증 분석"
        onResult={onResult}
      />

      {result && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>거래 정보</div>
          <KeyValueGrid items={[
            { k: '거래처', v: result.merchant },
            { k: '사용일', v: result.date || '—' },
            { k: '공급가액', v: toKRW(result.amount_supply) },
            { k: '부가세', v: toKRW(result.amount_vat) },
            { k: '합계', v: toKRW(result.amount_total) },
            { k: '회계 항목', v: result.category || '—' },
            { k: '사용 목적', v: result.purpose || '—' },
          ]} />

          {result.journal_entry && (
            <div style={{ marginTop: 12, padding: 12, borderRadius: 8,
              background: 'color-mix(in oklab, var(--hud-primary) 6%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-primary) 35%, transparent)' }}>
              <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>제안 분개</div>
              <KeyValueGrid items={[
                { k: '차변(Dr)', v: result.journal_entry.debit_account },
                { k: '대변(Cr)', v: result.journal_entry.credit_account },
                { k: '적요', v: result.journal_entry.summary },
              ]} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
