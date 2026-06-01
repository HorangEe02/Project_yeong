// Persona-aware dashboard widget — 디자인 시스템 v2 (60-30-10 monotone + gold)
// 9 페르소나 × 4-6 위젯을 데이터(메타) + 컴포넌트(렌더) 분리로 관리.

export type WidgetVariant =
  | 'metric'        // 큰 숫자 + EN/KO 라벨 (MetricCard 래퍼)
  | 'list'          // 짧은 항목 N개 (예: "추천 학습 3건")
  | 'gauge'         // 진행률 0-100 (예: 온보딩 Day 8/14)
  | 'trafficLight'  // 5공정 신호등 (●●●○●)
  | 'shortcut';     // 빠른 진입 카드 (큰 아이콘 + 라벨)

export type WidgetStatus = 'ok' | 'warn' | 'crit' | 'idle';

export interface WidgetListItem {
  label: string;
  value?: string | number;
  status?: WidgetStatus;
}

export interface WidgetGaugeValue {
  current: number;
  total: number;
  unit?: string;            // 예: 'Day', '건'
}

export interface WidgetTrafficLight {
  label: string;            // 공정명 (예: 'EWP')
  status: WidgetStatus;
}

export interface WidgetData {
  metric?: { value: number | string; secondary?: string; status?: WidgetStatus };
  list?: WidgetListItem[];
  gauge?: WidgetGaugeValue;
  lights?: WidgetTrafficLight[];
}

export interface WidgetSpec {
  id: string;
  variant: WidgetVariant;
  labelEn: string;
  labelKo: string;
  /** 데이터 fetch — 비동기 또는 즉시 값 */
  source: () => Promise<WidgetData> | WidgetData;
  /** 클릭 시 이동 경로 (예: '/equipment'). shortcut variant 는 필수. */
  link?: string;
  /** 자동 갱신 (초). 미지정 시 한 번만 fetch. */
  refreshSec?: number;
}

// 9 페르소나 식별자
export type PersonaId =
  | 'P1_NEWBIE'         // 신입사원
  | 'P2_QA'             // 품질보증팀
  | 'P3_SAFETY'         // 안전보건팀
  | 'P4_SALES'          // 구매·영업
  | 'P5_PRODUCTION'     // 생산기술·자동화
  | 'P6_HR_ADMIN'       // HR_ADMIN
  | 'P7_IT_ADMIN'       // IT_ADMIN
  | 'P8_EXECUTIVE'      // 임원
  | 'P9_SYS_ADMIN';     // SYS_ADMIN
