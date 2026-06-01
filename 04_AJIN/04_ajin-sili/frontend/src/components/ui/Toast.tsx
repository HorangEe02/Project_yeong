import { X } from 'lucide-react';
import { useToastStore, type ToastItem } from '@store/toast';

const GLYPH = '●';

function ToastView({ toast, onClose }: { toast: ToastItem; onClose: () => void }) {
  return (
    <div className={`ui-toast type-${toast.type}`} role="status" aria-live="polite">
      <span className="ui-toast-glyph" aria-hidden>{GLYPH}</span>
      <div className="ui-toast-content">
        {toast.title && <div className="ui-toast-title">{toast.title}</div>}
        <div className="ui-toast-msg">{toast.message}</div>
      </div>
      {toast.action && (
        <button className="ui-toast-action" onClick={toast.action.onClick}>
          {toast.action.label}
        </button>
      )}
      <button className="ui-toast-close" onClick={onClose} aria-label="Close">
        <X size={12} strokeWidth={1.5} />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);
  if (toasts.length === 0) return null;
  return (
    <div className="ui-toast-stack" aria-label="Notifications">
      {toasts.map((t) => (
        <ToastView key={t.id} toast={t} onClose={() => removeToast(t.id)} />
      ))}
    </div>
  );
}
