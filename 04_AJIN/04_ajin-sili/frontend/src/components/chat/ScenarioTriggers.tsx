// Day 5 — 협업 시나리오 5종 트리거 chip (chat 빈 상태)
// 클릭 시 query 텍스트로 sendMessage 호출 — 시나리오 매칭으로 LLM 호출 0회 즉시 응답.

import { useTranslation } from 'react-i18next';

const SCENARIO_KEYS = [
  'chat.scenarios.triggers.0', // 8D
  'chat.scenarios.triggers.1', // ECN
  'chat.scenarios.triggers.2', // SPC
  'chat.scenarios.triggers.3', // PPAP
  'chat.scenarios.triggers.4', // 안전 점검
];

interface Props {
  onPick: (text: string) => void;
}

export function ScenarioTriggers({ onPick }: Props) {
  const { t } = useTranslation();
  return (
    <div className="scenario-triggers" aria-label={t('chat.scenarios.triggers_title')}>
      <span className="scenario-triggers-eyebrow">
        {t('chat.scenarios.triggers_title')}
      </span>
      <div className="scenario-triggers-row">
        {SCENARIO_KEYS.map((k) => {
          const text = t(k);
          return (
            <button
              key={k}
              type="button"
              className="scenario-trigger-chip"
              onClick={() => onPick(text)}
            >
              {text}
            </button>
          );
        })}
      </div>
    </div>
  );
}
