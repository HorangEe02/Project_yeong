// Day 5++.2 — NoteBox: 중앙 상단 3-Tab (SOP / COLLAB / QUICK) + 접기/펼치기 토글.
// 좌측 SOP 컬럼 제거 후 SOP/Scenario/QuickPrompts 콘텐츠를 NoteBox 내부 탭에 통합.
// 펼침 60vh, 접힘 헤더만 — 채팅이 그 아래로 풀화면 사용 가능.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import { useUIStore } from '@store/ui';
import { useSopStore } from '@store/sop';
import { fetchSopList, type SopSummary } from '@api/sop';
import { SOPProgressBar } from '@components/sop/SOPProgressBar';
import { ScenarioPanel } from '@components/sop/ScenarioPanel';
import { QuickPrompts } from '@components/chat/QuickPrompts';

type NoteBoxTab = 'sop' | 'collab' | 'quick';

interface Props {
  isStreaming: boolean;
  onSend: (text: string) => void;
}

/**
 * SOPContent — SOP 8 카드 그리드 (SOPSidePanel SOP 탭의 콘텐츠를 추출).
 * NoteBox 내부 SOP 탭에서만 사용 — 외부 탭 헤더 중복 방지.
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
  if (items.length === 0)
    return <div className="sop-side-empty">{t('chat.sop.empty')}</div>;

  return (
    <ul className="sop-side-list note-box__sop-list">
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

export function NoteBox({ isStreaming, onSend }: Props) {
  const { t } = useTranslation();
  const expanded = useUIStore((s) => s.noteBoxExpanded);
  const toggle = useUIStore((s) => s.toggleNoteBox);
  // 디폴트 탭 = QUICK — 시연 동선 (chip 클릭 → 즉시 전송)
  const [tab, setTab] = useState<NoteBoxTab>('quick');

  const sopBadge = 8;
  const collabBadge = 5;
  const quickBadge = 7;

  return (
    <section
      className={clsx('note-box', { 'note-box--collapsed': !expanded })}
      aria-label={t('chat.notebox.aria_label')}
    >
      <header className="note-box__header">
        <div role="tablist" className="note-box__tabs">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'sop'}
            className={clsx('note-box__tab', { 'note-box__tab--active': tab === 'sop' })}
            onClick={() => setTab('sop')}
          >
            <span className="note-box__tab-en">{t('chat.notebox.tab.sop')}</span>
            <span className="note-box__tab-badge">{sopBadge}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'collab'}
            className={clsx('note-box__tab', { 'note-box__tab--active': tab === 'collab' })}
            onClick={() => setTab('collab')}
          >
            <span className="note-box__tab-en">{t('chat.notebox.tab.collab')}</span>
            <span className="note-box__tab-badge">{collabBadge}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'quick'}
            className={clsx('note-box__tab', { 'note-box__tab--active': tab === 'quick' })}
            onClick={() => setTab('quick')}
          >
            <span className="note-box__tab-en">{t('chat.notebox.tab.quick')}</span>
            <span className="note-box__tab-badge">{quickBadge}</span>
          </button>
        </div>
        <button
          type="button"
          className="note-box__toggle"
          onClick={toggle}
          aria-expanded={expanded}
          aria-label={
            expanded
              ? t('chat.notebox.toggle.collapse')
              : t('chat.notebox.toggle.expand')
          }
          title={
            expanded
              ? t('chat.notebox.toggle.collapse')
              : t('chat.notebox.toggle.expand')
          }
        >
          <span aria-hidden>{expanded ? '▲' : '▼'}</span>
        </button>
      </header>

      {expanded && (
        <div className="note-box__body" role="tabpanel">
          {tab === 'sop' && <SOPContent />}
          {tab === 'collab' && <ScenarioPanel onPickScenario={onSend} />}
          {tab === 'quick' && (
            <QuickPrompts isStreaming={isStreaming} onSend={onSend} />
          )}
        </div>
      )}
    </section>
  );
}
