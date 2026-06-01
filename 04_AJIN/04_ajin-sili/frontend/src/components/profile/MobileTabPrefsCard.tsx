// 모바일 BottomTab 사용자 커스터마이즈 카드 (v4.5).
//
// /profile 페이지의 'MOBILE · 모바일 빠른 탭' 탭 진입 시 노출.
// 슬롯 1·2·3 (DRAFT/CHAT/HOME) 잠금. 슬롯 4·5 만 변경 가능.
// 자동 추천(페르소나) vs 직접 선택 토글.

import { useMemo } from 'react';
import { RotateCcw } from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { useMobileTabPrefs } from '@hooks/useMobileTabPrefs';
import { detectPersona } from '@components/dashboard/personas';
import { PERSONA_LABELS } from '@components/dashboard/personas';
import {
  DEFAULT_CUSTOM_SLOTS,
  TAB_META,
  getCustomizableSlugs,
  resolveMobileTabs,
} from '@components/shell/mobileTabs';

export function MobileTabPrefsCard() {
  const user = useAuthStore((s) => s.user);
  const prefs = useMobileTabPrefs();

  const persona = useMemo(() => detectPersona(user), [user]);
  const personaLabel = PERSONA_LABELS[persona];
  const availableSlugs = useMemo(() => getCustomizableSlugs(user), [user]);

  const preview = useMemo(
    () => resolveMobileTabs(user, { override: prefs.override, customSlots: prefs.customSlots }),
    [user, prefs.override, prefs.customSlots],
  );

  const slot4 = prefs.customSlots[0];
  const slot5 = prefs.customSlots[1];

  const updateSlot = (idx: 0 | 1) => (slug: string) => {
    const next: [string, string] = [...prefs.customSlots] as [string, string];
    next[idx] = slug;
    // 동일 모듈 중복 차단 — 다른 슬롯과 같으면 반대편을 회전
    if (next[0] === next[1]) {
      const others = availableSlugs.filter((s) => s !== slug);
      next[1 - idx] = others[0] ?? DEFAULT_CUSTOM_SLOTS[1 - idx];
    }
    void prefs.save({ customSlots: next });
  };

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">MOBILE · 모바일 빠른 탭</div>
          <h2 className="lg-h2">하단 탭 5개 슬롯</h2>
        </div>
        {prefs.saving && <span className="lg-sub">저장 중…</span>}
      </div>

      <p className="lg-sub" style={{ marginTop: 8, lineHeight: 1.6 }}>
        모바일 화면 하단 탭의 <b>슬롯 4·5</b> 만 변경할 수 있습니다.
        <br />
        슬롯 1·2·3 (<b>문서 · 챗봇 · 대시보드</b>) 은 모든 사용자 공통 고정입니다.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 18 }}>
        <label
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            cursor: 'pointer',
            padding: 12,
            borderRadius: 8,
            border: '1px solid var(--hud-border)',
            background: !prefs.override ? 'var(--aj-gold-soft, color-mix(in oklab, var(--hud-primary) 8%, transparent))' : 'transparent',
          }}
        >
          <input
            type="radio"
            checked={!prefs.override}
            onChange={() => void prefs.save({ override: false })}
            style={{ marginTop: 3 }}
          />
          <div>
            <div style={{ fontWeight: 600 }}>페르소나 자동 추천</div>
            <div className="lg-sub" style={{ marginTop: 2 }}>
              내 페르소나 <b>{personaLabel.ko}</b> ({personaLabel.en}) 에 맞는 모듈 2개 자동 선정
            </div>
          </div>
        </label>

        <label
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            cursor: 'pointer',
            padding: 12,
            borderRadius: 8,
            border: '1px solid var(--hud-border)',
            background: prefs.override ? 'var(--aj-gold-soft, color-mix(in oklab, var(--hud-primary) 8%, transparent))' : 'transparent',
          }}
        >
          <input
            type="radio"
            checked={prefs.override}
            onChange={() => void prefs.save({ override: true })}
            style={{ marginTop: 3 }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>직접 선택</div>
            <div className="lg-sub" style={{ marginTop: 2 }}>
              아래에서 슬롯 4·5 에 표시할 모듈 직접 지정
            </div>

            {prefs.override && (
              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <SlotPicker
                  label="슬롯 4"
                  value={slot4}
                  options={availableSlugs}
                  onChange={updateSlot(0)}
                />
                <SlotPicker
                  label="슬롯 5"
                  value={slot5}
                  options={availableSlugs}
                  onChange={updateSlot(1)}
                />
              </div>
            )}
          </div>
        </label>
      </div>

      {prefs.override && (
        <div style={{ marginTop: 14 }}>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={() => void prefs.resetDefaults()}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <RotateCcw size={14} aria-hidden />
            기본으로 복원
          </button>
        </div>
      )}

      {/* 미리보기 */}
      <div style={{ marginTop: 20 }}>
        <div className="lg-eyebrow" style={{ fontSize: 11, marginBottom: 8 }}>
          PREVIEW · 미리보기
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${Math.min(5, preview.tabs.length + (preview.emptySlots > 0 ? 1 : 0))}, 1fr)`,
            gap: 8,
            padding: 12,
            border: '1px solid var(--hud-border)',
            borderRadius: 12,
            background: 'var(--hud-surface)',
          }}
          aria-label="모바일 하단 탭 미리보기"
        >
          {preview.tabs.map((t, idx) => {
            const Icon = t.icon;
            const fixed = idx < 3;
            return (
              <div
                key={t.slug + idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  padding: '8px 4px',
                  borderRadius: 6,
                  background: fixed ? 'transparent' : 'var(--aj-gold-soft, color-mix(in oklab, var(--hud-primary) 8%, transparent))',
                  fontSize: 11,
                }}
                title={`슬롯 ${idx + 1}${fixed ? ' (고정)' : ' (동적)'}`}
              >
                <Icon size={18} strokeWidth={1.5} aria-hidden />
                <span style={{ fontWeight: 600 }}>{t.labelKo}</span>
                <span style={{ fontSize: 8, letterSpacing: '0.08em', color: 'var(--hud-text-dim)' }}>
                  {fixed ? `슬롯 ${idx + 1} · 고정` : `슬롯 ${idx + 1} · 동적`}
                </span>
              </div>
            );
          })}
          {preview.emptySlots > 0 && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
                padding: '8px 4px',
                fontSize: 11,
                color: 'var(--hud-text-dim)',
                opacity: 0.7,
              }}
              title="RBAC 통과 모듈 부족 — 햄버거 메뉴로 이동"
            >
              <span>⋯</span>
              <span style={{ fontWeight: 600 }}>더보기</span>
              <span style={{ fontSize: 8, letterSpacing: '0.08em' }}>MORE</span>
            </div>
          )}
        </div>
      </div>

      {prefs.error && (
        <p className="lg-sub" style={{ color: 'var(--hud-red)', marginTop: 12 }}>
          저장 실패: {prefs.error}
        </p>
      )}
    </section>
  );
}

function SlotPicker({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (slug: string) => void;
}) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
      <span style={{ minWidth: 64, color: 'var(--hud-text-dim)' }}>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          flex: 1,
          padding: '8px 12px',
          minHeight: 40,
          fontSize: 14,
          border: '1px solid var(--hud-border)',
          borderRadius: 6,
          background: 'var(--hud-surface)',
          color: 'var(--hud-text)',
        }}
      >
        {options.map((slug) => {
          const meta = TAB_META[slug];
          if (!meta) return null;
          return (
            <option key={slug} value={slug}>
              {meta.labelKo} · {meta.labelEn}
            </option>
          );
        })}
      </select>
    </label>
  );
}
