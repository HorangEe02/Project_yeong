// Mock fallback data — API 실패 시 사용 (시연 안전성 확보).
// equipment.tsx 가 useMemo 안에서 API 응답이 없을 때 fallback 으로 사용한다.

import type {
  EquipRow,
  EquipState,
  ErrResultDisplay,
  InspectionRow,
  MaintCostDisplay,
  MarkovBranchDisplay,
  MetricCard,
  MLEngineDisplay,
  MoldDisplay,
  ProcessHealthDisplay,
} from './types';

export const MOCK_METRICS: readonly MetricCard[] = [
  { v: '92%', en: 'UPTIME', ko: '가동률' },
  { v: '1.42', en: 'AVG Cpk', ko: '평균 공정능력' },
  { v: '3', en: 'ALERTS', ko: '활성 알람' },
  { v: '720h', en: 'MTBF', ko: '평균 무고장' },
  { v: '2', en: 'MAINT DUE', ko: '정비 임박' },
] as const;

export const MOCK_EQUIPMENT: EquipRow[] = [
  { type: '프레스', en: 'PRESS', state: 'ok', cpk: 1.51, alarm: 0 },
  { type: '용접', en: 'WELD', state: 'warn', cpk: 1.18, alarm: 2 },
  { type: 'CNC', en: 'CNC', state: 'ok', cpk: 1.45, alarm: 0 },
  { type: '사출', en: 'INJECT', state: 'ok', cpk: 1.38, alarm: 0 },
  { type: '도장', en: 'PAINT', state: 'crit', cpk: 0.89, alarm: 1 },
  { type: '검사', en: 'INSPECT', state: 'ok', cpk: 1.62, alarm: 0 },
  { type: '컨베이어', en: 'CONVEY', state: 'ok', cpk: 1.55, alarm: 0 },
];

export const MOCK_PROCESSES5: ProcessHealthDisplay[] = [
  { name: 'CCH', state: 'ok' as EquipState, cpk: 1.51, viol: 0, rules: [] },
  { name: 'OBC', state: 'warn' as EquipState, cpk: 1.18, viol: 2, rules: ['Rule 2'] },
  { name: '범퍼빔', state: 'crit' as EquipState, cpk: 0.89, viol: 5, rules: ['Rule 1', 'Rule 2', 'Rule 5'] },
  { name: '도어', state: 'ok' as EquipState, cpk: 1.62, viol: 0, rules: [] },
  { name: '볼시트', state: 'ok' as EquipState, cpk: 1.55, viol: 1, rules: ['Rule 6'] },
];

export const MOCK_ML_ENGINES: MLEngineDisplay[] = [
  { name: 'TF-IDF Error Search', p99: '38ms', model: 'sklearn 1.4', online: true },
  { name: 'Isolation Forest SPC', p99: '87ms', model: 'sklearn 1.4', online: true },
  { name: 'XGBoost Mold Lifecycle', p99: '42ms', model: 'XGBoost 2.0', online: true },
  { name: 'Markov Failure Chain', p99: '24ms', model: 'numpy', online: true },
  { name: 'Doc Quality Scorer', p99: '18ms', model: 'rule-based', online: true },
  { name: 'Reg Risk Classifier', p99: '46ms', model: 'sklearn 1.4', online: true },
  { name: 'Intent Classifier', p99: '5ms', model: 'sklearn 1.4', online: true },
];

export const MOCK_ERR_RESULTS: ErrResultDisplay[] = [
  { code: 'E-101', name: '베어링 마모', sim: 0.87, sev: 'HIGH', count: 24, mttr: '35분', cause: '윤활 부족 누적' },
  { code: 'E-104', name: '가이드 핀 마모', sim: 0.76, sev: 'MED', count: 12, mttr: '25분', cause: '냉각 라인 불량' },
  { code: 'E-118', name: '클러치 슬립', sim: 0.71, sev: 'HIGH', count: 8, mttr: '90분', cause: '디스크 마모' },
  { code: 'E-122', name: '구동축 진동', sim: 0.64, sev: 'MED', count: 18, mttr: '40분', cause: '얼라인먼트' },
  { code: 'E-130', name: '전기 모터 이음', sim: 0.58, sev: 'LOW', count: 31, mttr: '15분', cause: '고정 볼트 풀림' },
];

export const MOCK_MARKOV_CHAIN: MarkovBranchDisplay[] = [
  { code: 'E-205', name: '윤활 부족', prob: 0.62 },
  { code: 'E-310', name: '모터 과열', prob: 0.31 },
  { code: 'E-407', name: '성형 불량', prob: 0.18 },
];

