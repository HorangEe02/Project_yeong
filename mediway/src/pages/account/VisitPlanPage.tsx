import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, Save, Share2, Trash2 } from 'lucide-react';
import { AccountLayout } from '@/components/account/AccountLayout';
import { POIPicker } from '@/components/account/POIPicker';
import { QuickTemplatePicker } from '@/components/account/QuickTemplatePicker';
import { VisitPlanEditor } from '@/components/account/VisitPlanEditor';
import { ShareDialog } from '@/components/account/ShareDialog';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { useAuthStore } from '@/stores/authStore';
import { useVisitPlan } from '@/hooks/useVisitPlan';
import type { PlannedWaypoint } from '@/types/visit-plan';

export function VisitPlanPage() {
  const user = useAuthStore((s) => s.user);
  const { plan, loading, expired, save, clear, toggleAutoSend, saving, error } =
    useVisitPlan(user?.uid);

  const [draft, setDraft] = useState<PlannedWaypoint[]>([]);
  const [message, setMessage] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [remaining, setRemaining] = useState<string>('');

  // plan 변경 시 draft 동기화 (초기 로드 또는 외부 갱신 후)
  useEffect(() => {
    if (plan && !expired) setDraft(plan.waypoints);
    else setDraft([]);
  }, [plan, expired]);

  // 만료 카운트다운
  useEffect(() => {
    if (!plan || expired) {
      setRemaining('');
      return;
    }
    const update = () => {
      const diff = plan.expiresAt - Date.now();
      if (diff <= 0) {
        setRemaining('만료됨');
        return;
      }
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      setRemaining(`${h}시간 ${m}분 남음`);
    };
    update();
    const id = setInterval(update, 60_000);
    return () => clearInterval(id);
  }, [plan, expired]);

  const excludeIds = useMemo(() => draft.map((w) => w.poiId), [draft]);

  const addPOI = (poiId: string) => {
    if (draft.length >= 10) {
      setMessage({ tone: 'err', text: '목적지는 최대 10개까지 추가할 수 있습니다' });
      return;
    }
    setDraft([...draft, { poiId }]);
    setMessage(null);
  };

  const reorder = (from: number, to: number) => {
    if (to < 0 || to >= draft.length) return;
    const next = [...draft];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setDraft(next);
  };

  const remove = (i: number) => {
    setDraft(draft.filter((_, idx) => idx !== i));
  };

  const applyTemplate = (poiIds: string[]) => {
    setDraft(poiIds.map((poiId) => ({ poiId })));
    setMessage({ tone: 'ok', text: '템플릿이 적용되었습니다. 아래에서 편집 후 저장하세요.' });
  };

  const onSave = async () => {
    setMessage(null);
    try {
      await save(draft, 'patient');
      setMessage({ tone: 'ok', text: '저장되었습니다 (24시간 유효)' });
    } catch {
      // error is already set by hook
    }
  };

  const onClear = async () => {
    setMessage(null);
    try {
      await clear();
      setDraft([]);
      setMessage({ tone: 'ok', text: '방문 계획이 삭제되었습니다' });
    } catch {}
  };

  if (!user) return null;

  const dirty = !plansEqual(draft, plan?.waypoints ?? []);

  return (
    <AccountLayout
      title="방문 계획"
      description="병원 방문 시 의료진이 자동으로 경로를 채울 수 있도록 목적지를 미리 입력해 두세요."
    >
      {loading ? (
        <p className="text-sm text-on-surface-variant">불러오는 중...</p>
      ) : (
        <div className="flex flex-col gap-6">
          {/* 상태 배너 */}
          {plan && !expired && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary/5 px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-primary">
                <Clock className="h-4 w-4" />
                <span>유효기간 {remaining}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-on-surface-variant">
                  입력자: {plan.source === 'patient' ? '본인' : plan.source === 'staff' ? '의료진' : '관리자'}
                </span>
                {plan.source === 'patient' && (
                  <button
                    type="button"
                    onClick={() => setShareOpen(true)}
                    className="flex items-center gap-1 rounded-lg border border-primary bg-surface px-2.5 py-1 text-xs font-medium text-primary"
                  >
                    <Share2 className="h-3 w-3" />
                    공유
                  </button>
                )}
              </div>
            </div>
          )}

          {/* 빠른 시작 */}
          <QuickTemplatePicker onApply={applyTemplate} />

          {/* 직접 추가 */}
          <div className="flex flex-col gap-2">
            <p className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
              직접 목적지 추가
            </p>
            <POIPicker onAdd={addPOI} excludeIds={excludeIds} />
          </div>

          {/* 현재 계획 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <p className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
                현재 계획 ({draft.length}/10)
              </p>
              {draft.length > 0 && (
                <button
                  type="button"
                  onClick={() => setDraft([])}
                  className="text-xs text-on-surface-variant hover:text-red-600"
                >
                  전체 비우기
                </button>
              )}
            </div>
            <VisitPlanEditor
              waypoints={draft}
              onReorder={reorder}
              onRemove={remove}
            />
          </div>

          {/* 자동 전송 옵션 */}
          {plan && !expired && plan.source !== 'patient' && (
            <label className="flex items-start gap-3 rounded-xl border border-surface-container-high bg-surface p-4">
              <input
                type="checkbox"
                checked={!!plan.autoSendOptIn}
                onChange={(e) => void toggleAutoSend(e.target.checked)}
                className="mt-0.5"
              />
              <div>
                <p className="text-sm font-medium text-on-surface">자동 전송 동의</p>
                <p className="mt-0.5 text-xs text-on-surface-variant">
                  체크 시 의료진이 QR 스캔할 때 확인 없이 바로 전송됩니다. (병원이 배정한 계획만 해당)
                </p>
              </div>
            </label>
          )}

          {(error || message) && (
            <p
              className={`rounded-lg px-3 py-2 text-xs ${
                message?.tone === 'ok'
                  ? 'bg-green-50 text-green-700'
                  : 'bg-red-50 text-red-600'
              }`}
            >
              {message?.text ?? error}
            </p>
          )}

          {/* 하단 액션 */}
          <div className="flex items-center justify-between border-t border-surface-container-high pt-4">
            <button
              type="button"
              onClick={() => setConfirmClear(true)}
              disabled={!plan || saving}
              className="flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              저장된 계획 삭제
            </button>
            <div className="flex gap-2">
              {plan && !expired && dirty && (
                <span className="self-center text-[11px] text-amber-700">
                  <AlertTriangle className="mr-1 inline h-3 w-3" />
                  저장되지 않은 변경 사항
                </span>
              )}
              <button
                type="button"
                onClick={onSave}
                disabled={saving || draft.length === 0 || !dirty}
                className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
              >
                {saving ? (
                  '저장 중...'
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    저장
                  </>
                )}
              </button>
            </div>
          </div>

          {expired && plan && (
            <p className="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              이전 계획이 만료되어 새 계획을 저장하면 24시간 유효해집니다.
            </p>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmClear}
        title="저장된 방문 계획을 삭제할까요?"
        description="이 계획은 서버에서 제거됩니다. 되돌릴 수 없습니다."
        danger
        confirmLabel="삭제"
        onClose={() => setConfirmClear(false)}
        onConfirm={onClear}
      />

      <ShareDialog open={shareOpen} onClose={() => setShareOpen(false)} />
    </AccountLayout>
  );
}

function plansEqual(a: PlannedWaypoint[], b: PlannedWaypoint[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((x, i) => x.poiId === b[i].poiId && x.note === b[i].note);
}
