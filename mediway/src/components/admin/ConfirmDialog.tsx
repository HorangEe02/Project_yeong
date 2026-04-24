import { useState, type ReactNode } from 'react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  requireText?: string;
  children?: ReactNode;
  onConfirm: () => void | Promise<void>;
  onClose: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = '확인',
  cancelLabel = '취소',
  danger,
  requireText,
  children,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const canConfirm = !requireText || input === requireText;

  const onClick = async () => {
    setLoading(true);
    try {
      await onConfirm();
      setInput('');
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <h3 className="text-base font-semibold text-on-surface">{title}</h3>
        {description && (
          <p className="mt-1 text-sm text-on-surface-variant">{description}</p>
        )}
        {children}
        {requireText && (
          <div className="mt-3 flex flex-col gap-1.5">
            <label className="text-xs text-on-surface-variant">
              계속하려면{' '}
              <span className="font-mono text-red-600">{requireText}</span> 을(를)
              입력하세요
            </label>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => {
              setInput('');
              onClose();
            }}
            className="rounded-lg border border-surface-container-high px-4 py-2 text-sm text-on-surface"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onClick}
            disabled={!canConfirm || loading}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50 ${
              danger ? 'bg-red-600' : 'bg-primary'
            }`}
          >
            {loading ? '처리 중...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
