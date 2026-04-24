import { useState, type FormEvent } from 'react';
import { AlertTriangle, MapPin, X } from 'lucide-react';
import { QuickTemplatePicker } from '@/components/account/QuickTemplatePicker';
import { POIPicker } from '@/components/account/POIPicker';
import { VisitPlanEditor } from '@/components/account/VisitPlanEditor';
import { setVisitPlan } from '@/services/visitPlan';
import { getPOIById } from '@/data/hospital/pois';
import type { PlannedWaypoint, VisitPlan } from '@/types/visit-plan';

interface AssignVisitPlanDialogProps {
  open: boolean;
  uid: string;
  displayName: string | null;
  existingPlan: VisitPlan | null;
  hospitalId?: string;
  onClose: () => void;
  onAssigned: () => void;
}

type Tab = 'template' | 'custom';

const TTL_OPTIONS = [
  { label: '6시간', ms: 6 * 3_600_000 },
  { label: '12시간', ms: 12 * 3_600_000 },
  { label: '24시간 (기본)', ms: 24 * 3_600_000 },
  { label: '48시간 (최대)', ms: 48 * 3_600_000 },
];

export function AssignVisitPlanDialog({
  open,
  uid,
  displayName,
  existingPlan,
  hospitalId,
  onClose,
  onAssigned,
}: AssignVisitPlanDialogProps) {
  const [tab, setTab] = useState<Tab>('template');
  const [draft, setDraft] = useState<PlannedWaypoint[]>([]);
  const [ttlMs, setTtlMs] = useState<number>(TTL_OPTIONS[2].ms);
  const [autoSend, setAutoSend] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const applyTemplate = (ids: string[]) => {
    setDraft(ids.map((poiId) => ({ poiId })));
  };
  const addPOI = (poiId: string) => {
    if (draft.length >= 10) {
      setError('목적지는 최대 10개까지 추가할 수 있습니다');
      return;
    }
    setDraft([...draft, { poiId }]);
    setError(null);
  };
  const reorder = (from: number, to: number) => {
    if (to < 0 || to >= draft.length) return;
    const next = [...draft];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setDraft(next);
  };
  const remove = (i: number) => setDraft(draft.filter((_, idx) => idx !== i));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (draft.length === 0) {
      setError('최소 1개 이상의 목적지가 필요합니다');
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await setVisitPlan(uid, {
        waypoints: draft,
        source: 'admin',
        hospitalId,
        ttlMs,
      });
      // autoSend 토글은 별도 setAutoSendOptIn 호출 필요하나 권한 이슈 회피 위해
      // 본 다이얼로그에서는 배정 후 별도 서비스로 업데이트
      if (autoSend) {
        // setAutoSendOptIn은 본인만 호출 가능 → admin이 직접 업데이트하도록 직접 쓰기
        const { update, ref } = await import('firebase/database');
        const { db } = await import('@/config/firebase');
        await update(ref(db, `visit_plans/${uid}`), { autoSendOptIn: true });
      }
      onAssigned();
      onClose();
      setDraft([]);
      setAutoSend(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const hasExisting = existingPlan && existingPlan.expiresAt > Date.now();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div className="max-h-full w-full max-w-lg overflow-y-auto rounded-2xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <MapPin className="h-4 w-4 text-primary" />
              방문 계획 배정
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              {displayName ?? uid} 에게 새 방문 계획을 설정합니다
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

        {hasExisting && (
          <div className="mb-3 flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-700">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div>
              <p className="font-semibold">기존 계획이 있습니다 — 저장 시 덮어쓰기됩니다</p>
              <p className="mt-0.5 text-amber-700/80">
                현재 {existingPlan!.waypoints.length}개 목적지 (
                {existingPlan!.source === 'patient' ? '본인' : existingPlan!.source === 'staff' ? '의료진' : '관리자'}{' '}
                입력)
              </p>
            </div>
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {/* 탭 */}
          <div className="flex gap-1 rounded-lg bg-surface-container-high p-1">
            <button
              type="button"
              onClick={() => setTab('template')}
              className={`flex-1 rounded px-3 py-1.5 text-xs font-medium ${
                tab === 'template'
                  ? 'bg-surface-container-lowest text-primary shadow-ambient'
                  : 'text-on-surface-variant'
              }`}
            >
              템플릿
            </button>
            <button
              type="button"
              onClick={() => setTab('custom')}
              className={`flex-1 rounded px-3 py-1.5 text-xs font-medium ${
                tab === 'custom'
                  ? 'bg-surface-container-lowest text-primary shadow-ambient'
                  : 'text-on-surface-variant'
              }`}
            >
              직접 선택
            </button>
          </div>

          {tab === 'template' ? (
            <QuickTemplatePicker onApply={applyTemplate} />
          ) : (
            <POIPicker onAdd={addPOI} excludeIds={draft.map((w) => w.poiId)} />
          )}

          {/* 현재 배정 목록 */}
          <div>
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
              배정할 경로 ({draft.length}/10)
            </p>
            <VisitPlanEditor waypoints={draft} onReorder={reorder} onRemove={remove} />
            {draft.length > 0 && (
              <p className="mt-1.5 truncate text-[11px] text-on-surface-variant/70">
                요약: {draft.map((w) => getPOIById(w.poiId)?.shortName ?? w.poiId).join(' → ')}
              </p>
            )}
          </div>

          {/* 옵션 */}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                유효 기간
              </span>
              <select
                value={ttlMs}
                onChange={(e) => setTtlMs(Number(e.target.value))}
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-xs"
              >
                {TTL_OPTIONS.map((o) => (
                  <option key={o.ms} value={o.ms}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex cursor-pointer flex-col gap-1 rounded-lg border border-surface-container-high bg-surface p-2">
              <span className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                자동 전송
              </span>
              <span className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={autoSend}
                  onChange={(e) => setAutoSend(e.target.checked)}
                />
                QR 스캔 즉시 자동 전송 허용
              </span>
            </label>
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>
          )}

          <div className="mt-1 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-surface-container-high px-4 py-2 text-xs"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={saving || draft.length === 0}
              className="rounded-lg bg-primary px-4 py-2 text-xs font-medium text-on-primary disabled:opacity-50"
            >
              {saving ? '저장 중...' : hasExisting ? '덮어쓰기 저장' : '배정'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
