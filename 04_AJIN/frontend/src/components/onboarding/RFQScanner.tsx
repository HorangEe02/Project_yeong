// 부록 K Phase 1 — G6 영업 RFQ 스캔 분석 카드.

import { useState } from 'react';
import { FileSearch } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { RFQData, VisionTaskResponse } from '@api/visionTasks';

interface Props { department?: string }

export function RFQScanner({ department = '' }: Props) {
  const navigate = useNavigate();
  const [result, setResult] = useState<RFQData | null>(null);

  const onResult = (resp: VisionTaskResponse<RFQData>) => {
    if (resp.data._parse_error) return;
    setResult(resp.data);
  };

  const onPrefillDraft = () => {
    if (!result) return;
    const prefill = `[견적 요청 회신] ${result.customer || '고객사'} 귀하

부품번호: ${result.part_number}
부품명: ${result.part_name}
요청 수량: ${result.quantity}
요청 납기: ${result.due_date}
납품지: ${result.delivery_location}
특이사항: ${(result.special_requirements ?? []).join(' / ')}

위 RFQ에 대한 견적서 초안을 작성해 주세요. 결제 조건·유효기간 30일 포함.`;
    navigate('/draft', { state: { prefill, doc_type: 'Quote' } });
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader
        icon={<FileSearch size={16} />}
        eyebrow="RFQ SCANNER"
        title="RFQ 스캔 — 견적서 자동 prefill"
        subtitle="고객 RFQ 문서 → 부품·수량·납기 추출 → B 모듈 견적 초안 자동 생성"
      />

      <VisionDropzone<RFQData>
        task="rfq"
        department={department}
        accept="image/*,application/pdf"
        hint="RFQ 스캔본 또는 PDF 드래그·클릭"
        ctaLabel="RFQ 분석"
        onResult={onResult}
      />

      {result && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>추출 결과</div>
          <KeyValueGrid items={[
            { k: '고객사', v: result.customer },
            { k: '담당자', v: result.contact_person || '—' },
            { k: '부품번호', v: result.part_number },
            { k: '부품명', v: result.part_name },
            { k: '수량', v: String(result.quantity ?? '—') },
            { k: '납기', v: result.due_date || '—' },
            { k: '납품지', v: result.delivery_location || '—' },
            { k: '특이사항', v: (result.special_requirements ?? []).join(' · ') || '—' },
          ]} />
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={onPrefillDraft} className="lg-btn primary" style={{ padding: '6px 14px' }}>
              견적서 초안 작성 →
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
