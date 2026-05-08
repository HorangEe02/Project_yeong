// Dashboard 정밀 폴리싱 — 환영 헤더 + 카운트업 메트릭 + RBAC dim 카드 + 알람 카드 + 시스템 정보

import { useEffect, useState } from 'react';
import {
  getModuleCounts,
  getSystemInfo,
  type ModuleCounts,
  type SystemInfoResponse,
} from '@api/dashboard';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Lock } from 'lucide-react';
import { useAuthStore } from '@store/auth';
import { useMetricsStore } from '@store/metrics';
import { MetricCard } from '@components/ui/MetricCard';
import { Badge } from '@components/ui/Badge';
import { Button } from '@components/ui/Button';
import { isMenuVisible, getLockReason } from '@lib/rbac';
import { ALARMS, SEVERITY_LABEL, type MockAlarm, type AlarmSeverity } from '@api/mock/seed/alarms';
import { SYSTEM_INFO } from '@api/mock/seed/system';
import { useEquipmentRTDB } from '@hooks/useEquipmentRTDB';
import type { RecentViolation } from '@/types/equipment';

interface ModuleCard {
  path: string;
  slug: string;
  letter: string;
  titleKey: string;
  bullets: string[];
  /** 한 줄 부제 — 카드 타이틀 바로 아래에 표시. 비전공자/신입 대상 안내 문구. */
  tagline: string;
}

/**
 * 모듈 카드 정의 — 일부 bullet 은 백엔드 카운트 (counts) 로 동적 채움.
 * counts 가 null 이면 기본 시연 값 사용 (오프라인/loading 시 안전망).
 *
 * v3.5 폴리싱: bullet 문구를 비전공자/신입사원이 한눈에 이해 가능한 자연어로 재작성.
 * 기술 용어(FTS5, ChromaDB, XGBoost 등)는 카드 hover/상세 페이지에서 제공.
 */
function buildModules(counts: ModuleCounts | null): ModuleCard[] {
  const c = counts;
  return [
    {
      path: '/search', slug: 'search', letter: 'A', titleKey: 'modules.search',
      tagline: '이름·부서·직책으로 동료를 빠르게 찾기',
      bullets: [
        '오타나 줄임말도 알아서 인식',
        '부서·직급별 5가지 정렬 지원',
        '본부→팀 조직도 한눈에 보기',
      ],
    },
    {
      path: '/draft', slug: 'draft', letter: 'B', titleKey: 'modules.draft',
      tagline: '메일·보고서 초안을 AI가 대신 작성',
      bullets: [
        `사내 문서 ${c?.fewShotRag ?? 584}건 학습한 AI`,
        '문서 완성도 자동 평가 (5가지 기준)',
        'Word·PDF·HWP 등 7가지로 저장',
      ],
    },
    {
      path: '/chat', slug: 'chat', titleKey: 'modules.onboarding', letter: 'C',
      tagline: '사내 용어·업무 절차를 24시간 알려주는 AI',
      bullets: [
        `업무 매뉴얼 ${c?.sopGuides ?? 8}종 · 협업 가이드 ${c?.collaborations ?? 5}종`,
        '질문하기 / 학습하기 두 가지 모드',
        '사진·문서 업로드해서 바로 질문 가능',
      ],
    },
    {
      path: '/compliance', slug: 'compliance', letter: 'D', titleKey: 'modules.compliance',
      tagline: '법규·관세 변동을 자동 추적해 알려주기',
      bullets: [
        `국내외 법규 ${c?.crawlers ?? 9}곳 자동 수집`,
        '내 업무에 미치는 영향 100점 만점 점수',
        '관세 변동 비용 시뮬레이션',
      ],
    },
    {
      path: '/admin', slug: 'admin', letter: 'E', titleKey: 'modules.admin',
      tagline: '계정·권한·인력 통계를 한 곳에서 관리',
      bullets: [
        `직급별 접근 권한 ${c?.roles ?? 6}단계`,
        '로그인·권한 변경 자동 감사 기록',
        '부서별 인원 현황 7가지 차트',
      ],
    },
    {
      path: '/equipment', slug: 'equipment', letter: 'F', titleKey: 'modules.equipment',
      tagline: '설비 이상을 사전에 감지·예측',
      bullets: [
        '공정 이상을 8가지 규칙으로 자동 감지',
        `금형 ${c?.molds ?? 25}대 고장 가능성 AI 예측`,
        '설비 다음 상태 확률 분석',
      ],
    },
  ];
}

