import { useState, useCallback, useEffect } from 'react';
import {
  ScanLine,
  CheckCircle2,
  AlertCircle,
  LayoutTemplate,
  PenLine,
} from 'lucide-react';
import { QRScanner } from './QRScanner';
import { RouteTemplateList } from './RouteTemplateList';
import { RouteBuilder } from './RouteBuilder';
import { SendConfirm } from './SendConfirm';
import { VisitPlanBanner } from './VisitPlanBanner';
import { routeTemplates } from '@/data/route-templates';
import { createSession, getQRToken, updateQRTokenStatus } from '@/services/session';
import { getCurrentUid } from '@/services/auth';
import { appendAudit } from '@/services/auditLog';
import { useAutoFillFromPlan } from '@/hooks/useAutoFillFromPlan';
import { isFirebaseConfigured } from '@/config/firebase';
import { NotificationMessages } from '@/services/notification';
import { v4 as uuidv4 } from 'uuid';
import type { RouteTemplate } from '@/types/route-template';
import type { WaypointStatus } from '@/types/session';
import type { VisitPlan } from '@/types/visit-plan';

const DEMO_HOSPITAL_ID = 'demo-hospital';
const AUTO_SEND_COUNTDOWN_SEC = 3;

type StaffState =
  | 'idle'
  | 'scanning'
  | 'scanned'
  | 'selecting_template'
  | 'building_custom'
  | 'confirming'
  | 'auto_sending'
  | 'sent'
  | 'error';

