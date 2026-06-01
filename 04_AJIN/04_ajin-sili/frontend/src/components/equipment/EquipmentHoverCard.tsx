// EquipmentHoverCard — 7대 장비 카드 hover 시 표시되는 풍부 학습용 tooltip 카드.
// 신입사원이 Cpk·알람의 의미를 한눈에 이해할 수 있도록 정의 + 현재값 + 미니 게이지 표시.
// 디자인 톤: ModelSelect 의 옵션 hover 카드와 통일 (좌측 4px family-color bar + glass surface).

import { useState, useRef, useLayoutEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight } from 'lucide-react';
import type { EquipRow, EquipState } from './types';

// ─────────────────────────────────────────────────────────────
// 신입 교육 카피 — 7대 장비별 정의·핵심 지표·알람 기준
// (백엔드 EquipmentTypeCard 에 key_metric_ko 추가되면 그 값을 우선 사용)
// ─────────────────────────────────────────────────────────────
export interface EquipmentCopy {
  description: string;
  key_metric: string;
  alarm_basis: string;
}

export const EQUIPMENT_HELP_COPY: Record<string, EquipmentCopy> = {
  '프레스': {
    description: '금속 판재를 stroke 동작으로 성형 — 차체 패널·브래킷의 핵심 가공',
    key_metric: 'Stroke 정밀도·BDC 위치 (mm)',
    alarm_basis: 'Stroke 위치 이탈·하중 초과·금형 마모 누적',
  },
  '용접기': {
    description: '스폿/아크 용접으로 부품 결합 — BIW(Body-in-White) 공정의 핵심',
    key_metric: '용접점 강도·열영향부(HAZ)',
    alarm_basis: '용접 시간 이탈·전류 변동·갭 비정상',
  },
  '로봇': {
    description: '다관절 매니퓰레이터로 핸들링·용접·조립 자동화',
    key_metric: '반복 정밀도(±0.05mm)·사이클 타임',
    alarm_basis: 'Encoder 이상·관절 토크 초과·교시 점 이탈',
  },
  '사출기': {
    description: '플라스틱 수지를 mold 에 주입 — 내장재·트림 부품 성형',
    key_metric: '사출 압력·냉각 시간·수축률',
    alarm_basis: '주입 압력 이상·온도 편차·플래시 발생',
  },
  'CNC': {
    description: '컴퓨터 수치 제어 가공 — 정밀 부품(커넥터·하우징) 절삭',
    key_metric: '치수 공차·표면 거칠기(Ra)',
    alarm_basis: 'Tool 마모·축 위치 오차·진동',
  },
  '레이저': {
    description: '레이저 빔으로 절단·용접·마킹 — 비접촉·고정밀',
    key_metric: '절단면 품질·HAZ·정밀도',
    alarm_basis: '빔 power 이탈·assist gas 압력 변동·렌즈 오염',
  },
  '공통설비': {
    description: '컴프레서·펌프·냉각수 등 공장 공통 인프라(Utility)',
    key_metric: '공기압·온도·유량·진동',
    alarm_basis: '공압 저하·온도 초과·진동 ISO 등급 이탈',
  },
};

// state → risk color (ROT prototype 의 riskColor 와 동일 톤)
const STATE_COLOR: Record<EquipState, { bar: string; text: string; label: string }> = {
  ok:   { bar: '#639922', text: '#3b6d11', label: '정상' },
  warn: { bar: '#ef9f27', text: '#633806', label: '주의' },
  crit: { bar: '#e24b4a', text: '#501313', label: '위험' },
};

// Cpk 값 → 등급 (1.33 우수 / 1.0~1.33 양호 / <1.0 개선 필요)
function cpkGrade(cpk: number): { label: string; color: string } {
  if (cpk >= 1.33) return { label: '우수', color: '#639922' };
  if (cpk >= 1.0)  return { label: '양호', color: '#97c459' };
  if (cpk >= 0.67) return { label: '주의', color: '#ef9f27' };
  return { label: '개선 필요', color: '#e24b4a' };
}

// Cpk 0~2 범위 → 0~100% 시각화
function cpkPercent(cpk: number): number {
  const clamped = Math.min(2, Math.max(0, cpk));
  return Math.round((clamped / 2) * 100);
}

// ─────────────────────────────────────────────────────────────
// Hover Card 본체 — children 위 마우스 enter 시 floating card 표시.
// position: 'top' 기준 (위에 띄움). 화면 가장자리에 맞춰 자동 조정.
// ─────────────────────────────────────────────────────────────

interface Props {
  row: EquipRow;
  children: ReactNode;
  /** 클릭 시 호출 — 상세 Drawer 열기 트리거. */
  onClick?: () => void;
}

const CARD_WIDTH = 300;

