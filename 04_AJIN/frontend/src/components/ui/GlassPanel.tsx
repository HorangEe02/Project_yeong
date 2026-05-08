import type { ReactNode } from 'react';
import clsx from 'clsx';

interface Props {
  children: ReactNode;
  intensity?: 'normal' | 'strong';
  as?: 'div' | 'aside' | 'header' | 'section';
  className?: string;
}

export function GlassPanel({ children, intensity = 'normal', as = 'div', className }: Props) {
  const Component = as;
  return (
    <Component
      className={clsx('ui-glass', intensity === 'strong' && 'intensity-strong', className)}
    >
      {children}
    </Component>
  );
}
