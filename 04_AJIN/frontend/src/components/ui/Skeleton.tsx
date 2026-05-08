import clsx from 'clsx';

interface Props {
  variant?: 'text' | 'card' | 'avatar' | 'metric';
  width?: string | number;
  height?: string | number;
  count?: number;
  className?: string;
}

export function Skeleton({ variant = 'text', width, height, count = 1, className }: Props) {
  const items = Array.from({ length: count });
  return (
    <>
      {items.map((_, i) => (
        <span
          key={i}
          aria-hidden
          role="status"
          className={clsx('ui-skeleton', `variant-${variant}`, className)}
          style={{
            width: typeof width === 'number' ? `${width}px` : width,
            height: typeof height === 'number' ? `${height}px` : height,
            display: 'block',
          }}
        />
      ))}
    </>
  );
}
