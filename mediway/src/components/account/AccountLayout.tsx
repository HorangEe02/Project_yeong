import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { KeyRound, UserCircle2, Mail, MapPin } from 'lucide-react';

interface AccountLayoutProps {
  title: string;
  description?: string;
  children: ReactNode;
}

const NAV_ITEMS = [
  { to: '/account/profile', label: '프로필', icon: UserCircle2 },
  { to: '/account/visits', label: '방문 계획', icon: MapPin },
  { to: '/account/email', label: '이메일', icon: Mail },
  { to: '/account/password', label: '비밀번호', icon: KeyRound },
];

export function AccountLayout({ title, description, children }: AccountLayoutProps) {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
          Account
        </p>
        <h1 className="text-2xl font-bold text-on-surface">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-on-surface-variant">{description}</p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside>
          <nav className="flex gap-1 overflow-x-auto rounded-xl bg-surface-container-lowest p-1.5 shadow-ambient lg:flex-col lg:p-2">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-xs no-underline transition-colors sm:text-sm ${
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-on-surface hover:bg-surface-container-low'
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <section className="rounded-xl bg-surface-container-lowest p-6 shadow-ambient">
          {children}
        </section>
      </div>
    </main>
  );
}
