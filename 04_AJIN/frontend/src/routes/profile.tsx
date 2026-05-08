// profile.tsx — 본인 프로필 편집 페이지.
// AJIN AI Assistant Design System v2 (lg-*) 양식 그대로 적용 — compliance.tsx 와 동일 패턴.
// 3탭: BASIC (기본 정보) / SECURITY (보안) / ACTIVITY (활동 이력)

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, AlertTriangle, ShieldCheck } from 'lucide-react';
import { useAuthStore } from '@store/auth';
import {
  getMe,
  updateMe,
  getMyLoginHistory,
  type MeProfile,
  type LoginHistoryEntry,
} from '@api/me';
import { changePassword as apiChangePassword, extractError } from '@api/auth';

// 부서 드롭다운 옵션 — 자유 입력 차단 (백엔드 config.DEPARTMENTS 30개와 동기화 권장)
const DEPARTMENT_OPTIONS = [
  '경영지원본부', '총무인사팀', '인사관리', 'IT전략팀',
  '품질본부', '품질보증팀', '품질경영팀',
  '생산본부', '생산관리팀', '생산기술팀', '안전보건팀',
  '구매물류본부', '구매팀', '해외지원팀',
  '영업본부', '영업팀', '해외영업팀',
  '기술연구소', '바디선행개발팀', '전장선행개발팀', '부품개발팀',
  '자동화기술팀', '비전연구팀', '금형생산팀',
  'ESG경영팀', '기술교육원', '경영지원',
];

// 역할 드롭다운 옵션 — 백엔드 _VALID_ROLE_NAMES 와 동기화
const ROLE_OPTIONS = [
  { value: 'EMPLOYEE', label: 'EMPLOYEE (Lv 1)' },
  { value: 'MANAGER', label: 'MANAGER (Lv 2)' },
  { value: 'TEAM_LEAD', label: 'TEAM_LEAD (Lv 3)' },
  { value: 'HR_ADMIN', label: 'HR_ADMIN (Lv 4)' },
  { value: 'SYS_ADMIN', label: 'SYS_ADMIN (Lv 5)' },
];

type ProfileTab = 'basic' | 'security' | 'activity';

const TABS: { k: ProfileTab; en: string; ko: string }[] = [
  { k: 'basic', en: 'BASIC', ko: '기본 정보' },
  { k: 'security', en: 'SECURITY', ko: '보안' },
  { k: 'activity', en: 'ACTIVITY', ko: '활동 이력' },
];

// ─────────────────────────────────────────────────────────────
// 검증 유틸
// ─────────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// 휴대폰(010-XXXX-XXXX) + 일반전화(02-XXX-XXXX, 053-XXX-XXXX 등) 모두 허용
const PHONE_RE = /^0\d{1,2}-?\d{3,4}-?\d{4}$/;

function autoFormatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '');
  if (d.length < 4) return d;
  // 02 (서울) 만 2자리, 나머지 모두 3자리
  const areaLen = d.startsWith('02') ? 2 : 3;
  if (d.length < areaLen + 3) return `${d.slice(0, areaLen)}-${d.slice(areaLen)}`;
  if (d.length < areaLen + 7) return `${d.slice(0, areaLen)}-${d.slice(areaLen, areaLen + 3)}-${d.slice(areaLen + 3)}`;
  // 010-XXXX-XXXX (11자리) 또는 053-XXX-XXXX (10자리)
  const midLen = d.length - areaLen - 4;
  return `${d.slice(0, areaLen)}-${d.slice(areaLen, areaLen + midLen)}-${d.slice(areaLen + midLen)}`;
}

interface PwStrength {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
  color: string;
}

function pwStrength(pw: string): PwStrength {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pw)) s++;
  const map: PwStrength[] = [
    { score: 0, label: '미입력', color: 'var(--hud-text-dim)' },
    { score: 1, label: '약함', color: 'var(--hud-red, #C0392B)' },
    { score: 2, label: '보통', color: 'var(--hud-orange, #E8A317)' },
    { score: 3, label: '강함', color: 'var(--hud-blue, #2980B9)' },
    { score: 4, label: '아주 강함', color: 'var(--hud-green, #2ECC71)' },
  ];
  return map[Math.min(s, 4)];
}