// RTDB live_alarms 의 RecentViolation → 대시보드 MockAlarm 형태로 어댑트.
// SPC 위반은 모듈 F (설비) 로 매핑. severity 매핑: critical→CRITICAL, warning→HIGH, info→MEDIUM.
function adaptViolation(v: RecentViolation): MockAlarm {
  const sevMap: Record<string, AlarmSeverity> = {
    critical: 'CRITICAL',
    warning: 'HIGH',
    info: 'MEDIUM',
  };
  return {
    id: v.id,
    severity: sevMap[v.severity] ?? 'MEDIUM',
    title: `SPC ${v.process_name || v.process_id} 위반`,
    detail: v.message || `Rule ${v.rule_number} — Nelson 위반`,
    module: 'F',
    timestamp: new Date(v.timestamp || Date.now()).toISOString(),
    acknowledged: false,
  };
}

function formatRelativeTime(iso: string | null, lang: string): string {
  if (!iso) return lang === 'ko' ? '없음' : 'Never';
  const then = new Date(iso);
  const diff = Date.now() - then.getTime();
  const min = Math.floor(diff / 60_000);
  if (min < 1) return lang === 'ko' ? '방금' : 'just now';
  if (min < 60) return lang === 'ko' ? `${min}분 전` : `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return lang === 'ko' ? `${hr}시간 전` : `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day === 1) return lang === 'ko' ? '어제' : 'yesterday';
  return lang === 'ko' ? `${day}일 전` : `${day}d ago`;
}

