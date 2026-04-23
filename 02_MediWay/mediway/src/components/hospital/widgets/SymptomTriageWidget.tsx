import { useState } from 'react';
import { Stethoscope, AlertTriangle, Loader2 } from 'lucide-react';
import { requestTriage, type TriageResponse } from '@/services/triage';

const MIN_LEN = 3;
const MAX_LEN = 500;

/**
 * AI 증상 triage 위젯 — v2 F19.
 *
 * 병원 `features.aiTriage=true` 일 때 HomeTab 4번째 슬롯으로 렌더.
 * "진단 아님" 고지 UI 필수 (법적·윤리적 안전장치).
 */
export function SymptomTriageWidget() {
  const [symptoms, setSymptoms] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TriageResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const canSubmit =
    symptoms.trim().length >= MIN_LEN &&
    symptoms.trim().length <= MAX_LEN &&
    !loading;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setErr(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await requestTriage(symptoms.trim());
      setResult(res);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setLoading(false);
    }
  };

  const onReset = () => {
    setSymptoms('');
    setResult(null);
    setErr(null);
  };

  return (
    <article
      className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      aria-labelledby="triage-title"
    >
      <header className="mb-2 flex items-center gap-2">
        <Stethoscope className="h-5 w-5 text-primary" aria-hidden="true" />
        <h3 id="triage-title" className="text-base font-semibold">
          AI 진료과 추천
        </h3>
      </header>

      <p className="mb-3 flex items-start gap-1 text-xs text-on-surface-variant">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
        <span>
          AI가 증상을 분석해 추천하는 참고용이며 진단이 아닙니다. 증상 텍스트는
          저장되지 않습니다.
        </span>
      </p>

      {!result ? (
        <form onSubmit={onSubmit} className="space-y-2">
          <label className="block text-sm">
            <span className="sr-only">증상 입력</span>
            <textarea
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
              rows={3}
              maxLength={MAX_LEN}
              placeholder="예: 2일째 기침과 미열이 있어요"
              className="w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
              disabled={loading}
            />
          </label>
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant">
              {symptoms.trim().length}/{MAX_LEN}
            </span>
            <button
              type="submit"
              disabled={!canSubmit}
              className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary disabled:opacity-50"
            >
              {loading && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              )}
              {loading ? '분석 중…' : '진료과 추천'}
            </button>
          </div>
          {err && (
            <p role="alert" className="text-xs text-error">
              {err}
            </p>
          )}
        </form>
      ) : (
        <div className="space-y-2">
          <ul className="space-y-1" aria-label="추천 진료과 목록">
            {result.recommendations.map((r, i) => (
              <li
                key={`${r.department}-${i}`}
                className="rounded-lg border border-outline-variant px-3 py-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{r.department}</span>
                  <span className="text-xs text-on-surface-variant">
                    신뢰도 {Math.round(r.confidence * 100)}%
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-on-surface-variant">
                  {r.reason}
                </p>
              </li>
            ))}
          </ul>
          <p className="rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-900">
            {result.disclaimer}
          </p>
          <button
            type="button"
            onClick={onReset}
            className="text-xs text-primary underline-offset-2 hover:underline"
          >
            다시 입력
          </button>
        </div>
      )}
    </article>
  );
}
