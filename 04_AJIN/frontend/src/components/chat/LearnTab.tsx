// Day 5++.3 — LEARN 탭 (메인 2-Tab 의 두 번째 탭).
// SOP / 협업 / 퀴즈 3-Sub-Tab — 학습 콘텐츠 풀 영역.
// 시연 동선: SOP/협업 카드 클릭 → onSwitchToChat() + onSend(trigger) → CHAT 탭 자동 전환 + 시나리오 매처 자동 전송.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import { fetchSopList, type SopSummary } from '@api/sop';
import { useSopStore } from '@store/sop';
import { SOPProgressBar } from '@components/sop/SOPProgressBar';
import { ScenarioPanel } from '@components/sop/ScenarioPanel';
import { QuizPanelEmpty } from '@components/sop/QuizPanelEmpty';

type SubTab = 'sop' | 'collab' | 'quiz';

interface Props {
  /** CHAT 탭으로 전환 (시나리오/SOP 카드 클릭 시 호출). */
  onSwitchToChat: () => void;
  /** 시나리오 카드 클릭 시 자동 전송. */
  onSend: (text: string) => void;
}

/**
 * SOPContent — SOP 8 카드 그리드 (NoteBox/SOPSidePanel 의 SOP 콘텐츠를 LearnTab 안에서 재사용).
 * SOP 카드 클릭 → SOPStepDrawer 자동 오픈 (SopStore.openSop). CHAT 자동 전환은 협업 시나리오에서만.
 */
function SOPContent() {
  const { t } = useTranslation();
  const [items, setItems] = useState<SopSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const progress = useSopStore((s) => s.progress);
  const openSop = useSopStore((s) => s.openSop);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchSopList()
      .then((res) => {
        if (!mounted) return;
        setItems(res.items);
        setError(null);
      })
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) return <div className="sop-side-empty">{t('common.loading')}</div>;
  if (error) return <div className="sop-side-empty error">{error}</div>;
  if (items.length === 0) return <div className="sop-side-empty">{t('chat.sop.empty')}</div>;

  return (
    <ul className="sop-side-list learn-tab__sop-list">
      {items.map((it) => {
        const prog = progress[it.sop_id];
        const completed = prog?.completedSteps.length ?? 0;
        return (
          <li key={it.sop_id}>
            <button
              type="button"
              className="sop-side-item"
              onClick={() => openSop(it.sop_id)}
            >
              <div className="sop-side-item-h">
                <span className="sop-side-id">{it.sop_id}</span>
                <span className="sop-side-cat" data-cat={it.category}>
                  {it.category}
                </span>
              </div>
              <span className="sop-side-name">{it.title}</span>
              <span className="sop-side-dept">{it.department}</span>
              <SOPProgressBar total={it.steps_count} completed={completed} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function LearnTab({ onSwitchToChat, onSend }: Props) {
  const { t } = useTranslation();
  const [sub, setSub] = useState<SubTab>('sop');

  // 협업 시나리오 카드 클릭 → CHAT 탭 자동 전환 + 시나리오 매처 자동 전송.
  const handleScenarioPick = (text: string) => {
    onSwitchToChat();
    onSend(text);
  };

  return (
    <div className="learn-tab">
      <nav role="tablist" className="learn-tab__sub-nav" aria-label={t('chat.pageTab.learn')}>
        <button
          type="button"
          role="tab"
          aria-selected={sub === 'sop'}
          className={clsx('learn-tab__sub-btn', { 'learn-tab__sub-btn--active': sub === 'sop' })}
          onClick={() => setSub('sop')}
        >
          <span>{t('chat.learn.sub.sop')}</span>
          <span className="learn-tab__sub-badge">8</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={sub === 'collab'}
          className={clsx('learn-tab__sub-btn', { 'learn-tab__sub-btn--active': sub === 'collab' })}
          onClick={() => setSub('collab')}
        >
          <span>{t('chat.learn.sub.collab')}</span>
          <span className="learn-tab__sub-badge">5</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={sub === 'quiz'}
          className={clsx('learn-tab__sub-btn', { 'learn-tab__sub-btn--active': sub === 'quiz' })}
          onClick={() => setSub('quiz')}
        >
          <span>{t('chat.learn.sub.quiz')}</span>
        </button>
      </nav>
      <div className="learn-tab__body" role="tabpanel">
        {sub === 'sop' && <SOPContent />}
        {sub === 'collab' && <ScenarioPanel onPickScenario={handleScenarioPick} />}
        {sub === 'quiz' && <QuizPanelEmpty />}
      </div>
    </div>
  );
}
