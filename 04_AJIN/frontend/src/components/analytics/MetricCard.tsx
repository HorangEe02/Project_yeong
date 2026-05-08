// Day 5++ — 우측 분석 패널용 경량 메트릭 카드 (LATENCY 124ms, QPS 8.4k).
// Day 1 의 metric-mini 스타일과 호환되며 시안 패턴(EN+KO 페어 + 골드 값) 강화.

interface Props {
  labelEn: string;
  labelKo?: string;
  value: string;
  /** 시안 강조 시 골드 칠 (LATENCY 만 골드, QPS 는 일반). */
  emphasized?: boolean;
}

export function MetricCard({ labelEn, labelKo, value, emphasized = false }: Props) {
  return (
    <div className="analytics-metric">
      <div className="analytics-metric__labels">
        <span className="label-en analytics-metric__en">{labelEn}</span>
        {labelKo && <span className="analytics-metric__ko">{labelKo}</span>}
      </div>
      <strong
        className="analytics-metric__value"
        data-emphasized={emphasized || undefined}
      >
        {value}
      </strong>
    </div>
  );
}
