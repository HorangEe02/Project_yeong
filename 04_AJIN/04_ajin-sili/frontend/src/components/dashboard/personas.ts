// Persona detection + widget mappings.
// 9 페르소나에 각각 4-6 위젯을 매핑한다.
//
// 분류 우선순위 (위에서부터 매칭):
//   1. role_level === 5      → P9 SYS_ADMIN
//   2. role_level >= 4       → P8 EXECUTIVE
//   3. role_name === HR_ADMIN OR dept === '총무인사팀' → P6 HR_ADMIN
//   4. role_name === IT_ADMIN OR dept === 'IT전략팀'  → P7 IT_ADMIN
//   5. role_level <= 2 (신입 후보)                   → P1 NEWBIE
//   6. dept === '품질보증팀'                          → P2 QA
//   7. dept === '안전보건팀'                          → P3 SAFETY
//   8. dept includes 구매/영업                        → P4 SALES
//   9. dept includes 생산기술/자동화/금형/정비/프레스 → P5 PRODUCTION
//  default: P1 NEWBIE (안전 default)

import type { AuthUser } from '@store/auth';
import { fetchChangeKpi, fetchComplianceAlarms } from '@api/compliance';
import { getIngestion, getModuleCounts, getAlarms } from '@api/dashboard';
import type { PersonaId, WidgetSpec, WidgetData } from './widgets/types';

export function detectPersona(user: AuthUser | null): PersonaId {
  if (!user) return 'P1_NEWBIE';
  const dept = user.department ?? '';

  if (user.role_level === 5) return 'P9_SYS_ADMIN';
  if (user.role_level >= 4) return 'P8_EXECUTIVE';
  if (user.role_name === 'HR_ADMIN' || dept === '총무인사팀') return 'P6_HR_ADMIN';
  if (user.role_name === 'IT_ADMIN' || dept === 'IT전략팀') return 'P7_IT_ADMIN';
  if (user.role_level <= 2) return 'P1_NEWBIE';
  if (dept === '품질보증팀') return 'P2_QA';
  if (dept === '안전보건팀') return 'P3_SAFETY';
  if (/구매|영업/.test(dept)) return 'P4_SALES';
  if (/생산기술|자동화|금형|정비|프레스/.test(dept)) return 'P5_PRODUCTION';
  return 'P1_NEWBIE';
}

export const PERSONA_LABELS: Record<PersonaId, { en: string; ko: string }> = {
  P1_NEWBIE:     { en: 'NEWBIE',     ko: '신입사원' },
  P2_QA:         { en: 'QUALITY',    ko: '품질보증' },
  P3_SAFETY:     { en: 'SAFETY',     ko: '안전보건' },
  P4_SALES:      { en: 'TRADE',      ko: '구매·영업' },
  P5_PRODUCTION: { en: 'PRODUCTION', ko: '생산기술' },
  P6_HR_ADMIN:   { en: 'HR ADMIN',   ko: '계정·통계 운영' },
  P7_IT_ADMIN:   { en: 'IT ADMIN',   ko: '시스템 운영' },
  P8_EXECUTIVE:  { en: 'EXECUTIVE',  ko: '임원' },
  P9_SYS_ADMIN:  { en: 'SYS ADMIN',  ko: '총괄 관리자' },
};

// ─────────────────────────────────────────────────────────────
// Source helpers — 기존 API 또는 mock 데이터로 WidgetData 생성
// ─────────────────────────────────────────────────────────────

