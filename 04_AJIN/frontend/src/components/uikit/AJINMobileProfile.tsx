// AJINMobileProfile — iPhone 모바일 프로필 화면.
// 디자인 시스템: aj-screen / aj-bg-grad / aj-glass / aj-divlist / aj-chip.
// profile.tsx 의 4 tab (BASIC/SECURITY/ACTIVITY/MOBILE) 을 모바일에선 segmented control + 단순화된 form.

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, ChevronRight, LogOut, Settings, ShieldCheck, User } from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { getMe, updateMe, type MeProfile } from '@api/me';
import { logout } from '@api/auth';

type Tab = 'basic' | 'security' | 'activity';

const TABS: { k: Tab; ko: string; en: string }[] = [
  { k: 'basic', ko: '기본', en: 'BASIC' },
  { k: 'security', ko: '보안', en: 'SECURITY' },
  { k: 'activity', ko: '활동', en: 'ACTIVITY' },
];

export function AJINMobileProfile() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);

  const [tab, setTab] = useState<Tab>('basic');
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [editing, setEditing] = useState(false);
  const [emailDraft, setEmailDraft] = useState('');
  const [phoneDraft, setPhoneDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

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

  const handleSaveProfile = async () => {
    setSaving(true);
    setSaveErr(null);
    try {
      await updateMe({ email: emailDraft.trim(), phone: phoneDraft.trim() });
      setProfile((p) => (p ? { ...p, email: emailDraft.trim(), phone: phoneDraft.trim() } : p));
      setEditing(false);
    } catch {
      setSaveErr('저장에 실패했습니다. 잠시 후 다시 시도하세요.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 24,
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
          }}
        >
          {/* Header — avatar + name + role */}
          <div style={{ padding: '20px 20px 8px', textAlign: 'center' }}>
            <div
              style={{
                width: 88,
                height: 88,
                margin: '0 auto 12px',
                borderRadius: 999,
                background: 'linear-gradient(135deg, #FCB132, #B57600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 36,
                fontWeight: 800,
                color: '#07090C',
                boxShadow: '0 12px 40px -10px rgba(252,177,50,0.5)',
              }}
            >
              {userAvatarLetter}
            </div>
            <h1
              style={{
                margin: 0,
                fontSize: 22,
                fontWeight: 700,
                letterSpacing: '-0.012em',
              }}
            >
              {userName}
            </h1>
            <div
              className="aj-mono"
              style={{ marginTop: 4, fontSize: 10, opacity: 0.65 }}
            >
              {userEmpId} · {userDept}
            </div>
            <div style={{ marginTop: 8 }}>
              <span className="aj-chip gold dot" style={{ fontSize: 11 }}>
                {userRole} · L{userRoleLevel}
              </span>
            </div>
          </div>

          {/* Segmented tab control */}
          <div style={{ padding: '12px 12px 8px' }}>
            <div
              className="aj-glass"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 4,
                padding: 4,
                borderRadius: 16,
              }}
            >
              {TABS.map((t) => {
                const active = tab === t.k;
                return (
                  <button
                    key={t.k}
                    type="button"
                    onClick={() => setTab(t.k)}
                    style={{
                      padding: '10px 8px',
                      borderRadius: 12,
                      border: 0,
                      cursor: 'pointer',
                      background: active
                        ? 'color-mix(in oklab, var(--aj-gold, #FCB132) 22%, transparent)'
                        : 'transparent',
                      color: active ? 'var(--aj-gold, #FCB132)' : 'inherit',
                      fontFamily: 'inherit',
                      fontSize: 13,
                      fontWeight: active ? 700 : 500,
                    }}
                    aria-pressed={active}
                  >
                    {t.ko}
                    <div
                      className="aj-mono"
                      style={{
                        fontSize: 9,
                        marginTop: 2,
                        opacity: active ? 0.85 : 0.55,
                      }}
                    >
                      {t.en}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tab content */}
          {tab === 'basic' && (
            <div className="aj-glass" style={{ margin: '0 12px', padding: 16 }}>
              <BasicRow Icon={User} label="이름" value={userName} />
              <BasicRow Icon={Settings} label="부서" value={userDept} />
              {!editing ? (
                <>
                  <BasicRow Icon={ShieldCheck} label="이메일" value={userEmail || '미등록'} />
                  <BasicRow Icon={Bell} label="전화" value={userPhone || '미등록'} />
                  <button
                    type="button"
                    onClick={() => { setEmailDraft(userEmail); setPhoneDraft(userPhone); setSaveErr(null); setEditing(true); }}
                    className="aj-btn ghost full"
                    style={{ width: '100%', marginTop: 14 }}
                  >
                    이메일 · 전화 수정
                  </button>
                </>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 4 }}>
                  <EditField label="이메일" type="email" value={emailDraft} onChange={setEmailDraft} placeholder="name@ajin.com" />
                  <EditField label="전화" type="tel" value={phoneDraft} onChange={setPhoneDraft} placeholder="010-0000-0000" />
                  {saveErr && <div style={{ color: 'var(--hud-red, #FF7565)', fontSize: 12 }}>{saveErr}</div>}
                  <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                    <button type="button" disabled={saving} onClick={() => setEditing(false)} className="aj-btn ghost" style={{ flex: 1 }}>취소</button>
                    <button type="button" disabled={saving} onClick={handleSaveProfile} className="aj-btn full" style={{ flex: 1 }}>{saving ? '저장 중…' : '저장'}</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'security' && (
            <div className="aj-glass aj-divlist" style={{ margin: '0 12px' }}>
              <ActionRow
                Icon={ShieldCheck}
                ko="비밀번호 변경"
                en="CHANGE PASSWORD"
                onClick={() => navigate('/profile?tab=security')}
              />
              <ActionRow
                Icon={Bell}
                ko="2단계 인증 설정"
                en="2FA · TOTP"
                onClick={() => navigate('/profile?tab=security&section=2fa')}
              />
              <ActionRow
                Icon={Bell}
                ko="알림 설정"
                en="NOTIFICATIONS"
                onClick={() => navigate('/profile/notifications')}
              />
            </div>
          )}

          {tab === 'activity' && (
            <div className="aj-glass aj-divlist" style={{ margin: '0 12px' }}>
              <ActionRow
                Icon={Bell}
                ko="로그인 이력"
                en="LOGIN HISTORY"
                onClick={() => navigate('/profile?tab=activity')}
              />
              <ActionRow
                Icon={Settings}
                ko="모바일 빠른 탭"
                en="MOBILE TAB PREFS"
                onClick={() => navigate('/profile?tab=mobile')}
              />
            </div>
          )}

          <div style={{ padding: '20px 12px 8px' }}>
            <button
              type="button"
              onClick={handleLogout}
              className="aj-btn ghost full"
              style={{ width: '100%' }}
            >
              <LogOut size={16} aria-hidden style={{ marginRight: 6 }} />
              로그아웃
            </button>
          </div>

          <div style={{ height: 120 }} />
        </div>
      </div>
    </div>
  );
}

function BasicRow({
  Icon,
  label,
  value,
}: {
  Icon: React.ComponentType<{ size?: number; 'aria-hidden'?: boolean }>;
  label: string;
  value: string;
}) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '32px 1fr auto',
        gap: 12,
        alignItems: 'center',
        padding: '12px 0',
        borderBottom: '0.5px solid rgba(255,255,255,0.06)',
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 10,
          background: 'color-mix(in oklab, var(--aj-gold, #FCB132) 16%, transparent)',
          color: 'var(--aj-gold, #FCB132)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Icon size={16} aria-hidden />
      </div>
      <div>
        <div className="aj-mono" style={{ fontSize: 9, opacity: 0.6 }}>
          {label}
        </div>
        <div style={{ fontSize: 14, marginTop: 2 }}>{value}</div>
      </div>
    </div>
  );
}

function EditField({
  label,
  type,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span className="aj-mono" style={{ fontSize: 9, opacity: 0.6 }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        style={{
          padding: '10px 12px',
          borderRadius: 10,
          border: '1px solid var(--hud-border)',
          background: 'var(--hud-surface-2)',
          color: 'var(--hud-text)',
          fontSize: 14,
          fontFamily: 'inherit',
          width: '100%',
          boxSizing: 'border-box',
        }}
      />
    </label>
  );
}

function ActionRow({
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
