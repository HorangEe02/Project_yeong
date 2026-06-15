import { Suspense, lazy, useEffect, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { useThemeStore } from '@store/theme';
import { useMaintenanceStore } from '@store/maintenance';
import { api } from '@api/client';
import { MaintenanceBanner } from '@components/MaintenanceBanner';
import { AuthBootstrap } from '@components/auth/AuthBootstrap';
import { Shell } from '@routes/_shell';
import { GlossaryProvider } from '@components/compliance/GlossaryProvider';
// v4.8 — 기능 G(HR) 완전 삭제. /hr 라우트 + HR 컴포넌트 제거.
// v4.8 F — /management 가 정식 진입점 (4 카테고리). /admin, /hr 는 alias 로 redirect.
import { useFeatureDFlagsState, type FeatureDFlags } from '@lib/featureFlags';

const Login = lazy(() => import('@routes/login').then((m) => ({ default: m.Login })));
const Dashboard = lazy(() => import('@routes/dashboard').then((m) => ({ default: m.Dashboard })));
const Search = lazy(() => import('@routes/search').then((m) => ({ default: m.Search })));
const Draft = lazy(() => import('@routes/draft').then((m) => ({ default: m.Draft })));
const Chat = lazy(() => import('@routes/chat').then((m) => ({ default: m.Chat })));
const Onboarding = lazy(() => import('@routes/onboarding').then((m) => ({ default: m.Onboarding })));
const Compliance = lazy(() => import('@routes/compliance').then((m) => ({ default: m.Compliance })));
const ComplianceRegulationDetail = lazy(() => import('@routes/compliance-regulation').then((m) => ({ default: m.ComplianceRegulationDetail })));
const ComplianceSearchResults = lazy(() => import('@routes/compliance-search').then((m) => ({ default: m.ComplianceSearchResults })));
const ComplianceGlossary = lazy(() => import('@routes/compliance-glossary').then((m) => ({ default: m.ComplianceGlossary })));
// 2026-05-28 — 모바일 전용 "전체 변경 알림" 라우트 (AJINMobileCompliance "전체 →" 진입).
const MobileComplianceFeed = lazy(() => import('@routes/mobile-compliance-feed').then((m) => ({ default: m.MobileComplianceFeed })));
const Admin = lazy(() => import('@routes/admin').then((m) => ({ default: m.Admin })));
const Management = lazy(() => import('@routes/management').then((m) => ({ default: m.Management })));
const Equipment = lazy(() => import('@routes/equipment').then((m) => ({ default: m.Equipment })));
const EquipmentField = lazy(() => import('@routes/equipment-field').then((m) => ({ default: m.EquipmentField })));
const Profile = lazy(() => import('@routes/profile').then((m) => ({ default: m.Profile })));
const ProfileNotifications = lazy(() => import('@routes/profile-notifications').then((m) => ({ default: m.ProfileNotifications })));
const ProfileLLM = lazy(() => import('@routes/profile-llm').then((m) => ({ default: m.ProfileLLM })));
const ComponentCatalog = lazy(() => import('@routes/dev/components').then((m) => ({ default: m.ComponentCatalog })));
const Showcase = lazy(() => import('@routes/showcase').then((m) => ({ default: m.Showcase })));
const TechStack = lazy(() => import('@routes/tech').then((m) => ({ default: m.TechStack })));

function RequireAuth({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

function RequireRole({
  minLevel,
  children,
}: {
  minLevel: number;
  children: ReactNode;
}) {
  const user = useAuthStore((s) => s.user);
  if (!user || user.role_level < minLevel) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

function RequireFeatureD({
  flag,
  children,
}: {
  flag: keyof FeatureDFlags;
  children: ReactNode;
}) {
  const { flags, loading } = useFeatureDFlagsState();
  const user = useAuthStore((s) => s.user);
  if (loading) return null;
  // L5 SYS_ADMIN bypass (2026-05-28) — Feature D flag (d2_rag 등) 가 false 여도
  // L5 는 모든 sub-route (compliance/search, /reg/:id, /glossary) 접근 가능.
  if (user && user.role_level >= 5) return <>{children}</>;
  if (!flags[flag]) {
    return <Navigate to="/compliance" replace />;
  }
  return <>{children}</>;
}

function App() {
  const themePref = useThemeStore((s) => s.preference);
  const themeResolved = useThemeStore((s) => s.resolved());

  useEffect(() => {
    // /showcase iframe 등에서 ?theme=light|dark 로 테마 강제 가능 (localStorage 비오염 — data-theme 만 덮어씀).
    const urlTheme = new URLSearchParams(window.location.search).get('theme');
    const forced = urlTheme === 'light' || urlTheme === 'dark' ? urlTheme : null;
    document.documentElement.setAttribute('data-theme', forced ?? themeResolved);
  }, [themeResolved, themePref]);

  // v3.5 — Neural Expressive overlay 전체 활성 (사용자 Goal 확정 1).
  // styles/neural.css 의 [data-neural="on"] 셀렉터 전역 활성.
  // URL ?neural=0 또는 ?neural=off 로 비활성 가능 (시연 회귀 시 fallback).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const explicit = params.get('neural');
    const enabled = !(explicit === '0' || explicit === 'off');
    document.documentElement.setAttribute('data-neural', enabled ? 'on' : 'off');
  }, []);

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
      <AuthBootstrap>
        <MaintenanceBanner />
        <Suspense fallback={null}>
          <Routes>
          <Route path="/login" element={<Login />} />
          {import.meta.env.DEV && (
            <Route path="/dev/components" element={<ComponentCatalog />} />
          )}
          {/* W4 — 현장 모드 (Shell 사이드바 없이 풀스크린 PWA). RequireAuth 만 적용. */}
          <Route
            path="/equipment/field"
            element={
              <RequireAuth>
                <EquipmentField />
              </RequireAuth>
            }
          />
          {/* 전체 기능 화면 쇼케이스 — 공개(게스트 읽기전용 세션 자동 발급). Shell 없이 풀스크린.
              심사위원·팀원이 로그인 없이 열람 가능. */}
          <Route path="/showcase" element={<Showcase />} />
          {/* 백엔드 기술 스택 설명(비전공자용) — 공개 라우트(로그인 불필요). 민감 정보 없음. */}
          <Route path="/tech" element={<TechStack />} />
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
            <Route path="onboarding" element={<Onboarding />} />
            <Route
              path="compliance"
              element={
                <RequireRole minLevel={2}>
                  <Compliance />
                </RequireRole>
              }
            />
            {/* 2026-05-28 — 모바일 전용 전체 피드 (desktop 접근 시 자동 /compliance redirect) */}
            <Route
              path="m/compliance/feed"
              element={
                <RequireRole minLevel={2}>
                  <MobileComplianceFeed />
                </RequireRole>
              }
            />
            <Route
              path="compliance/search"
              element={
                <RequireRole minLevel={2}>
                  <RequireFeatureD flag="d2_rag">
                    <ComplianceSearchResults />
                  </RequireFeatureD>
                </RequireRole>
              }
            />
            <Route
              path="compliance/reg/:id"
              element={
                <RequireRole minLevel={2}>
                  <RequireFeatureD flag="d2_rag">
                    <ComplianceRegulationDetail />
                  </RequireFeatureD>
                </RequireRole>
              }
            />
            <Route
              path="compliance/glossary"
              element={
                <RequireRole minLevel={2}>
                  <RequireFeatureD flag="d2_rag">
                    <ComplianceGlossary />
                  </RequireFeatureD>
                </RequireRole>
              }
            />
            {/* v4.8 F — /management 가 정식 4-카테고리 진입점. */}
            <Route
              path="management"
              element={
                <RequireAuth>
                  <Management />
                </RequireAuth>
              }
            />
            {/* v4.8 — /hr 은 사용자 카테고리, /admin/legacy 는 기존 6-탭 콘솔(L4+), /admin 은 시스템 카테고리로 리다이렉트. */}
            <Route path="hr" element={<Navigate to="/management?cat=users" replace />} />
            <Route path="admin" element={<Navigate to="/management?cat=system" replace />} />
            <Route
              path="admin/legacy"
              element={
                <RequireRole minLevel={4}>
                  <Admin />
                </RequireRole>
              }
            />
            <Route path="equipment" element={<Equipment />} />
            <Route path="profile" element={<Profile />} />
            <Route path="profile/notifications" element={<ProfileNotifications />} />
            <Route path="profile/llm" element={<ProfileLLM />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthBootstrap>
    </BrowserRouter>
  );
}

export default App;
