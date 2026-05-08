import {
  forwardRef,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import clsx from 'clsx';

export interface FormFieldProps {
  label: string;
  name: string;
  required?: boolean;
  error?: string;
  helperText?: string;
  className?: string;
}

interface InputProps
  extends FormFieldProps,
    Omit<InputHTMLAttributes<HTMLInputElement>, 'name'> {
  type?: 'text' | 'email' | 'password' | 'number' | 'date' | 'search';
}

interface SelectProps
  extends FormFieldProps,
    Omit<SelectHTMLAttributes<HTMLSelectElement>, 'name'> {
  options: { value: string; label: string; disabled?: boolean }[];
}

interface TextareaProps
  extends FormFieldProps,
    Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'name'> {}

function Wrapper({
  label,
  name,
  required,
  error,
  helperText,
  className,
  children,
}: FormFieldProps & { children: React.ReactNode }) {
  return (
    <div className={clsx('ui-field', className)} data-error={Boolean(error)}>
      <label className="ui-field-label" htmlFor={name}>
        {label}
        {required && <span className="ui-field-required" aria-hidden>●</span>}
      </label>
      {children}
      {helperText && !error && <span className="ui-field-helper">{helperText}</span>}
      {error && (
        <span className="ui-field-error" role="alert">
          ● {error}
        </span>
      )}
    </div>
  );
}

export const TextField = forwardRef<HTMLInputElement, InputProps>(function TextField(
  { label, name, required, error, helperText, className, type = 'text', ...rest },
  ref,
) {
  return (
    <Wrapper {...{ label, name, required, error, helperText, className }}>
      <input
        ref={ref}
        id={name}
        name={name}
        type={type}
        required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : undefined}
        className="ui-field-input"
        {...rest}
      />
    </Wrapper>
  );
});

export const SelectField = forwardRef<HTMLSelectElement, SelectProps>(function SelectField(
  { label, name, required, error, helperText, className, options, ...rest },
  ref,
) {
  return (
    <Wrapper {...{ label, name, required, error, helperText, className }}>
      <select
        ref={ref}
        id={name}
        name={name}
        required={required}
        aria-invalid={Boolean(error)}
        className="ui-field-select"
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
    </Wrapper>
  );
});

export const TextareaField = forwardRef<HTMLTextAreaElement, TextareaProps>(function TextareaField(
  { label, name, required, error, helperText, className, ...rest },
  ref,
) {
  return (
    <Wrapper {...{ label, name, required, error, helperText, className }}>
      <textarea
        ref={ref}
        id={name}
        name={name}
        required={required}
        rows={4}
        aria-invalid={Boolean(error)}
        className="ui-field-textarea"
        {...rest}
      />
    </Wrapper>
  );
});
