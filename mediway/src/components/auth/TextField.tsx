import { forwardRef, useState } from 'react';
import type { InputHTMLAttributes } from 'react';
import { Eye, EyeOff } from 'lucide-react';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string | null;
  hint?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField({ label, error, hint, type = 'text', id, ...rest }, ref) {
    const [show, setShow] = useState(false);
    const inputId = id ?? `tf-${label.replace(/\s+/g, '-').toLowerCase()}`;
    const isPassword = type === 'password';
    const effectiveType = isPassword && show ? 'text' : type;

    return (
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={inputId}
          className="text-xs font-medium text-on-surface-variant"
        >
          {label}
        </label>
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            type={effectiveType}
            className={`w-full rounded-lg border bg-surface px-3 py-2.5 text-sm text-on-surface outline-none transition-colors placeholder:text-on-surface-variant/50 focus:border-primary ${
              error ? 'border-red-400' : 'border-surface-container-high'
            } ${isPassword ? 'pr-10' : ''}`}
            {...rest}
          />
          {isPassword && (
            <button
              type="button"
              onClick={() => setShow((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-on-surface-variant hover:text-on-surface"
              tabIndex={-1}
              aria-label={show ? '비밀번호 숨기기' : '비밀번호 보이기'}
            >
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          )}
        </div>
        {error ? (
          <p className="text-xs text-red-500">{error}</p>
        ) : hint ? (
          <p className="text-xs text-on-surface-variant/70">{hint}</p>
        ) : null}
      </div>
    );
  },
);
