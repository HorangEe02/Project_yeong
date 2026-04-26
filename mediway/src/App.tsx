import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header } from '@/components/common/Header';
import { HospitalShell } from '@/components/hospital/HospitalShell';
import { LegacyHospitalRedirect } from '@/components/hospital/LegacyRedirect';
import { LandingPage } from '@/pages/LandingPage';
import { StaffPage } from '@/pages/StaffPage';
import { StaffQueuePage } from '@/pages/StaffQueuePage';
import { PatientPage } from '@/pages/PatientPage';
import { HospitalHomePage } from '@/pages/HospitalHomePage';
import { LoginPage } from '@/pages/auth/LoginPage';
import { SignupChoicePage } from '@/pages/auth/SignupChoicePage';
import { StaffSignupPage } from '@/pages/auth/StaffSignupPage';
import { PatientSignupPage } from '@/pages/auth/PatientSignupPage';
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ChangePasswordPage } from '@/pages/auth/ChangePasswordPage';
import { SocialCallbackPage } from '@/pages/auth/SocialCallbackPage';
import { InviteAcceptPage } from '@/pages/auth/InviteAcceptPage';
import { ProfilePage } from '@/pages/account/ProfilePage';
import { EmailPage } from '@/pages/account/EmailPage';
import { VisitPlanPage } from '@/pages/account/VisitPlanPage';
import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage';
import { AdminHospitalsPage } from '@/pages/admin/AdminHospitalsPage';
import { AdminHospitalDetailPage } from '@/pages/admin/AdminHospitalDetailPage';
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage';
import { AdminUserDetailPage } from '@/pages/admin/AdminUserDetailPage';
import { AdminRequestsPage } from '@/pages/admin/AdminRequestsPage';
import { AdminInvitationsPage } from '@/pages/admin/AdminInvitationsPage';
import { AdminStaffCodesPage } from '@/pages/admin/AdminStaffCodesPage';
import { AdminSessionsPage } from '@/pages/admin/AdminSessionsPage';
import { AdminAuditPage } from '@/pages/admin/AdminAuditPage';
import { ForbiddenPage } from '@/pages/ForbiddenPage';
import { SharedPlanPage } from '@/pages/share/SharedPlanPage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { initAnonymousAuth } from '@/services/auth';
import { isFirebaseConfigured } from '@/config/firebase';
import { useAuthStore } from '@/stores/authStore';
import { usePreferencesStore } from '@/stores/preferencesStore';

export default function App() {
  const initAuth = useAuthStore((s) => s.init);
  const cleanupAuth = useAuthStore((s) => s.cleanup);
  const user = useAuthStore((s) => s.user);
  const uiSenior = usePreferencesStore((s) => s.uiSenior);

  useEffect(() => {
    initAuth();
    return () => cleanupAuth();
  }, [initAuth, cleanupAuth]);

  // QR-only 환자 플로우를 위해 익명 인증은 최초 1회 보장
  useEffect(() => {
    if (isFirebaseConfigured()) {
      initAnonymousAuth();
    }
  }, []);

  // 로그인 사용자 변경 시 preferences 구독 재개시 (로그아웃 시 localStorage fallback)
  useEffect(() => {
    const uid = user && !user.isAnonymous ? user.uid : null;
    usePreferencesStore.getState().init(uid);
    return () => {
      usePreferencesStore.getState().cleanup();
    };
  }, [user?.uid, user?.isAnonymous]);

  // uiSenior state → body.classList.ui-senior 동기화 (모든 탭/페이지에 일괄 적용)
  useEffect(() => {
    document.body.classList.toggle('ui-senior', uiSenior);
  }, [uiSenior]);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-surface">
        <Header />
        <Routes>
          <Route path="/" element={<LandingPage />} />

          {/* 인증 페이지 */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupChoicePage />} />
          <Route path="/signup/staff" element={<StaffSignupPage />} />
          <Route path="/signup/patient" element={<PatientSignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/auth/callback/:provider" element={<SocialCallbackPage />} />
          <Route path="/invite/:token" element={<InviteAcceptPage />} />
          <Route path="/forbidden" element={<ForbiddenPage />} />

          {/* 공유 방문 계획 (익명 포함 로그인 허용) */}
          <Route path="/share/plan" element={<SharedPlanPage />} />
          <Route path="/share/plan/:code" element={<SharedPlanPage />} />

          {/* 계정 관리 (로그인 필요) */}
          <Route
            path="/account"
            element={<Navigate to="/account/profile" replace />}
          />
          <Route
            path="/account/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/account/visits"
            element={
              <ProtectedRoute>
                <VisitPlanPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/account/email"
            element={
              <ProtectedRoute>
                <EmailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/account/password"
            element={
              <ProtectedRoute>
                <ChangePasswordPage />
              </ProtectedRoute>
            }
          />

          {/* 의료진 — flat 경로는 nested 로 redirect (B-3 item 10 ─ bookmark 호환) */}
          <Route
            path="/staff"
            element={
              <LegacyHospitalRedirect
                buildTarget={(slug) => `/h/${slug}/staff`}
              />
            }
          />
          <Route
            path="/staff/queue"
            element={
              <LegacyHospitalRedirect
                buildTarget={(slug) => `/h/${slug}/staff/queue`}
              />
            }
          />

          {/* 관리자 전용 */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/hospitals"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminHospitalsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/hospitals/:hospitalId"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminHospitalDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminUsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users/:uid"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminUserDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/requests"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminRequestsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/invitations"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminInvitationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/codes"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminStaffCodesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/sessions"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminSessionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <ProtectedRoute requireRole={['admin']}>
                <AdminAuditPage />
              </ProtectedRoute>
            }
          />

          {/* 환자 flat 경로 → nested redirect (B-3 item 10) */}
          <Route
            path="/patient"
            element={
              <LegacyHospitalRedirect
                buildTarget={(slug) => `/h/${slug}/patient/home`}
              />
            }
          />
          <Route
            path="/patient/:sessionId"
            element={
              <LegacyHospitalRedirect
                buildTarget={(slug, p) =>
                  `/h/${slug}/patient/${p.sessionId ?? ''}`
                }
              />
            }
          />

          {/*
           * 병원 slug 기반 nested routing (B-3 item 10).
           * HospitalShell 가 슬러그 검증 + profile 로드 + cross-tenant 가드 + themeColor 주입을
           * 일괄 처리하고, 자식 라우트들은 <Outlet/> 으로 마운트된다.
           */}
          <Route path="/h/:hospitalSlug" element={<HospitalShell />}>
            <Route path="patient" element={<Navigate to="home" replace />} />
            <Route path="patient/home" element={<HospitalHomePage />} />
            {/* 환자 — 익명 + 로그인 모두 허용 (QR 진입) */}
            <Route path="patient/:sessionId" element={<PatientPage />} />
            <Route
              path="staff"
              element={
                <ProtectedRoute requireRole={['staff', 'admin']}>
                  <StaffPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="staff/queue"
              element={
                <ProtectedRoute requireRole={['staff', 'admin']}>
                  <StaffQueuePage />
                </ProtectedRoute>
              }
            />
          </Route>
        </Routes>
      </div>
    </BrowserRouter>
  );
}
