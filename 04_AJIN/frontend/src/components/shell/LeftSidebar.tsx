// LeftSidebar — canonical uiux/web_app/LeftSidebar.jsx 스타일 (TS port)

import { NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { useThemeStore, type ThemePreference } from '@store/theme';
import { useUIStore } from '@store/ui';
import { signOutFirebase } from '@lib/firebaseAuth';
import { clearChatSession } from '@lib/chatSession';
import { isMenuVisible } from '@lib/rbac';
import { Icons, type IconName } from '@components/Icons';

interface ModuleItem {
  code: string;
  slug: string;
  path: string;
  ko: string;
  iconName: IconName;
}

// minRoleLevel + allowedDepartments 는 lib/rbac.ts MODULE_PERMISSIONS 에서 단일 진실 출처로 관리.
const MODULES: ModuleItem[] = [
  { code: 'A', slug: 'search', path: '/search', ko: '인원 검색', iconName: 'Employee' },
  { code: 'B', slug: 'draft', path: '/draft', ko: '문서 작성', iconName: 'Documents' },
  { code: 'C', slug: 'chat', path: '/chat', ko: 'AI 도우미', iconName: 'Onboarding' },
  { code: 'D', slug: 'compliance', path: '/compliance', ko: '법규 모니터', iconName: 'Compliance' },
  { code: 'E', slug: 'admin', path: '/admin', ko: '인사 관리', iconName: 'Admin' },
  { code: 'F', slug: 'equipment', path: '/equipment', ko: '설비 AI', iconName: 'Equipment' },
];

const THEMES: ThemePreference[] = ['light', 'dark', 'auto'];

export function LeftSidebar() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const themePref = useThemeStore((s) => s.preference);
  const setThemePref = useThemeStore((s) => s.setPreference);
  const isStreaming = useUIStore((s) => s.isStreaming);
  const activeAlarmCount = useUIStore((s) => s.activeAlarmCount);

  // F-2-14: 부서 + role_level 기반 화이트리스트 (lib/rbac.ts isMenuVisible)
  const allowed = MODULES.filter((m) => isMenuVisible(m.slug, user));

  const onLogout = () => {
    clearAuth();
    // v3.6.1 — 다음 사용자가 로그인했을 때 이전 사용자의 환영 메시지/대화가 그대로 남는
    // 버그 차단. 채팅 세션은 employee_id 단위로 격리한다.
    clearChatSession();
    void signOutFirebase();
    navigate('/login');
  };

  const userName = user?.username ?? '게스트';
  const userRole = user
    ? `${user.department ?? '품질보증팀'} · L${user.role_level} ${user.role_name?.toUpperCase() ?? ''}`
    : 'GUEST · L0';

  return (
    <aside className="sidebar">
      {/* BRAND — 클릭 시 대시보드(/) 로 이동 */}
      <div
        className="sb-brand"
        role="button"
        tabIndex={0}
        aria-label="대시보드로 이동"
        onClick={() => navigate('/')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            navigate('/');
          }
        }}
      >
        <div className="row">
          <img src="/logos/ajin_symbol.svg" alt="AJIN" width={32} height={32} />
          <div>
            <div className="name">AJIN INDUSTRY</div>
            <div className="sub">AI ASSISTANT</div>
          </div>
        </div>
        <div className="ver">v3.5 // KNU SILLI 2026</div>
      </div>

      {/* USER */}
      <div className="sb-user">
        <div className="who">
          <span className="name">{userName}</span>
          <span className="role">{userRole}</span>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => navigate('/profile')}>
            <Icons.Profile size={12} /> PROFILE
          </button>
          <button className="btn" onClick={onLogout}>
            <Icons.Logout size={12} /> LOGOUT
          </button>
        </div>
      </div>

      {/* DASHBOARD (standalone) */}
      <NavLink
        to="/"
        end
        className={({ isActive }) => 'module-btn' + (isActive ? ' active' : '')}
      >
        <span className="glyph">
          <Icons.Dashboard size={14} />
        </span>
        <span className="label">DASHBOARD</span>
        <span className="ko">대시보드</span>
      </NavLink>

      {/* THEME */}
      <div className="sb-section">
        <div className="sb-h">
          <span>
            THEME <span className="ko">테마</span>
          </span>
        </div>
        <div className="theme-row">
          {THEMES.map((t) => (
            <button
              key={t}
              className={themePref === t ? 'on' : ''}
              onClick={() => setThemePref(t)}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
        {themePref === 'auto' && (
          <div className="theme-cap">AUTO · 06–18 LIGHT / 18–06 DARK</div>
        )}
      </div>

      {/* CORE MODULES */}
      <div className="sb-section">
        <div className="sb-h">
          <span>
            CORE MODULES <span className="ko">핵심 모듈</span>
          </span>
        </div>
        {allowed.map((m) => {
          const Icon = Icons[m.iconName];
          // Phase 3: F 모듈에 활성 알람 있을 시 점멸
          const shouldPulse = m.slug === 'equipment' && activeAlarmCount > 0;
          return (
            <NavLink
              key={m.slug}
              to={m.path}
              className={({ isActive }) =>
                'module-btn' +
                (isActive ? ' active' : '') +
                (isStreaming ? ' disabled' : '') +
                (shouldPulse ? ' module-btn-alarm-pulse' : '')
              }
              onClick={(e) => {
                if (isStreaming) e.preventDefault();
              }}
            >
              <span className="glyph">{Icon && <Icon size={14} />}</span>
              <span className="label">
                {m.code}. {isStreaming ? '(응답 생성 중...)' : m.ko.toUpperCase()}
              </span>
              {shouldPulse && (
                <span className="module-btn-alarm-badge" aria-label="활성 알람 수">
                  {activeAlarmCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* SYSTEM REGISTRY */}
      <div className="sb-section">
        <div className="sb-h">
          <span>
            SYSTEM REGISTRY <span className="ko">시스템 등록</span>
          </span>
          <span className="pill">29 ●</span>
        </div>
        <div className="log-line">
          <span className="tag">[DEPT]</span> 29 / 29 <span className="dot">●</span>
        </div>
        <div className="log-line">
          <span className="tag">[ACCT]</span> 33 / 33 <span className="dot">●</span>
        </div>
      </div>

      {/* SECURITY LOG */}
      <div className="sb-section">
        <div className="sb-h">
          <span>
            SECURITY LOG <span className="ko">보안 로그</span>
          </span>
        </div>
        <div className="log-line">
          <span className="tag">[AUTH]</span> {user ? 'JWT_ACTIVE' : 'NOT_AUTH'}{' '}
          <span className="dot">●</span> {user ? 'OK' : '—'}
        </div>
        <div className="log-line">
          <span className="tag">[RBAC]</span> L{user?.role_level ?? 0}{' '}
          {user?.role_name?.toUpperCase() ?? 'GUEST'}
        </div>
        <div className="log-line">
          <span className="tag">[SYNC]</span> ChromaDB <span className="dot">●</span>
        </div>
        <div className="log-line">
          <span className="tag">[LLM]</span> QWEN-3.5 124ms
        </div>
      </div>

      <div className="sb-footer">
        AJIN INDUSTRY // ON-PREMISE AI
        <br />
        FastAPI · React · Ollama
      </div>
    </aside>
  );
}
