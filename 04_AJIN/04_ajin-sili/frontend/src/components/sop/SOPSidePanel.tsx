// Day 5 → Day 5++ — SOP 사이드 패널 3-탭 갱신 (DAY5_PLUS_HUD_PLAN Section 5).
// SOP 8 / 협업 5 / 퀴즈 — 좌측 컬럼 상단 50% 고정.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, type TabItem } from '@components/ui/Tabs';
import { fetchSopList, type SopSummary } from '@api/sop';
import { useSopStore } from '@store/sop';
import { SOPProgressBar } from './SOPProgressBar';
import { ScenarioPanel } from './ScenarioPanel';
import { QuizPanelEmpty } from './QuizPanelEmpty';

type TabId = 'sop' | 'collab' | 'quiz';

interface Props {
  className?: string;
  onPickScenario?: (text: string) => void;
}

export function SOPSidePanel({ className, onPickScenario }: Props) {
  const { t } = useTranslation();
  const [items, setItems] = useState<SopSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('sop');
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

  const tabs: TabItem[] = [
    { id: 'sop', labelEn: 'SOP', labelKo: t('chat.tabs.sop', { n: items.length || 8 }), badge: items.length || undefined },
    { id: 'collab', labelEn: 'COLLAB', labelKo: t('chat.tabs.collab', { n: 5 }), badge: 5 },
    { id: 'quiz', labelEn: 'QUIZ', labelKo: t('chat.tabs.quiz') },
  ];

  return (
    <aside
      className={`sop-side-panel sop-side-panel--tabs ${className ?? ''}`}
      aria-label={t('chat.sop.title')}
    >
      <Tabs items={tabs} active={tab} onChange={(id) => setTab(id as TabId)} variant="sub" />

      <div className="sop-side-body">
        {tab === 'sop' && (
          <>
            {loading && <div className="sop-side-empty">{t('common.loading')}</div>}
            {error && <div className="sop-side-empty error">{error}</div>}

            {!loading && !error && items.length === 0 && (
              <div className="sop-side-empty">{t('chat.sop.empty')}</div>
            )}

            {!loading && !error && items.length > 0 && (
              <ul className="sop-side-list">
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
            )}
          </>
        )}

        {tab === 'collab' && <ScenarioPanel onPickScenario={onPickScenario} />}
        {tab === 'quiz' && <QuizPanelEmpty />}
      </div>
    </aside>
  );
}
