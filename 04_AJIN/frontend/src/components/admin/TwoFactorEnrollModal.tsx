// v4.7 Feature E Phase 3 — 2FA enrollment 3-step wizard
//
// 1단계: "활성화" 클릭 → POST /auth/2fa/enroll → QR + manual key
// 2단계: 인증앱 6자리 코드 입력 → POST /auth/2fa/confirm → enabled
// 3단계: 백업코드 8개 표시 (복사/다운로드)

import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Modal } from '@components/ui/Modal';
import { Button } from '@components/ui/Button';
import {
  confirm2FA,
  enroll2FA,
  extractError,
  type TwoFactorEnrollResponse,
} from '@api/auth';
import { useToast } from '@store/toast';

type Step = 'intro' | 'qr' | 'codes' | 'done';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onEnabled?: () => void;
}

export function TwoFactorEnrollModal({ isOpen, onClose, onEnabled }: Props) {
  const { addToast } = useToast();

  const [step, setStep] = useState<Step>('intro');
  const [enrollData, setEnrollData] = useState<TwoFactorEnrollResponse | null>(null);
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    // 진행 중 상태 리셋
    setStep('intro');
    setEnrollData(null);
    setCode('');
    setError(null);
    onClose();
  };

  const startEnroll = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const data = await enroll2FA();
      setEnrollData(data);
      setStep('qr');
    } catch (e) {
      const { detail } = extractError(e);
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmCode = async () => {
    if (!/^\d{6}$/.test(code.trim())) {
      setError('6자리 숫자 코드를 입력하세요.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await confirm2FA(code.trim());
      setStep('codes');
      onEnabled?.();
    } catch (e) {
      const { detail } = extractError(e);
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const copyBackupCodes = async () => {
    if (!enrollData) return;
    try {
      await navigator.clipboard.writeText(enrollData.backup_codes.join('\n'));
      addToast({ type: 'success', message: '백업 코드를 클립보드에 복사했습니다.', duration: 3000 });
    } catch {
      addToast({ type: 'error', message: '클립보드 복사 실패. 수동으로 복사하세요.', duration: 4000 });
    }
  };

  const downloadBackupCodes = () => {
    if (!enrollData) return;
    const text = [
      '# AJIN AI Assistant — 2FA 백업 코드',
      '# 1회용. 인증앱 분실 시 1코드 = 1로그인.',
      '# 안전한 곳에 보관하고 노출되면 즉시 재발급하세요.',
      '',
      ...enrollData.backup_codes,
    ].join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `ajin-2fa-backup-codes-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="2단계 인증 (2FA) 설정" size="md">
      {error && (
        <div style={{ color: 'var(--hud-red)', marginBottom: 12, fontSize: 13 }}>● {error}</div>
      )}

      {step === 'intro' && (
        <div>
          <p style={{ marginBottom: 12 }}>
            2단계 인증을 활성화하면 비밀번호 외에 인증 앱(Google Authenticator, Authy 등)이
            생성한 6자리 코드가 매 로그인마다 필요합니다.
          </p>
          <ul style={{ paddingLeft: 18, marginBottom: 16, lineHeight: 1.7 }}>
            <li>설정 후 8개의 백업 코드가 발급됩니다.</li>
            <li>인증 앱 분실 시 백업 코드(1회용)로 로그인 가능합니다.</li>
            <li>관리자 권한이 있어도 2FA 우회는 불가합니다.</li>
          </ul>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="ghost" onClick={handleClose}>취소</Button>
            <Button variant="primary" loading={submitting} onClick={startEnroll}>2FA 활성화</Button>
          </div>
        </div>
      )}

      {step === 'qr' && enrollData && (
        <div>
          <p style={{ marginBottom: 12 }}>
            인증 앱으로 아래 QR 코드를 스캔하거나, 시크릿을 수동으로 입력하세요.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
            <div style={{ background: '#fff', padding: 12, borderRadius: 6 }}>
              <QRCodeSVG value={enrollData.otpauth_url} size={200} level="M" />
            </div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label className="label-en">수동 입력용 시크릿 (Base32)</label>
            <code
              style={{
                display: 'block',
                padding: 8,
                background: 'var(--hud-bg-elev)',
                fontSize: 13,
                wordBreak: 'break-all',
                userSelect: 'all',
              }}
            >
              {enrollData.secret_b32}
            </code>
          </div>
          <div className="field">
            <label className="label-en" htmlFor="totp-code">6자리 코드</label>
            <input
              id="totp-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              pattern="\d{6}"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              autoFocus
            />
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <Button variant="ghost" onClick={handleClose}>취소</Button>
            <Button variant="primary" loading={submitting} onClick={confirmCode}>코드 확인</Button>
          </div>
        </div>
      )}

      {step === 'codes' && enrollData && (
        <div>
          <p style={{ marginBottom: 8 }}>
            <strong style={{ color: 'var(--hud-orange)' }}>
              ⚠️ 이 백업 코드는 한 번만 표시됩니다.
            </strong>
          </p>
          <p style={{ marginBottom: 12, fontSize: 13 }}>
            안전한 곳(비밀번호 관리자, 인쇄 보관 등)에 저장하세요. 각 코드는 1회용입니다.
          </p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 8,
              padding: 12,
              background: 'var(--hud-bg-elev)',
              borderRadius: 6,
              fontFamily: 'var(--hud-font-mono, monospace)',
              marginBottom: 12,
            }}
          >
            {enrollData.backup_codes.map((c) => (
              <div key={c} style={{ fontSize: 14, letterSpacing: '0.05em' }}>
                {c}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button variant="ghost" onClick={copyBackupCodes}>복사</Button>
              <Button variant="ghost" onClick={downloadBackupCodes}>다운로드 (.txt)</Button>
            </div>
            <Button
              variant="primary"
              onClick={() => {
                setStep('done');
                handleClose();
              }}
            >
              완료
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
