// v3.5 — react-select 기반 동적 ModelSelect (사용자 친화 호버 카드 + Use case 그룹화).
//
// 기존 (v3.3):
//   native <select> + <option> — 호버 시 native title 만 가능, 스타일 불가.
//   MANUAL_OLLAMA_VALUE 옵션 — 사용자가 model_id 직접 입력 (anti-UX).
//
// 변경 (v3.5):
//   - react-select <Select grouped> — 4 Use case 그룹화 (한국어/다국어/비전/추론).
//   - react-tooltip — 옵션 호버 시 풍부한 카드 (display + summary_ko + use_when_ko).
//   - MANUAL_OLLAMA_VALUE 완전 제거 — ADR-0001 자동 폴백 정신 회복.
//
// 백엔드: GET /api/models/llm-options?feature=... 응답에 summary_ko, use_when_ko, use_case 포함.

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select, { components, type GroupBase, type OptionProps } from 'react-select';
import { Tooltip } from 'react-tooltip';
import 'react-tooltip/dist/react-tooltip.css';

import { apiUrl } from '@api/baseUrl';
import type { ForceProvider } from '@/types/chat';

interface Props {
  value: ForceProvider | null;
  onChange: (next: ForceProvider | null) => void;
  feature?: string;
  disabled?: boolean;
}

type Family = 'qwen' | 'gemma' | 'gemini' | 'exaone' | 'nemotron' | 'other';
type UseCase = 'korean' | 'multilingual' | 'vision' | 'reasoning';

interface BackendOption {
  provider: 'ollama' | 'gemini';
  id: string;
  label: string;
  available: boolean;
  blocked: boolean;
  blocked_reason: string;
  family: Family;
  summary_ko: string;
  use_when_ko: string;
  use_case: UseCase;
}

interface BackendResponse {
  options: BackendOption[];
  default_provider: string | null;
  default_id: string | null;
  feature: string;
}

// react-select 옵션 형식 — value(serialize) + 메타정보 carry.
interface SelectOption {
  value: string;
  label: string;
  family: Family;
  use_case: UseCase | 'auto';
  summary_ko: string;
  use_when_ko: string;
  blocked: boolean;
  blocked_reason: string;
}

// auto 옵션 sentinel.
const AUTO_VALUE = 'auto';

// family 별 색깔 (호버 카드 좌측 4px bar)
const FAMILY_COLOR: Record<Family, string> = {
  qwen: '#3b82f6',     // 파랑
  exaone: '#ef4444',   // 빨강
  gemma: '#22c55e',    // 초록
  nemotron: '#eab308', // 노랑
  gemini: '#a855f7',   // 보라 (★)
  other: '#6b7280',    // 회색
};

// v3.8 — 기본 이모지(🇰🇷·🌐·🖼️·🧠·🅀·🅖·🅔·🅝·⭐) 제거.
// AJIN 디자인 시스템에 맞춰: 옵션 좌측 4px family-color dot + 그룹 헤더는 텍스트만.

// Use case 그룹 헤더 (4 그룹) — 이모지 prefix 제거, 한·영 병기.
const USE_CASE_GROUPS: { key: UseCase; label: string }[] = [
  { key: 'korean',       label: '한국어 우수 — 격식·사내 보고서' },
  { key: 'multilingual', label: '다국어 — 일반 업무·빠른 응답' },
  { key: 'vision',       label: '비전 — 이미지·도면·차트' },
  { key: 'reasoning',    label: '추론 — 법규·복잡 분석' },
];

function serialize(v: ForceProvider | null): string {
  return v === null ? AUTO_VALUE : `${v.provider}:${v.model}`;
}

function deserialize(s: string): ForceProvider | null {
  if (s === AUTO_VALUE) return null;
  const idx = s.indexOf(':');
  if (idx <= 0) return null;
  const provider = s.slice(0, idx);
  const model = s.slice(idx + 1);
  if (provider === 'ollama' || provider === 'gemini') {
    return { provider, model };
  }
  return null;
}

// react-tooltip data-* 속성 생성 (HTML escape 처리).
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function tooltipHtml(opt: SelectOption): string {
  if (opt.value === AUTO_VALUE) {
    return '<div style="max-width:300px"><strong>자동 (라우터 결정)</strong><br/><span style="opacity:0.85">백엔드 LLMRouter 가 현재 컨텍스트에 최적 모델을 자동 선택합니다.</span></div>';
  }
  const color = FAMILY_COLOR[opt.family] || FAMILY_COLOR.other;
  const summary = opt.summary_ko ? escapeHtml(opt.summary_ko) : '메타데이터 없음';
  const useWhen = opt.use_when_ko ? escapeHtml(opt.use_when_ko) : '';
  const blockedNote = opt.blocked && opt.blocked_reason
    ? `<br/><em style="color:#fca5a5">⚠ ${escapeHtml(opt.blocked_reason)}</em>`
    : '';
  return `
    <div style="max-width:300px; border-left:4px solid ${color}; padding-left:8px">
      <strong>${escapeHtml(opt.label)}</strong>
      <p style="margin:6px 0 4px 0; opacity:0.92">${summary}</p>
      ${useWhen ? `<em style="opacity:0.75; font-size:0.92em">💡 ${useWhen}</em>` : ''}
      ${blockedNote}
    </div>
  `.trim();
}

