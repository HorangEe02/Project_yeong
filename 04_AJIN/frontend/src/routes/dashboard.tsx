// Dashboard 정밀 폴리싱 — 환영 헤더 + 카운트업 메트릭 + RBAC dim 카드 + 알람 카드 + 시스템 정보

import { useEffect, useMemo, useState } from 'react';
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
import { Badge } from '@components/ui/Badge';
import { Button } from '@components/ui/Button';
import { isMenuVisible, getLockReason } from '@lib/rbac';
import { SEVERITY_LABEL, type Alarm, type AlarmSeverity } from '@/types/alarms';
import { useEquipmentRTDB } from '@hooks/useEquipmentRTDB';
import { useIsMobile, useIsTablet } from '@hooks/useBreakpoint';
import { AJINMobileDashboard } from '@components/uikit/AJINMobileDashboard';
import { AJINTabletDashboard } from '@components/uikit/AJINTabletDashboard';
import { useComplianceAlarms } from '@hooks/useComplianceAlarms';
import { useComplianceAlarmsSse } from '@hooks/useComplianceAlarmsSse';
import { useComplianceRTDB, type ComplianceRtdbAlarm } from '@hooks/useComplianceRTDB';
import type { RecentViolation } from '@/types/equipment';
import { WidgetGrid } from '@components/dashboard/widgets/WidgetGrid';
import { detectPersona, PERSONA_WIDGETS, PERSONA_LABELS } from '@components/dashboard/personas';
import { useFeatureDFlags } from '@lib/featureFlags';

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
      path: '/onboarding', slug: 'onboarding', titleKey: 'modules.onboarding', letter: 'C',
      tagline: '사내 용어·업무 절차·사수까지 — 첫 주 가이드',
      bullets: [
        `업무 매뉴얼 ${c?.sopGuides ?? 8}종 · 협업 시나리오 ${c?.collaborations ?? 5}종`,
        '부서별 빠른 질문 + AI 도우미 prefill 이동',
        '도면·부품 사진 업로드 → Vision Q&A',
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
    // v4.7 — F=시스템 관리(/admin) + G=인사/HR(/hr) 분리 복구. E=설비(구 F) swap 유지.
    {
      path: '/equipment', slug: 'equipment', letter: 'E', titleKey: 'modules.equipment',
      tagline: '설비 이상을 사전에 감지·예측',
      bullets: [
        '공정 이상을 8가지 규칙으로 자동 감지',
        `금형 ${c?.molds ?? 25}대 고장 가능성 AI 예측`,
        '설비 다음 상태 확률 분석',
      ],
    },
    {
      path: '/admin', slug: 'admin', letter: 'F', titleKey: 'modules.admin',
      tagline: '관리자 콘솔 — 보안 감사·시나리오·시스템 도구',
      bullets: [
        `직급별 접근 권한 ${c?.roles ?? 6}단계 + 보안 감사 로그`,
        '협업 시나리오 관리·feature flags·시스템 진단',
        'AI 활용 분석·검색 분석',
      ],
    },
    // v4.8 — 기능 G(HR) 카드 제거
  ];
}

