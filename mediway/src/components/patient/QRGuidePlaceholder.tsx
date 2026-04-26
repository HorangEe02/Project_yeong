import { QrCode } from 'lucide-react';

/**
 * GuideTab 의 「QR 안내」 모드 — sessionId 없이 home 진입한 환자에게
 * QR 코드를 받는 방법을 안내한다.
 *
 * 본 컴포넌트는 PatientDashboard 의 qr_display state 와 달리 자가 발급 흐름을
 * 가지지 않음 (별도 sprint). 안내 데스크 → 의료진 스캔 의 단방향 경로만 명시.
 *
 * 라이프사이클:
 *  - mount-all 정책에 따라 hidden 상태에서도 DOM 에 머무름 (모드 전환 시 재마운트 비용 0)
 *  - 외부 의존성 없음 — useHospital / authStore 미사용 (텍스트 only)
 */
export function QRGuidePlaceholder() {
  return (
    <div
      role="region"
      aria-label="QR 안내"
      data-testid="qr-guide-placeholder"
      className="flex flex-col items-center gap-4 rounded-xl bg-surface-container-lowest p-6 text-center shadow-ambient sm:p-8"
    >
      <div className="flex h-24 w-24 items-center justify-center rounded-2xl bg-primary/10">
        <QrCode className="h-12 w-12 text-primary" aria-hidden="true" />
      </div>

      <div className="space-y-1">
        <h3 className="text-base font-semibold text-on-surface">
          QR 코드를 받아 안내를 시작하세요
        </h3>
        <p className="text-sm text-on-surface-variant">
          QR 코드를 의료진에게 보여 주면 동선 안내가 자동으로 시작됩니다.
        </p>
      </div>

      <ol className="w-full max-w-sm space-y-2 text-left text-sm text-on-surface">
        <Step n={1} text="병원 안내 데스크 방문" />
        <Step n={2} text="환자 QR 코드 발급 요청" />
        <Step n={3} text="의료진이 스캔하면 동선 안내 자동 시작" />
      </ol>

      <p className="rounded-lg bg-surface-container px-3 py-2 text-[12px] text-on-surface-variant">
        ※ 이미 QR 코드 화면이 열려 있다면 의료진에게 그대로 보여 주세요.
      </p>
    </div>
  );
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <li className="flex items-start gap-3 rounded-lg bg-surface-container-low p-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-on-primary tabular-nums">
        {n}
      </span>
      <span className="pt-0.5">{text}</span>
    </li>
  );
}
