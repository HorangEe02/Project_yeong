import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, QrCode } from 'lucide-react';
import { QRDisplay } from './QRDisplay';
import { useAuthStore } from '@/stores/authStore';
import { getCurrentUid, initAnonymousAuth } from '@/services/auth';
import { isFirebaseConfigured } from '@/config/firebase';
import { useHospital } from '@/contexts/HospitalContext';
import { useSession } from '@/hooks/useSession';
import {
  issueSelfQRToken,
  QRTokenRateLimitError,
} from '@/services/qrToken';

const LS_QR_TOKEN = 'mediway_qr_token';

/**
 * GuideTab 「QR 안내」 모드 — 두 상태 머신:
 *  1. 'placeholder' (기본) — 안내 데스크 → 발급 → 스캔 3단계 안내 + 「내 QR 코드 발급」 버튼
 *  2. 'displaying'         — `QRDisplay` 마운트 + 자가 발급 토큰을 RTDB 에 등록 + 「다시 안내 보기」 버튼
 *
 * Rate limit (시간당 30회):
 *  - `services/qrToken.ts` 의 `issueSelfQRToken` 가 transaction + RTDB rule 로 강제
 *  - `QRTokenRateLimitError` 캐치 시 inline 안내 + retryAfterSeconds 분 단위 표시
 *
 * Auth:
 *  - 로그인 / 익명 모두 발급 허용 — `auth.currentUser` 없으면 `initAnonymousAuth` 로 보강
 *  - QRDisplay 자체가 3분마다 자동 갱신 + 수동 갱신 버튼 → 토큰마다 issueSelfQRToken 호출
 */

type Mode = 'placeholder' | 'displaying';

export function QRGuidePlaceholder() {
  const navigate = useNavigate();
  const { slug } = useHospital();
  const initialized = useAuthStore((s) => s.initialized);
  const [mode, setMode] = useState<Mode>('placeholder');
  const [error, setError] = useState<{ msg: string } | null>(null);
  const [currentToken, setCurrentToken] = useState<string | null>(null);

  // 발급한 token 의 status 실시간 구독 — staff 가 스캔해서 'matched' + sessionId 부여되면
  // 환자 동선 화면 (`/h/{slug}/patient/{sessionId}`) 으로 자동 이동.
  const { qrTokenData } = useSession(currentToken);

  useEffect(() => {
    if (qrTokenData?.status === 'matched' && qrTokenData?.sessionId) {
      navigate(`/h/${slug}/patient/${qrTokenData.sessionId}`, { replace: true });
    }
  }, [qrTokenData?.status, qrTokenData?.sessionId, slug, navigate]);

  /** QRDisplay 의 onTokenGenerated 콜백 — 토큰 RTDB 등록 + rate-limit 처리. */
  const handleTokenGenerated = useCallback(async (token: string) => {
    if (!isFirebaseConfigured()) return;
    let uid = getCurrentUid();
    if (!uid) {
      const u = await initAnonymousAuth().catch(() => null);
      uid = u?.uid ?? null;
    }
    if (!uid) {
      setError({ msg: '인증을 확인할 수 없습니다. 다시 시도해 주세요.' });
      setMode('placeholder');
      return;
    }
    try {
      await issueSelfQRToken(token, uid);
      setError(null);
      // 매칭 감지 + PatientDashboard 복원 위해 token 보관
      setCurrentToken(token);
      localStorage.setItem(LS_QR_TOKEN, token);
    } catch (err) {
      if (err instanceof QRTokenRateLimitError) {
        const minutes = Math.max(1, Math.ceil(err.retryAfterSeconds / 60));
        setError({
          msg: `시간당 발급 한도를 초과했습니다. 약 ${minutes}분 후 다시 시도해 주세요.`,
        });
      } else {
        setError({
          msg: '토큰 발급에 실패했습니다. 잠시 후 다시 시도해 주세요.',
        });
      }
      setMode('placeholder');
    }
  }, []);

  const onIssue = useCallback(() => {
    setError(null);
    setMode('displaying');
  }, []);

  const onBack = useCallback(() => {
    setError(null);
    setMode('placeholder');
  }, []);

  if (mode === 'displaying') {
    return (
      <section
        role="region"
        aria-label="QR 코드 발급"
        data-testid="qr-self-issue"
        className="flex flex-col gap-4 rounded-xl bg-surface-container-lowest p-4 sm:p-6"
      >
        <button
          type="button"
          onClick={onBack}
          className="flex w-fit items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-on-surface-variant hover:bg-surface-container"
          aria-label="안내로 돌아가기"
        >
          <ArrowLeft className="h-4 w-4" />
          다시 안내 보기
        </button>
        <QRDisplay onTokenGenerated={handleTokenGenerated} />
      </section>
    );
  }

  return (
    <div
      role="region"
      aria-label="QR 안내"
      data-testid="qr-guide-placeholder"
      className="flex flex-col items-center gap-4 rounded-xl bg-surface-container-lowest p-6 text-center shadow-ambient sm:p-8"
    >
      <div className="flex h-24 w-24 items-center justify-center rounded-2xl bg-primary/10">
        <QrCode className="h-12 w-12 text-primary" aria-hidden="true" />
      </div>

      <div className="space-y-1">
        <h3 className="text-base font-semibold text-on-surface">
          QR 코드를 받아 안내를 시작하세요
        </h3>
        <p className="text-sm text-on-surface-variant">
          QR 코드를 의료진에게 보여 주면 동선 안내가 자동으로 시작됩니다.
        </p>
      </div>

      <ol className="w-full max-w-sm space-y-2 text-left text-sm text-on-surface">
        <Step n={1} text="병원 안내 데스크 방문" />
        <Step n={2} text="환자 QR 코드 발급 요청" />
        <Step n={3} text="의료진이 스캔하면 동선 안내 자동 시작" />
      </ol>

      <p className="rounded-lg bg-surface-container px-3 py-2 text-[12px] text-on-surface-variant">
        ※ 이미 QR 코드 화면이 열려 있다면 의료진에게 그대로 보여 주세요.
      </p>

      {error && (
        <div
          role="alert"
          data-testid="qr-issue-error"
          className="w-full rounded-lg bg-error-container p-3 text-sm text-error"
        >
          {error.msg}
        </div>
      )}

      <button
        type="button"
        onClick={onIssue}
        disabled={!initialized}
        data-testid="qr-issue-button"
        className="flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary disabled:opacity-50"
      >
        <QrCode className="h-4 w-4" />
        내 QR 코드 발급
      </button>
    </div>
  );
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <li className="flex items-start gap-3 rounded-lg bg-surface-container-low p-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-on-primary tabular-nums">
        {n}
      </span>
      <span className="pt-0.5">{text}</span>
    </li>
  );
}
