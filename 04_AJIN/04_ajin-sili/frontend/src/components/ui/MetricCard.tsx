// 메트릭 카드 — 큰 숫자(3xl) + 영문 라벨 + 한글 부제 + 카운트업 애니메이션
//
// v3.6 — "사업장 상태" 카드 모드 지원:
//   - status: 'ok' | 'warn' | 'crit' → 좌측 보더 색상 시그널
//   - secondaryValue: "/ 25" 같은 분모 표기 또는 단위 (예: "ms")
//   - onClick: 카드 클릭 시 라우팅용 핸들러 (포인터 커서 + 호버)

import type { CSSProperties, KeyboardEvent } from 'react';
import { useCountUp } from '@hooks/useCountUp';

export type MetricStatus = 'ok' | 'warn' | 'crit' | 'idle';

interface Props {
  value: number;
  labelEn: string;
  labelKo?: string;
  sub?: string;
  /** "/ 25" 같은 분모 또는 "ms" 같은 단위 — 큰 숫자 우측에 작게 표기 */
  secondaryValue?: string;
  /** 운영 상태 시그널 — 좌측 보더 색상 변화 */
  status?: MetricStatus;
  /** 클릭 시 페이지 이동. 지정하면 카드가 버튼 역할로 동작 (포인터 + Enter 지원) */
  onClick?: () => void;
  format?: (n: number) => string;
}

const defaultFormat = (n: number) => n.toLocaleString();

const STATUS_COLOR: Record<MetricStatus, string> = {
  ok: 'var(--hud-primary)',           // 골드 — 정상
  warn: '#F59E0B',                     // 주황 — 주의
  crit: '#EF4444',                     // 빨강 — 위험
  idle: 'var(--hud-text-muted, #888)', // 회색 — 데이터 없음
};

export function MetricCard({
  value,
  labelEn,
  labelKo,
  sub,
  secondaryValue,
  status = 'ok',
  onClick,
  format = defaultFormat,
}: Props) {
  const animated = useCountUp(value);
  const interactive = typeof onClick === 'function';

  const style: CSSProperties = {
    borderLeft: `3px solid ${STATUS_COLOR[status]}`,
    cursor: interactive ? 'pointer' : 'default',
    transition: 'transform 0.15s ease, box-shadow 0.15s ease',
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!interactive) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick?.();
    }
  };

  return (
    <div
      className="metric-card"
      style={style}
      onClick={interactive ? onClick : undefined}
      onKeyDown={interactive ? handleKeyDown : undefined}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? `${labelEn} ${labelKo ?? ''}` : undefined}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <div className="metric-value">{format(animated)}</div>
        {secondaryValue && (
          <div className="dim" style={{ fontSize: 14, fontWeight: 600 }}>
            {secondaryValue}
          </div>
        )}
      </div>
      <div className="label-en">{labelEn}</div>
      {labelKo && <div className="dim" style={{ fontSize: 13, marginTop: 2 }}>{labelKo}</div>}
      {sub && <div className="dim" style={{ fontSize: 12, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}
