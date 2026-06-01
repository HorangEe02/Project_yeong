import { useEffect, useRef, type ReactNode, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import clsx from 'clsx';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  closeOnEsc?: boolean;
  closeOnOverlay?: boolean;
  hideCloseButton?: boolean;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  size = 'md',
  closeOnEsc = true,
  closeOnOverlay = true,
  hideCloseButton = false,
  children,
  footer,
  className,
}: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    lastFocused.current = document.activeElement as HTMLElement;
    dialogRef.current?.focus();
    const handleKey = (e: KeyboardEvent) => {
      if (closeOnEsc && e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = '';
      lastFocused.current?.focus();
    };
  }, [isOpen, closeOnEsc, onClose]);

  if (!isOpen) return null;

  const handleScrimClick = (e: MouseEvent<HTMLDivElement>) => {
    if (closeOnOverlay && e.target === e.currentTarget) {
      onClose();
    }
  };

  return createPortal(
    <div className="ui-modal-scrim" onClick={handleScrimClick} role="presentation">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'ui-modal-title' : undefined}
        tabIndex={-1}
        className={clsx('ui-modal ui-glass', `size-${size}`, className)}
      >
        {(title || !hideCloseButton) && (
          <div className="ui-modal-header">
            {title && <span id="ui-modal-title" className="ui-modal-title">{title}</span>}
            {!hideCloseButton && (
              <button className="ui-modal-close" onClick={onClose} aria-label="Close">
                <X size={16} strokeWidth={1.5} />
              </button>
            )}
          </div>
        )}
        <div className="ui-modal-body">{children}</div>
        {footer && (
          <div className="ui-modal-header" style={{ borderBottom: 'none', borderTop: '1px solid var(--hud-border)' }}>
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
