// v4.7 C-4 — 좌측 사이드바 하단 배지 카드.
// "내 배지 N개" + 가장 가까운 미획득 1개 progress (placeholder) + 부서 리더보드 본인 순위.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Award } from 'lucide-react';
import { fetchMyBadges, type BadgesMeResponse } from '@api/gamification';
import { BadgeModal } from './BadgeModal';

export function BadgeSidebar() {
  const { t } = useTranslation();
  const [data, setData] = useState<BadgesMeResponse | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchMyBadges()
      .then((d) => alive && setData(d))
      .catch(() => alive && setData({ earned: [], definitions: [], rank: null }));
    return () => {
      alive = false;
    };
  }, []);

  if (!data) return null;
  const earnedCount = data.earned.length;
  const totalCount = data.definitions.length;
  const rank = data.rank;

  return (
    <>
      <div
        className="badge-sidebar"
        style={{
          padding: 12,
          border: '1px solid var(--hud-border, #2a2a2a)',
          borderRadius: 8,
          background: 'var(--hud-card, rgba(255,255,255,0.02))',
          margin: '8px 0',
          fontSize: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <Award size={14} strokeWidth={2.5} color="var(--hud-primary, #3b82f6)" />
          <strong style={{ fontSize: 12, letterSpacing: 0.5 }}>{t('gamification.sidebar.title')}</strong>
        </div>
        <div style={{ color: 'var(--hud-text-dim, #9ca3af)' }}>
          {t('gamification.sidebar.count', { n: earnedCount })} / {totalCount}
        </div>
        {/* progress bar — N / total */}
        <div
          style={{
            height: 4,
            background: 'var(--hud-border, #2a2a2a)',
            borderRadius: 2,
            marginTop: 6,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: totalCount > 0 ? `${(earnedCount / totalCount) * 100}%` : '0%',
              background: 'var(--hud-primary, #3b82f6)',
              transition: 'width 0.3s ease',
            }}
          />
        </div>
        {rank ? (
          <div style={{ marginTop: 8, color: 'var(--hud-text-dim, #9ca3af)' }}>
            <div>{t('gamification.sidebar.leaderboard')}</div>
            <div>
              {t('gamification.sidebar.rank', { rank: rank.rank, total: rank.total })} ·{' '}
              {t('gamification.sidebar.percentile', { p: rank.percentile })}
            </div>
          </div>
        ) : (
          <div style={{ marginTop: 8, color: 'var(--hud-text-dim, #9ca3af)', fontSize: 11 }}>
            {t('gamification.sidebar.too_small')}
          </div>
        )}
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{
            marginTop: 8,
            width: '100%',
            padding: '4px 8px',
            background: 'transparent',
            border: '1px solid var(--hud-border, #2a2a2a)',
            borderRadius: 4,
            color: 'var(--hud-text-dim, #9ca3af)',
            cursor: 'pointer',
            fontSize: 11,
          }}
        >
          {t('gamification.sidebar.open')}
        </button>
      </div>
      {open && <BadgeModal data={data} onClose={() => setOpen(false)} />}
    </>
  );
}
