import { Fragment } from 'react';
import clsx from 'clsx';

export interface Step {
  id: string;
  title: string;
  description?: string;
}

interface Props {
  steps: Step[];
  current: number;
  onStepClick?: (idx: number) => void;
  variant?: 'horizontal' | 'vertical';
}

export function Stepper({ steps, current, onStepClick, variant = 'horizontal' }: Props) {
  return (
    <div className={clsx('ui-stepper', variant === 'vertical' && 'vertical')}>
      {steps.map((step, idx) => {
        const isDone = idx < current;
        const isCurrent = idx === current;
        return (
          <Fragment key={step.id}>
            <div
              className={clsx(
                'ui-step',
                isDone && 'done',
                isCurrent && 'current',
                onStepClick && 'clickable',
              )}
              onClick={() => onStepClick?.(idx)}
              role={onStepClick ? 'button' : undefined}
              tabIndex={onStepClick ? 0 : undefined}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span className="ui-step-glyph" aria-hidden>
                {isDone ? '●' : isCurrent ? '◉' : idx + 1}
              </span>
              <div className="ui-step-text">
                <span className="ui-step-title">{step.title}</span>
                {step.description && <span className="ui-step-desc">{step.description}</span>}
              </div>
            </div>
            {variant === 'horizontal' && idx < steps.length - 1 && (
              <span className="ui-step-line" aria-hidden />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
