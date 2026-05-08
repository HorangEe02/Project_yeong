import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import type { User as FirebaseUser } from 'firebase/auth';
import { useAuthStore } from '@store/auth';
import { useThemeStore } from '@store/theme';
import { useMaintenanceStore } from '@store/maintenance';
import { watchFirebaseUser } from '@lib/firebaseAuth';
import { api } from '@api/client';
import { MaintenanceBanner } from '@components/MaintenanceBanner';
import { Shell } from '@routes/_shell';
import { Login } from '@routes/login';
import { Dashboard } from '@routes/dashboard';
import { Search } from '@routes/search';
import { Draft } from '@routes/draft';
import { Chat } from '@routes/chat';
import { Compliance } from '@routes/compliance';
import { ComplianceRegulationDetail } from '@routes/compliance-regulation';
import { ComplianceSearchResults } from '@routes/compliance-search';
import { ComplianceGlossary } from '@routes/compliance-glossary';
import { GlossaryProvider } from '@components/compliance/GlossaryProvider';
import { Admin } from '@routes/admin';
import { Equipment } from '@routes/equipment';
import { Profile } from '@routes/profile';
import { ProfileNotifications } from '@routes/profile-notifications';
import { ComponentCatalog } from '@routes/dev/components';

/**
 * Day 5++.5: Firebase Auth 사용자 + 백엔드 JWT 둘 중 하나라도 OK 면 통과.
 * - 백엔드 access_token 만료(1시간) 후에도 Firebase 세션이 살아 있으면 페이지 접근 허용
 * - axios interceptor 가 401 시 firebase-exchange 로 silent 재발급 → 사용자 미체감
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const [fbUser, setFbUser] = useState<FirebaseUser | null>(null);
  const location = useLocation();

  useEffect(() => {
    return watchFirebaseUser((u) => setFbUser(u));
  }, []);

  // user 정보(persisted) 또는 Firebase currentUser 둘 중 하나라도 있으면 통과
  if (!user && !fbUser) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

function RequireRole({
  minLevel,
  children,
}: {
  minLevel: number;
  children: React.ReactNode;
}) {
  const user = useAuthStore((s) => s.user);
  if (!user || user.role_level < minLevel) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

function App() {
  const themePref = useThemeStore((s) => s.preference);
  const themeResolved = useThemeStore((s) => s.resolved());

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', themeResolved);
  }, [themeResolved, themePref]);

  // Plan A 변형: Mac Ollama 가용성 polling (60s).
  // /api/health 의 llm_connected 가 false 면 maintenance banner 활성.
  useEffect(() => {
    const setActive = useMaintenanceStore.getState().setActive;
    const tick = async () => {
      try {
        const r = await api.get<{ llm_connected?: boolean; status?: string }>('/health', {
          timeout: 5000,
        });
        const ok = r.data?.llm_connected !== false;
        setActive(!ok, ok ? '' : 'Mac Ollama 응답 없음', 'health-poll');
      } catch {
        // 503 은 client.ts response interceptor 가 처리하므로 무시
      }
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <BrowserRouter>
      <MaintenanceBanner />
      <Routes>
        <Route path="/login" element={<Login />} />
        {import.meta.env.DEV && (
          <Route path="/dev/components" element={<ComponentCatalog />} />
        )}
        <Route
          element={
            <RequireAuth>
              <GlossaryProvider>
                <Shell />
              </GlossaryProvider>
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="search" element={<Search />} />
          <Route path="draft" element={<Draft />} />
          <Route path="chat" element={<Chat />} />
          <Route
            path="compliance"
            element={
              <RequireRole minLevel={2}>
                <Compliance />
              </RequireRole>
            }
          />
          <Route
            path="compliance/search"
            element={
              <RequireRole minLevel={2}>
                <ComplianceSearchResults />
              </RequireRole>
            }
          />
          <Route
            path="compliance/reg/:id"
            element={
              <RequireRole minLevel={2}>
                <ComplianceRegulationDetail />
              </RequireRole>
            }
          />
          <Route
            path="compliance/glossary"
            element={
              <RequireRole minLevel={2}>
                <ComplianceGlossary />
              </RequireRole>
            }
          />
          <Route
            path="admin"
            element={
              <RequireRole minLevel={3}>
                <Admin />
              </RequireRole>
            }
          />
          <Route path="equipment" element={<Equipment />} />
          <Route path="profile" element={<Profile />} />
          <Route path="profile/notifications" element={<ProfileNotifications />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
