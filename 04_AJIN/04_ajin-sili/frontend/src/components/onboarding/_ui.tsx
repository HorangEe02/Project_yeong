// 부서별 신입 가이드 카드 공통 UI (JP1~JP3).
// AJIN Design System v2 lg-* 클래스 + 통일된 헤더/리스트 패턴.

import type { ReactNode } from 'react';
import { Sparkles } from 'lucide-react';

export function CardHeader({
  icon, eyebrow, title, subtitle,
}: { icon: ReactNode; eyebrow: string; title: string; subtitle: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
      <div
        style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'color-mix(in oklab, var(--hud-primary) 14%, transparent)',
          color: 'var(--hud-primary)',
          display: 'grid', placeItems: 'center', flexShrink: 0,
        }}
      >{icon}</div>
      <div>
        <div style={{ fontSize: 10, opacity: 0.55, letterSpacing: '0.06em' }}>
          <Sparkles size={10} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          {eyebrow}
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>{title}</div>
        <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 2 }}>{subtitle}</div>
      </div>
    </div>
  );
}

export function StepList({ items }: { items: { title: string; body: string }[] }) {
  return (
    <ol style={{ margin: '14px 0 0', paddingLeft: 0, listStyle: 'none' }}>
      {items.map((it, i) => (
        <li key={i} style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
          <div
            style={{
              minWidth: 24, height: 24, borderRadius: 999,
              background: 'color-mix(in oklab, var(--hud-primary) 18%, transparent)',
              color: 'var(--hud-primary)',
              display: 'grid', placeItems: 'center',
              fontSize: 11, fontWeight: 700,
              flexShrink: 0,
            }}
          >{i + 1}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{it.title}</div>
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 2, lineHeight: 1.5 }}>{it.body}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function FaqList({ items }: { items: { q: string; a: string }[] }) {
  return (
    <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map((it, i) => (
        <details key={i} style={{
          padding: '10px 12px',
          borderRadius: 8,
          border: '1px solid var(--hud-border)',
          background: 'var(--hud-surface-2)',
        }}>
          <summary style={{ fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>{it.q}</summary>
          <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 8, lineHeight: 1.6 }}>{it.a}</div>
        </details>
      ))}
    </div>
  );
}

export function ChipRow({ items }: { items: string[] }) {
  return (
    <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {items.map((t, i) => (
        <span key={i} style={{
          padding: '4px 10px', borderRadius: 999, fontSize: 11,
          border: '1px solid var(--hud-border)', background: 'var(--hud-surface-2)',
          color: 'var(--hud-text-dim)',
        }}>{t}</span>
      ))}
    </div>
  );
}

export function KeyValueGrid({ items }: { items: { k: string; v: string }[] }) {
  return (
    <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '110px 1fr', gap: '8px 14px', fontSize: 12 }}>
      {items.map((it, i) => (
        <Row key={i} k={it.k} v={it.v} />
      ))}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <>
      <span style={{ color: 'var(--hud-text-dim)' }}>{k}</span>
      <span>{v}</span>
    </>
  );
}