// 그룹화: 4 use_case 별 옵션 분리. 빈 그룹은 결과에서 제외.
function groupOptions(opts: BackendOption[]): GroupBase<SelectOption>[] {
  const buckets: Record<UseCase, SelectOption[]> = {
    korean: [], multilingual: [], vision: [], reasoning: [],
  };

  for (const o of opts) {
    const blocked = !o.available || o.blocked;
    const sel: SelectOption = {
      value: `${o.provider}:${o.id}`,
      label: `${o.label}${blocked ? '  (사용 불가)' : ''}`,
      family: o.family,
      use_case: o.use_case,
      summary_ko: o.summary_ko,
      use_when_ko: o.use_when_ko,
      blocked,
      blocked_reason: o.blocked_reason,
    };
    if (buckets[o.use_case]) {
      buckets[o.use_case].push(sel);
    } else {
      buckets.multilingual.push(sel);
    }
  }

  return USE_CASE_GROUPS
    .map((g) => ({ label: g.label, options: buckets[g.key] }))
    .filter((g) => g.options.length > 0);
}

// react-select 커스텀 Option 컴포넌트 — tooltip data-* 부착 + family color dot.
// v3.8 — 이모지(🅀🅖🅔🅝⭐) 대신 좌측 8px family-color dot 으로 family 시각 구분.
function CustomOption(props: OptionProps<SelectOption, false, GroupBase<SelectOption>>) {
  const html = tooltipHtml(props.data);
  const isAuto = props.data.value === AUTO_VALUE;
  const dotColor = FAMILY_COLOR[props.data.family] || FAMILY_COLOR.other;
  return (
    <div
      data-tooltip-id="model-select-tooltip"
      data-tooltip-html={html}
      data-tooltip-place="right"
    >
      <components.Option {...props}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
          {!isAuto && (
            <span
              aria-hidden
              style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: dotColor,
                flexShrink: 0,
                boxShadow: '0 0 0 1px rgba(0,0,0,0.08) inset',
              }}
            />
          )}
          <span>{props.children}</span>
        </span>
      </components.Option>
    </div>
  );
}

