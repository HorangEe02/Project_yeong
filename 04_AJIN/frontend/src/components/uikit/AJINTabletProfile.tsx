// AJINTabletProfile — iPad 전용 프로필.
// aj-pad split: 좌 avatar + 4-tab nav + logout / 우 active tab content.

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  ChevronRight,
  History,
  LogOut,
  Settings,
  ShieldCheck,
  User as UserIcon,
} from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { getMe, getMyLoginHistory, type LoginHistoryEntry, type MeProfile } from '@api/me';
import { logout } from '@api/auth';

type Tab = 'basic' | 'security' | 'activity';

const TABS: { k: Tab; ko: string; en: string; Icon: typeof UserIcon }[] = [
  { k: 'basic', ko: '기본 정보', en: 'BASIC', Icon: UserIcon },
  { k: 'security', ko: '보안', en: 'SECURITY', Icon: ShieldCheck },
  { k: 'activity', ko: '활동 이력', en: 'ACTIVITY', Icon: History },
];

export function AJINTabletProfile() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);

  const [tab, setTab] = useState<Tab>('basic');
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [history, setHistory] = useState<LoginHistoryEntry[]>([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const p = await getMe();
        if (alive) setProfile(p);
      } catch {
        // ignore
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (tab !== 'activity') return;
    let alive = true;
    (async () => {
      try {
        const h = await getMyLoginHistory();
        if (alive) setHistory(h.history);
      } catch {
        // ignore
      }
    })();
    return () => {
      alive = false;
    };
  }, [tab]);

  const userName = user?.username || profile?.username || '익명';
  const userEmpId = (user as { employee_id?: string })?.employee_id || profile?.employee_id || '—';
  const userDept = user?.department || profile?.department || 'R&D';
  const userRole = profile?.role_name || 'EMPLOYEE';
  const userRoleLevel = user?.role_level ?? 1;
  const userEmail = profile?.email || '';
  const userPhone = profile?.phone || '';
  const userAvatarLetter = userName.charAt(0);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore
    }
    clearAuth();
    navigate('/login', { replace: true });
  };

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div className="aj-pad dark" style={{ position: 'relative', zIndex: 3, minHeight: '100vh' }}>
          {/* ===== Rail ===== */}
          <div className="rail">
            {/* Avatar + name */}
            <div style={{ padding: '0 8px 16px', textAlign: 'center' }}>
              <div
                style={{
                  width: 72,
                  height: 72,
                  margin: '0 auto 10px',
                  borderRadius: 999,
                  background: 'linear-gradient(135deg, #FCB132, #B57600)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 30,
                  fontWeight: 800,
                  color: '#07090C',
                  boxShadow: '0 10px 30px -8px rgba(252,177,50,0.5)',
                }}
              >
                {userAvatarLetter}
              </div>
              <div style={{ fontSize: 16, fontWeight: 700 }}>{userName}</div>
              <div className="aj-mono" style={{ fontSize: 9, opacity: 0.65, marginTop: 4 }}>
                {userEmpId}
              </div>
              <div style={{ marginTop: 6 }}>
                <span className="aj-chip gold dot" style={{ fontSize: 10 }}>
                  {userRole} · L{userRoleLevel}
                </span>
              </div>
            </div>

            {/* Tab nav */}
            {TABS.map((t) => {
              const active = tab === t.k;
              return (
                <div
                  key={t.k}
                  className={'rail-row' + (active ? ' on' : '')}
                  role="button"
                  tabIndex={0}
                  onClick={() => setTab(t.k)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setTab(t.k);
                    }
                  }}
                  aria-pressed={active}
                >
                  <div className="icn">
                    <t.Icon size={14} aria-hidden />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{t.ko}</div>
                    <div className="aj-mono" style={{ fontSize: 9, opacity: 0.7, marginTop: 1 }}>
                      {t.en}
                    </div>
                  </div>
                </div>
              );
            })}

            <div style={{ flex: 1 }} />

            {/* Logout */}
            <button
              type="button"
              onClick={handleLogout}
              className="aj-btn ghost full"
              style={{ marginTop: 8 }}
            >
              <LogOut size={14} aria-hidden style={{ marginRight: 6 }} />
              로그아웃
            </button>
          </div>

          {/* ===== Work ===== */}
          <div className="work">
            <div style={{ marginBottom: 18 }}>
              <div className="aj-mono" style={{ fontSize: 10, color: 'var(--aj-gold, #FCB132)' }}>
                PROFILE · {TABS.find((t) => t.k === tab)?.en}
              </div>
              <h1 style={{ margin: '4px 0 0', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em' }}>
                {TABS.find((t) => t.k === tab)?.ko}
              </h1>
            </div>

            {tab === 'basic' && (
              <div className="aj-glass" style={{ padding: 24, borderRadius: 18 }}>
                <BasicGrid
                  rows={[
                    { label: '이름', value: userName },
                    { label: '사번', value: userEmpId },
                    { label: '부서', value: userDept },
                    { label: '직급', value: userRole },
                    { label: '이메일', value: userEmail || '미등록' },
                    { label: '전화', value: userPhone || '미등록' },
                  ]}
                />
                <div style={{ marginTop: 18, display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => navigate('/profile?tab=basic')}
                    className="aj-btn primary"
                  >
                    데스크탑에서 편집 →
                  </button>
                </div>
              </div>
            )}

            {tab === 'security' && (
              <div className="aj-glass aj-divlist" style={{ borderRadius: 18 }}>
                <SecRow
                  Icon={ShieldCheck}
                  ko="비밀번호 변경"
                  en="CHANGE PASSWORD · 12자 이상"
                  onClick={() => navigate('/profile?tab=security')}
                />
                <SecRow
                  Icon={Settings}
                  ko="2단계 인증 (TOTP)"
                  en="2FA · BACKUP CODE"
                  onClick={() => navigate('/profile?tab=security&section=2fa')}
                />
                <SecRow
                  Icon={Bell}
                  ko="알림 설정"
                  en="NOTIFICATIONS"
                  onClick={() => navigate('/profile/notifications')}
                />
              </div>
            )}

            {tab === 'activity' && (
              <div className="aj-glass" style={{ padding: 0, borderRadius: 18, overflow: 'hidden' }}>
                {history.length === 0 && (
                  <div style={{ padding: 24, textAlign: 'center', opacity: 0.6, fontSize: 14 }}>
                    <History size={16} style={{ marginRight: 8, verticalAlign: 'middle' }} />
                    로그인 이력 없음
                  </div>
                )}
                {history.slice(0, 12).map((h, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '120px 1fr auto',
                      gap: 14,
                      padding: '14px 18px',
                      alignItems: 'center',
                      borderTop: i === 0 ? 'none' : '0.5px solid rgba(255,255,255,0.06)',
                    }}
                  >
                    <div className="aj-mono" style={{ fontSize: 11, opacity: 0.65 }}>
                      {(h.timestamp || '').slice(0, 16).replace('T', ' ')}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{h.ip_address || 'unknown'}</div>
                      <div style={{ fontSize: 11, opacity: 0.55, marginTop: 1 }}>{h.user_agent || '—'}</div>
                    </div>
                    <span className={'aj-status ' + (h.success ? 'ok' : 'crit')}>
                      {h.success ? 'OK' : 'FAIL'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function BasicGrid({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 28px' }}>
      {rows.map((r) => (
        <div key={r.label}>
          <div className="aj-mono" style={{ fontSize: 9, opacity: 0.6 }}>
            {r.label}
          </div>
          <div style={{ fontSize: 15, marginTop: 4, fontWeight: 500 }}>{r.value}</div>
        </div>
      ))}
    </div>
  );
}

function SecRow({
  Icon,
  ko,
  en,
  onClick,
}: {
  Icon: React.ComponentType<{ size?: number; 'aria-hidden'?: boolean }>;
  ko: string;
  en: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="aj-row"
      style={{
        background: 'transparent',
        border: 0,
        cursor: 'pointer',
        color: 'inherit',
        fontFamily: 'inherit',
        textAlign: 'left',
        width: '100%',
      }}
    >
      <div className="ico">
        <Icon size={18} aria-hidden />
      </div>
      <div>
        <div className="ko">{ko}</div>
        <div className="en">{en}</div>
      </div>
      <div className="meta">
        <ChevronRight size={14} aria-hidden />
      </div>
    </button>
  );
}
