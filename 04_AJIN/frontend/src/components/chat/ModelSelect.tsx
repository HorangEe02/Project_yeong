// v3.3 Feature C — Phase A 동적 ModelSelect.
//
// 백엔드 GET /api/models/llm-options?feature=onboarding 에서 옵션을 동적으로 로딩.
// - 설치된 Ollama 모델만 노출 (qwen3.5/gemma4/exaone3.5 패밀리)
// - GEMINI_API_KEY 없으면 disabled + tooltip
// - 기본값('자동')은 항상 첫 옵션으로 유지 — 백엔드 LLMRouter 폴백 활용
//
// Props
//   value         — 현재 강제 선택값 (null 이면 자동)
//   onChange      — 변경 콜백
//   feature       — 옵션 컨텍스트 (기본 'onboarding')
//   disabled      — 스트리밍 중 잠금 등

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ForceProvider } from '@/types/chat';

interface Props {
  value: ForceProvider | null;
  onChange: (next: ForceProvider | null) => void;
  feature?: string;
  disabled?: boolean;
}

interface BackendOption {
  provider: 'ollama' | 'gemini';
  id: string;
  label: string;
  available: boolean;
  blocked: boolean;
  blocked_reason: string;
  family: 'qwen' | 'gemma' | 'gemini' | 'exaone' | 'other';
}

interface BackendResponse {
  options: BackendOption[];
  default_provider: string | null;
  default_id: string | null;
  feature: string;
}

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

function serialize(v: ForceProvider | null): string {
  return v === null ? 'auto' : `${v.provider}:${v.model}`;
}

function familyMark(family: BackendOption['family']): string {
  switch (family) {
    case 'qwen':   return '[Q]';
    case 'gemma':  return '[G]';
    case 'exaone': return '[E]';
    case 'gemini': return '[★]';
    default:       return '[·]';
  }
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
          `${API_URL}/api/models/llm-options?feature=${encodeURIComponent(feature)}`,
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

  const current = serialize(value);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value;
    if (v === 'auto') {
      onChange(null);
      return;
    }
    // value 형식: "{provider}:{model}". model 이름에 콜론 포함 가능 (qwen3.5:9b).
    const idx = v.indexOf(':');
    if (idx <= 0) return;
    const provider = v.slice(0, idx);
    const model = v.slice(idx + 1);
    if (provider === 'ollama' || provider === 'gemini') {
      onChange({ provider, model });
    }
  };

  return (
    <div className="lg-field" style={{ minWidth: 200 }}>
      <label htmlFor="lg-model-select">{t('chat.model.label', 'AI 모델')}</label>
      <select
        id="lg-model-select"
        value={current}
        onChange={handleChange}
        disabled={disabled || loading}
        aria-label={t('chat.model.label', 'AI 모델')}
        title={err ? `옵션 로딩 실패: ${err} — 자동 모드로 동작` : undefined}
      >
        <option value="auto">{loading ? '로딩…' : t('chat.model.auto', '자동 (라우터 결정)')}</option>
        {opts.map((o) => {
          const key = `${o.provider}:${o.id}`;
          const blocked = !o.available || o.blocked;
          const reason = o.blocked_reason || (blocked ? '사용 불가' : '');
          return (
            <option
              key={key}
              value={key}
              disabled={blocked}
              title={reason || undefined}
            >
              {familyMark(o.family)} {o.label}{blocked ? '  (사용 불가)' : ''}
            </option>
          );
        })}
      </select>
    </div>
  );
}
