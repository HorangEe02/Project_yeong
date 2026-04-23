import { useEffect, useRef, useState, type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  KeyRound,
  Activity,
  ClipboardList,
  UserCheck,
  Mail,
  Menu,
  X,
  ChevronDown,
  Building2,
} from 'lucide-react';

const NAV = [
  { to: '/admin', label: '대시보드', icon: LayoutDashboard, end: true },
  { to: '/admin/hospitals', label: '병원 관리', icon: Building2, end: false },
  { to: '/admin/users', label: '사용자', icon: Users, end: false },
  { to: '/admin/requests', label: '승인 대기', icon: UserCheck, end: false },
  { to: '/admin/invitations', label: '초대', icon: Mail, end: false },
  { to: '/admin/codes', label: '의료진 코드', icon: KeyRound, end: false },
  { to: '/admin/sessions', label: '세션', icon: Activity, end: false },
  { to: '/admin/audit', label: '감사 로그', icon: ClipboardList, end: false },
];

export function AdminLayout({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const currentNav =
    NAV.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to))) ??
    NAV[0];

  // 외부 클릭 닫기 (NavLink onClick에서 선택 시 닫는 처리는 별도)
  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menuOpen]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
            Admin
          </p>
          <h1 className="text-2xl font-bold text-on-surface">{title}</h1>
          {description && (
            <p className="mt-1 text-sm text-on-surface-variant">{description}</p>
          )}
        </div>
        {actions && <div className="flex gap-2">{actions}</div>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="lg:self-start">
          {/* 모바일(< lg): 드롭다운 트리거 + 확장 메뉴 */}
          <div ref={menuRef} className="relative lg:hidden">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex w-full items-center justify-between rounded-xl bg-surface-container-lowest px-4 py-3 shadow-ambient"
            >
              <span className="flex items-center gap-2 text-sm font-semibold text-on-surface">
                <currentNav.icon className="h-4 w-4 text-primary" />
                {currentNav.label}
              </span>
              {menuOpen ? (
                <X className="h-4 w-4 text-on-surface-variant" />
              ) : (
                <Menu className="h-4 w-4 text-on-surface-variant" />
              )}
            </button>

            {menuOpen && (
              <nav
                role="menu"
                className="absolute left-0 right-0 top-full z-20 mt-2 flex flex-col gap-1 rounded-xl bg-surface-container-lowest p-2 shadow-ambient-lg"
              >
                {NAV.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm no-underline transition-colors ${
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-on-surface hover:bg-surface-container-low'
                      }`
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1">{label}</span>
                    {currentNav.to === to && (
                      <ChevronDown className="h-3 w-3 -rotate-90 text-primary" />
                    )}
                  </NavLink>
                ))}
              </nav>
            )}
          </div>

          {/* 데스크탑(lg+): 세로 사이드바 */}
          <nav className="hidden gap-1 rounded-xl bg-surface-container-lowest p-2 shadow-ambient lg:flex lg:flex-col">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm no-underline transition-colors ${
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

        <section>{children}</section>
      </div>
    </main>
  );
}