export function EquipmentHoverCard({ row, children, onClick }: Props) {
  const [isHovering, setIsHovering] = useState(false);
  const triggerRef = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const copy = EQUIPMENT_HELP_COPY[row.type] ?? {
    description: '설비 정보가 등록되지 않았습니다.',
    key_metric: '—',
    alarm_basis: '—',
  };
  const stateMeta = STATE_COLOR[row.state];
  const grade = cpkGrade(row.cpk);

  useLayoutEffect(() => {
    if (!isHovering || !triggerRef.current) {
      setPos(null);
      return;
    }
    const rect = triggerRef.current.getBoundingClientRect();
    // 카드를 trigger 위쪽에 띄움. 위 공간 부족하면 아래로 폴백.
    let top = rect.top + window.scrollY - 8 - 280; // 280 = approx card height
    let left = rect.left + window.scrollX + rect.width / 2 - CARD_WIDTH / 2;
    if (top < window.scrollY + 8) {
      top = rect.bottom + window.scrollY + 8;
    }
    // 좌우 가장자리 보정
    const minLeft = window.scrollX + 8;
    const maxLeft = window.scrollX + window.innerWidth - CARD_WIDTH - 8;
    if (left < minLeft) left = minLeft;
    if (left > maxLeft) left = maxLeft;
    setPos({ top, left });
  }, [isHovering]);

  return (
    <>
      <div
        ref={triggerRef}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        onClick={onClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onClick?.();
          }
        }}
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        style={{ cursor: onClick ? 'pointer' : 'default' }}
      >
        {children}
      </div>

      {isHovering && pos &&
        createPortal(
          <div
            role="tooltip"
            style={{
              position: 'absolute',
              top: pos.top,
              left: pos.left,
              width: CARD_WIDTH,
              zIndex: 1000,
              pointerEvents: 'none',
              background: 'color-mix(in oklab, var(--hud-surface) 96%, transparent)',
              border: '0.5px solid color-mix(in oklab, var(--hud-text) 14%, transparent)',
              borderRadius: 12,
              boxShadow: '0 12px 32px rgba(0,0,0,0.22)',
              backdropFilter: 'blur(10px)',
              WebkitBackdropFilter: 'blur(10px)',
              fontFamily: 'var(--hud-font-sans)',
              color: 'var(--hud-text)',
              padding: '12px 14px 12px 18px',
              borderLeft: `4px solid ${stateMeta.bar}`,
            }}
          >
            {/* 헤더 — 장비명 + state pill */}
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{row.type}</div>
                <div style={{ fontSize: 10, fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-text-dim)', letterSpacing: '0.08em' }}>{row.en}</div>
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: stateMeta.text,
                  background: `color-mix(in oklab, ${stateMeta.bar} 18%, transparent)`,
                  border: `1px solid color-mix(in oklab, ${stateMeta.bar} 35%, transparent)`,
                  borderRadius: 999,
                  padding: '2px 8px',
                }}
              >
                {stateMeta.label}
              </span>
            </div>

            {/* description */}
            <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--hud-text-dim)', marginTop: 8 }}>
              {copy.description}
            </div>

            {/* Cpk 블록 */}
            <div style={{ marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600 }}>Cpk · 공정능력지수</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: grade.color }}>{row.cpk.toFixed(2)} · {grade.label}</span>
              </div>
              <div style={{ height: 5, background: 'color-mix(in oklab, var(--hud-text) 10%, transparent)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${cpkPercent(row.cpk)}%`, height: '100%', background: grade.color, transition: 'width 0.3s' }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--hud-text-muted, var(--hud-text-dim))', marginTop: 4 }}>
                1.33↑ 우수 · 1.0~1.33 양호 · &lt;1.0 개선 필요
              </div>
            </div>

            {/* 알람 블록 */}
            <div style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 2 }}>
                <span style={{ fontSize: 11, fontWeight: 600 }}>알람 · 누적 (24h)</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: row.alarm > 30 ? '#e24b4a' : row.alarm > 10 ? '#ef9f27' : 'var(--hud-text)' }}>{row.alarm}건</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--hud-text-muted, var(--hud-text-dim))' }}>
                기준: {copy.alarm_basis}
              </div>
            </div>

            {/* 핵심 지표 */}
            <div style={{ marginTop: 10, padding: '6px 8px', background: 'color-mix(in oklab, var(--hud-text) 5%, transparent)', borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--hud-text-dim)', marginBottom: 2 }}>핵심 모니터링 지표</div>
              <div style={{ fontSize: 11, fontWeight: 500 }}>{copy.key_metric}</div>
            </div>

            {/* 클릭 안내 */}
            {onClick && (
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4, fontSize: 11, fontWeight: 500, color: 'var(--hud-primary, #FBBF24)' }}>
                클릭하여 상세 보기
                <ChevronRight size={12} strokeWidth={2} />
              </div>
            )}
          </div>,
          document.body,
        )}
    </>
  );
}
