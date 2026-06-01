// WizardStepper — .lg-wiz-steps 마크업.
// 3-step 계정 생성: 기본정보 / 권한 설정 / 인증 발급.

interface Step {
  ko: string;
  en: string;
}

interface Props {
  steps: Step[];
  current: number;
}

export function WizardStepper({ steps, current }: Props) {
  return (
    <div className="lg-wiz-steps">
      {steps.map((s, i) => (
        <div key={s.ko} style={{ display: 'contents' }}>
          <div className={`lg-wiz-step ${i === current ? 'on' : ''}`}>
            <span>{i + 1}</span>
            <div>
              <b>{s.ko}</b>
              <i>STEP {i + 1} · {s.en}</i>
            </div>
          </div>
          {i < steps.length - 1 && <div className="lg-wiz-line" />}
        </div>
      ))}
    </div>
  );
}