export function StaffDashboard() {
  const [state, setState] = useState<StaffState>('idle');
  const [patientToken, setPatientToken] = useState<string | null>(null);
  const [patientUid, setPatientUid] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<RouteTemplate | null>(null);
  const [customWaypoints, setCustomWaypoints] = useState<string[]>(['entrance_main']);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [appliedPlan, setAppliedPlan] = useState<VisitPlan | null>(null);
  const [autoSendCountdown, setAutoSendCountdown] = useState(AUTO_SEND_COUNTDOWN_SEC);

  const { plan, mismatched, autoSendEligible } = useAutoFillFromPlan(
    patientUid,
    DEMO_HOSPITAL_ID,
  );

  // 플랜 자동 채움
  useEffect(() => {
    if (state !== 'scanned' || !plan || mismatched) return;
    setCustomWaypoints([...plan.waypoints.map((w) => w.poiId), 'entrance_main']);
    setAppliedPlan(plan);
    if (autoSendEligible) {
      setAutoSendCountdown(AUTO_SEND_COUNTDOWN_SEC);
      setState('auto_sending');
    } else {
      setState('building_custom');
    }
  }, [state, plan, mismatched, autoSendEligible]);

  // 자동 전송 카운트다운
  useEffect(() => {
    if (state !== 'auto_sending') return;
    if (autoSendCountdown <= 0) {
      void triggerSend(true);
      return;
    }
    const t = setTimeout(() => setAutoSendCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, autoSendCountdown]);

  const resetAll = () => {
    setState('idle');
    setPatientToken(null);
    setPatientUid(null);
    setSelectedTemplate(null);
    setCustomWaypoints(['entrance_main']);
    setAppliedPlan(null);
    setAutoSendCountdown(AUTO_SEND_COUNTDOWN_SEC);
  };

  // QR 스캔 성공
  const handleScanSuccess = useCallback(async (token: string) => {
    if (isFirebaseConfigured()) {
      const qrData = await getQRToken(token);
      if (!qrData || qrData.status !== 'waiting') {
        setErrorMessage('유효하지 않거나 이미 사용된 QR 코드입니다.');
        setState('error');
        return;
      }
      setPatientUid(qrData.patientUid);
    } else {
      setPatientUid('demo-patient');
    }
    setPatientToken(token);
    setState('scanned');
  }, []);

  const handleScanError = useCallback((error: string) => {
    setErrorMessage(error);
    setState('error');
  }, []);

  const handleTemplateSelect = useCallback((template: RouteTemplate) => {
    setSelectedTemplate(template);
    setAppliedPlan(null); // 템플릿 선택 시 적용된 계획 해제
    setState('confirming');
  }, []);

  const handleCustomSend = useCallback(() => {
    if (customWaypoints.length >= 2) {
      setSelectedTemplate(null);
      setState('confirming');
    }
  }, [customWaypoints]);

  // 수동 재선택 (자동 전송 취소)
  const handleCancelAutoSend = useCallback(() => {
    setState('building_custom');
  }, []);

  // 현재 전송할 경유지 배열
  const activeWaypoints = selectedTemplate
    ? selectedTemplate.waypointPoiIds
    : customWaypoints;

  const triggerSend = useCallback(
    async (isAuto: boolean) => {
      try {
        if (isFirebaseConfigured() && patientToken) {
          const sessionId = uuidv4();
          const staffUid = getCurrentUid() ?? 'demo-staff';
          const qrData = await getQRToken(patientToken);
          const resolvedPatientUid = qrData?.patientUid ?? 'demo-patient';

          const sessionData: Parameters<typeof createSession>[0] = {
            sessionId,
            patientUid: resolvedPatientUid,
            staffUid,
            qrToken: patientToken,
            hospitalId: DEMO_HOSPITAL_ID,
            status: 'navigating',
            currentWaypointIndex: 0,
            waypoints: activeWaypoints.map((poiId, i) => ({
              poiId,
              status: (i === 0 ? 'current' : 'pending') as WaypointStatus,
            })),
            createdAt: Date.now(),
          };
          if (appliedPlan) {
            sessionData.autoGenerated = true;
            sessionData.planSource = appliedPlan.source;
          }

          await createSession(sessionData);
          await updateQRTokenStatus(patientToken, 'matched', sessionId);

          if (isAuto) {
            await appendAudit('visit_plan.auto_send', resolvedPatientUid, {
              sessionId,
              source: appliedPlan?.source ?? 'unknown',
            });
          }
        }

        NotificationMessages.routeReceived();
        setState('sent');
        setTimeout(resetAll, 3000);
      } catch (error) {
        console.error('[MediWay] 세션 생성 실패:', error);
        setErrorMessage('동선 전송에 실패했습니다. 다시 시도해주세요.');
        setState('error');
      }
    },
    [patientToken, activeWaypoints, appliedPlan],
  );

  const handleSendConfirm = useCallback(() => void triggerSend(false), [triggerSend]);
  const handleSendCancel = useCallback(() => setState('scanned'), []);
  const handleRetry = useCallback(() => {
    resetAll();
    setErrorMessage(null);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      {state === 'sent' && (
        <div className="flex items-center gap-3 rounded-xl bg-green-50 p-4">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          <p className="text-sm font-semibold text-green-800">
            동선이 환자에게 전송되었습니다!
          </p>
        </div>
      )}

      {state === 'error' && (
        <div className="flex items-center justify-between rounded-xl bg-error-container/30 p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-error" />
            <p className="text-sm font-medium text-error">
              {errorMessage ?? '오류가 발생했습니다.'}
            </p>
          </div>
          <button
            onClick={handleRetry}
            className="rounded-lg bg-error/10 px-3 py-1.5 text-xs font-semibold text-error"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* Step 1: QR 스캔 */}
      {(state === 'idle' || state === 'scanning') && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
              1
            </div>
            <h2 className="text-base font-semibold text-on-surface">환자 QR 스캔</h2>
          </div>
          <QRScanner onScanSuccess={handleScanSuccess} onScanError={handleScanError} />
        </section>
      )}

      {/* Step 2: 동선 선택 / 자동 전송 */}
      {(state === 'scanned' ||
        state === 'selecting_template' ||
        state === 'building_custom' ||
        state === 'auto_sending') && (
        <>
          <div className="flex items-center gap-3 rounded-xl bg-primary/5 p-4">
            <ScanLine className="h-5 w-5 text-primary" />
            <div>
              <p className="text-sm font-semibold text-on-surface">환자 매칭 완료</p>
              <p className="text-xs text-on-surface-variant">
                토큰: {patientToken?.slice(0, 8)}...
              </p>
            </div>
          </div>

          {/* 병원 불일치 경고 */}
          {plan && mismatched && (
            <VisitPlanBanner plan={plan} variant="mismatched" />
          )}

          {/* 자동 적용 배너 */}
          {appliedPlan && state !== 'auto_sending' && (
            <VisitPlanBanner
              plan={appliedPlan}
              variant="applied"
              onDismiss={() => {
                setAppliedPlan(null);
                setCustomWaypoints(['entrance_main']);
              }}
            />
          )}

          {/* 자동 전송 카운트다운 */}
          {state === 'auto_sending' && appliedPlan && (
            <VisitPlanBanner
              plan={appliedPlan}
              variant="auto-sending"
              countdownSec={autoSendCountdown}
              onCancelAutoSend={handleCancelAutoSend}
            />
          )}

          {state !== 'auto_sending' && (
            <>
              {/* 탭: 템플릿 / 커스텀 */}
              <div className="flex gap-1 rounded-xl bg-surface-container-high p-1">
                <button
                  onClick={() => setState('selecting_template')}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${
                    state !== 'building_custom'
                      ? 'bg-surface-container-lowest text-primary shadow-ambient'
                      : 'text-on-surface-variant'
                  }`}
                >
                  <LayoutTemplate className="h-4 w-4" />
                  템플릿 선택
                </button>
                <button
                  onClick={() => setState('building_custom')}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${
                    state === 'building_custom'
                      ? 'bg-surface-container-lowest text-primary shadow-ambient'
                      : 'text-on-surface-variant'
                  }`}
                >
                  <PenLine className="h-4 w-4" />
                  {appliedPlan ? '계획 편집' : '커스텀 경로'}
                </button>
              </div>

              {state !== 'building_custom' && (
                <section>
                  <RouteTemplateList
                    templates={routeTemplates}
                    selectedId={selectedTemplate?.id ?? null}
                    onSelect={handleTemplateSelect}
                  />
                </section>
              )}

              {state === 'building_custom' && (
                <section>
                  <RouteBuilder
                    waypoints={customWaypoints}
                    onChange={setCustomWaypoints}
                  />
                  {customWaypoints.length >= 2 && (
                    <button
                      onClick={handleCustomSend}
                      className="mt-4 w-full rounded-xl bg-gradient-to-r from-primary to-primary-container py-3 text-sm font-semibold text-on-primary transition-transform active:scale-[0.98]"
                    >
                      {appliedPlan ? '이 경로로 전송하기 (계획 기반)' : '이 경로로 전송하기'}
                    </button>
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}

      {state === 'confirming' && (
        <SendConfirm
          waypointPoiIds={activeWaypoints}
          templateName={selectedTemplate?.name}
          onConfirm={handleSendConfirm}
          onCancel={handleSendCancel}
        />
      )}
    </div>
  );
}
