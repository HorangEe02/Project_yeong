// Day 5 — 협업 시나리오 응답 카드
// 시나리오 매칭 시 메시지 풍선 안에 표시 (LLM 호출 0회 — 본선 시연 차별점).

import { useTranslation } from 'react-i18next';
import { useSopStore } from '@store/sop';
import type { ScenarioCard as ScenarioCardData } from '@api/scenarios';

interface Props {
  card: ScenarioCardData;
}

export function ScenarioCard({ card }: Props) {
  const { t } = useTranslation();
  const openSop = useSopStore((s) => s.openSop);

  return (
    <div className="scenario-card" role="article" aria-label={card.scenario_id}>
      <div className="scenario-card-h">
        <span className="scenario-card-eyebrow">{t('chat.scenarios.eyebrow')}</span>
        <span className="scenario-card-id">{card.scenario_id}</span>
      </div>

      <p className="scenario-situation">{card.situation}</p>

      <dl className="scenario-meta">
        <div>
          <dt>{t('chat.scenarios.requesting_dept')}</dt>
          <dd>{card.requesting_dept}</dd>
        </div>
        <div>
          <dt>{t('chat.scenarios.deadline')}</dt>
          <dd>{card.deadline_info}</dd>
        </div>
      </dl>

      <section className="scenario-section">
        <span className="scenario-section-h">{t('chat.scenarios.my_actions')}</span>
        <ol className="scenario-actions">
          {card.my_actions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ol>
      </section>

      <section className="scenario-section">
        <span className="scenario-section-h">
          {t('chat.scenarios.handoff_to', { to: card.hand_off_to })}
        </span>
        <ul className="scenario-handoff">
          {card.hand_off_items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      </section>

      {card.tips.length > 0 && (
        <section className="scenario-section">
          <span className="scenario-section-h">{t('chat.scenarios.tips')}</span>
          <ul className="scenario-tips">
            {card.tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </section>
      )}

      {card.related_sop_id && (
        <button
          type="button"
          className="scenario-related-sop"
          onClick={() => openSop(card.related_sop_id)}
        >
          {t('chat.scenarios.open_sop', { id: card.related_sop_id })}
        </button>
      )}
    </div>
  );
}
