type LogoSize = 'sm' | 'md' | 'lg';

interface LogoProps {
  size?: LogoSize;
  className?: string;
}

const HEIGHT: Record<LogoSize, string> = {
  sm: 'h-10', // Header (40px)
  md: 'h-16', // AuthCard (64px)
  lg: 'h-40', // Landing hero (160px)
};

export function Logo({ size = 'md', className }: LogoProps) {
  return (
    <img
      src="/mediway_logo_transparent.png"
      alt="MediWay"
      className={`${HEIGHT[size]} w-auto object-contain ${className ?? ''}`}
      draggable={false}
    />
  );
}
