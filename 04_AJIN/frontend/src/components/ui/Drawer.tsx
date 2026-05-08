import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import clsx from 'clsx';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  side?: 'right' | 'left' | 'bottom';
  width?: number;
  height?: number;
  title?: string;
  children: ReactNode;
}

export function Drawer({
  isOpen,
  onClose,
  side = 'right',
  width = 400,
  height = 400,
  title,
  children,
}: Props) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizeStyle =
    side === 'bottom' ? { height, width: '100%' } : { width, height: '100%' };

  return createPortal(
    <>
      <div className="ui-drawer-scrim" onClick={onClose} role="presentation" />
      <aside
        className={clsx('ui-drawer', `side-${side}`)}
        style={sizeStyle}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'ui-drawer-title' : undefined}
      >
        {title && (
          <div className="ui-modal-header">
            <span id="ui-drawer-title" className="ui-modal-title">{title}</span>
            <button className="ui-modal-close" onClick={onClose} aria-label="Close">
              <X size={16} strokeWidth={1.5} />
            </button>
          </div>
        )}
        <div className="ui-modal-body">{children}</div>
      </aside>
    </>,
    document.body,
  );
}
