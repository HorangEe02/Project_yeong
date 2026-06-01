// 부록 K — 16 카드 공통 Vision Dropzone.
// 각 카드는 이 컴포넌트를 dropzone 으로 사용 + onAnalyze 콜백으로 결과 처리.

import { useRef, useState, type ReactNode } from 'react';
import { Image as ImageIcon, Loader2 } from 'lucide-react';
import { runVisionTask, type VisionTaskId, type VisionTaskResponse } from '@api/visionTasks';

interface Props<T> {
  task: VisionTaskId;
  department?: string;
  accept?: string;            // 'image/*' | 'application/pdf,image/*'
  hint?: string;              // dropzone 안내 텍스트
  ctaLabel?: string;          // 분석 버튼 라벨
  onResult: (resp: VisionTaskResponse<T>) => void;
  children?: ReactNode;       // dropzone 외 추가 입력
}

export function VisionDropzone<T = Record<string, unknown>>({
  task, department = '', accept = 'image/*',
  hint = '이미지를 드래그하거나 클릭하여 선택 (최대 5 MB)',
  ctaLabel = '분석', onResult, children,
}: Props<T>) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = (f: File | null) => {
    setError(null);
    setFile(f);
  };

  const onAnalyze = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await runVisionTask<T>(task, file, department);
      if ((resp.data as { _parse_error?: boolean })._parse_error) {
        setError('AI 응답 파싱 실패 — 이미지가 명확한지 확인 후 재시도하세요.');
      }
      onResult(resp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div
        onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; }}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files?.[0] ?? null;
          if (f) onFile(f);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        style={{
          marginTop: 14,
          padding: 18,
          borderRadius: 10,
          border: '2px dashed var(--hud-border-light)',
          textAlign: 'center',
          cursor: 'pointer',
          background: file
            ? 'color-mix(in oklab, var(--hud-primary) 6%, transparent)'
            : 'transparent',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          hidden
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        <ImageIcon size={20} style={{ opacity: 0.6 }} />
        <div style={{ marginTop: 8, fontSize: 12 }}>
          {file ? file.name : hint}
        </div>
      </div>

      {children}

      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          className="lg-btn primary"
          onClick={onAnalyze}
          disabled={busy || !file}
          style={{ padding: '8px 18px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          {busy && <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />}
          {busy ? '분석 중…' : ctaLabel}
        </button>
      </div>

      {error && (
        <div style={{
          marginTop: 10, padding: '8px 12px', borderRadius: 8,
          border: '1px solid color-mix(in oklab, #dc2626 35%, transparent)',
          background: 'color-mix(in oklab, #dc2626 8%, transparent)',
          fontSize: 11,
        }}>⚠️ {error}</div>
      )}
    </>
  );
}
