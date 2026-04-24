import { useEffect, useRef, useState } from 'react';
import { LogOut, KeyRound, UserCircle2, User, Shield } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore, selectIsAdmin } from '@/stores/authStore';
import { signOutUser, canChangePassword } from '@/services/auth';
import { Logo } from '@/components/common/Logo';

export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const isStaff = location.pathname.startsWith('/staff');
  const isPatient = location.pathname.startsWith('/patient');

  const { user, profile, initialized } = useAuthStore();
  const isAdmin = useAuthStore(selectIsAdmin);
  const isLoggedIn = !!user && !user.isAnonymous;

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  const onLogout = async () => {
    setMenuOpen(false);
    await signOutUser();
    navigate('/', { replace: true });
  };

  return (
    <header className="glass sticky top-0 z-50 px-4 py-3">
      <div className="mx-auto flex max-w-5xl items-center justify-between">
        <Link to="/" className="flex items-center gap-3 no-underline">
          <Logo size="sm" />
          <span className="text-xl font-semibold tracking-tight text-on-surface">
            MediWay
          </span>
        </Link>

        <nav className="flex items-center gap-2">
          {isStaff && (
            <span className="rounded-lg bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">
              의료진
            </span>
          )}
          {isPatient && (
            <span className="rounded-lg bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">
              환자
            </span>
          )}

          {initialized && !isLoggedIn && (
            <Link
              to="/login"
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-primary no-underline"
            >
              로그인
            </Link>
          )}

          {isLoggedIn && (
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-on-surface hover:bg-surface-container-low"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
              >
                <UserCircle2 className="h-6 w-6 text-on-surface-variant" />
                <span className="hidden max-w-[120px] truncate sm:inline">
                  {profile?.displayName ?? user?.email ?? '사용자'}
                </span>
                {profile?.role && (
                  <span className="hidden rounded bg-surface-container-high px-1.5 py-0.5 text-[10px] font-medium uppercase text-on-surface-variant sm:inline">
                    {profile.role}
                  </span>
                )}
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl bg-surface-container-lowest shadow-ambient-lg"
                >
                  <div className="border-b border-surface-container-high px-4 py-3">
                    <p className="truncate text-sm font-medium text-on-surface">
                      {profile?.displayName ?? '사용자'}
                    </p>
                    <p className="truncate text-xs text-on-surface-variant">
                      {user?.email}
                    </p>
                  </div>

                  <Link
                    to="/account/profile"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm text-on-surface no-underline hover:bg-surface-container-low"
                  >
                    <User className="h-4 w-4" />
                    내 프로필
                  </Link>

                  {isAdmin && (
                    <Link
                      to="/admin"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm text-on-surface no-underline hover:bg-surface-container-low"
                    >
                      <Shield className="h-4 w-4" />
                      관리자 페이지
                    </Link>
                  )}

                  {canChangePassword(user) && (
                    <Link
                      to="/account/password"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm text-on-surface no-underline hover:bg-surface-container-low"
                    >
                      <KeyRound className="h-4 w-4" />
                      비밀번호 변경
                    </Link>
                  )}

                  <button
                    type="button"
                    onClick={onLogout}
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-red-600 hover:bg-surface-container-low"
                  >
                    <LogOut className="h-4 w-4" />
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