export function Dashboard() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const metrics = useMetricsStore((s) => s.metrics);
  const loadMetrics = useMetricsStore((s) => s.load);

  useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  // 모듈 카드 동적 카운트 (실패 시 fallback default 사용)
  const [moduleCounts, setModuleCounts] = useState<ModuleCounts | null>(null);
  useEffect(() => {
    let cancelled = false;
    getModuleCounts()
      .then((c) => { if (!cancelled) setModuleCounts(c); })
      .catch(() => { /* fallback null → 기본값 사용 */ });
    return () => { cancelled = true; };
  }, []);
  const modules = buildModules(moduleCounts);

  // 시스템 정보(LLM/비전/임베딩 등) — 백엔드 .env 기반 응답을 fetch, 실패시 mock SYSTEM_INFO 폴백.
  const [sysInfo, setSysInfo] = useState<SystemInfoResponse | null>(null);
  useEffect(() => {
    let cancelled = false;
    getSystemInfo()
      .then((info) => { if (!cancelled) setSysInfo(info as SystemInfoResponse); })
      .catch(() => { /* fallback null → SYSTEM_INFO mock 사용 */ });
    return () => { cancelled = true; };
  }, []);
  // 표시용 통합 객체 (백엔드 응답 우선, 누락 필드는 mock 으로 보완)
  const sys = {
    llm: sysInfo?.llm ?? SYSTEM_INFO.llm,
    vision: sysInfo?.vision ?? SYSTEM_INFO.vision,
    embedding: sysInfo?.embedding ?? SYSTEM_INFO.embedding,
    router: sysInfo?.router ?? SYSTEM_INFO.router,
    ml: sysInfo?.ml ?? SYSTEM_INFO.ml,
    rbac: sysInfo?.rbac ?? SYSTEM_INFO.rbac,
    data: sysInfo?.data ?? SYSTEM_INFO.data,
  };

  const lastLoginText = user
    ? formatRelativeTime((user as { last_login?: string }).last_login ?? null, i18n.language)
    : '';

  // RTDB live_alarms 구독 — Cloud Run 백엔드 + Firebase RTDB 통합.
  // 비어있으면 mock 으로 fallback (오프라인 데모 안전망 + D 모듈 시연 알람 보존).
  const rtdbViolations = useEquipmentRTDB();
  const liveAlarms: MockAlarm[] = rtdbViolations.map(adaptViolation);
  const baseAlarms: MockAlarm[] = liveAlarms.length > 0
    ? liveAlarms.concat(ALARMS.filter((a) => a.module === 'D'))  // D 컴플라이언스는 mock 보존
    : ALARMS;
  const activeAlarms = baseAlarms.filter((a) => !a.acknowledged);
  const topAlarm = [...activeAlarms].sort((a, b) => {
    const order: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return order[a.severity] - order[b.severity];
  })[0];

  return (
    <div className="page">
      {/* 환영 헤더 */}
      <div className="page-h" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
        <h1 className="h1">
          {user
            ? t('dashboard.greeting', { name: user.username, position: user.position ?? '' })
            : t('dashboard.title')}
        </h1>
        {user && (
          <>
            <div className="dim" style={{ fontSize: 13 }}>
              {t('dashboard.context', {
                division: (user as { department?: string }).department ?? '',
                department: (user as { department?: string }).department ?? '',
                plant: '본사 (대구)',
              })}
            </div>
            <div className="dim" style={{ fontSize: 12 }}>
              {t('dashboard.last_login', { at: lastLoginText })}
            </div>
          </>
        )}
      </div>

      {/* "사업장 상태" 메트릭 카드 4종 — v3.6
          1. 가동 설비 (active+maintenance / total)
          2. 금일 공정 알람 (RTDB live_alarms 24h + ALARMS F 모듈 합산)
          3. 법규 미해결 (D 모듈 severity ≥ HIGH)
          4. 시스템 응답 (latency ms · qps)
          → 카드 클릭 시 해당 모듈로 즉시 이동, 임계값 색상 시그널 적용. */}
      <div className="metrics-grid">
        {/* 1. 가동 설비 */}
        <MetricCard
          value={metrics?.equipmentOnline ?? 25}
          secondaryValue={`/ ${metrics?.equipmentTotal ?? 25}`}
          labelEn={t('dashboard.metrics.equipment_en')}
          labelKo={t('dashboard.metrics.equipment_ko')}
          status={
            metrics && metrics.equipmentOnline < metrics.equipmentTotal * 0.8
              ? 'warn'
              : 'ok'
          }
          onClick={() => navigate('/equipment')}
        />

        {/* 2. 금일 공정 알람 — RTDB SPC + F 모듈 알람 24h */}
        {(() => {
          const since = Date.now() - 24 * 60 * 60 * 1000;
          const rtdbToday = rtdbViolations.filter((v) => {
            const t = v.timestamp ? new Date(v.timestamp).getTime() : Date.now();
            return t >= since;
          }).length;
          const mockToday = ALARMS.filter(
            (a) => a.module === 'F' && new Date(a.timestamp).getTime() >= since
          ).length;
          const todayCount = rtdbToday + mockToday;
          const status: 'ok' | 'warn' | 'crit' =
            todayCount === 0 ? 'ok' : todayCount >= 5 ? 'crit' : 'warn';
          return (
            <MetricCard
              value={todayCount}
              secondaryValue="건"
              labelEn={t('dashboard.metrics.today_alerts_en')}
              labelKo={t('dashboard.metrics.today_alerts_ko')}
              status={status}
              onClick={() => navigate('/equipment')}
            />
          );
        })()}

        {/* 3. 법규 미해결 — Critical 이 있으면 빨강 */}
        <MetricCard
          value={metrics?.openAlarms ?? 0}
          secondaryValue="건"
          labelEn={t('dashboard.metrics.compliance_en')}
          labelKo={t('dashboard.metrics.compliance_ko')}
          status={
            (metrics?.criticalAlarms ?? 0) > 0
              ? 'crit'
              : (metrics?.openAlarms ?? 0) > 0
                ? 'warn'
                : 'ok'
          }
          onClick={() => navigate('/compliance')}
        />

        {/* 4. 시스템 응답 — latency 200ms ↑ 주황, 500ms ↑ 빨강 */}
        <MetricCard
          value={Math.round(metrics?.latencyMs ?? 0)}
          secondaryValue={`ms · ${(metrics?.qps ?? 0).toFixed(1)} QPS`}
          labelEn={t('dashboard.metrics.system_en')}
          labelKo={t('dashboard.metrics.system_ko')}
          status={
            (metrics?.latencyMs ?? 0) > 500
              ? 'crit'
              : (metrics?.latencyMs ?? 0) > 200
                ? 'warn'
                : 'ok'
          }
          onClick={() => navigate('/admin')}
        />
      </div>

      {/* 진행 중 알람 카드 */}
      <section style={{ margin: '24px 0' }}>
        <div className="sb-h">
          <span className="label-en">{t('dashboard.alarm.title')}</span>
          <span className="dim" style={{ fontSize: 11 }}>{activeAlarms.length}건</span>
        </div>

        {topAlarm ? (
          <div className="metric-card" style={{ borderLeft: `3px solid ${SEVERITY_LABEL[topAlarm.severity].color}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <Badge status={topAlarm.severity === 'CRITICAL' ? 'fail' : topAlarm.severity === 'HIGH' ? 'warn' : 'info'}>
                  {SEVERITY_LABEL[topAlarm.severity].en} · {SEVERITY_LABEL[topAlarm.severity].ko}
                </Badge>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 8 }}>
                  {topAlarm.title}
                </div>
                <div className="dim" style={{ fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
                  {topAlarm.detail}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate(topAlarm.module === 'F' ? '/equipment' : topAlarm.module === 'D' ? '/compliance' : '/')}
              >
                {t('dashboard.alarm.view_all')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="dim" style={{ padding: 16, textAlign: 'center' }}>
            {t('dashboard.alarm.no_alarms')}
          </div>
        )}
      </section>

      {/* 6 모듈 카드 (RBAC dim) */}
      <div className="modules-grid">
        {modules.map((mod) => {
          const visible = isMenuVisible(mod.slug, user);
          const lockReason = getLockReason(mod.slug, user);
          const Wrapper: React.ElementType = visible ? Link : 'div';
          return (
            <Wrapper
              key={mod.letter}
              {...(visible ? { to: mod.path } : {})}
              className={`module-card ${visible ? '' : 'locked'}`}
              aria-disabled={!visible || undefined}
            >
              {/* 카드 타이틀 — 폰트 크기 강조 (label-en 14px → 18px, 굵기 800) */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div
                  className="label-en"
                  style={{
                    color: visible ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
                    fontSize: 18,
                    fontWeight: 800,
                    letterSpacing: '0.04em',
                    lineHeight: 1.2,
                  }}
                >
                  {mod.letter} · {t(mod.titleKey)}
                </div>
                {!visible && <Lock size={14} strokeWidth={1.5} />}
              </div>
              {/* 부제 — 비전공자 대상 한 줄 요약 */}
              <div
                className="dim"
                style={{
                  fontSize: 12.5,
                  marginTop: 4,
                  lineHeight: 1.45,
                  opacity: visible ? 0.85 : 0.55,
                }}
              >
                {mod.tagline}
              </div>
              <ul style={{ margin: '10px 0 0 0', paddingLeft: 18, fontSize: 13, lineHeight: 1.65 }}>
                {mod.bullets.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
              {!visible && lockReason && (
                <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                  ○ {t('dashboard.module_card.lock_label')}: {lockReason}
                </div>
              )}
            </Wrapper>
          );
        })}
      </div>

      {/* 시스템 정보 */}
      <section className="metric-card" style={{ marginTop: 24 }}>
        <div className="label-en" style={{ color: 'var(--hud-primary)', marginBottom: 12 }}>
          {t('dashboard.system.title')}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px 16px', fontSize: 13 }}>
          <span className="dim">{t('dashboard.system.llm')}</span>
          <span>{sys.llm.join(' · ')}</span>
          <span className="dim">{t('dashboard.system.vision')}</span>
          <span>{sys.vision.join(' · ')}</span>
          <span className="dim">{t('dashboard.system.embedding')}</span>
          <span>{sys.embedding}</span>
          <span className="dim">{t('dashboard.system.router')}</span>
          <span>{sys.router}</span>
          <span className="dim">{t('dashboard.system.ml')}</span>
          <span>{sys.ml}</span>
          <span className="dim">{t('dashboard.system.data')}</span>
          <span>
            사원 {sys.data.employees} · 에러 {sys.data.errorCodes} · 금형 {sys.data.molds} ·
            SPC {sys.data.spcProcesses}공정 · 용어 {sys.data.glossary} · Few-shot {sys.data.fewShotRag}
          </span>
          <span className="dim">{t('dashboard.system.rbac')}</span>
          <span>{sys.rbac}</span>
        </div>
      </section>
    </div>
  );
}
