import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react';
import { AlertTriangle, RefreshCw, Sparkles } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useFeature, useHospital } from '@/contexts/HospitalContext';
import { requestTriageRecommendation } from '@/services/triage';
import type {
  TriageError,
  TriageRecommendation,
  TriageResponse,
} from '@/types/triage';

/**
 * AI 진료과 추천 위젯 — 환자 홈 탭에 features.aiTriage=true 일 때만 마운트.
 *
 * 데이터: 서버 `triageSymptoms` callable. 일회성 요청 (chat 아님 — 매번 fresh).
 *
 * UX 원칙:
 *  - 입력: textarea (10..500자) — 너무 짧으면 의미 없는 추천 방지
 *  - 결과: 3개 진료과 카드 + confidence bar + reason
 *  - 응급 응답 시 빨간 배너 + 119/응급실 강조
 *  - "진단 아님" disclaimer 카드 하단에 prominent
 *  - 에러는 친근 한국어. rate-limit 일 때 분 단위 retry 안내
 *  - IME(한국어) 조합 안전 — 위젯은 form submit 만 사용 (Enter 단축키 없음)
 *  - [다시 입력] 버튼으로 결과 초기화 → 재입력
 *
 * 마운트 가드:
 *  - HomeTab 가 features.aiTriage 로 conditional mount (defense in depth)
 *  - 본 위젯도 미로그인/익명 시 null
 */

const MAX_CHARS = 500;
const MIN_CHARS = 10;

const ERROR_COPY: Record<TriageError['code'], string> = {
  unauthenticated: '로그인 후 다시 시도해 주세요.',
  feature_disabled: '이 병원에서는 AI 진료과 추천이 제공되지 않습니다.',
  invalid_argument: '증상 설명을 다시 확인해 주세요.',
  rate_limited: '잠시 후 다시 시도해 주세요.',
  network: '네트워크가 불안정합니다. 다시 시도해 주세요.',
  internal: 'AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.',
  unknown: '일시적인 오류가 발생했습니다.',
};

export function TriageWidget() {
  const user = useAuthStore((s) => s.user);
  const { slug } = useHospital();
  const aiTriageOn = useFeature('aiTriage');
  const isAnon = user?.isAnonymous ?? true;

  const [symptomText, setSymptomText] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TriageResponse | null>(null);
  const [error, setError] = useState<{
    msg: string;
    code: TriageError['code'];
    retryAfterSeconds?: number;
  } | null>(null);
  const composingRef = useRef(false);

  const charCount = symptomText.trim().length;
  const canSubmit = useMemo(
    () => charCount >= MIN_CHARS && charCount <= MAX_CHARS && !busy,
    [charCount, busy],
  );

  const onSubmit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      if (!canSubmit) return;
      setBusy(true);
      setError(null);
      setResult(null);
      try {
        const r = await requestTriageRecommendation({
          hospitalId: slug,
          symptomText,
        });
        setResult(r);
      } catch (err) {
        const typed = err as TriageError;
        const baseMsg = ERROR_COPY[typed.code] ?? ERROR_COPY.unknown;
        let msg = baseMsg;
        if (typed.code === 'rate_limited' && typed.retryAfterSeconds) {
          const minutes = Math.max(1, Math.ceil(typed.retryAfterSeconds / 60));
          msg = `시간당 한도를 초과했습니다. 약 ${minutes}분 후 다시 시도해 주세요.`;
        } else if (typed.code === 'invalid_argument') {
          msg = typed.message || baseMsg;
        }
        setError({
          msg,
          code: typed.code,
          retryAfterSeconds: typed.retryAfterSeconds,
        });
      } finally {
        setBusy(false);
      }
    },
    [canSubmit, slug, symptomText],
  );

  const onReset = useCallback(() => {
    setResult(null);
    setError(null);
    setSymptomText('');
  }, []);

  if (!user || isAnon || !aiTriageOn) return null;

  return (
    <section
      aria-label="AI 진료과 추천"
      className="flex flex-col gap-3 rounded-xl bg-surface-container-lowest p-4"
      data-testid="triage-widget"
    >
      <header className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-on-surface">
          <Sparkles className="h-4 w-4 text-primary" />
          AI 진료과 추천
        </h3>
        {result && (
          <button
            type="button"
            onClick={onReset}
            disabled={busy}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-on-surface-variant hover:bg-surface-container"
            aria-label="새 추천"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            다시 입력
          </button>
        )}
      </header>

      {!result && (
        <form onSubmit={onSubmit} className="flex flex-col gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-on-surface-variant">
              어떤 증상이 있는지 자세히 적어 주세요 ({MIN_CHARS}~{MAX_CHARS}자)
            </span>
            <textarea
              value={symptomText}
              onChange={(e) => setSymptomText(e.target.value)}
              onCompositionStart={() => {
                composingRef.current = true;
              }}
              onCompositionEnd={() => {
                composingRef.current = false;
              }}
              placeholder="예: 2일째 기침과 미열이 있어요"
              disabled={busy}
              rows={3}
              maxLength={MAX_CHARS}
              aria-label="증상 입력"
              className="resize-none rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm text-on-surface disabled:opacity-50"
            />
            <div
              className={`text-right text-[11px] ${
                charCount > MAX_CHARS ? 'text-error' : 'text-on-surface-variant'
              }`}
              aria-live="polite"
            >
              {charCount} / {MAX_CHARS}
            </div>
          </label>
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
          >
            {busy ? '추천 중...' : '진료과 추천 받기'}
          </button>
        </form>
      )}

      {result?.emergencyNotice && (
        <div
          role="alert"
          data-testid="triage-emergency"
          className="flex items-start gap-2 rounded-lg bg-error-container p-3 text-sm text-error"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p className="font-medium">{result.emergencyNotice}</p>
        </div>
      )}

      {result && (
        <ul className="flex flex-col gap-2" data-testid="triage-results">
          {result.recommendations.map((rec, idx) => (
            <RecCard key={`${rec.department}-${idx}`} rec={rec} rank={idx + 1} />
          ))}
        </ul>
      )}

      {result && (
        <p
          className="rounded-lg bg-surface-container p-2 text-[11px] text-on-surface-variant"
          data-testid="triage-disclaimer"
        >
          ⚠️ {result.disclaimer}
        </p>
      )}

      {error && (
        <div
          role="alert"
          data-testid="triage-error"
          className="rounded-lg bg-surface-container p-3 text-sm text-primary"
        >
          {error.msg}
        </div>
      )}

      {!result && (
        <p className="text-[11px] text-on-surface-variant">
          개인정보(이름·주민등록번호·연락처 등)는 입력하지 마세요. AI 답변은 참고용이며 진단이 아닙니다.
        </p>
      )}
    </section>
  );
}

function RecCard({ rec, rank }: { rec: TriageRecommendation; rank: number }) {
  const pct = Math.round(rec.confidence * 100);
  return (
    <li className="rounded-lg border border-outline-variant bg-surface-container-lowest p-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-on-surface">
          <span className="mr-1 text-xs text-on-surface-variant">{rank}.</span>
          {rec.department}
        </p>
        <span
          className="text-xs font-medium tabular-nums text-primary"
          aria-label={`신뢰도 ${pct}%`}
        >
          {pct}%
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-container"
        aria-hidden="true"
      >
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-on-surface-variant">{rec.reason}</p>
    </li>
  );
}
