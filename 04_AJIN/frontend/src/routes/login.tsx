// Login 페이지 — 정책 6 조건 + 잠금 + 슬라이드 비번 변경 + DEV 데모 칩 + originalRoute

import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, type Location } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { useAuthStore } from '@store/auth';
import { useToast } from '@store/toast';
import { login as apiLogin, changePassword as apiChangePassword, extractError } from '@api/auth';
import { POLICY_RULES, evaluatePolicy, type PolicyKey } from '@lib/passwordPolicy';
import { DEMO_CHIPS, shouldShowDemoChips } from '@lib/demoAccounts';
import { ensureFirebaseUser, syncFirebasePassword } from '@lib/firebaseAuth';
import { Button } from '@components/ui/Button';
import { ErrorAlert } from '@components/ui/ErrorAlert';
import { useThemeStore } from '@store/theme';

type ViewMode = 'sign_in' | 'change_pw';

interface SignInValues {
  employee_id: string;
  password: string;
}

interface ChangePwValues {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

interface LocationState {
  from?: Location;
}

export function Login() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);
  const themeResolved = useThemeStore((s) => s.resolved());
  const { addToast } = useToast();

  const [view, setView] = useState<ViewMode>('sign_in');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingEmpId, setPendingEmpId] = useState<string | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);

  const signInForm = useForm<SignInValues>({ defaultValues: { employee_id: '', password: '' } });
  const changeForm = useForm<ChangePwValues>({ defaultValues: { current_password: '', new_password: '', confirm_password: '' } });

  const newPwValue = changeForm.watch('new_password');
  const confirmPwValue = changeForm.watch('confirm_password');
  const policy = evaluatePolicy(newPwValue);
  const passwordMismatch = confirmPwValue.length > 0 && newPwValue !== confirmPwValue;

  const empIdRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    empIdRef.current?.focus();
  }, []);

  const fromPath = (location.state as LocationState | null)?.from?.pathname;
  const redirectAfterAuth = () => {
    if (fromPath && fromPath !== '/login') {
      navigate(fromPath, { replace: true });
    } else {
      navigate('/', { replace: true });
    }
  };

  const handleCapsLock = (e: React.KeyboardEvent<HTMLInputElement>) => {
    setCapsLockOn(e.getModifierState('CapsLock'));
  };

  const onSignIn = async (values: SignInValues) => {
    setError(null);
    setSubmitting(true);
    try {
      const data = await apiLogin(values);
      if (data.must_change_pw) {
        setPendingEmpId(data.employee_id);
        signInForm.reset();
        setView('change_pw');
        return;
      }
      // Firebase Auth 자동 부트스트랩 — 실패해도 백엔드 JWT 만으로 진행 (graceful degrade)
      let firebaseUid: string | undefined;
      try {
        const fb = await ensureFirebaseUser(data.employee_id, values.password);
        firebaseUid = fb.uid;
        if (fb.isNewlyCreated) {
          addToast({ type: 'info', message: t('auth.firebase.bootstrap'), duration: 3000 });
        }
      } catch (fbErr) {
        if (import.meta.env.DEV) {
          console.warn('[Login] Firebase Auth 실패 — 백엔드 JWT 만으로 진행:', fbErr);
        }
        addToast({ type: 'warning', message: t('auth.firebase.warning'), duration: 5000 });
      }
      setSession(
        data.access_token,
        data.refresh_token,
        {
          employee_id: data.employee_id,
          username: data.username,
          role_name: data.role_name,
          role_level: data.role_level,
          department: data.department,
          position: data.position,
        },
        firebaseUid,
      );
      redirectAfterAuth();
    } catch (e) {
      const { detail } = extractError(e);
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const onChangePassword = async (values: ChangePwValues) => {
    if (!pendingEmpId) return;
    if (passwordMismatch) return;
    if (!policy.allValid) {
      setError(t('login.error.unknown'));
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await apiChangePassword({
        employee_id: pendingEmpId,
        current_password: values.current_password,
        new_password: values.new_password,
      });
      // 변경 후 자동 재로그인
      const data = await apiLogin({ employee_id: pendingEmpId, password: values.new_password });
      // Firebase 비밀번호 동기화 — 실패해도 백엔드 JWT 만으로 진행
      let firebaseUid: string | undefined;
      try {
        const fb = await syncFirebasePassword(data.employee_id, values.new_password);
        firebaseUid = fb.uid;
      } catch (fbErr) {
        if (import.meta.env.DEV) {
          console.warn('[Login] Firebase 비밀번호 동기화 실패 — 백엔드 JWT 만으로 진행:', fbErr);
        }
        addToast({ type: 'warning', message: t('auth.firebase.warning'), duration: 5000 });
      }
      setSession(
        data.access_token,
        data.refresh_token,
        {
          employee_id: data.employee_id,
          username: data.username,
          role_name: data.role_name,
          role_level: data.role_level,
          department: data.department,
          position: data.position,
        },
        firebaseUid,
      );
      redirectAfterAuth();
    } catch (e) {
      const { detail } = extractError(e);
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const onDemoChip = async (empId: string, password: string) => {
    signInForm.setValue('employee_id', empId);
    signInForm.setValue('password', password);
    await onSignIn({ employee_id: empId, password });
  };

  const toggleLang = () => {
    const next = i18n.language === 'ko' ? 'en' : 'ko';
    void i18n.changeLanguage(next);
  };

  const showDemoChips = shouldShowDemoChips() && view === 'sign_in';

  return (
    <div className="login-wrap">
      <div className="login-card glass">
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <img
            src={`/logos/ajin_logo_${themeResolved === 'light' ? 'light' : 'dark'}.svg`}
            alt="AJIN"
            style={{ width: 180 }}
          />
          <div className="label-en" style={{ marginTop: 12 }}>AI ASSISTANT</div>
          <div className="dim" style={{ fontSize: 11, marginTop: 4, letterSpacing: 2 }}>
            {t('app.version')} // {t('app.tagline')}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
          <h1 className="h1">
            {view === 'sign_in' ? t('login.title') : t('login.change_pw.title')}
          </h1>
          <button
            type="button"
            onClick={toggleLang}
            className="btn ghost sm"
            style={{ minWidth: 50 }}
            aria-label="Toggle language"
          >
            {i18n.language === 'ko' ? 'KO' : 'EN'}
          </button>
        </div>
        <p className="dim" style={{ marginBottom: 20 }}>
          {view === 'sign_in' ? t('login.subtitle') : t('login.change_pw.subtitle')}
        </p>

        {error && (
          <ErrorAlert
            title={t('login.error.title')}
            message={error}
            severity="critical"
          />
        )}

        {view === 'sign_in' && (
          <form onSubmit={signInForm.handleSubmit(onSignIn)}>
            <div className="field">
              <label className="label-en" htmlFor="employee_id">{t('login.employee_id')}</label>
              <input
                id="employee_id"
                type="text"
                autoComplete="username"
                {...signInForm.register('employee_id', { required: true })}
                ref={(el) => {
                  signInForm.register('employee_id').ref(el);
                  empIdRef.current = el;
                }}
              />
            </div>

            <div className="field">
              <label className="label-en" htmlFor="password">{t('login.password')}</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                onKeyUp={handleCapsLock}
                onKeyDown={handleCapsLock}
                {...signInForm.register('password', { required: true })}
              />
              {capsLockOn && (
                <div className="dim" style={{ fontSize: 11, color: 'var(--hud-orange)', marginTop: 4 }}>
                  ● Caps Lock ON
                </div>
              )}
            </div>

            <Button type="submit" variant="primary" fullWidth loading={submitting} style={{ marginTop: 16 }}>
              {t('login.submit')}
            </Button>
          </form>
        )}

        {view === 'change_pw' && (
          <form onSubmit={changeForm.handleSubmit(onChangePassword)}>
            <div className="field">
              <label className="label-en" htmlFor="current_password">{t('login.change_pw.current')}</label>
              <input
                id="current_password"
                type="password"
                autoComplete="current-password"
                autoFocus
                {...changeForm.register('current_password', { required: true })}
              />
            </div>
            <div className="field">
              <label className="label-en" htmlFor="new_password">{t('login.change_pw.new')}</label>
              <input
                id="new_password"
                type="password"
                autoComplete="new-password"
                {...changeForm.register('new_password', { required: true })}
              />
            </div>

            <div className="label-en" style={{ marginTop: 8 }}>{t('login.policy_title')}</div>
            <div className="policy">
              {POLICY_RULES.map((rule) => {
                const ok = policy.passed.includes(rule.key as PolicyKey);
                return (
                  <span
                    key={rule.key}
                    style={{ color: ok ? 'var(--hud-green)' : 'var(--hud-text-muted)' }}
                  >
                    {ok ? '●' : '○'} {t(`login.policy.${rule.key}`)}
                  </span>
                );
              })}
            </div>

            <div className="field" style={{ marginTop: 12 }}>
              <label className="label-en" htmlFor="confirm_password">{t('login.change_pw.confirm')}</label>
              <input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                aria-invalid={passwordMismatch || undefined}
                {...changeForm.register('confirm_password', { required: true })}
              />
              {passwordMismatch && (
                <div style={{ color: 'var(--hud-red)', fontSize: 12, marginTop: 4 }}>
                  ● {t('login.change_pw.mismatch')}
                </div>
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              fullWidth
              loading={submitting}
              disabled={!policy.allValid || passwordMismatch}
              style={{ marginTop: 12 }}
            >
              {t('login.change_pw.submit')}
            </Button>

            <Button
              type="button"
              variant="ghost"
              fullWidth
              onClick={() => {
                setView('sign_in');
                setError(null);
              }}
              style={{ marginTop: 8 }}
            >
              {t('login.change_pw.back')}
            </Button>
          </form>
        )}

        {showDemoChips && (
          <div className="demo-chips">
            <div className="label-en" style={{ marginTop: 16, marginBottom: 6 }}>
              {t('login.demo.label')}
            </div>
            <div className="dim" style={{ fontSize: 11, marginBottom: 8 }}>
              {t('login.demo.hint')}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {DEMO_CHIPS.map((chip) => (
                <button
                  key={chip.employee_id}
                  type="button"
                  className="btn ghost sm"
                  disabled={submitting}
                  onClick={() => onDemoChip(chip.employee_id, chip.password)}
                  style={{ flexDirection: 'column', height: 'auto', padding: 8, textAlign: 'left' }}
                >
                  <span style={{ fontSize: 11, color: 'var(--hud-primary)', letterSpacing: '0.05em' }}>
                    {chip.role_label}
                  </span>
                  <span style={{ fontSize: 13, marginTop: 2 }}>
                    {chip.username} <span className="dim">· L{chip.role_level}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