export const MOCK_MOLDS: MoldDisplay[] = [
  { id: 'MD-001', part: 'CCH-FR', shots: 412000, max: 500000, risk: 'LOW' },
  { id: 'MD-007', part: 'OBC-RR', shots: 485000, max: 500000, risk: 'HIGH' },
  { id: 'MD-012', part: 'BUMPER', shots: 280000, max: 600000, risk: 'LOW' },
  { id: 'MD-015', part: 'DOOR-IN', shots: 442000, max: 500000, risk: 'MED' },
  { id: 'MD-019', part: '볼시트', shots: 188000, max: 400000, risk: 'LOW' },
  { id: 'MD-022', part: 'EV-CASE', shots: 51000, max: 800000, risk: 'LOW' },
  { id: 'MD-024', part: 'CCH-RR', shots: 478000, max: 500000, risk: 'HIGH' },
  { id: 'MD-025', part: 'DOOR-OUT', shots: 320000, max: 500000, risk: 'MED' },
];

export const MOCK_MAINT_COST: MaintCostDisplay[] = [
  { eq: '프레스 #3', cost: 1240, jobs: 18, next: 'D-3' },
  { eq: '용접 #2', cost: 920, jobs: 14, next: 'D-12' },
  { eq: '도장 #1', cost: 880, jobs: 22, next: 'D-24' },
  { eq: 'CNC #5', cost: 640, jobs: 11, next: 'D-45' },
  { eq: '컨베이어 #2', cost: 410, jobs: 9, next: 'D-60' },
];

// 7장비 × ~6 카테고리 = 40개 증상 (사양서 일치)
export const SYMPTOM_CATS: Record<string, string[]> = {
  프레스: ['이음', '진동', '압력 저하', '성형 불량', '누유', '전기'],
  용접: ['스패터', '강도 부족', '크랙', '전류 불안', '이음', '아크 불안', '와이어 끊김'],
  CNC: ['가공면 불량', '채터링', '공구 마모', '진동', '치수 불량', '냉각수 부족'],
  사출: ['플래시', '수축', '색상 불균', '쇼트샷', '버닝', '게이트 막힘'],
  도장: ['오렌지필', '핀홀', '색차', '광택 불량', '먼지 부착', '흐름 자국'],
  검사: ['오감지', '센서 불안', '캘리브레이션', '데이터 누락', '광원 변동'],
  컨베이어: ['이음', '속도 불안', '벨트 슬립', '롤러 마모'],
};

// 에러 인과 25개 카테고리
export const CAUSALITY_CATEGORIES = [
  '균열', '마모', '누유', '누수', '과열',
  '진동', '이음', '압력', '온도', '전기',
  '전류 불안', '센서 불안', '제어 신호', '캘리브레이션', '베어링',
  '윤활', '냉각', '필터', '벨트', '체인',
  '치수 불량', '성형 불량', '표면 불량', '강도 부족', '구동축',
];

export const MOCK_INSPECTIONS: InspectionRow[] = [
  { eq: '프레스', cycle: '일간', date: '2026-04-26', rate: 100, lvl: 'ok', miss: '—' },
  { eq: '프레스', cycle: '주간', date: '2026-04-22', rate: 95, lvl: 'ok', miss: '가이드 핀 마모 측정 1건 보류' },
  { eq: '프레스', cycle: '월간', date: '2026-04-01', rate: 88, lvl: 'warn', miss: '유압 누수 점검 미완' },
  { eq: '용접', cycle: '일간', date: '2026-04-26', rate: 100, lvl: 'ok', miss: '—' },
  { eq: '용접', cycle: '주간', date: '2026-04-23', rate: 82, lvl: 'warn', miss: '전극 마모 확인 누락' },
  { eq: '용접', cycle: '월간', date: '2026-04-05', rate: 96, lvl: 'ok', miss: '—' },
  { eq: 'CNC', cycle: '일간', date: '2026-04-26', rate: 100, lvl: 'ok', miss: '—' },
  { eq: 'CNC', cycle: '주간', date: '2026-04-22', rate: 98, lvl: 'ok', miss: '—' },
  { eq: 'CNC', cycle: '월간', date: '2026-04-08', rate: 94, lvl: 'ok', miss: '—' },
];

// SPC mock — Rule 1·2 위반 패턴 시드 (API 실패 시 fallback)
export const MOCK_SPC_DATA: number[] = (() => {
  const out: number[] = [];
  for (let i = 0; i < 40; i++) {
    let v = 50 + Math.sin(i * 0.4) * 1.5 + ((i * 0.7) % 1.8 - 0.9);
    if (i >= 18 && i <= 26) v += 4;
    if (i === 32) v += 8;
    out.push(v);
  }
  return out;
})();
export const MOCK_CL = 50;
export const MOCK_UCL = 56;
export const MOCK_LCL = 44;
