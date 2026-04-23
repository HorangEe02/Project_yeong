import { useEffect, useState } from 'react';
import { Phone, Siren } from 'lucide-react';

/**
 * 응급실 CTA 위젯 — v2 홈 위젯 #3 (상시 고정).
 *
 * v2 §Phase 2: P4의 F10 응급 버튼을 P2 홈 위젯으로 앞당김.
 *
 * 안전장치:
 * - 1회 탭 → 확인 모달 (119 오발신 방지)
 * - 모달에서 "응급실 위치 안내"와 "119 전화" 두 옵션 제공
 */
export function EmergencyCtaWidget() {
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <>
      <article
        className="rounded-xl border-2 border-error bg-error-container p-4"
        aria-labelledby="emergency-cta-title"
      >
        <header className="mb-2 flex items-center gap-2">
          <Siren className="h-5 w-5 text-error" aria-hidden="true" />
          <h3
            id="emergency-cta-title"
            className="text-base font-semibold text-error"
          >
            응급실 바로가기
          </h3>
        </header>
        <p className="mb-3 text-sm text-on-surface">
          응급 상황에서 바로 응급실로 안내하거나 119에 전화할 수 있습니다.
        </p>
        <button
          type="button"
          onClick={() => setConfirmOpen(true)}
          className="w-full rounded-lg bg-error px-4 py-3 text-sm font-semibold text-on-primary hover:bg-error/90 focus:outline-none focus:ring-2 focus:ring-error"
        >
          응급 도움 받기
        </button>
      </article>

      {confirmOpen && (
        <EmergencyConfirmDialog onClose={() => setConfirmOpen(false)} />
      )}
    </>
  );
}

export function EmergencyConfirmDialog({ onClose }: { onClose: () => void }) {
  // P4 C5 polish:
  //  - Escape 키로 닫기 (키보드 네비 사용자)
  //  - body scroll lock (모달 뒤 배경 고정)
  //  - 초기 focus를 "취소" 버튼에 (Enter 실수로 119 발신 방지)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="emergency-dialog-title"
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-sm rounded-xl bg-surface-container-lowest p-5 shadow-ambient-lg">
        <h4
          id="emergency-dialog-title"
          className="mb-3 text-lg font-semibold"
        >
          어떻게 도와드릴까요?
        </h4>
        <p className="mb-4 text-sm text-on-surface-variant">
          원내 응급실까지 길을 안내하거나 119에 전화를 걸 수 있습니다.
        </p>
        <div className="flex flex-col gap-2">
          <a
            href="?tab=guide&target=emergency"
            className="rounded-lg bg-primary px-4 py-3 text-center text-sm font-medium text-on-primary"
            onClick={onClose}
          >
            원내 응급실 길 안내
          </a>
          <a
            href="tel:119"
            className="flex items-center justify-center gap-2 rounded-lg bg-error px-4 py-3 text-sm font-semibold text-on-primary"
            onClick={onClose}
          >
            <Phone className="h-4 w-4" aria-hidden="true" />
            119 전화
          </a>
          <button
            type="button"
            onClick={onClose}
            // 초기 focus — Enter 실수로 119 발신 방지 (취소가 디폴트)
            autoFocus
            className="rounded-lg border border-outline-variant px-4 py-3 text-sm"
          >
            취소
          </button>
        </div>
      </div>
    </div>
  );
}
