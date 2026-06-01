// v4.7 C-4 — 10 배지 grid 모달.
// 획득 = 컬러, 미획득 = 흑백 + 잠금 아이콘. 클릭 시 조건 popover.

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Award, Lock, X } from 'lucide-react';
import type { BadgesMeResponse, BadgeDefinition } from '@api/gamification';

interface Props {
  data: BadgesMeResponse;
  onClose: () => void;
}

const TIER_COLORS: Record<string, string> = {
  bronze: '#cd7f32',
  silver: '#c0c0c0',
  gold: '#ffd700',
  platinum: '#e5e4e2',
};

export function BadgeModal({ data, onClose }: Props) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<BadgeDefinition | null>(null);

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.65)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(560px, 100%)',
          maxHeight: '85vh',
          overflow: 'auto',
          background: 'var(--hud-card, #1a1a1a)',
          border: '1px solid var(--hud-border, #2a2a2a)',
          borderRadius: 8,
          padding: 20,
          color: 'var(--hud-text, #e5e7eb)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ fontSize: 16, margin: 0 }}>{t('gamification.modal.title')}</h2>
            <p style={{ fontSize: 11, color: 'var(--hud-text-dim, #9ca3af)', margin: '4px 0 0' }}>
              {t('gamification.modal.subtitle')}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('gamification.modal.close')}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--hud-text-dim, #9ca3af)',
              cursor: 'pointer',
              padding: 4,
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div
          style={{
            marginTop: 16,
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 10,
          }}
        >
          {data.definitions.map((d) => {
            const color = TIER_COLORS[d.tier] ?? '#888';
            return (
              <button
                type="button"
                key={d.badge_id}
                onClick={() => setSelected(d)}
                style={{
                  position: 'relative',
                  aspectRatio: '1',
                  padding: 8,
                  borderRadius: 8,
                  border: `1px solid ${d.earned ? color : 'var(--hud-border, #2a2a2a)'}`,
                  background: d.earned
                    ? `linear-gradient(135deg, ${color}33, transparent)`
                    : 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  filter: d.earned ? 'none' : 'grayscale(1) opacity(0.55)',
                  color: 'var(--hud-text, #e5e7eb)',
                  fontFamily: 'inherit',
                }}
                title={t(`gamification.badges.${d.badge_id}.name`)}
              >
                {d.earned ? <Award size={22} color={color} /> : <Lock size={18} />}
                <span style={{ fontSize: 10, textAlign: 'center', lineHeight: 1.2 }}>
                  {t(`gamification.badges.${d.badge_id}.name`)}
                </span>
              </button>
            );
          })}
        </div>

        {selected && (
          <div
            style={{
              marginTop: 16,
              padding: 12,
              borderRadius: 6,
              background: 'var(--hud-bg-soft, rgba(255,255,255,0.04))',
              fontSize: 12,
            }}
          >
            <strong>{t(`gamification.badges.${selected.badge_id}.name`)}</strong>
            <div style={{ marginTop: 4, color: 'var(--hud-text-dim, #9ca3af)' }}>
              {t(`gamification.badges.${selected.badge_id}.description`)}
            </div>
            <div style={{ marginTop: 6, fontSize: 11 }}>
              <em>{t('gamification.modal.condition')}: </em>
              {t(`gamification.badges.${selected.badge_id}.condition`)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
