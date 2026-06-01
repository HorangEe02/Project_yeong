// 부록 K Phase 1 — G6 영업 명함 OCR 카드.

import { useState } from 'react';
import { Contact } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { CardHeader, KeyValueGrid } from './_ui';
import { VisionDropzone } from './_visionDropzone';
import type { BusinessCardData, VisionTaskResponse } from '@api/visionTasks';

interface Props { department?: string }

export function BusinessCardOCR({ department = '' }: Props) {
  const navigate = useNavigate();
  const [result, setResult] = useState<BusinessCardData | null>(null);

  const onResult = (resp: VisionTaskResponse<BusinessCardData>) => {
    if (resp.data._parse_error) return;
    setResult(resp.data);
  };

  const onSaveToCRM = () => {
    if (!result) return;
    // CRM 시스템 미연동 — 시연용 alert + /search 인사 탭으로 라우팅 (참고용)
    alert(`CRM 등록 완료 (시연):\n${result.name} · ${result.company} · ${result.email}`);
    navigate('/search', { state: { prefillQuery: result.company, source: 'card-ocr' } });
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <CardHeader
        icon={<Contact size={16} />}
        eyebrow="BUSINESS CARD OCR"
        title="명함 OCR — CRM 자동 등록"
        subtitle="고객·협력사 명함 사진 → 이름·회사·연락처 자동 추출 → CRM 등록"
      />

      <VisionDropzone<BusinessCardData>
        task="business-card"
        department={department}
        hint="명함 사진을 드래그하거나 클릭하여 선택"
        ctaLabel="명함 분석"
        onResult={onResult}
      />

      {result && (
        <div style={{ marginTop: 16, padding: 14, borderRadius: 10,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)' }}>
          <div className="lg-eyebrow" style={{ fontSize: 10, opacity: 0.7 }}>추출 결과</div>
          <KeyValueGrid items={[
            { k: '이름', v: `${result.name}${result.name_en ? ` (${result.name_en})` : ''}` },
            { k: '회사', v: result.company },
            { k: '직책', v: result.title || '—' },
            { k: '부서', v: result.department || '—' },
            { k: '이메일', v: result.email || '—' },
            { k: '휴대전화', v: result.phone_mobile || '—' },
            { k: '사무실', v: result.phone_office || '—' },
            { k: '주소', v: result.address || '—' },
          ]} />
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={onSaveToCRM} className="lg-btn primary" style={{ padding: '6px 14px' }}>
              CRM 등록
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
