import { useEffect, type ReactNode } from 'react';
import { useLocation, useNavigate, type Location, type To } from 'react-router-dom';
import { getMe, type MeProfile } from '@api/me';
import { useAuthStore, type AuthUser } from '@store/auth';

const AUTH_QUERY_KEYS = ['ajin_idp'] as const;

interface AuthBootstrapProps {
  children: ReactNode;
}

/**
 * Converts the backend profile response into the frontend session user shape.
 *
 * Args:
 *   profile: Profile returned by `/auth/me`.
 *
 * Returns:
 *   AuthUser stored as the browser-side JWT session principal.
 */
function profileToAuthUser(profile: MeProfile): AuthUser {
  return {
    employee_id: profile.employee_id,
    username: profile.username,
    role_name: profile.role_name,
    role_level: profile.role_level,
    department: profile.department,
    position: profile.position,
  };
}

function hasAnyAuthQuery(search: string): boolean {
  const params = new URLSearchParams(search);
  return AUTH_QUERY_KEYS.some((key) => params.has(key));
}

function cleanAuthSearch(search: string): string {
  const params = new URLSearchParams(search);
  AUTH_QUERY_KEYS.forEach((key) => params.delete(key));
  const next = params.toString();
  return next ? `?${next}` : '';
}

function cleanAuthLocation(location: Location): To {
  return {
    pathname: location.pathname,
    search: cleanAuthSearch(location.search),
    hash: location.hash,
  };
}

/**
 * Restores AJIN cookie sessions after an IdP callback before routes render.
 *
 * Args:
 *   children: Application routes that require a hydrated auth store.
 *
 * Returns:
 *   Children after bootstrap, or a short blocking state while `/auth/me` resolves.
 */
export function AuthBootstrap({ children }: AuthBootstrapProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const isBootstrapping = hasAnyAuthQuery(location.search);

  useEffect(() => {
    if (!hasAnyAuthQuery(location.search)) {
      return;
    }

    let cancelled = false;

    const restoreSession = async () => {
      try {
        const profile = await getMe();
        if (cancelled) return;

        useAuthStore.getState().setSession(profileToAuthUser(profile));
        navigate(
          {
            pathname: location.pathname,
            search: cleanAuthSearch(location.search),
            hash: location.hash,
          },
          { replace: true },
        );
      } catch (error) {
        if (cancelled) return;
        if (import.meta.env.DEV) {
          console.warn('[AuthBootstrap] IdP 세션 복원 실패:', error);
        }
        useAuthStore.getState().clear();
        navigate('/login', {
          replace: true,
          state: { from: cleanAuthLocation(location) },
        });
      }
    };

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, [location, navigate]);

  if (isBootstrapping) {
    return (
      <div className="login-wrap">
        <div className="login-card glass">
          <div className="dim" style={{ textAlign: 'center' }}>
            인증 확인 중...
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