const toFiniteNumber = (value: unknown, fallback = 0): number => {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

interface DashboardAlarmRow {
  timestamp?: string;
  ts?: string;
  severity?: string;
  title?: string;
}

function isRecent(timestamp: string | undefined, sinceMs: number): boolean {
  if (!timestamp) return false;
  const parsed = new Date(timestamp).getTime();
  return Number.isFinite(parsed) && parsed >= sinceMs;
}

function normalizeDashboardAlarms(payload: unknown): DashboardAlarmRow[] {
  if (Array.isArray(payload)) return payload as DashboardAlarmRow[];
  if (payload && typeof payload === 'object' && Array.isArray((payload as { alarms?: unknown }).alarms)) {
    return (payload as { alarms: DashboardAlarmRow[] }).alarms;
  }
  return [];
}

function statusFromSeverity(severity: string | undefined): 'crit' | 'warn' | 'ok' {
  const normalized = (severity ?? '').toUpperCase();
  if (normalized === 'CRITICAL') return 'crit';
  if (normalized === 'HIGH' || normalized === 'WARNING') return 'warn';
  return 'ok';
}

const equipmentMetricSource = async (): Promise<WidgetData> => {
  const ingestion = await getIngestion();
  const online = toFiniteNumber(ingestion?.molds?.have);
  const total = toFiniteNumber(ingestion?.molds?.total);
  const ratio = total > 0 ? online / total : 1;
  return {
    metric: {
      value: online,
      secondary: `/ ${total}`,
      status: ratio < 0.8 ? 'warn' : 'ok',
    },
  };
};

const openComplianceSource = async (): Promise<WidgetData> => {
  const kpi = await fetchChangeKpi(30);
  const openCount = toFiniteNumber(kpi.open_count);
  return {
    metric: {
      value: openCount,
      secondary: '건',
      status: openCount >= 10 ? 'crit' : openCount > 0 ? 'warn' : 'ok',
    },
  };
};

const systemHealthSource = async (): Promise<WidgetData> => {
  const ingestion = await getIngestion();
  const latencyMs = toFiniteNumber(ingestion?.latency_ms);
  const qps = toFiniteNumber(ingestion?.qps);
  return {
    metric: {
      value: Math.round(latencyMs),
      secondary: `ms · ${qps.toFixed(1)} QPS`,
      status: latencyMs > 800 ? 'warn' : 'ok',
    },
  };
};

const todayAlarmsSource = async (): Promise<WidgetData> => {
  try {
    const since = Date.now() - 24 * 60 * 60 * 1000;
    const [compliance, dashboard] = await Promise.allSettled([
      fetchComplianceAlarms(0, 50),
      getAlarms(),
    ]);
    const complianceToday = compliance.status === 'fulfilled'
      ? compliance.value.items.filter((a) => isRecent(a.timestamp, since)).length
      : 0;
    const dashboardToday = dashboard.status === 'fulfilled'
      ? normalizeDashboardAlarms(dashboard.value).filter((a) => isRecent(a.timestamp ?? a.ts, since)).length
      : 0;
    const today = complianceToday + dashboardToday;
    return {
      metric: {
        value: today,
        secondary: '건',
        status: today >= 5 ? 'crit' : today > 0 ? 'warn' : 'ok',
      },
    };
  } catch {
    return { metric: { value: 0, secondary: '건', status: 'ok' } };
  }
};

const moduleCountSource = async (): Promise<WidgetData> => {
  const c = await getModuleCounts();
  return {
    list: [
      { label: '학습 SOP', value: `${c.sopGuides}종` },
      { label: '협업 가이드', value: `${c.collaborations}종` },
      { label: '문서 학습', value: `${c.fewShotRag}건` },
      { label: '크롤 소스', value: `${c.crawlers}곳` },
    ],
  };
};

const recentAlarmsSource = async (): Promise<WidgetData> => {
  try {
    const payload = await getAlarms();
    const alarms = normalizeDashboardAlarms(payload);
    return {
      list: alarms.slice(0, 4).map((a) => ({
        label: a.title ?? '알람',
        status: statusFromSeverity(a.severity),
      })),
    };
  } catch {
    return { list: [] };
  }
};

// ─────────────────────────────────────────────────────────────
// 정적 / mock source — 추후 backend endpoint 추가 시 교체
// ─────────────────────────────────────────────────────────────

const onboardingProgress = (): WidgetData => ({
  gauge: { current: 8, total: 14, unit: 'Day' },
});

const sopProgress = (): WidgetData => ({
  gauge: { current: 5, total: 8, unit: '종' },
});

const recommendedLearning = (): WidgetData => ({
  list: [
    { label: 'SOP-PPAP', value: 'D+1' },
    { label: 'SOP-8D', value: 'D+3' },
    { label: '산안법 38조', value: 'D+5' },
  ],
});

const spcLights = (): WidgetData => ({
  lights: [
    { label: 'EWP', status: 'crit' },
    { label: 'CCH', status: 'ok' },
    { label: '범퍼', status: 'ok' },
    { label: '시트레일', status: 'warn' },
    { label: '도어', status: 'ok' },
  ],
});

const open8D = (): WidgetData => ({
  metric: { value: 4, secondary: '건', status: 'warn' },
});

const ppapDday = (): WidgetData => ({
  metric: { value: 'D-7', status: 'warn' },
});

const safetyAlerts = (): WidgetData => ({
  list: [
    { label: '산안법 38조 시행 임박', status: 'crit' },
    { label: 'MSDS 만료 12건', status: 'warn' },
    { label: '안전 점검 진행 중', status: 'ok' },
  ],
});

const supplierImpact = (): WidgetData => ({
  metric: { value: 6, secondary: '협력사', status: 'warn' },
});

const tariffWhatif = (): WidgetData => ({
  metric: { value: '+12.4', secondary: '% 원가 영향', status: 'warn' },
});

const moldLifecycle = (): WidgetData => ({
  metric: { value: 3, secondary: '대 임박', status: 'warn' },
});

const fourMChanges = (): WidgetData => ({
  metric: { value: 7, secondary: '건 진행', status: 'ok' },
});

const mtbf = (): WidgetData => ({
  metric: { value: 142, secondary: 'h MTBF', status: 'ok' },
});

const newEmployees = (): WidgetData => ({
  metric: { value: 3, secondary: '명 / 이번주', status: 'ok' },
});

const pwExpiring = (): WidgetData => ({
  metric: { value: 12, secondary: '건 임박', status: 'warn' },
});

const pendingApprovals = (): WidgetData => ({
  metric: { value: 5, secondary: '결재 대기', status: 'warn' },
});

const headcountTrend = (): WidgetData => ({
  list: [
    { label: '전사 헤드카운트', value: '329명' },
    { label: '본부 8 / 팀 30', value: '' },
    { label: '이번 분기 변동', value: '+5명' },
  ],
});

const suspiciousLogins = (): WidgetData => ({
  metric: { value: 0, secondary: '24h', status: 'ok' },
});

const dauHeatmap = (): WidgetData => ({
  metric: { value: 187, secondary: 'DAU', status: 'ok' },
});

const llmLatency = (): WidgetData => ({
  metric: { value: 569, secondary: 'ms p95', status: 'ok' },
});

const crawlerLast = (): WidgetData => ({
  list: [
    { label: '국내법', value: '02:01', status: 'ok' },
    { label: 'EU CBAM', value: '02:03', status: 'ok' },
    { label: 'MSDS', value: '02:08', status: 'warn' },
  ],
});

const topChanges = (): WidgetData => ({
  list: [
    { label: '산안법 38조 개정', status: 'crit' },
    { label: '미국 관세 25%', status: 'crit' },
    { label: 'EU REACH SVHC', status: 'warn' },
    { label: 'OEM HKMC SQ v3.2', status: 'ok' },
  ],
});

const quarterlyKpi = (): WidgetData => ({
  metric: { value: 87, secondary: '/ 100 점', status: 'ok' },
});

const dbStatus = (): WidgetData => ({
  list: [
    { label: 'compliance.db', value: '142 MB', status: 'ok' },
    { label: 'employees.db', value: '8.2 MB', status: 'ok' },
    { label: 'audit.db', value: '67 MB', status: 'ok' },
    { label: 'ChromaDB', value: 'sync', status: 'warn' },
  ],
});

const backupStatus = (): WidgetData => ({
  metric: { value: 'OK', secondary: '12h 전', status: 'ok' },
});

const cloudRunRevision = (): WidgetData => ({
  metric: { value: 196, secondary: 'rev · 100%', status: 'ok' },
});

// ─────────────────────────────────────────────────────────────
// 9 페르소나 × widget 매핑
// ─────────────────────────────────────────────────────────────

export const PERSONA_WIDGETS: Record<PersonaId, WidgetSpec[]> = {
  P1_NEWBIE: [
    { id: 'p1.onboarding',   variant: 'gauge',    labelEn: 'ONBOARDING',     labelKo: '온보딩 진행',     source: onboardingProgress },
    { id: 'p1.sop',          variant: 'gauge',    labelEn: 'SOP LEARN',      labelKo: '이번 주 학습',    source: sopProgress },
    { id: 'p1.recommend',    variant: 'list',     labelEn: 'RECOMMENDED',    labelKo: '추천 학습',       source: recommendedLearning, link: '/chat' },
    { id: 'p1.chat',         variant: 'shortcut', labelEn: 'AI ASSISTANT',   labelKo: '챗봇으로 질문하기', source: () => ({}), link: '/chat' },
    { id: 'p1.search',       variant: 'shortcut', labelEn: 'ORG CHART',      labelKo: '조직도 보기',     source: () => ({}), link: '/search' },
  ],
  P2_QA: [
    { id: 'p2.open8d',       variant: 'metric',    labelEn: 'OPEN 8D',        labelKo: '진행 중 8D',     source: open8D, link: '/draft' },
    { id: 'p2.ppap',         variant: 'metric',    labelEn: 'PPAP D-DAY',     labelKo: 'PPAP 마일스톤',  source: ppapDday },
    { id: 'p2.spc',          variant: 'trafficLight', labelEn: 'SPC LIGHTS',  labelKo: '5공정 신호등',   source: spcLights, link: '/equipment' },
    { id: 'p2.compliance',   variant: 'metric',    labelEn: 'OPEN COMPLIANCE',labelKo: 'OEM 품질 변경',  source: openComplianceSource, link: '/compliance' },
    { id: 'p2.alarms',       variant: 'list',      labelEn: 'RECENT ALARMS',  labelKo: '최근 알람',      source: recentAlarmsSource, link: '/equipment' },
  ],
  P3_SAFETY: [
    { id: 'p3.compliance',   variant: 'metric', labelEn: 'OPEN COMPLIANCE', labelKo: '법규 미해결',   source: openComplianceSource, link: '/compliance' },
    { id: 'p3.alerts',       variant: 'list',   labelEn: 'SAFETY ALERTS',   labelKo: '안전 알림',     source: safetyAlerts, link: '/compliance' },
    { id: 'p3.lights',       variant: 'trafficLight', labelEn: 'FACILITY LIGHTS', labelKo: '영향 시설',source: spcLights, link: '/equipment' },
    { id: 'p3.alarms',       variant: 'list',   labelEn: 'TODAY ALARMS',    labelKo: '금일 알람',     source: recentAlarmsSource },
    { id: 'p3.draft',        variant: 'shortcut', labelEn: 'SAFETY DRAFT',  labelKo: '안전 보고 작성', source: () => ({}), link: '/draft' },
  ],
  P4_SALES: [
    { id: 'p4.suppliers',    variant: 'metric', labelEn: 'SUPPLIER IMPACT', labelKo: '협력사 영향',   source: supplierImpact, link: '/compliance' },
    { id: 'p4.tariff',       variant: 'metric', labelEn: 'TARIFF WHAT-IF',  labelKo: '관세 시뮬',     source: tariffWhatif, link: '/compliance' },
    { id: 'p4.compliance',   variant: 'metric', labelEn: 'OPEN COMPLIANCE', labelKo: '미해결 법규',   source: openComplianceSource, link: '/compliance' },
    { id: 'p4.email',        variant: 'shortcut', labelEn: 'OEM EMAIL',     labelKo: '영문 이메일',   source: () => ({}), link: '/draft' },
    { id: 'p4.search',       variant: 'shortcut', labelEn: 'PEOPLE SEARCH', labelKo: '담당자 검색',   source: () => ({}), link: '/search' },
  ],
  P5_PRODUCTION: [
    { id: 'p5.equipment',    variant: 'metric', labelEn: 'EQUIPMENT ONLINE', labelKo: '가동 설비',    source: equipmentMetricSource, link: '/equipment' },
    { id: 'p5.spc',          variant: 'trafficLight', labelEn: 'SPC LIGHTS', labelKo: '5공정 신호등', source: spcLights, link: '/equipment' },
    { id: 'p5.fourm',        variant: 'metric', labelEn: '4M CHANGES',       labelKo: '4M 변경',      source: fourMChanges },
    { id: 'p5.mold',         variant: 'metric', labelEn: 'MOLD LIFECYCLE',   labelKo: '금형 임박',    source: moldLifecycle, link: '/equipment' },
    { id: 'p5.mtbf',         variant: 'metric', labelEn: 'MTBF',             labelKo: '평균 고장간격', source: mtbf },
    { id: 'p5.alarms',       variant: 'list',   labelEn: 'TODAY ALARMS',     labelKo: '금일 알람',    source: recentAlarmsSource },
  ],
  P6_HR_ADMIN: [
    { id: 'p6.new',          variant: 'metric', labelEn: 'NEW EMPLOYEES',    labelKo: '신규 입사',    source: newEmployees, link: '/admin' },
    { id: 'p6.pw',           variant: 'metric', labelEn: 'PW EXPIRING',      labelKo: '비밀번호 만료', source: pwExpiring, link: '/admin' },
    { id: 'p6.approvals',    variant: 'metric', labelEn: 'PENDING APPROVALS',labelKo: '결재 대기',    source: pendingApprovals, link: '/admin' },
    { id: 'p6.headcount',    variant: 'list',   labelEn: 'HEADCOUNT',        labelKo: '인원 현황',    source: headcountTrend, link: '/search' },
    { id: 'p6.security',     variant: 'metric', labelEn: 'SUSPICIOUS LOGIN', labelKo: '의심 로그인',  source: suspiciousLogins, link: '/admin' },
    { id: 'p6.draft',        variant: 'shortcut', labelEn: 'HR DRAFT',       labelKo: '인사 양식',    source: () => ({}), link: '/draft' },
  ],
  P7_IT_ADMIN: [
    { id: 'p7.health',       variant: 'metric', labelEn: 'SYSTEM HEALTH',    labelKo: '시스템 응답',  source: systemHealthSource, link: '/admin' },
    { id: 'p7.dau',          variant: 'metric', labelEn: 'DAU',              labelKo: '활성 사용자',  source: dauHeatmap, link: '/admin' },
    { id: 'p7.llm',          variant: 'metric', labelEn: 'LLM LATENCY',      labelKo: 'LLM 응답',    source: llmLatency },
    { id: 'p7.crawler',      variant: 'list',   labelEn: 'CRAWLER LAST RUN', labelKo: '크롤러 상태',  source: crawlerLast, link: '/compliance' },
    { id: 'p7.security',     variant: 'metric', labelEn: 'SUSPICIOUS LOGIN', labelKo: '의심 로그인',  source: suspiciousLogins, link: '/admin' },
    { id: 'p7.modules',      variant: 'list',   labelEn: 'MODULE COUNTS',    labelKo: '모듈 카운트',  source: moduleCountSource },
  ],
  P8_EXECUTIVE: [
    { id: 'p8.dau',          variant: 'metric', labelEn: 'DAU',              labelKo: '활성 사용자',  source: dauHeatmap },
    { id: 'p8.changes',      variant: 'list',   labelEn: 'TOP CHANGES',      labelKo: '주요 변경',    source: topChanges, link: '/compliance' },
    { id: 'p8.kpi',          variant: 'metric', labelEn: 'QUARTERLY KPI',    labelKo: '분기 KPI',     source: quarterlyKpi },
    { id: 'p8.tariff',       variant: 'metric', labelEn: 'TARIFF WHAT-IF',   labelKo: '관세 시뮬',    source: tariffWhatif, link: '/compliance' },
    { id: 'p8.headcount',    variant: 'list',   labelEn: 'HEADCOUNT',        labelKo: '인원 현황',    source: headcountTrend, link: '/admin' },
    { id: 'p8.compliance',   variant: 'metric', labelEn: 'OPEN COMPLIANCE',  labelKo: '미해결 법규',  source: openComplianceSource, link: '/compliance' },
  ],
  P9_SYS_ADMIN: [
    { id: 'p9.health',       variant: 'metric', labelEn: 'SYSTEM HEALTH',    labelKo: '시스템 응답',  source: systemHealthSource },
    { id: 'p9.equipment',    variant: 'metric', labelEn: 'EQUIPMENT ONLINE', labelKo: '가동 설비',    source: equipmentMetricSource, link: '/equipment' },
    { id: 'p9.alarms',       variant: 'metric', labelEn: 'TODAY ALARMS',     labelKo: '금일 알람',    source: todayAlarmsSource, link: '/equipment' },
    { id: 'p9.compliance',   variant: 'metric', labelEn: 'OPEN COMPLIANCE',  labelKo: '미해결 법규',  source: openComplianceSource, link: '/compliance' },
    { id: 'p9.db',           variant: 'list',   labelEn: 'DATABASES',        labelKo: 'DB 상태',      source: dbStatus },
    { id: 'p9.backup',       variant: 'metric', labelEn: 'BACKUP',           labelKo: '백업 상태',    source: backupStatus },
    { id: 'p9.revision',     variant: 'metric', labelEn: 'CLOUD RUN',        labelKo: '리비전',       source: cloudRunRevision },
  ],
};
