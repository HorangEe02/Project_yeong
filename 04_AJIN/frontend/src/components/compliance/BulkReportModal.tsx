// BulkReportModal — Module D Phase 4.
// 9개 크롤러 결과를 단일 파일로 통합 다운로드하는 모달.
// 디자인 시스템 v3.5 (HUD): 2px radius, 골드 강조.

import { useState } from 'react';
import { Package, Download, CheckCircle2 } from 'lucide-react';
import { Modal } from '@components/ui/Modal';
import { Button } from '@components/ui/Button';
import { api } from '@api/client';
import { useToastStore } from '@store/toast';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

type BulkFormat = 'report' | 'docx' | 'xlsx' | 'pdf' | 'json' | 'zip';

const BULK_FORMATS: {
  fmt: BulkFormat;
  label: string;
  ext: string;
  tagline: string;
  desc: string;
  recommended?: boolean;
}[] = [
  {
    fmt: 'report',
    label: '📑 회사 양식 보고서',
    ext: 'docx',
    tagline: 'DOCX · 회사 양식',
    desc: '표지(회사명·작성자·기간) + 목차 + Executive Summary + 9개 섹션 + 부록. 그대로 임원 보고에 활용 가능.',
    recommended: true,
  },
  {
    fmt: 'xlsx',
    label: '📊 엑셀 (9 시트)',
    ext: 'xlsx',
    tagline: 'XLSX · 시트별 분리',
    desc: 'Summary + 9개 크롤러별 시트. 데이터 분석/필터/피벗에 적합.',
  },
  {
    fmt: 'docx',
    label: '📝 워드 (간단)',
    ext: 'docx',
    tagline: 'DOCX · 간단',
    desc: '표지 없이 9 섹션만. 회사 양식보다 짧은 버전.',
  },
  {
    fmt: 'pdf',
    label: '📄 PDF',
    ext: 'pdf',
    tagline: 'PDF · 한글 폰트',
    desc: '각 크롤러 상위 10개 항목. 출력/아카이빙용.',
  },
  {
    fmt: 'json',
    label: '🗂 JSON 합본',
    ext: 'json',
    tagline: 'JSON · raw',
    desc: '9개 크롤러 raw 데이터 단일 객체. 자동화/추가 가공용.',
  },
  {
    fmt: 'zip',
    label: '📦 ZIP 묶음',
    ext: 'zip',
    tagline: 'ZIP · 9 개별 JSON + index.csv',
    desc: '개별 파일이 필요한 경우. index.csv 포함.',
  },
];

export function BulkReportModal({ isOpen, onClose }: Props) {
  const [selectedFmt, setSelectedFmt] = useState<BulkFormat>('report');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addToast = useToastStore.getState().addToast;

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      // axios 사용 — interceptor 의 auto auth + 401 refresh + /login 리다이렉트 활용
      const res = await api.get<Blob>(
        `/compliance/crawl/results/bulk-download`,
        { params: { format: selectedFmt }, responseType: 'blob' },
      );
      const blob = res.data;
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const meta = BULK_FORMATS.find((f) => f.fmt === selectedFmt);
      const suffix = selectedFmt === 'report' ? '_report' : '';
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `compliance_bulk_${today}${suffix}.${meta?.ext ?? selectedFmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      addToast({
        type: 'success',
        message: `통합 보고서 다운로드 완료 (${meta?.label ?? selectedFmt})`,
        duration: 2500,
      });
      setTimeout(() => onClose(), 600);
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        addToast({
          type: 'warning',
          message: '세션이 만료되었습니다. 다시 로그인해 주세요.',
          duration: 3500,
        });
        // axios interceptor 가 이미 /login 리다이렉트를 처리했을 것
      } else {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        addToast({
          type: 'error',
          message: `통합 보고서 다운로드 실패: ${msg}`,
          duration: 4000,
        });
      }
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg" title="전체 통합 보고서 다운로드">
      <div style={{ padding: '4px 4px 12px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 6,
          }}
        >
          <Package
            size={18}
            strokeWidth={1.5}
            style={{ color: 'var(--hud-primary)' }}
          />
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>
            9개 크롤러 결과 통합 다운로드
          </h3>
        </div>
        <p
          style={{
            margin: '0 0 16px 0',
            fontSize: 12,
            color: 'var(--hud-text-dim)',
            lineHeight: 1.55,
          }}
        >
          ISO · MSDS · EU Regulation · Domestic Law · OEM Quality · APQP · Carbon ESG ·
          EV Battery · Global Trade — 모든 크롤러 결과를 하나의 파일로 받습니다.
        </p>

        {/* 포맷 선택 카드 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 8,
            marginBottom: 14,
          }}
        >
          {BULK_FORMATS.map(({ fmt, label, tagline, desc, recommended }) => {
            const selected = selectedFmt === fmt;
            return (
              <button
                key={fmt}
                onClick={() => setSelectedFmt(fmt)}
                style={{
                  textAlign: 'left',
                  padding: 12,
                  borderRadius: 2,
                  border: selected
                    ? '2px solid var(--hud-primary)'
                    : '1px solid var(--hud-border, #2A2520)',
                  background: selected
                    ? 'color-mix(in oklab, var(--hud-primary) 10%, transparent)'
                    : 'var(--hud-surface, #111820)',
                  cursor: 'pointer',
                  position: 'relative',
                  transition: 'border 0.15s, background 0.15s',
                }}
                disabled={downloading}
              >
                {recommended && (
                  <span
                    style={{
                      position: 'absolute',
                      top: 6,
                      right: 6,
                      fontSize: 9,
                      padding: '2px 6px',
                      borderRadius: 999,
                      background: 'var(--hud-primary)',
                      color: 'var(--hud-bg)',
                      fontWeight: 700,
                      letterSpacing: '0.05em',
                    }}
                  >
                    추천
                  </span>
                )}
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: selected ? 'var(--hud-primary)' : 'var(--hud-text)',
                    marginBottom: 2,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  {selected && (
                    <CheckCircle2
                      size={14}
                      strokeWidth={2}
                      style={{ color: 'var(--hud-primary)' }}
                    />
                  )}
                  {label}
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--hud-text-muted)',
                    letterSpacing: '0.05em',
                    marginBottom: 4,
                  }}
                >
                  {tagline}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--hud-text-dim)',
                    lineHeight: 1.5,
                  }}
                >
                  {desc}
                </div>
              </button>
            );
          })}
        </div>

        {/* 에러 메시지 */}
        {error && (
          <div
            style={{
              padding: 10,
              marginBottom: 12,
              borderRadius: 2,
              background: 'rgba(232,163,23,0.10)',
              border: '1px solid var(--hud-orange)',
              color: 'var(--hud-orange)',
              fontSize: 12,
            }}
          >
            ⚠ 다운로드 실패: {error}
          </div>
        )}

        {/* 액션 버튼 */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={downloading}>
            취소
          </Button>
          <Button variant="primary" size="sm" onClick={handleDownload} disabled={downloading}>
            <Download size={14} strokeWidth={1.5} style={{ marginRight: 6 }} />
            {downloading ? '다운로드 중...' : '다운로드'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
