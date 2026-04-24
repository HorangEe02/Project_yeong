import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Logo } from '@/components/common/Logo';

interface AuthCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <main className="flex min-h-[calc(100vh-60px)] flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <Link
          to="/"
          className="mb-6 flex items-center justify-center gap-2 no-underline"
        >
          <Logo size="md" />
          <span className="text-xl font-semibold tracking-tight text-on-surface">
            MediWay
          </span>
        </Link>

        <div className="rounded-2xl bg-surface-container-lowest p-6 shadow-ambient sm:p-8">
          <div className="mb-6">
            <h1 className="text-xl font-bold text-on-surface">{title}</h1>
            {subtitle && (
              <p className="mt-1 text-sm text-on-surface-variant">{subtitle}</p>
            )}
          </div>
          {children}
        </div>

        {footer && (
          <div className="mt-4 text-center text-sm text-on-surface-variant">
            {footer}
          </div>
        )}
      </div>
    </main>
  );
}
