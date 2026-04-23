import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header } from '@/components/common/Header';
import { LandingPage } from '@/pages/LandingPage';
import { StaffPage } from '@/pages/StaffPage';
import { PatientPage } from '@/pages/PatientPage';
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
import { HospitalRouteWrapper } from '@/components/hospital/HospitalRouteWrapper';
import { HospitalHomePage } from '@/pages/HospitalHomePage';
import { SelectHospitalPage } from '@/pages/SelectHospitalPage';
import { initAnonymousAuth } from '@/services/auth';
import { isFirebaseConfigured } from '@/config/firebase';
import { useAuthStore } from '@/stores/authStore';

export default function App() {
  const initAuth = useAuthStore((s) => s.init);
  const cleanupAuth = useAuthStore((s) => s.cleanup);

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

          {/* P1 병원 선택 페이지 — 가입 직후 · 로비 QR 부트스트랩 */}
          <Route path="/hospitals/select" element={<SelectHospitalPage />} />

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

          {/* 의료진 (staff + admin 허용) */}
          <Route
            path="/staff"
            element={
              <ProtectedRoute requireRole={['staff', 'admin']}>
                <StaffPage />
              </ProtectedRoute>
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

          {/* 환자 — 익명+로그인 모두 허용 (레거시 경로, P1 호환 유지) */}
          <Route path="/patient" element={<PatientPage />} />
          <Route path="/patient/:sessionId" element={<PatientPage />} />

          {/*
            P1 신규 Multi-Tenant 라우트 (/h/:slug/*)
            - HospitalRouteWrapper가 slug 유효성 · 프로필 로딩을 처리
            - 기존 페이지 컴포넌트를 그대로 재사용 (P1 범위)
            - P2+에서 각 페이지가 useHospital()로 병원별 동작 전환
          */}
          <Route path="/h/:slug" element={<HospitalRouteWrapper />}>
            {/* P2 신규 대시보드 홈 (6탭 셸) */}
            <Route path="patient/home" element={<HospitalHomePage />} />
            {/*
              P2 이후: /h/:slug/patient 접근은 대시보드 홈으로 자동 리다이렉트.
              PatientPage는 GuideTab 내부에 흡수되었으므로 동일 UX 유지.
              sessionId가 있는 deep link는 레거시 PatientPage로 유지 (QR 세션 복원).
            */}
            <Route
              path="patient"
              element={<Navigate to="home" replace />}
            />
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
              path="admin"
              element={
                <ProtectedRoute requireRole={['admin']}>
                  <AdminDashboardPage />
                </ProtectedRoute>
              }
            />
            {/* 빈 경로 접근 시 patient로 */}
            <Route index element={<Navigate to="patient" replace />} />
          </Route>
        </Routes>
      </div>
    </BrowserRouter>
  );
}
