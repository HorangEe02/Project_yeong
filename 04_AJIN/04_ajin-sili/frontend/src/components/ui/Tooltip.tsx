import type { ReactElement, ReactNode } from 'react';
import clsx from 'clsx';

interface Props {
  content: ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  children: ReactElement;
  className?: string;
}

export function Tooltip({ content, position = 'top', children, className }: Props) {
  return (
    <span className={clsx('ui-tooltip-trigger', className)}>
      {children}
      <span role="tooltip" className={clsx('ui-tooltip', `position-${position}`)}>
        {content}
      </span>
    </span>
  );
}