function formatTs(iso: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('ko-KR', { hour12: false });
  } catch {
    return iso;
  }
}

// ─────────────────────────────────────────────────────────────
// 메인 컴포넌트
// ─────────────────────────────────────────────────────────────

export function Profile() {
  const navigate = useNavigate();
  const clearAuth = useAuthStore((s) => s.clear);

  const [tab, setTab] = useState<ProfileTab>('basic');
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── 초기 로드 ──
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getMe()
      .then((p) => { if (!cancelled) { setProfile(p); setLoadError(null); } })
      .catch((e) => { if (!cancelled) setLoadError(extractError(e).detail); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="page lg-page" data-screen-label="Profile · 내 프로필">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">PROFILE · MY INFO</div>
        <h1 className="lg-display">내 프로필</h1>
        <p className="lg-sub">
          기본 정보를 확인하고 연락처·직급을 직접 수정할 수 있습니다. 사번·소속·역할은 인사팀이 관리합니다.
        </p>
        {loadError && (
          <p
            className="lg-sub"
            style={{
              color: 'var(--hud-red, #f33)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <AlertTriangle size={13} strokeWidth={1.6} />
            프로필 로드 실패: {loadError}
          </p>
        )}
      </section>

      <div className="lg-tabs">
        {TABS.map((t) => (
          <button
            key={t.k}
            className={'lg-tab' + (tab === t.k ? ' on' : '')}
            onClick={() => setTab(t.k)}
          >
            <span className="en">{t.en}</span>
            <span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {loading && <div className="lg-card"><div className="lg-sub">불러오는 중…</div></div>}

      {!loading && profile && tab === 'basic' && (
        <BasicTab
          profile={profile}
          onUpdated={(p) => setProfile(p)}
          onReissued={() => {
            clearAuth();
            navigate('/login', { replace: true });
          }}
        />
      )}
      {!loading && profile && tab === 'security' && (
        <SecurityTab
          employeeId={profile.employee_id}
          onChanged={() => {
            // 비밀번호 변경 후 자동 로그아웃 → /login
            setTimeout(() => {
              clearAuth();
              navigate('/login', { replace: true });
            }, 1200);
          }}
        />
      )}
      {!loading && profile && tab === 'activity' && (
        <ActivityTab />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Tab 1: BASIC — 기본 정보
// ─────────────────────────────────────────────────────────────

function BasicTab({
  profile,
  onUpdated,
  onReissued,
}: {
  profile: MeProfile;
  onUpdated: (p: MeProfile) => void;
  onReissued: () => void;
}) {
  // 일반 필드
  const [email, setEmail] = useState(profile.email);
  const [phone, setPhone] = useState(profile.phone);
  const [position, setPosition] = useState(profile.position);
  // 특권 필드 (HR_ADMIN/SYS_ADMIN)
  const [empId, setEmpId] = useState(profile.employee_id);
  const [username, setUsername] = useState(profile.username);
  const [department, setDepartment] = useState(profile.department);
  const [roleName, setRoleName] = useState(profile.role_name);

  const [saving, setSaving] = useState(false);
  const [savedTs, setSavedTs] = useState<number | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const privileged = profile.role_level >= 4;

  const dirty = useMemo(
    () =>
      email !== profile.email ||
      phone !== profile.phone ||
      position !== profile.position ||
      (privileged && (
        empId !== profile.employee_id ||
        username !== profile.username ||
        department !== profile.department ||
        roleName !== profile.role_name
      )),
    [email, phone, position, empId, username, department, roleName, profile, privileged],
  );

  const emailValid = email === '' || EMAIL_RE.test(email);
  const phoneValid = phone === '' || PHONE_RE.test(phone);
  const empIdValid = empId === profile.employee_id || /^[A-Za-z0-9_-]{3,20}$/.test(empId);
  const canSave = dirty && emailValid && phoneValid && empIdValid && !saving;

  // 사번 또는 역할이 바뀌면 위험 변경 → 확인 다이얼로그
  const isRiskyChange =
    privileged && (empId !== profile.employee_id || roleName !== profile.role_name);

  async function handleSave() {
    setErrMsg(null);

    if (isRiskyChange) {
      const msg = [
        '아래 변경은 보안 영향이 큰 변경입니다:',
        empId !== profile.employee_id ? `  • 사번: ${profile.employee_id} → ${empId}` : '',
        roleName !== profile.role_name ? `  • 역할: ${profile.role_name} → ${roleName}` : '',
        '',
        '저장 후 자동으로 로그아웃되며, 다시 로그인해야 합니다.',
        '계속하시겠습니까?',
      ].filter(Boolean).join('\n');
      if (!window.confirm(msg)) return;
    }

    setSaving(true);
    try {
      const payload: Parameters<typeof updateMe>[0] = { email, phone, position };
      if (privileged) {
        if (empId !== profile.employee_id) payload.employee_id = empId;
        if (username !== profile.username) payload.username = username;
        if (department !== profile.department) payload.department = department;
        if (roleName !== profile.role_name) payload.role_name = roleName;
      }
      const res = await updateMe(payload);
      onUpdated(res.profile);
      setSavedTs(Date.now());
      setTimeout(() => setSavedTs(null), 3000);

      if (res.reissued) {
        // 사번/역할 변경 → 1.5초 후 강제 로그아웃
        setTimeout(() => onReissued(), 1500);
      }
    } catch (e) {
      setErrMsg(extractError(e).detail);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">BASIC · 기본 정보</div>
          <h2 className="lg-h2">{profile.username} <span className="lg-h2-sub">· {profile.role_name}</span></h2>
        </div>
        <div className="lg-actions">
          {savedTs && <span className="lg-ok">✓ 저장됨</span>}
          <button className="lg-btn" disabled={!canSave} onClick={() => void handleSave()}>
            {saving ? '저장 중…' : '저장'}
          </button>
        </div>
      </div>

      {privileged && (
        <div
          className="lg-sub"
          style={{
            marginBottom: 16,
            fontSize: 12,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <ShieldCheck size={13} strokeWidth={1.6} />
          인사·시스템 관리자 권한으로 모든 필드 편집 가능. 사번/역할 변경 시 재로그인 필요.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px 24px' }}>
        {/* 사번 */}
        <div className="lg-field">
          <FieldLabel
            text="사번"
            marker={privileged ? 'risky' : 'locked'}
          />
          <input
            type="text"
            value={empId}
            onChange={(e) => setEmpId(e.target.value)}
            disabled={!privileged}
            placeholder="예: QA-0100"
            maxLength={20}
            style={!empIdValid ? { borderColor: 'var(--hud-red)' } : !privileged ? { opacity: 0.6 } : undefined}
          />
          {!empIdValid && (
            <span style={{ fontSize: 11, color: 'var(--hud-red)' }}>
              영문/숫자/-/_ 3~20자만 허용됩니다.
            </span>
          )}
        </div>

        {/* 이름 */}
        <div className="lg-field">
          <FieldLabel
            text="이름"
            marker={privileged ? 'admin' : 'locked'}
          />
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={!privileged}
            maxLength={100}
            style={!privileged ? { opacity: 0.6 } : undefined}
          />
        </div>

        {/* 부서 */}
        <div className="lg-field">
          <FieldLabel
            text="부서"
            marker={privileged ? 'admin' : 'locked'}
          />
          {privileged ? (
            <select value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="">— 선택 —</option>
              {DEPARTMENT_OPTIONS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
              {/* 현재 값이 옵션에 없으면 그대로 표시 */}
              {department && !DEPARTMENT_OPTIONS.includes(department) && (
                <option value={department}>{department} (현재)</option>
              )}
            </select>
          ) : (
            <input type="text" value={department || '—'} disabled style={{ opacity: 0.6 }} />
          )}
        </div>

        {/* 역할 */}
        <div className="lg-field">
          <FieldLabel
            text="역할"
            marker={privileged ? 'risky' : 'locked'}
          />
          {privileged ? (
            <select value={roleName} onChange={(e) => setRoleName(e.target.value)}>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
              {roleName && !ROLE_OPTIONS.find((r) => r.value === roleName) && (
                <option value={roleName}>{roleName} (현재)</option>
              )}
            </select>
          ) : (
            <input
              type="text"
              value={`${profile.role_name} (Lv ${profile.role_level})`}
              disabled
              style={{ opacity: 0.6 }}
            />
          )}
        </div>

        {/* 입사일 / 마지막 로그인 — 항상 읽기 전용 */}
        <ReadOnlyField label="입사일" value={profile.hire_date || '—'} />
        <ReadOnlyField label="마지막 로그인" value={formatTs(profile.last_login)} />

        {/* 본인 편집 가능 */}
        <div className="lg-field grow">
          <label>이메일</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="example@ajin.com"
            style={!emailValid ? { borderColor: 'var(--hud-red)' } : undefined}
          />
          {!emailValid && (
            <span style={{ fontSize: 11, color: 'var(--hud-red)' }}>
              올바른 이메일 형식이 아닙니다.
            </span>
          )}
        </div>

        <div className="lg-field">
          <label>전화</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(autoFormatPhone(e.target.value))}
            placeholder="010-XXXX-XXXX 또는 053-XXX-XXXX"
            maxLength={13}
            style={!phoneValid ? { borderColor: 'var(--hud-red)' } : undefined}
          />
          {!phoneValid && (
            <span style={{ fontSize: 11, color: 'var(--hud-red)' }}>
              010-XXXX-XXXX 또는 02/053 등 일반전화 형식.
            </span>
          )}
        </div>

        <div className="lg-field">
          <label>직급</label>
          <input
            type="text"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            placeholder="예: 대리, 과장, 팀장"
            maxLength={50}
          />
        </div>
      </div>

      {errMsg && (
        <div
          className="lg-error"
          style={{
            marginTop: 12,
            color: 'var(--hud-red)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <AlertTriangle size={13} strokeWidth={1.6} />
          {errMsg}
        </div>
      )}
    </section>
  );
}

/**
 * 라벨 + 권한 마커 (lucide 아이콘) — Design System v2 양식.
 *  - locked: 🔒 잠금 (인사팀 관리 영역)
 *  - admin:  관리자 권한으로 편집 가능 (방패 아이콘 단순)
 *  - risky:  위험 변경 (사번/역할 — 재로그인 필요)
 */
function FieldLabel({
  text,
  marker,
}: {
  text: string;
  marker?: 'locked' | 'admin' | 'risky' | 'none';
}) {
  let icon: React.ReactNode = null;
  let title = '';
  if (marker === 'locked') {
    icon = <Lock size={11} strokeWidth={1.6} />;
    title = '인사팀이 관리하는 항목입니다';
  } else if (marker === 'admin') {
    icon = <ShieldCheck size={11} strokeWidth={1.6} />;
    title = '인사·시스템 관리자 권한으로 편집 가능';
  } else if (marker === 'risky') {
    icon = <AlertTriangle size={11} strokeWidth={1.6} />;
    title = '위험 변경 — 저장 시 재로그인 필요';
  }
  return (
    <label
      title={title}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
    >
      <span>{text}</span>
      {icon}
    </label>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="lg-field">
      <FieldLabel text={label} marker="locked" />
      <input type="text" value={value} disabled style={{ opacity: 0.6 }} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Tab 2: SECURITY — 비밀번호 변경
// ─────────────────────────────────────────────────────────────

function SecurityTab({
  employeeId,
  onChanged,
}: {
  employeeId: string;
  onChanged: () => void;
}) {
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const strength = pwStrength(next);
  const matches = confirm.length > 0 && next === confirm;
  const canSubmit = cur.length > 0 && strength.score >= 3 && matches && !busy;

  async function handleSubmit() {
    setBusy(true);
    setErrMsg(null);
    try {
      await apiChangePassword({
        employee_id: employeeId,
        current_password: cur,
        new_password: next,
      });
      setDone(true);
      onChanged();
    } catch (e) {
      setErrMsg(extractError(e).detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">SECURITY · 보안</div>
          <h2 className="lg-h2">비밀번호 변경</h2>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 16, maxWidth: 460 }}>
        <div className="lg-field">
          <label>현재 비밀번호</label>
          <input
            type="password"
            value={cur}
            onChange={(e) => setCur(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        <div className="lg-field">
          <label>새 비밀번호</label>
          <input
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            autoComplete="new-password"
          />
          {next.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
              <div
                style={{
                  flex: 1,
                  height: 4,
                  background: 'color-mix(in oklab, var(--hud-text) 8%, transparent)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${(strength.score / 4) * 100}%`,
                    height: '100%',
                    background: strength.color,
                    transition: 'all .2s',
                  }}
                />
              </div>
              <span style={{ color: strength.color, fontWeight: 600, minWidth: 60 }}>
                {strength.label}
              </span>
            </div>
          )}
          <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
            8자 이상 · 대소문자 · 숫자 · 특수문자 4가지 모두 권장
          </span>
        </div>

        <div className="lg-field">
          <label>새 비밀번호 확인</label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            style={confirm && !matches ? { borderColor: 'var(--hud-red)' } : undefined}
          />
          {confirm && !matches && (
            <span style={{ fontSize: 11, color: 'var(--hud-red)' }}>
              새 비밀번호와 일치하지 않습니다.
            </span>
          )}
        </div>

        <button
          className="lg-btn"
          disabled={!canSubmit}
          onClick={() => void handleSubmit()}
        >
          {busy ? '변경 중…' : done ? '✓ 변경 완료 — 로그아웃 됩니다' : '비밀번호 변경'}
        </button>

        {errMsg && (
          <div
            style={{
              color: 'var(--hud-red)',
              fontSize: 13,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <AlertTriangle size={13} strokeWidth={1.6} />
            {errMsg}
          </div>
        )}

        <div className="lg-sub" style={{ fontSize: 12, marginTop: 8 }}>
          ※ 변경 성공 시 보안을 위해 자동 로그아웃됩니다. 새 비밀번호로 다시 로그인하세요.
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
// Tab 3: ACTIVITY — 로그인 이력
// ─────────────────────────────────────────────────────────────

function ActivityTab() {
  const [entries, setEntries] = useState<LoginHistoryEntry[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getMyLoginHistory(20)
      .then((d) => setEntries(d.history))
      .catch((e) => setErr(extractError(e).detail));
  }, []);

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">ACTIVITY · 활동 이력</div>
          <h2 className="lg-h2">최근 로그인 기록</h2>
        </div>
        <div className="lg-actions">
          <span className="lg-pill">{entries?.length ?? 0} 건</span>
        </div>
      </div>

      {err && (
        <div
          style={{
            color: 'var(--hud-red)',
            fontSize: 13,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <AlertTriangle size={13} strokeWidth={1.6} />
          {err}
        </div>
      )}

      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr>
              <th>시각</th>
              <th>액션</th>
              <th>결과</th>
              <th>IP</th>
              <th>User-Agent</th>
            </tr>
          </thead>
          <tbody>
            {entries === null && (
              <tr><td colSpan={5} className="dim">불러오는 중…</td></tr>
            )}
            {entries?.length === 0 && (
              <tr><td colSpan={5} className="dim">로그인 이력이 없습니다.</td></tr>
            )}
            {entries?.map((e) => (
              <tr key={e.id}>
                <td className="mono dim">{formatTs(e.timestamp)}</td>
                <td>{e.action}</td>
                <td>
                  {e.success ? (
                    <span className="lg-ok">✓ 성공</span>
                  ) : (
                    <span style={{ color: 'var(--hud-red)' }}>✗ 실패</span>
                  )}
                </td>
                <td className="mono dim">{e.ip_address || '—'}</td>
                <td className="dim" style={{ fontSize: 11 }}>
                  {e.user_agent ? e.user_agent.slice(0, 40) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
