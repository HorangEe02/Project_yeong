// 기능 F (설비/공정 AI) 공유 타입.
// equipment.tsx 라우트와 tabs/ 컴포넌트가 공유한다.

export type EquipState = 'ok' | 'warn' | 'crit';
export type RiskLevel = 'LOW' | 'MED' | 'HIGH';

export interface EquipRow {
  type: string;
  en: string;
  state: EquipState;
  cpk: number;
  alarm: number;
}

export interface ProcessHealthDisplay {
  name: string;
  state: EquipState;
  cpk: number;
  viol: number;
  rules: string[];
}

export interface MoldDisplay {
  id: string;
  part: string;
  shots: number;
  max: number;
  risk: RiskLevel;
}

export interface MaintCostDisplay {
  eq: string;
  cost: number;
  jobs: number;
  next: string;
}

export interface ErrResultDisplay {
  code: string;
  name: string;
  sim: number;
  sev: string;
  count: number;
  mttr: string;
  cause: string;
}

export interface MarkovBranchDisplay {
  code: string;
  name: string;
  prob: number;
}

export interface InspectionRow {
  eq: string;
  cycle: string;
  date: string;
  rate: number;
  lvl: string;
  miss: string;
}

export interface MetricCard {
  v: string;
  en: string;
  ko: string;
}

export interface MLEngineDisplay {
  name: string;
  p99: string;
  model: string;
  online: boolean;
}
