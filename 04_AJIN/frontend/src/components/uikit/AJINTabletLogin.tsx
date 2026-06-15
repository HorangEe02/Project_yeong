// AJINTabletLogin — iPad 1024×1366 viewport 전용 로그인 화면.
// reference: uiux/AJIN AI Assistant Design System/ui_kits/mobile/PadScreens.jsx 패턴
//            (.aj-pad split — 좌 brand hero / 우 form).
//
// 모바일과 동일한 props 인터페이스 — login.tsx 의 단일 분기 지점에서 view-port 별 컴포넌트만 교체.

import { useTranslation } from 'react-i18next';
import { useThemeStore } from '@store/theme';
import { DEMO_CHIPS, shouldShowDemoChips } from '@lib/demoAccounts';
import { POLICY_RULES, type PolicyKey } from '@lib/passwordPolicy';
import type { AJINMobileLoginProps } from './AJINMobileLogin';

export function AJINTabletLogin(props: AJINMobileLoginProps) {
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

  const dividerColor =
    theme === 'dark' ? '0.5px solid rgba(255,255,255,0.08)' : '0.5px solid rgba(0,0,0,0.06)';

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
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)',
            minHeight: '100vh',
          }}
        >
          {/* LEFT — brand hero panel */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              padding: '48px 64px',
              gap: 20,
              borderRight: dividerColor,
            }}
          >
            <img
              src={`/logos/ajin_logo_${theme}.svg`}
              alt="AJIN INDUSTRIAL CO. LTD."
              style={{ width: 220, marginBottom: 8 }}
            />
            <div className="aj-mono" style={{ color: 'var(--aj-gold, #FCB132)' }}>
              AI ASSISTANT · v3.5 // KNU SILLI 2026
            </div>
            <h1
              style={{
                margin: 0,
                fontSize: 48,
                fontWeight: 700,
                letterSpacing: '-0.025em',
                lineHeight: 1.05,
              }}
            >
              {i18n.language === 'ko' ? '제조 현장의' : 'Smart factory'}
              <br />
              <span style={{ color: 'var(--aj-gold, #FCB132)' }}>
                {i18n.language === 'ko' ? 'AI 어시스턴트' : 'AI assistant'}
              </span>
            </h1>
            <p
              style={{
                fontSize: 16,
                opacity: 0.7,
                lineHeight: 1.55,
                maxWidth: 480,
                margin: 0,
              }}
            >
              {i18n.language === 'ko'
                ? '문서 검색 · SPC 알람 · 컴플라이언스 · 사출 보고서 — 하나의 콘솔에서 사무 업무를 자동화합니다.'
                : 'Search · SPC · Compliance · Reporting — one AI console for your factory.'}
            </p>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
              <span className="aj-status gold">DOCS RAG</span>
              <span className="aj-status ok">SPC ALERTS</span>
              <span className="aj-status warn">COMPLIANCE</span>
              <span className="aj-status gold">DRAFT GEN</span>
            </div>
          </div>

          {/* RIGHT — form panel */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              padding: '48px 64px',
              gap: 16,
            }}
          >
            {/* Lang toggle */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={props.toggleLang}
                className="aj-chip"
                style={{ minWidth: 60, height: 32 }}
              >
                {i18n.language === 'ko' ? 'KO' : 'EN'}
              </button>
            </div>

            <div>
              <h2
                style={{
                  margin: 0,
                  fontSize: 28,
                  fontWeight: 700,
                  letterSpacing: '-0.02em',
                }}
              >
                {props.view === 'sign_in' && t('login.title')}
                {props.view === 'change_pw' && t('login.change_pw.title')}
                {props.view === 'two_factor' && '2단계 인증'}
              </h2>
              <p style={{ marginTop: 6, fontSize: 14, opacity: 0.65 }}>
                {props.view === 'sign_in' && t('login.subtitle')}
                {props.view === 'change_pw' && t('login.change_pw.subtitle')}
                {props.view === 'two_factor' &&
                  '인증 앱의 6자리 코드 또는 백업 코드를 입력하세요.'}
              </p>
            </div>

            {props.error && (
              <div
                className="aj-glass"
                style={{
                  padding: 14,
                  color: '#FF7565',
                  fontSize: 13,
                  borderColor: 'rgba(255,117,101,0.4)',
                }}
              >
                ● {props.error}
              </div>
            )}

            {props.view === 'sign_in' && (
              <form onSubmit={props.signInForm.handleSubmit(props.onSignIn)}>
                <div className="aj-glass aj-login-card" style={{ margin: 0 }}>
                  <div className="field">
                    <label htmlFor="t_employee_id">{t('login.employee_id')}</label>
                    <input
                      id="t_employee_id"
                      type="text"
                      autoComplete="username"
                      placeholder="EMP-20260524"
                      {...props.signInForm.register('employee_id', { required: true })}
                      ref={setEmpRef}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="t_password">{t('login.password')}</label>
                    <input
                      id="t_password"
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

            {props.view === 'two_factor' && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void props.on2FAVerify();
                }}
              >
                <div className="aj-glass aj-login-card" style={{ margin: 0 }}>
                  <div className="field">
                    <label htmlFor="t_totp">인증 코드</label>
                    <input
                      id="t_totp"
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
                      6자리 TOTP 또는 11자 백업
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

            {props.view === 'change_pw' && (
              <form onSubmit={props.changeForm.handleSubmit(props.onChangePassword)}>
                <div className="aj-glass aj-login-card" style={{ margin: 0 }}>
                  <div className="field">
                    <label htmlFor="t_current_pw">{t('login.change_pw.current')}</label>
                    <input
                      id="t_current_pw"
                      type="password"
                      autoComplete="current-password"
                      autoFocus
                      {...props.changeForm.register('current_password', { required: true })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="t_new_pw">{t('login.change_pw.new')}</label>
                    <input
                      id="t_new_pw"
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
                      gap: '6px 12px',
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
                    <label htmlFor="t_confirm_pw">{t('login.change_pw.confirm')}</label>
                    <input
                      id="t_confirm_pw"
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

            {showDemoChips && (
              <div>
                <div className="aj-mono" style={{ marginBottom: 8 }}>
                  {t('login.demo.label')}
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 8,
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
                        padding: '8px 12px',
                        alignItems: 'flex-start',
                        textAlign: 'left',
                        gap: 2,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 11,
                          color: 'var(--aj-gold, #FCB132)',
                          letterSpacing: '0.05em',
                        }}
                      >
                        {chip.role_label}
                      </span>
                      <span style={{ fontSize: 13 }}>
                        {chip.username}{' '}
                        <span style={{ opacity: 0.6 }}>· L{chip.role_level}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                gap: 24,
                fontSize: 12,
                opacity: 0.6,
                marginTop: 12,
              }}
            >
              <span>SSO</span>
              <span style={{ opacity: 0.3 }}>·</span>
              <span>지원</span>
              <span style={{ opacity: 0.3 }}>·</span>
              <span>약관</span>
            </div>

            <div
              className="aj-mono"
              style={{ textAlign: 'center', fontSize: 9, opacity: 0.5 }}
            >
              ISO 27001 · IATF 16949 · INTERNAL USE ONLY
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