// RTDB live_alarms 의 RecentViolation → 대시보드 Alarm 형태로 어댑트.
// SPC 위반은 모듈 F (설비) 로 매핑. severity 매핑: critical→CRITICAL, warning→HIGH, info→MEDIUM.
function adaptViolation(v: RecentViolation): Alarm {
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

// useComplianceRTDB 가 반환하는 D 알람 → 공통 Alarm 카드 schema.
// alarm_aggregator → firebase_rtdb.push_alarm 체인을 거쳐 /live_alarms path 에
// push 된 module='D' 알람을 그대로 매핑한다.
function adaptComplianceRtdb(a: ComplianceRtdbAlarm): Alarm {
  return {
    id: a.id,
    severity: a.severity,
    title: a.title || (a.regulation_id ? `법규 변경 — ${a.regulation_id}` : '컴플라이언스 알림'),
    detail: a.detail || (a.effective_date ? `시행일 ${a.effective_date}` : ''),
    module: 'D',
    timestamp: new Date(a.timestamp).toISOString(),
    acknowledged: a.acknowledged,
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

  // 시스템 정보(LLM/비전/임베딩 등) — 관리자(role_level ≥ 5) 전용 → 그 외에는 fetch 생략.
  const [sysInfo, setSysInfo] = useState<SystemInfoResponse | null>(null);
  const isAdminFetch = (user?.role_level ?? 0) >= 5;
  useEffect(() => {
    if (!isAdminFetch) return;
    let cancelled = false;
    getSystemInfo()
      .then((info) => { if (!cancelled) setSysInfo(info as SystemInfoResponse); })
      .catch(() => { /* 실패 시 sys 필드는 '—' 표기 */ });
    return () => { cancelled = true; };
  }, [isAdminFetch]);
  const sys = {
    llm: sysInfo?.llm ?? [],
    vision: sysInfo?.vision ?? [],
    embedding: sysInfo?.embedding ?? '',
    router: sysInfo?.router ?? '',
    ml: sysInfo?.ml ?? '',
    rbac: sysInfo?.rbac ?? '',
    data: sysInfo?.data,
  };

  const lastLoginText = user
    ? formatRelativeTime((user as { last_login?: string }).last_login ?? null, i18n.language)
    : '';

  // 페르소나 분류 + 위젯 매핑 (user 의 role_level/role_name/department 기반)
  const personaId = useMemo(() => detectPersona(user), [user]);

  // SYS 정보 (LLM/비전/임베딩 모델 라벨 + 데이터 카운트 + RBAC) 는 관리자 전용.
  // _shell.tsx 의 SYS 우측 패널과 동일 임계값 (role_level >= 5).
  const isAdmin = (user?.role_level ?? 0) >= 5;
  const featureDFlags = useFeatureDFlags();
  const personaWidgets = useMemo(
    () => PERSONA_WIDGETS[personaId].filter((widget) => {
      if (widget.id.includes('supplier') && !featureDFlags.d5_supply) return false;
      if (widget.id.includes('tariff') && !featureDFlags.d3_whatif) return false;
      return true;
    }),
    [featureDFlags.d3_whatif, featureDFlags.d5_supply, personaId],
  );
  const personaLabel = PERSONA_LABELS[personaId];

  // RTDB live_alarms 구독 — F 모듈 SPC 위반 (Cloud Run + Firebase RTDB)
  const rtdbViolations = useEquipmentRTDB();
  const liveSpcAlarms: Alarm[] = rtdbViolations.map(adaptViolation);

  // v4.2 P5 — D 컴플라이언스 알람 (1차 통로 — REST polling/SSE).
  // Native EventSource cannot attach CSRF headers for cookie-auth POST flows,
  // so release builds default to authenticated polling. SSE remains opt-in.
  const complianceSseEnabled = import.meta.env.VITE_COMPLIANCE_ALARMS_SSE === 'true';
  const [useSse, setUseSse] = useState(complianceSseEnabled && typeof EventSource !== 'undefined');
  const sseAlarms = useComplianceAlarmsSse({
    enabled: useSse,
    onClose: () => setUseSse(false),
  });
  const polledAlarms = useComplianceAlarms({ enabled: !useSse });
  const liveDAlarmsRest = useSse ? sseAlarms : polledAlarms;

  // v4.x — D 컴플라이언스 알람 (2차 통로 — RTDB).
  // alarm_aggregator → firebase_rtdb.push_alarm 체인이 /live_alarms 에 push 한
  // module='D' 알람. F SPC 와 동일 통로를 공유 → 실시간성·응답성 일치.
  const rtdbDRaw = useComplianceRTDB();
  const liveDAlarmsRtdb: Alarm[] = rtdbDRaw.map(adaptComplianceRtdb);

  // 양쪽 통로 머지 — id 기준 dedup (RTDB push 가 가장 빠르므로 우선).
  const dAlarmMap = new Map<string, Alarm>();
  for (const a of liveDAlarmsRest) dAlarmMap.set(a.id, a);
  for (const a of liveDAlarmsRtdb) dAlarmMap.set(a.id, a);
  const liveDAlarms = Array.from(dAlarmMap.values());

  const activeAlarms = [...liveSpcAlarms, ...liveDAlarms].filter((a) => !a.acknowledged);
  const topAlarm = [...activeAlarms].sort((a, b) => {
    const order: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return order[a.severity] - order[b.severity];
  })[0];

  // v3.5 모바일 / 태블릿 — uiux MobDashboard / PadDashboard 패턴 풀스크린.
  const isMobileDashboard = useIsMobile();
  const isTabletDashboard = useIsTablet();
  const adaptedTopAlarm = topAlarm ? {
    id: topAlarm.id,
    severity: topAlarm.severity,
    title: topAlarm.title,
    detail: topAlarm.detail,
    module: (topAlarm.module === 'D' ? 'D' : 'F') as 'F' | 'D',
  } : null;
  if (isMobileDashboard) {
    return <AJINMobileDashboard activeAlarmsCount={activeAlarms.length} topAlarm={adaptedTopAlarm} />;
  }
  if (isTabletDashboard) {
    return <AJINTabletDashboard activeAlarmsCount={activeAlarms.length} topAlarm={adaptedTopAlarm} />;
  }

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

      {/* 페르소나별 위젯 그리드 — 사용자 역할/부서/직급에 맞춘 KPI 자동 큐레이션.
          기존 4 메트릭 카드 (가동 설비 / 금일 알람 / 법규 미해결 / 시스템 응답) 는
          P9 SYS_ADMIN 페르소나에 동일하게 매핑되어 보존된다.
          모바일은 함수 상단의 isMobileDashboard early-return 으로 AJINMobileDashboard 가
          전용 렌더링하므로 본 desktop layout 은 비-모바일 viewport 에서만 동작. */}
      {/* v3.5 — Neural Expressive 브랜드 orb (data-neural=on 시 발광 애니메이션) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '8px 0 12px' }}>
        <div className="ne-orb sm" aria-hidden style={{ flexShrink: 0 }} />
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span className="lg-eyebrow" style={{ fontSize: 10 }}>{personaLabel.en}</span>
          <span className="dim" style={{ fontSize: 12 }}>· {personaLabel.ko} 맞춤 화면</span>
        </div>
      </div>
      <div className="ne-brief-grid-wrap">
        <WidgetGrid widgets={personaWidgets} />
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
                onClick={() => {
                  if (topAlarm.module === 'F') {
                    navigate('/equipment');
                  } else if (topAlarm.module === 'D') {
                    // alarm.id = "D-{source}-{regulation_id}" — regulation_id 추출 후 deep-link
                    const m = topAlarm.id.match(/^D-[a-z_]+-(.+)$/);
                    navigate(m ? `/compliance?focus=${encodeURIComponent(m[1])}` : '/compliance');
                  } else {
                    navigate('/');
                  }
                }}
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

      {/* 시스템 정보 — 관리자(role_level ≥ 5) 전용. 일반 사용자는 비노출. */}
      {isAdmin && (
        <section className="metric-card" style={{ marginTop: 24 }}>
          <div className="label-en" style={{ color: 'var(--hud-primary)', marginBottom: 12 }}>
            {t('dashboard.system.title')}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px 16px', fontSize: 13 }}>
            <span className="dim">{t('dashboard.system.llm')}</span>
            <span>{sys.llm.length ? sys.llm.join(' · ') : '—'}</span>
            <span className="dim">{t('dashboard.system.vision')}</span>
            <span>{sys.vision.length ? sys.vision.join(' · ') : '—'}</span>
            <span className="dim">{t('dashboard.system.embedding')}</span>
            <span>{sys.embedding || '—'}</span>
            <span className="dim">{t('dashboard.system.router')}</span>
            <span>{sys.router || '—'}</span>
            <span className="dim">{t('dashboard.system.ml')}</span>
            <span>{sys.ml || '—'}</span>
            <span className="dim">{t('dashboard.system.data')}</span>
            <span>
              {sys.data
                ? `사원 ${sys.data.employees} · 에러 ${sys.data.errorCodes} · 금형 ${sys.data.molds} · SPC ${sys.data.spcProcesses}공정 · 용어 ${sys.data.glossary} · Few-shot ${sys.data.fewShotRag}`
                : '—'}
            </span>
            <span className="dim">{t('dashboard.system.rbac')}</span>
            <span>{sys.rbac || '—'}</span>
          </div>
        </section>
      )}
    </div>
  );
}
