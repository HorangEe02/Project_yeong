// Day 5 — SOP 단계별 Drawer
// useSopStore.activeSopId 가 set 되면 자동 fetch + 단계 네비게이션 + 체크리스트.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Drawer } from '@components/ui/Drawer';
import { Stepper, type Step } from '@components/ui/Stepper';
import { Button } from '@components/ui/Button';
import { fetchSopDetail, type SopDetail } from '@api/sop';
import { useSopStore } from '@store/sop';

export function SOPStepDrawer() {
  const { t } = useTranslation();
  const activeSopId = useSopStore((s) => s.activeSopId);
  const closeSop = useSopStore((s) => s.closeSop);
  const progress = useSopStore((s) => (activeSopId ? s.progress[activeSopId] : undefined));
  const setCurrentStep = useSopStore((s) => s.setCurrentStep);
  const toggleStepCompleted = useSopStore((s) => s.toggleStepCompleted);

  const [detail, setDetail] = useState<SopDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeSopId) {
      setDetail(null);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
    fetchSopDetail(activeSopId)
      .then((d) => {
        if (mounted) setDetail(d);
      })
      .catch((e) => {
        if (mounted) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [activeSopId]);

  const isOpen = activeSopId !== null;
  const currentIdx = progress?.currentStep ?? 0;
  const completedSteps = progress?.completedSteps ?? [];

  const steps: Step[] =
    detail?.steps.map((s) => ({
      id: String(s.step_number),
      title: `${s.step_number}. ${s.title}`,
      description: s.estimated_time || undefined,
    })) ?? [];

  const currentStep = detail?.steps[currentIdx];
  const totalSteps = detail?.steps.length ?? 0;

  const handlePrev = () => {
    if (!activeSopId) return;
    if (currentIdx > 0) setCurrentStep(activeSopId, currentIdx - 1);
  };
  const handleNext = () => {
    if (!activeSopId) return;
    if (currentIdx < totalSteps - 1) setCurrentStep(activeSopId, currentIdx + 1);
  };
  const handleToggleStep = () => {
    if (!activeSopId || !currentStep) return;
    toggleStepCompleted(activeSopId, currentStep.step_number);
  };

  return (
    <Drawer
      isOpen={isOpen}
      onClose={closeSop}
      side="right"
      width={520}
      title={detail ? `${detail.sop_id} · ${detail.title}` : t('chat.sop.title')}
    >
      {loading && <div className="sop-drawer-empty">{t('common.loading')}</div>}
      {error && <div className="sop-drawer-empty error">{error}</div>}

      {detail && currentStep && (
        <div className="sop-drawer">
          <div className="sop-drawer-meta">
            <span className="sop-drawer-dept">{detail.department}</span>
            <span className="sop-drawer-cat" data-cat={detail.category}>{detail.category}</span>
          </div>

          {detail.safety_warnings.length > 0 && (
            <div className="sop-drawer-warning" role="note">
              <span className="sop-warning-eyebrow">{t('chat.sop.safety')}</span>
              <ul>
                {detail.safety_warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <Stepper
            steps={steps}
            current={currentIdx}
            variant="vertical"
            onStepClick={(idx) => activeSopId && setCurrentStep(activeSopId, idx)}
          />

          <div className="sop-drawer-step">
            <div className="sop-drawer-step-h">
              <span className="sop-drawer-step-num">
                {t('chat.sop.step_n_of_m', { n: currentStep.step_number, m: totalSteps })}
              </span>
              {currentStep.estimated_time && (
                <span className="sop-drawer-step-time">{currentStep.estimated_time}</span>
              )}
            </div>
            <h3 className="sop-drawer-step-title">{currentStep.title}</h3>
            <p className="sop-drawer-step-desc">{currentStep.description}</p>

            {currentStep.checklist.length > 0 && (
              <div className="sop-drawer-checklist">
                <span className="sop-section-eyebrow">{t('chat.sop.checklist')}</span>
                <ul>
                  {currentStep.checklist.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {currentStep.caution && (
              <div className="sop-drawer-caution" role="note">
                <span className="sop-caution-eyebrow">{t('chat.sop.caution')}</span>
                <span>{currentStep.caution}</span>
              </div>
            )}

            {currentStep.related_terms.length > 0 && (
              <div className="sop-drawer-terms">
                <span className="sop-section-eyebrow">{t('chat.sop.related_terms')}</span>
                <div className="sop-drawer-terms-row">
                  {currentStep.related_terms.map((term, i) => (
                    <span key={i} className="sop-drawer-term-chip">
                      {term}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="sop-drawer-actions">
            <Button variant="secondary" onClick={handlePrev} disabled={currentIdx === 0}>
              {t('chat.sop.prev')}
            </Button>
            <Button
              variant={completedSteps.includes(currentStep.step_number) ? 'tertiary' : 'primary'}
              onClick={handleToggleStep}
            >
              {completedSteps.includes(currentStep.step_number)
                ? t('chat.sop.unmark_done')
                : t('chat.sop.mark_done')}
            </Button>
            <Button
              variant="secondary"
              onClick={handleNext}
              disabled={currentIdx >= totalSteps - 1}
            >
              {t('chat.sop.next')}
            </Button>
          </div>
        </div>
      )}
    </Drawer>
  );
}
