// AJINMobileLogin — iPhone 모바일 전용 로그인 화면.
// reference: uiux/AJIN AI Assistant Design System/ui_kits/mobile/MobScreens.jsx::MobLogin (L54-105)
// 사용자 mockup (claude.ai design 1번 image): AJIN 브랜딩 + 한국어 hero + SSO·지원·약관 dock + KO 토글.
//
// design tokens: mobile-theme.css (.aj-mobile / .aj-screen / .aj-bg-grad / .aj-glass /
//                .aj-login-card / .aj-btn.primary / .aj-mono / .aj-chip)
//
// state 는 routes/login.tsx 의 useForm/useState 를 props 로 받아 wire — 동작 로직(2FA/changePassword/
// apiLogin) 은 기존 그대로, visual layer 만 reference 디자인으로 교체.

import type { RefObject } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useThemeStore } from '@store/theme';
import { DEMO_CHIPS, shouldShowDemoChips } from '@lib/demoAccounts';
import { POLICY_RULES, type PolicyKey } from '@lib/passwordPolicy';

export type LoginViewMode = 'sign_in' | 'change_pw' | 'two_factor';

export interface SignInValues {
  employee_id: string;
  password: string;
}

export interface ChangePwValues {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface PolicyResult {
  passed: string[];
  allValid: boolean;
}

export interface AJINMobileLoginProps {
  view: LoginViewMode;
  signInForm: UseFormReturn<SignInValues>;
  changeForm: UseFormReturn<ChangePwValues>;
  onSignIn: (values: SignInValues) => void | Promise<void>;
  onChangePassword: (values: ChangePwValues) => void | Promise<void>;
  on2FAVerify: () => void | Promise<void>;
  twoFactorCode: string;
  setTwoFactorCode: (v: string) => void;
  pendingEmpId: string | null;
  submitting: boolean;
  error: string | null;
  capsLockOn: boolean;
  handleCapsLock: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  empIdRef: RefObject<HTMLInputElement | null>;
  policy: PolicyResult;
  passwordMismatch: boolean;
  onDemoChip: (empId: string, password: string) => void | Promise<void>;
  toggleLang: () => void;
  goSignIn: () => void;
}

export function AJINMobileLogin(props: AJINMobileLoginProps) {
  const { t, i18n } = useTranslation();
  const themeResolved = useThemeStore((s) => s.resolved());
  const theme: 'dark' | 'light' = themeResolved === 'light' ? 'light' : 'dark';
  const showDemoChips = shouldShowDemoChips() && props.view === 'sign_in';

  const setEmpRef = (el: HTMLInputElement | null) => {
    props.signInForm.register('employee_id').ref(el);
    if (props.empIdRef) {
      (props.empIdRef as React.MutableRefObject<HTMLInputElement | null>).current = el;
    }
  };

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh', display: 'flex' }}>
      <div
        className={`aj-screen ${theme}`}
        style={{ position: 'relative', flex: 1, minHeight: '100vh', overflow: 'hidden' }}
      >
        <div className={`aj-bg-grad ${theme}`} />

        <div
          style={{
            position: 'relative',
            zIndex: 2,
            padding: '60px 16px 24px',
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {/* KO 토글 */}
          <div style={{ position: 'absolute', top: 22, right: 16, zIndex: 3 }}>
            <button
              type="button"
              onClick={props.toggleLang}
              className="aj-chip"
              aria-label="Toggle language"
              style={{ minWidth: 50, height: 28, fontSize: 11, padding: '0 12px' }}
            >
              {i18n.language === 'ko' ? 'KO' : 'EN'}
            </button>
          </div>

          {/* Hero — AJIN brand + greeting */}
          <div style={{ textAlign: 'center', paddingTop: 28 }}>
            <img
              src={`/logos/ajin_logo_${theme}.svg`}
              alt="AJIN INDUSTRIAL CO. LTD."
              style={{ width: 140, display: 'block', margin: '0 auto 6px' }}
            />
            <div
              className="aj-mono"
              style={{ color: 'var(--aj-gold, #FCB132)', fontSize: 10 }}
            >
              AI ASSISTANT · v3.5
            </div>
            <div className="aj-mono" style={{ marginTop: 2, opacity: 0.55, fontSize: 9 }}>
              KNU SILLI 2026
            </div>

            <div style={{ marginTop: 24 }}>
              <h1
                style={{
                  margin: 0,
                  fontSize: 26,
                  fontWeight: 700,
                  letterSpacing: '-0.02em',
                  lineHeight: 1.2,
                }}
              >
                {props.view === 'sign_in' && (i18n.language === 'ko' ? '안녕하세요,' : 'Welcome,')}
                {props.view === 'change_pw' && t('login.change_pw.title')}
                {props.view === 'two_factor' && '2단계 인증'}
              </h1>
              {props.view === 'sign_in' && (
                <h2
                  style={{
                    margin: '4px 0 0',
                    fontSize: 26,
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                    color: 'var(--aj-gold, #FCB132)',
                  }}
                >
                  {i18n.language === 'ko' ? '아진 가족 여러분' : 'AJIN team'}
                </h2>
              )}
              <p
                style={{
                  margin: '10px auto 0',
                  maxWidth: 300,
                  fontSize: 13,
                  opacity: 0.7,
                  lineHeight: 1.45,
                }}
              >
                {props.view === 'sign_in' &&
                  (i18n.language === 'ko'
                    ? '제조 현장의 사무 업무를 하나씩 해결해드려요.'
                    : t('login.subtitle'))}
                {props.view === 'change_pw' && t('login.change_pw.subtitle')}
                {props.view === 'two_factor' &&
                  '인증 앱의 6자리 코드 또는 백업 코드를 입력하세요.'}
              </p>
            </div>
          </div>

          {/* Error */}
          {props.error && (
            <div
              className="aj-glass"
              style={{
                padding: 12,
                margin: '0 4px',
                borderColor: 'rgba(255,117,101,0.4)',
                color: '#FF7565',
                fontSize: 13,
              }}
            >
              ● {props.error}
            </div>
          )}

          {/* Sign in form */}
          {props.view === 'sign_in' && (
            <form onSubmit={props.signInForm.handleSubmit(props.onSignIn)}>
              <div className="aj-glass aj-login-card" style={{ margin: 0 }}>
                <div className="field">
                  <label htmlFor="m_employee_id">{t('login.employee_id')}</label>
                  <input
                    id="m_employee_id"
                    type="text"
                    autoComplete="username"
                    placeholder="EMP-20260524"
                    {...props.signInForm.register('employee_id', { required: true })}
                    ref={setEmpRef}
                  />
                </div>
                <div className="field">
                  <label htmlFor="m_password">{t('login.password')}</label>
                  <input
                    id="m_password"
                    type="password"
                    autoComplete="current-password"
                    onKeyUp={props.handleCapsLock}
                    onKeyDown={props.handleCapsLock}
                    {...props.signInForm.register('password', { required: true })}
                  />
                  {props.capsLockOn && (
                    <div
                      className="aj-mono"
                      style={{ fontSize: 10, color: '#FCB132', marginTop: 4 }}
                    >
                      ● CAPS LOCK ON
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  className="aj-btn primary full"
                  disabled={props.submitting}
                >
                  {props.submitting ? '...' : `${t('login.submit')} →`}
                </button>
              </div>
            </form>
          )}

          {/* 2FA form */}
          {props.view === 'two_factor' && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void props.on2FAVerify();
              }}
            >
              <div className="aj-glass aj-login-card" style={{ margin: 0 }}>
                <div className="field">
                  <label htmlFor="m_totp">인증 코드</label>
                  <input
                    id="m_totp"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={11}
                    value={props.twoFactorCode}
                    onChange={(e) => props.setTwoFactorCode(e.target.value)}
                    placeholder="123456"
                    autoFocus
                  />
                  <div
                    className="aj-mono"
                    style={{ fontSize: 10, marginTop: 4, opacity: 0.7 }}
                  >
                    {props.pendingEmpId ? `사번 ${props.pendingEmpId} · ` : ''}
                    6자리 TOTP 또는 11자 백업 (XXXXX-XXXXX)
                  </div>
                </div>
                <button
                  type="submit"
                  className="aj-btn primary full"
                  disabled={props.submitting}
                >
                  {props.submitting ? '...' : '인증 →'}
                </button>
                <button
                  type="button"
                  className="aj-btn ghost full"
                  onClick={props.goSignIn}
                >
                  취소
                </button>
              </div>
            </form>
          )}

          {/* Change password form */}
          {props.view === 'change_pw' && (
            <form onSubmit={props.changeForm.handleSubmit(props.onChangePassword)}>
              <div className="aj-glass aj-login-card" style={{ margin: 0 }}>
                <div className="field">
                  <label htmlFor="m_current_pw">{t('login.change_pw.current')}</label>
                  <input
                    id="m_current_pw"
                    type="password"
                    autoComplete="current-password"
                    autoFocus
                    {...props.changeForm.register('current_password', { required: true })}
                  />
                </div>
                <div className="field">
                  <label htmlFor="m_new_pw">{t('login.change_pw.new')}</label>
                  <input
                    id="m_new_pw"
                    type="password"
                    autoComplete="new-password"
                    {...props.changeForm.register('new_password', { required: true })}
                  />
                </div>
                <div className="aj-mono" style={{ fontSize: 10 }}>
                  {t('login.policy_title')}
                </div>
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '6px 10px',
                    fontSize: 11,
                  }}
                >
                  {POLICY_RULES.map((rule) => {
                    const ok = props.policy.passed.includes(rule.key as PolicyKey);
                    return (
                      <span
                        key={rule.key}
                        style={{
                          color: ok ? '#4FB774' : 'rgba(255,255,255,0.4)',
                        }}
                      >
                        {ok ? '●' : '○'} {t(`login.policy.${rule.key}`)}
                      </span>
                    );
                  })}
                </div>
                <div className="field">
                  <label htmlFor="m_confirm_pw">{t('login.change_pw.confirm')}</label>
                  <input
                    id="m_confirm_pw"
                    type="password"
                    autoComplete="new-password"
                    aria-invalid={props.passwordMismatch || undefined}
                    {...props.changeForm.register('confirm_password', { required: true })}
                  />
                  {props.passwordMismatch && (
                    <div style={{ color: '#FF7565', fontSize: 11, marginTop: 4 }}>
                      ● {t('login.change_pw.mismatch')}
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  className="aj-btn primary full"
                  disabled={
                    props.submitting || !props.policy.allValid || props.passwordMismatch
                  }
                >
                  {props.submitting ? '...' : `${t('login.change_pw.submit')} →`}
                </button>
                <button
                  type="button"
                  className="aj-btn ghost full"
                  onClick={props.goSignIn}
                >
                  {t('login.change_pw.back')}
                </button>
              </div>
            </form>
          )}

          {/* Demo chips */}
          {showDemoChips && (
            <div style={{ padding: '0 4px' }}>
              <div className="aj-mono" style={{ marginBottom: 6 }}>
                {t('login.demo.label')}
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 6,
                }}
              >
                {DEMO_CHIPS.map((chip) => (
                  <button
                    key={chip.employee_id}
                    type="button"
                    className="aj-chip"
                    disabled={props.submitting}
                    onClick={() => props.onDemoChip(chip.employee_id, chip.password)}
                    style={{
                      flexDirection: 'column',
                      height: 'auto',
                      padding: '6px 10px',
                      alignItems: 'flex-start',
                      textAlign: 'left',
                      gap: 2,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        color: 'var(--aj-gold, #FCB132)',
                        letterSpacing: '0.05em',
                      }}
                    >
                      {chip.role_label}
                    </span>
                    <span style={{ fontSize: 12 }}>
                      {chip.username}{' '}
                      <span style={{ opacity: 0.6 }}>· L{chip.role_level}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ flex: 1 }} />

          {/* Dock (SSO · 지원 · 약관) */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              gap: 18,
              padding: '8px 0',
              fontSize: 11,
              opacity: 0.75,
            }}
          >
            <span>SSO</span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>지원</span>
            <span style={{ opacity: 0.3 }}>·</span>
            <span>약관</span>
          </div>

          {/* Footer */}
          <div
            className="aj-mono"
            style={{ textAlign: 'center', fontSize: 9, opacity: 0.5 }}
          >
            ISO 27001 · IATF 16949 · INTERNAL USE ONLY
          </div>
        </div>
      </div>
    </div>
  );
}
