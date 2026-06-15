// VariableForm — Module B · 변수 입력 폼 (그룹별 섹션).
// B2 v4.0: var_metadata 를 그룹(수신/발신, 기본, 내용, 일정, 참조) 으로 묶어 렌더.
// 진행률 바 + 필수 변수 충족 여부 표시.

import { useMemo } from 'react';
import type { VarMetadata } from '@/types/draft';
import { VariableField } from './VariableField';

interface Props {
  variables: VarMetadata[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

const GROUP_ORDER = ['기본', '수신/발신', '내용', '일정', '참조'];

export function VariableForm({ variables, values, onChange }: Props) {
  const grouped = useMemo(() => {
    const map = new Map<string, VarMetadata[]>();
    for (const v of variables) {
      const g = v.group || '내용';
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push(v);
    }
    // GROUP_ORDER 순서로 정렬
    return GROUP_ORDER.filter((g) => map.has(g)).map((g) => ({
      name: g,
      items: map.get(g)!,
    }));
  }, [variables]);

  const requiredVars = variables.filter((v) => v.required);
  const requiredFilled = requiredVars.filter((v) => (values[v.name] ?? '').trim().length > 0).length;
  const progress =
    requiredVars.length === 0 ? 1 : requiredFilled / requiredVars.length;

  if (variables.length === 0) {
    return null;
  }

  return (
    <div style={{ marginBottom: 14 }}>
      {/* 헤더 — 진행률 + 필수 충족 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          marginBottom: 10,
        }}
      >
        <div className="lg-eyebrow" style={{ marginBottom: 0 }}>
          STRUCTURED VARIABLES · 구조화 변수 입력
        </div>
        <span
          className="mono"
          style={{
            fontFamily: 'var(--hud-font-mono)',
            fontSize: 10,
            letterSpacing: '0.1em',
            color:
              progress >= 1
                ? 'var(--hud-green, #2D8A4E)'
                : progress > 0
                  ? 'var(--hud-orange, #E8A317)'
                  : 'var(--hud-text-muted)',
          }}
          title={`필수 변수 ${requiredFilled}/${requiredVars.length} 채움`}
        >
          REQUIRED · {requiredFilled}/{requiredVars.length}
        </span>
      </div>

      {/* 진행률 바 */}
      <div
        style={{
          height: 4,
          borderRadius: 999,
          background: 'color-mix(in oklab, var(--hud-text) 8%, transparent)',
          overflow: 'hidden',
          marginBottom: 14,
        }}
        aria-hidden
      >
        <div
          style={{
            height: '100%',
            width: `${progress * 100}%`,
            background:
              progress >= 1
                ? 'var(--hud-green, #2D8A4E)'
                : 'var(--hud-primary)',
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      {/* 그룹별 섹션 */}
      {grouped.map((g) => (
        <section
          key={g.name}
          style={{
            marginBottom: 16,
            padding: 14,
            borderRadius: 16,
            border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
          }}
        >
          <div
            className="lg-eyebrow"
            style={{
              marginBottom: 10,
              fontSize: 10,
            }}
          >
            {g.name.toUpperCase()} · {g.name}
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 12,
            }}
          >
            {g.items.map((v) => (
              <VariableField
                key={v.name}
                variable={v}
                value={values[v.name] ?? ''}
                onChange={(val) => onChange(v.name, val)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
