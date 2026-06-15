// 부록 3 — 템플릿 그리드의 11번째 카드: "내 양식 업로드".
// 기존 TemplateCard 와 시각 일관성 유지하되 점선 테두리 + Upload 아이콘.
// 페르소나: 사외 양식 강제 사용자 + 사내 표준 외 양식 첨부 시.

import { useRef } from 'react';
import { Upload, FileText, X as XIcon, AlertCircle } from 'lucide-react';
import type { UploadReferenceResponse } from '@/types/draft';

interface Props {
  uploadedRef: UploadReferenceResponse | null;
  uploadBusy: boolean;
  uploadError: string | null;
  onUpload: (file: File) => void;
  onClear: () => void;
}

export function TemplateUploadCard({
  uploadedRef,
  uploadBusy,
  uploadError,
  onUpload,
  onClear,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const selected = !!uploadedRef;

  const handleClick = () => {
    if (selected) return; // 업로드된 상태에서는 카드 자체 클릭 무시 — 변경/제거 버튼만 활성
    inputRef.current?.click();
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (!selected && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          handleClick();
        }
      }}
      className="lg-card lg-card-tight"
      style={{
        position: 'relative',
        cursor: selected ? 'default' : 'pointer',
        marginBottom: 0,
        outline: selected
          ? '2px solid var(--hud-primary)'
          : '1px dashed color-mix(in oklab, var(--hud-text) 22%, transparent)',
        outlineOffset: selected ? -2 : 0,
        background: selected
          ? 'color-mix(in oklab, var(--hud-primary) 8%, transparent)'
          : 'color-mix(in oklab, var(--hud-text) 2%, transparent)',
        transition: 'all 0.15s ease',
        minHeight: 158, // 다른 카드와 시각 균형
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
      title={selected ? '업로드된 양식 사용 중' : '내 양식 업로드 (DOCX/PDF/HWP/HWPX/TXT/MD ≤ 5MB)'}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".docx,.pdf,.hwp,.hwpx,.txt,.md,.markdown"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
        }}
        style={{ display: 'none' }}
      />

      {!selected ? (
        <>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: 8,
            }}
          >
            <span className="lg-pill">사용자 양식</span>
            <Upload size={14} strokeWidth={2} style={{ color: 'var(--hud-text-dim)' }} />
          </div>
          <h3
            style={{
              margin: '0 0 4px',
              fontSize: 16,
              lineHeight: 1.3,
              fontWeight: 600,
              color: 'var(--hud-text)',
              letterSpacing: '-0.01em',
            }}
          >
            내 양식 업로드
          </h3>
          <div
            style={{
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.1em',
              color: 'var(--hud-text-dim)',
              textTransform: 'uppercase',
              marginBottom: 10,
            }}
          >
            CUSTOM TEMPLATE
          </div>
          <p
            style={{
              margin: '0 0 10px',
              fontSize: 12,
              lineHeight: 1.55,
              color: 'var(--hud-text-dim)',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            기업 양식·신청서 등을 업로드하면 그 구조 그대로 작성됩니다.
          </p>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              paddingTop: 8,
              borderTop: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.06em',
              color: 'var(--hud-text-dim)',
            }}
          >
            {uploadBusy ? '업로드 중…' : 'DOCX · PDF · HWP · HWPX · TXT · MD'}
          </div>
        </>
      ) : (
        <>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: 8,
            }}
          >
            <span className="lg-pill">업로드됨</span>
            <button
              type="button"
              className="lg-btn ghost sm"
              onClick={(e) => {
                e.stopPropagation();
                onClear();
              }}
              title="양식 제거"
              style={{ padding: '2px 6px' }}
            >
              <XIcon size={12} strokeWidth={1.5} />
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={20} strokeWidth={1.5} style={{ color: 'var(--hud-primary)', flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: 'var(--hud-text)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
                title={uploadedRef.filename}
              >
                {uploadedRef.filename}
              </div>
              <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginTop: 2 }}>
                {uploadedRef.detected_format.toUpperCase()} · {uploadedRef.extracted_chars.toLocaleString()}자
                {uploadedRef.truncated && ' · 잘림'}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={(e) => {
              e.stopPropagation();
              inputRef.current?.click();
            }}
            style={{ marginTop: 'auto', fontSize: 11 }}
          >
            다른 양식으로 변경
          </button>
        </>
      )}

      {uploadError && (
        <div
          style={{
            marginTop: 8,
            padding: 6,
            borderRadius: 2,
            background: 'rgba(232,163,23,0.12)',
            border: '1px solid var(--hud-orange, #E8A317)',
            fontSize: 11,
            color: 'var(--hud-orange, #E8A317)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <AlertCircle size={12} strokeWidth={1.5} />
          {uploadError}
        </div>
      )}
    </div>
  );
}
