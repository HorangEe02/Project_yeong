import { Sparkles, AlertTriangle, X, Clock, Zap } from 'lucide-react';
import { getPOIById } from '@/data/hospital/pois';
import { describePlanSource } from '@/services/visitPlan';
import type { VisitPlan } from '@/types/visit-plan';

interface VisitPlanBannerProps {
  plan: VisitPlan;
  variant: 'applied' | 'mismatched' | 'auto-sending';
  countdownSec?: number;
  onCancelAutoSend?: () => void;
  onDismiss?: () => void;
}

export function VisitPlanBanner({
  plan,
  variant,
  countdownSec,
  onCancelAutoSend,
  onDismiss,
}: VisitPlanBannerProps) {
  const remaining = formatRemaining(plan.expiresAt);
  const preview = plan.waypoints
    .map((w) => getPOIById(w.poiId)?.shortName ?? w.poiId)
    .join(' → ');

  if (variant === 'mismatched') {
    return (
      <div className="flex items-start gap-3 rounded-xl bg-amber-50 p-4">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-800">
            다른 병원의 방문 계획입니다
          </p>
          <p className="mt-0.5 text-xs text-amber-700">
            이 환자의 계획은 다른 병원({plan.hospitalId})에 등록되어 있어 자동 적용하지 않습니다. 수동으로 경로를 선택해주세요.
          </p>
        </div>
      </div>
    );
  }

  if (variant === 'auto-sending') {
    return (
      <div className="flex items-start gap-3 rounded-xl bg-green-50 p-4">
        <Zap className="mt-0.5 h-5 w-5 shrink-0 text-green-600" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-green-800">
            {countdownSec ?? 0}초 후 자동 전송
          </p>
          <p className="mt-0.5 text-xs text-green-700">
            {describePlanSource(plan.source)}이 설정한 계획을 환자에게 바로 전송합니다.
          </p>
          <p className="mt-1 truncate text-xs text-green-700/80">{preview}</p>
        </div>
        {onCancelAutoSend && (
          <button
            type="button"
            onClick={onCancelAutoSend}
            className="shrink-0 rounded-lg border border-green-700 bg-white/80 px-3 py-1.5 text-xs font-medium text-green-800"
          >
            취소 · 수동 선택
          </button>
        )}
      </div>
    );
  }

  // applied
  return (
    <div className="flex items-start gap-3 rounded-xl bg-primary/5 p-4">
      <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-on-surface">
          환자 방문 계획이 자동 적용되었습니다
        </p>
        <p className="mt-0.5 text-xs text-on-surface-variant">
          {describePlanSource(plan.source)} · {plan.waypoints.length}개 목적지
          <span className="mx-1.5 opacity-50">·</span>
          <Clock className="mr-0.5 inline h-3 w-3 align-[-2px]" />
          {remaining}
        </p>
        <p className="mt-1 truncate text-xs text-on-surface-variant/80">{preview}</p>
      </div>
      {onDismiss && (
        <button
          type="button"
          aria-label="배너 닫기"
          onClick={onDismiss}
          className="shrink-0 rounded-lg p-1 text-on-surface-variant hover:bg-surface-container-low"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

function formatRemaining(expiresAt: number): string {
  const diff = expiresAt - Date.now();
  if (diff <= 0) return '만료됨';
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  if (h > 0) return `${h}시간 ${m}분 남음`;
  return `${m}분 남음`;
}