export function ModelSelect({ value, onChange, feature = 'onboarding', disabled }: Props) {
  const { t } = useTranslation();
  const [opts, setOpts] = useState<BackendOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          apiUrl(`/models/llm-options?feature=${encodeURIComponent(feature)}`),
          { headers: { Accept: 'application/json' } },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: BackendResponse = await res.json();
        if (!cancelled) {
          setOpts(data.options ?? []);
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [feature]);

  // auto 옵션 (그룹 외 최상단 단독)
  const autoOption: SelectOption = useMemo(
    () => ({
      value: AUTO_VALUE,
      label: loading
        ? '로딩…'
        : t('chat.model.auto', '자동 (라우터 결정)'),
      family: 'other',
      use_case: 'auto',
      summary_ko: '',
      use_when_ko: '',
      blocked: false,
      blocked_reason: '',
    }),
    [loading, t],
  );

  // 4 그룹 + auto 단독 옵션 + 그룹화 옵션 결합
  const groupedOptions = useMemo<GroupBase<SelectOption>[]>(
    () => [
      { label: '', options: [autoOption] },
      ...groupOptions(opts),
    ],
    [autoOption, opts],
  );

  // 현재 선택값 찾기
  const currentSerialized = serialize(value);
  const selectedOption = useMemo<SelectOption | null>(() => {
    for (const g of groupedOptions) {
      for (const o of g.options) {
        if (o.value === currentSerialized) return o;
      }
    }
    return autoOption;
  }, [currentSerialized, groupedOptions, autoOption]);

  return (
    <div className="lg-field" style={{ minWidth: 240 }}>
      <label htmlFor="lg-model-select">{t('chat.model.label', 'AI 모델')}</label>
      <Select<SelectOption, false, GroupBase<SelectOption>>
        inputId="lg-model-select"
        value={selectedOption}
        onChange={(opt) => {
          if (!opt) {
            onChange(null);
            return;
          }
          onChange(deserialize(opt.value));
        }}
        options={groupedOptions}
        isDisabled={disabled || loading}
        isOptionDisabled={(opt) => opt.blocked}
        components={{ Option: CustomOption }}
        placeholder={loading ? '로딩…' : t('chat.model.label', 'AI 모델')}
        aria-label={t('chat.model.label', 'AI 모델')}
        classNamePrefix="ajin-model-select"
        // v3.7 — 부서 드롭다운(lg-field select)과 시각 통일.
        // lg-theme.css:1029 의 padding/border-radius/border/background/focus 와 1:1 매칭.
        // 다크모드 색은 var(--hud-text)=#E8E1D5 (밝은 베이지), 라이트모드는 #2C241A (검정에 가까운 갈색).
        // selected/focused option 은 AJIN primary (노란색) 으로 강조.
        styles={{
          control: (base, state) => ({
            ...base,
            minHeight: 44,
            backgroundColor: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
            borderRadius: 12,
            borderColor: state.isFocused
              ? 'var(--hud-primary)'
              : 'color-mix(in oklab, var(--hud-text) 12%, transparent)',
            color: 'var(--hud-text)',
            boxShadow: state.isFocused
              ? '0 0 0 3px color-mix(in oklab, var(--hud-primary) 18%, transparent)'
              : 'none',
            transition: 'all 0.15s',
            fontFamily: 'var(--hud-font-sans)',
            fontSize: 14,
            '&:hover': {
              borderColor: 'color-mix(in oklab, var(--hud-text) 24%, transparent)',
            },
          }),
          valueContainer: (base) => ({
            ...base,
            padding: '4px 14px',
          }),
          menu: (base) => ({
            ...base,
            backgroundColor: 'var(--hud-surface-3, var(--hud-surface-2))',
            border: '1px solid var(--hud-border, rgba(120,120,120,0.3))',
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            zIndex: 50,
          }),
          menuList: (base) => ({
            ...base,
            backgroundColor: 'var(--hud-surface-3, var(--hud-surface-2))',
            paddingTop: 4,
            paddingBottom: 4,
          }),
          singleValue: (base) => ({
            ...base,
            color: 'var(--hud-text)',
          }),
          input: (base) => ({
            ...base,
            color: 'var(--hud-text)',
          }),
          placeholder: (base) => ({
            ...base,
            color: 'var(--hud-text-muted, #8A8276)',
          }),
          groupHeading: (base) => ({
            ...base,
            fontSize: '0.78rem',
            fontWeight: 700,
            color: 'var(--hud-text-dim, var(--hud-text))',
            backgroundColor: 'var(--hud-surface-2)',
            textTransform: 'none',
            paddingTop: 8,
            paddingBottom: 4,
          }),
          option: (base, state) => ({
            ...base,
            cursor: state.isDisabled ? 'not-allowed' : 'pointer',
            opacity: state.isDisabled ? 0.55 : 1,
            // 다크모드에서 글씨 안 보이던 핵심 fix — 텍스트 색 명시.
            color: state.isSelected
              ? '#1a1a1a'
              : state.isFocused
                ? 'var(--ajin-yellow, #FBBF24)'
                : 'var(--hud-text)',
            backgroundColor: state.isSelected
              ? 'var(--ajin-yellow, #FBBF24)'
              : state.isFocused
                ? 'rgba(251, 191, 36, 0.12)'
                : 'transparent',
            fontWeight: state.isSelected ? 600 : 400,
          }),
          dropdownIndicator: (base, state) => ({
            ...base,
            color: state.isFocused ? 'var(--ajin-yellow, #FBBF24)' : 'var(--hud-text-muted, #8A8276)',
            '&:hover': { color: 'var(--ajin-yellow, #FBBF24)' },
          }),
          indicatorSeparator: (base) => ({
            ...base,
            backgroundColor: 'var(--hud-border, rgba(120,120,120,0.3))',
          }),
          noOptionsMessage: (base) => ({
            ...base,
            color: 'var(--hud-text-muted, #8A8276)',
          }),
        }}
        noOptionsMessage={() =>
          err ? `옵션 로딩 실패: ${err} — 자동 모드로 동작` : '사용 가능한 모델 없음'
        }
      />
      <Tooltip
        id="model-select-tooltip"
        style={{
          zIndex: 9999,
          backgroundColor: 'rgba(17, 24, 39, 0.96)',
          color: '#fff',
          borderRadius: 8,
          padding: '10px 12px',
          maxWidth: 320,
          fontSize: '0.88rem',
          lineHeight: 1.45,
          transition: 'opacity 200ms',
        }}
        opacity={1}
      />
    </div>
  );
}
