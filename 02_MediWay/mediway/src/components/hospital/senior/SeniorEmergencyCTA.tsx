import { useState } from 'react';
import { Siren } from 'lucide-react';
import { EmergencyConfirmDialog } from '@/components/hospital/widgets/EmergencyCtaWidget';
import { useSeniorCopy } from '@/hooks/useSeniorCopy';

/**
 * 고령자 모드 전용 풀폭 응급 버튼.
 *
 * 시안 PlusUltra SaaS 2/5: 하단 큰 빨간 EMERGENCY HELP CTA.
 * 119 오발신 방지를 위해 EmergencyConfirmDialog를 그대로 재사용 (모달 안에
 * 원내 안내·119·취소 3 액션, 초기 focus 취소).
 */
export function SeniorEmergencyCTA() {
  const [open, setOpen] = useState(false);
  const copy = useSeniorCopy();

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="emergency-cta mt-6 flex w-full items-center justify-center gap-3 rounded-2xl border-2 border-error bg-error px-6 py-5 text-lg font-semibold text-on-primary"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-on-primary/15">
          <Siren className="h-6 w-6" aria-hidden />
        </span>
        <span className="flex flex-col items-start">
          <span>{copy('senior.emergency.title', '응급 도움 받기')}</span>
          <span className="text-sm font-normal opacity-90">
            {copy(
              'senior.emergency.sub',
              '버튼을 누르면 응급실 안내나 119 전화로 연결돼요',
            )}
          </span>
        </span>
      </button>
      {open && <EmergencyConfirmDialog onClose={() => setOpen(false)} />}
    </>
  );
}
