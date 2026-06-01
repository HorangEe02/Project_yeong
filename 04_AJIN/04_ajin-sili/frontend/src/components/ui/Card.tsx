import type { ReactNode, MouseEventHandler, CSSProperties } from 'react';
import clsx from 'clsx';

export type CardVariant = 'default' | 'highlighted' | 'flat';
export type CardPadding = 'none' | 'sm' | 'md' | 'lg';

interface Props {
  children: ReactNode;
  variant?: CardVariant;
  padding?: CardPadding;
  className?: string;
  style?: CSSProperties;
  onClick?: MouseEventHandler<HTMLDivElement>;
  asGlass?: boolean;
}

export function Card({
  children,
  variant = 'default',
  padding = 'md',
  className,
  style,
  onClick,
  asGlass = false,
}: Props) {
  return (
    <div
      className={clsx(
        'ui-card',
        variant !== 'default' && variant,
        padding !== 'md' && `padding-${padding}`,
        onClick && 'clickable',
        asGlass && 'ui-glass',
        className,
      )}
      style={style}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}
