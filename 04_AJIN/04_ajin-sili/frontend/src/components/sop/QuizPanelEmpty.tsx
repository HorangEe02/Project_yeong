// Day 5++ — 퀴즈 탭 placeholder (Day 13 본격 구현 — DAY5_PLUS_HUD_PLAN Section 5-4).

import { useTranslation } from 'react-i18next';

export function QuizPanelEmpty() {
  const { t } = useTranslation();
  return (
    <div className="sop-side-quiz-empty" role="status">
      <span className="label-en">QUIZ · AUTO</span>
      <div>{t('chat.tabs.quiz_empty')}</div>
    </div>
  );
}
