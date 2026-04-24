import { useEffect, useRef, useState } from 'react';
import { QRCodeCanvas } from 'qrcode.react';
import { Copy, RefreshCcw, Share2, X, Link as LinkIcon } from 'lucide-react';
import { buildShareUrl, createShareCode, revokeShareCode } from '@/services/sharedPlan';
import { useAuthStore } from '@/stores/authStore';
import type { SharedPlan } from '@/types/shared-plan';

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
}

export function ShareDialog({ open, onClose }: ShareDialogProps) {
  const displayName = useAuthStore((s) => s.profile?.displayName ?? null);
  const [plan, setPlan] = useState<SharedPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<'code' | 'url' | null>(null);
  const [remaining, setRemaining] = useState('');

  const mountedRef = useRef(false);
  useEffect(() => {
    if (!open) {
      setPlan(null);
      setError(null);
      mountedRef.current = false;
      return;
    }
    if (mountedRef.current) return;
    mountedRef.current = true;
    void generate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // 만료 카운트다운
  useEffect(() => {
    if (!plan) {
      setRemaining('');
      return;
    }
    const tick = () => {
      const diff = plan.expiresAt - Date.now();
      if (diff <= 0) {
        setRemaining('만료됨');
        return;
      }
      const m = Math.floor(diff / 60_000);
      const s = Math.floor((diff % 60_000) / 1000);
      setRemaining(`${m}분 ${s}초 남음`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [plan]);

  const generate = async () => {
    setCreating(true);
    setError(null);
    try {
      // 기존 코드가 있으면 폐기 후 재생성
      if (plan) await revokeShareCode(plan.code).catch(() => {});
      const created = await createShareCode(displayName);
      setPlan(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  };

  const copy = async (what: 'code' | 'url') => {
    if (!plan) return;
    const text = what === 'code' ? plan.code : buildShareUrl(plan.code);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // ignore
    }
  };

  if (!open) return null;

  const url = plan ? buildShareUrl(plan.code) : '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <Share2 className="h-4 w-4 text-primary" />
              방문 계획 공유
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              보호자에게 코드나 링크를 전달하세요. 30분 후 자동 만료됩니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container-low"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
            {error}
          </p>
        )}

        {creating && !plan && (
          <p className="py-6 text-center text-sm text-on-surface-variant">
            공유 코드 생성 중...
          </p>
        )}

        {plan && (
          <div className="flex flex-col items-center gap-4">
            {/* QR 코드 */}
            <div className="rounded-2xl bg-white p-3 shadow-ambient">
              <QRCodeCanvas value={url} size={160} />
            </div>

            {/* 6자리 코드 */}
            <div className="w-full">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                공유 코드
              </p>
              <div className="flex items-stretch gap-2">
                <div className="flex-1 rounded-lg border border-surface-container-high bg-surface px-4 py-3 text-center font-mono text-2xl tracking-[0.3em] text-on-surface">
                  {plan.code}
                </div>
                <button
                  type="button"
                  onClick={() => copy('code')}
                  className="flex items-center gap-1 rounded-lg border border-primary px-3 text-xs font-medium text-primary"
                >
                  <Copy className="h-3.5 w-3.5" />
                  {copied === 'code' ? '복사됨' : '복사'}
                </button>
              </div>
            </div>

            {/* URL */}
            <div className="w-full">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                공유 URL
              </p>
              <div className="flex items-stretch gap-2">
                <div className="flex-1 overflow-hidden rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-xs text-on-surface">
                  <span className="block truncate">{url}</span>
                </div>
                <button
                  type="button"
                  onClick={() => copy('url')}
                  className="flex items-center gap-1 rounded-lg border border-primary px-3 text-xs font-medium text-primary"
                >
                  <LinkIcon className="h-3.5 w-3.5" />
                  {copied === 'url' ? '복사됨' : '복사'}
                </button>
              </div>
            </div>

            <p className="text-xs text-on-surface-variant">
              ⏱ {remaining}
            </p>

            <div className="flex w-full items-center justify-between gap-2 border-t border-surface-container-high pt-3">
              <button
                type="button"
                onClick={async () => {
                  await revokeShareCode(plan.code).catch(() => {});
                  setPlan(null);
                  onClose();
                }}
                className="text-xs text-on-surface-variant hover:text-red-600"
              >
                코드 폐기
              </button>
              <button
                type="button"
                onClick={generate}
                disabled={creating}
                className="flex items-center gap-1 rounded-lg border border-surface-container-high px-3 py-1.5 text-xs"
              >
                <RefreshCcw className="h-3 w-3" />
                {creating ? '생성 중...' : '새 코드 생성'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
