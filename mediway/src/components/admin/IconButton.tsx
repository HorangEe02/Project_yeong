import { forwardRef } from 'react';

type Tone = 'default' | 'primary' | 'danger';

interface IconButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'ref'> {
  label: string;
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}

const toneClass: Record<Tone, string> = {
  default:
    'border-surface-container-high text-on-surface-variant hover:bg-surface-container-low',
  primary:
    'border-primary/40 bg-primary/5 text-primary hover:bg-primary/10',
  danger:
    'border-red-300 bg-red-50 text-red-600 hover:bg-red-100',
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton({ label, children, tone = 'default', className, ...rest }, ref) {
    return (
      <button
        ref={ref}
        type="button"
        aria-label={label}
        title={label}
        className={`flex h-7 w-7 items-center justify-center rounded-lg border ${toneClass[tone]} ${className ?? ''}`}
        {...rest}
      >
        {children}
      </button>
    );
  },
);
