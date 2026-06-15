// SecurityAlertsTab — 보안 알림 (알림 카드 + 달력 히트맵 + 일별 시간대 분포 + 이력 표).
// v4.9 — 기간 dropdown 제거, LoginCalendar 도입, URL ?date= 동기화, 부서·역할 필터.
// PR-E4 (6→3 탭 통합) — 기존 SecurityTab 에서 rename.
// PR-E5 — 5 dashboard 컴포넌트 통합 (AnomalyAlertFeed, TimeHeatmap, PermissionViolationTable, FeatureUsageChart, ChangeAuditTimeline).

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  fetchArchivedLogins,
  fetchAuditAnomalyFeed,
  fetchAuditDashboard,
  fetchLoginHistory,
  fetchLoginStats,
  fetchSecurityAlerts,
  type AnomalyFeedItem,
  type AuditDashboardResponse,
  type LoginHistoryEntry,
  type LoginStatsResponse,
  type SecurityAlertsResponse,
} from '@api/admin';
import { AnomalyAlertFeed } from '@components/admin/audit/AnomalyAlertFeed';
import { TimeHeatmap } from '@components/admin/audit/TimeHeatmap';
import { PermissionViolationTable } from '@components/admin/audit/PermissionViolationTable';
import { FeatureUsageChart } from '@components/admin/audit/FeatureUsageChart';
import { ChangeAuditTimeline } from '@components/admin/audit/ChangeAuditTimeline';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { SecurityAlertCard } from '@components/admin/widgets/SecurityAlertCard';
import { LoginCalendar } from '@components/admin/LoginCalendar';
import { WeeklyHeatmap } from '@components/admin/WeeklyHeatmap';
import { TwoFactorEnrollModal } from '@components/admin/TwoFactorEnrollModal';
import { disable2FA, fetch2FAStatus, regenBackupCodes, extractError } from '@api/auth';
import { useToast } from '@store/toast';

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
type ViewMode = 'daily' | 'weekly';

function buildLoginHistoryMd(rows: LoginHistoryEntry[]): string {
  const lines = ['# 로그인 이력 보고서', '', `총 ${rows.length}건`, '',
    '| 타임스탬프 | 사번 | 이름 | 부서 | 역할 | IP | 결과 | 플래그 |',
    '|---|---|---|---|---|---|---|---|'];
  for (const r of rows) {
    lines.push(
      `| ${r.timestamp} | ${r.employee_id} | ${r.username || '—'} ` +
      `| ${r.department || '—'} | ${r.role_name || '—'} ` +
      `| ${r.ip_address || '—'} | ${r.success ? '성공' : '실패'} | ${r.flag ?? '—'} |`,
    );
  }
  return lines.join('\n');
}

export function SecurityAlertsTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);
  const { addToast } = useToast();
  const [alerts, setAlerts] = useState<SecurityAlertsResponse | null>(null);
  const [stats, setStats] = useState<LoginStatsResponse | null>(null);
  const [history, setHistory] = useState<LoginHistoryEntry[]>([]);
  const [hours, setHours] = useState(24);
  const [days, setDays] = useState(90);   // v4.9 — 달력 90일치 fetch (월 navigation 위해 넉넉히)
  const [error, setError] = useState<string | null>(null);

  // PR-E5 — Audit Dashboard 상태
  const [anomalyFeed, setAnomalyFeed] = useState<AnomalyFeedItem[]>([]);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [dashboard, setDashboard] = useState<AuditDashboardResponse | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardPeriod, setDashboardPeriod] = useState<'day' | 'week' | 'month'>('week');
  // sub-tab 상태: 0=실시간알람, 1=시간대패턴, 2=권한위반, 3=사용ROI, 4=데이터변경
  const [auditSubTab, setAuditSubTab] = useState(0);

  // v4.9 — URL ?date= 동기화 + 부서·역할 필터 + 월/연 navigation
  const [params, setParams] = useSearchParams();
  const rawDate = params.get('date');
  const selectedDate = rawDate && DATE_RE.test(rawDate) ? rawDate : null;

  const today = useMemo(() => new Date(), []);
  const [viewYear, setViewYear] = useState<number>(() => {
    if (selectedDate) return Number(selectedDate.slice(0, 4));
    return today.getFullYear();
  });
  const [viewMonth, setViewMonth] = useState<number>(() => {
    if (selectedDate) return Number(selectedDate.slice(5, 7));
    return today.getMonth() + 1;
  });

  const [deptFilter, setDeptFilter] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('');

  // v4.9.2 — 90일 초과 일자 archived 이력 (BigQuery audit)
  const [archivedHistory, setArchivedHistory] = useState<LoginHistoryEntry[] | null>(null);
  const [archivedLoading, setArchivedLoading] = useState(false);
  const [archivedAvailable, setArchivedAvailable] = useState<boolean | null>(null);

  // v4.9.2 — 일별 (달력) / 주간 (7×24 heatmap) 모드 토글
  const [viewMode, setViewMode] = useState<ViewMode>('daily');

  // v4.7 Feature E Phase 3 — 2FA 상태 + enroll modal
  const [twoFAEnabled, setTwoFAEnabled] = useState<boolean | null>(null);
  const [enrollModalOpen, setEnrollModalOpen] = useState(false);
  const [twoFABusy, setTwoFABusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch2FAStatus().then((r) => {
      if (!cancelled) setTwoFAEnabled(r.enabled);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRegenBackup = async () => {
    const pw = window.prompt('현재 비밀번호를 입력하세요 (백업 코드 재발급).');
    if (!pw) return;
    setTwoFABusy(true);
    try {
      const r = await regenBackupCodes(pw);
      addToast({
        type: 'success',
        message: `새 백업 코드 8개가 발급되었습니다. 첫 코드: ${r.backup_codes[0]} … (전체 다운로드 권장)`,
        duration: 8000,
      });
      // 다운로드 자동 트리거
      const text = ['# AJIN 2FA 백업 코드 (재발급)', '', ...r.backup_codes].join('\n');
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `ajin-2fa-backup-codes-${new Date().toISOString().slice(0, 10)}.txt`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      addToast({ type: 'error', message: extractError(e).detail, duration: 5000 });
    } finally {
      setTwoFABusy(false);
    }
  };

  const handleDisable2FA = async () => {
    const pw = window.prompt('현재 비밀번호를 입력하세요 (2FA 비활성화).');
    if (!pw) return;
    if (!window.confirm('정말 2단계 인증을 비활성화하시겠습니까? 보안 수준이 낮아집니다.')) return;
    setTwoFABusy(true);
    try {
      await disable2FA(pw);
      setTwoFAEnabled(false);
      addToast({ type: 'success', message: '2FA 가 비활성화되었습니다.', duration: 4000 });
    } catch (e) {
      addToast({ type: 'error', message: extractError(e).detail, duration: 5000 });
    } finally {
      setTwoFABusy(false);
    }
  };

  const setSelectedDate = (date: string | null) => {
    const next = new URLSearchParams(params);
    if (date) {
      next.set('date', date);
      // 선택 일자의 월·연으로 view 동기화
      setViewYear(Number(date.slice(0, 4)));
      setViewMonth(Number(date.slice(5, 7)));
    } else {
      next.delete('date');
    }
    setParams(next, { replace: false });
  };

  // G6 — 30초 자동 폴링 (마운트 시 1회 + 이후 매 30초).
  // 한계: Cloud Run 단일 컨테이너 SQLite 기반이라 멀티 인스턴스 일관성 부족 — v2.0 Firestore 이전 시 해소.
  useEffect(() => {
    if (myLevel < 4) return;
    const load = () => {
      Promise.all([
        fetchSecurityAlerts(hours),
        fetchLoginStats(days),
        fetchLoginHistory(50),
      ])
        .then(([a, s, h]) => {
          setAlerts(a);
          setStats(s);
          setHistory(h.history);
        })
        .catch((e) => setError((e as Error).message));
    };
    load();
    const t = window.setInterval(load, 30_000);
    return () => window.clearInterval(t);
  }, [myLevel, hours, days]);

  // PR-E5 — Anomaly feed 폴링 (60초)
  useEffect(() => {
    if (myLevel < 4) return;
    let cancelled = false;
    const load = () => {
      setAnomalyLoading(true);
      fetchAuditAnomalyFeed(hours)
        .then((r) => { if (!cancelled) setAnomalyFeed(r.items); })
        .catch(() => { /* 무시 — 기존 에러 표시 있음 */ })
        .finally(() => { if (!cancelled) setAnomalyLoading(false); });
    };
    load();
    const t = window.setInterval(load, 60_000);
    return () => { cancelled = true; window.clearInterval(t); };
  }, [myLevel, hours]);

  // PR-E5 — Dashboard (period 변경 시 재조회)
  useEffect(() => {
    if (myLevel < 4) return;
    let cancelled = false;
    setDashboardLoading(true);
    fetchAuditDashboard(dashboardPeriod)
      .then((r) => { if (!cancelled) setDashboard(r); })
      .catch(() => { /* 무시 */ })
      .finally(() => { if (!cancelled) setDashboardLoading(false); });
    return () => { cancelled = true; };
  }, [myLevel, dashboardPeriod]);

  const cards = useMemo(() => {
    const summary = alerts?.summary ?? { brute_force: 0, unusual_hour: 0, inactive_access: 0 };
    return [
      {
        kind: 'crit' as const,
        en: 'BRUTE FORCE',
        title: '무차별 대입',
        count: summary.brute_force,
        desc: '동일 계정 3회 이상 실패 → 자동 잠금 후보',
      },
      {
        kind: 'warn' as const,
        en: 'OFF-HOURS LOGIN',
        title: '야간 접근',
        count: summary.unusual_hour,
        desc: '22:00~06:00 로그인 (HR_ADMIN 알림)',
      },
      {
        kind: 'info' as const,
        en: 'INACTIVE ACCESS',
        title: '비활성 계정 접근',
        count: summary.inactive_access,
        desc: '비활성 계정으로 로그인 시도 감지',
      },
    ];
  }, [alerts]);

  // v4.9.2 — selectedDate 가 90일 초과 시 BigQuery archived fetch
  useEffect(() => {
    if (!selectedDate) {
      setArchivedHistory(null);
      setArchivedAvailable(null);
      return;
    }
    const targetMs = new Date(`${selectedDate}T00:00:00`).getTime();
    const daysAgo = (Date.now() - targetMs) / 86_400_000;
    if (daysAgo <= 90) {
      setArchivedHistory(null);  // 90일 이내 → SQLite history 사용
      setArchivedAvailable(null);
      return;
    }
    let cancelled = false;
    setArchivedLoading(true);
    fetchArchivedLogins(selectedDate)
      .then((res) => {
        if (cancelled) return;
        setArchivedHistory(res.history);
        setArchivedAvailable(res.available);
      })
      .catch(() => {
        if (cancelled) return;
        setArchivedHistory([]);
        setArchivedAvailable(false);
      })
      .finally(() => { if (!cancelled) setArchivedLoading(false); });
    return () => { cancelled = true; };
  }, [selectedDate]);

  // v4.9 — 부서·역할 필터 + selectedDate 적용된 history (client-side)
  // v4.9.2 — archivedHistory 가 있으면 그 source 사용 (90일 초과 일자)
  const filteredHistory = useMemo(() => {
    const useArchived = archivedHistory !== null;
    let h = useArchived ? archivedHistory! : history;
    if (deptFilter) h = h.filter((r) => (r.department ?? '') === deptFilter);
    if (roleFilter) h = h.filter((r) => (r.role_name ?? '') === roleFilter);
    if (selectedDate && !useArchived) h = h.filter((r) => r.timestamp.startsWith(selectedDate));
    return h;
  }, [history, archivedHistory, deptFilter, roleFilter, selectedDate]);

  // v4.9 — selectedDate 가 있으면 그 일자의 24h 분포 (history/archived 에서 계산), 없으면 backend stats
  // v4.9.2 — archivedHistory 가 있으면 그 source 사용 (90일 초과)
  const hourDistribution = useMemo(() => {
    if (!selectedDate) return stats?.hour_distribution ?? [];
    const bins: { hour: number; count: number; failed: number }[] = Array.from(
      { length: 24 },
      (_, h) => ({ hour: h, count: 0, failed: 0 }),
    );
    const source = archivedHistory ?? history.filter((x) => x.timestamp.startsWith(selectedDate));
    for (const r of source) {
      const hr = Number(r.timestamp.slice(11, 13));
      if (Number.isFinite(hr) && hr >= 0 && hr < 24) {
        bins[hr].count += 1;
        if (!r.success) bins[hr].failed += 1;
      }
    }
    return bins;
  }, [selectedDate, history, archivedHistory, stats]);

  const hourMax = Math.max(1, ...hourDistribution.map((h) => h.count));

  // v4.9 — 부서·역할 옵션 풀 (history 에서 도출)
  const deptOptions = useMemo(() => {
    const s = new Set<string>();
    for (const r of history) {
      if (r.department) s.add(r.department);
    }
    return Array.from(s).sort();
  }, [history]);
  const roleOptions = useMemo(() => {
    const s = new Set<string>();
    for (const r of history) {
      if (r.role_name) s.add(r.role_name);
    }
    return Array.from(s).sort();
  }, [history]);

  // 선택 일자의 통계 요약
  const dateStats = useMemo(() => {
    if (!selectedDate) return null;
    const rows = filteredHistory;
    const total = rows.length;
    const failed = rows.filter((r) => !r.success).length;
    const successful = total - failed;
    const unique = new Set(rows.map((r) => r.employee_id)).size;
    return { total, successful, failed, unique };
  }, [selectedDate, filteredHistory]);

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>보안 감사는 HR_ADMIN(L4) 이상에게만 노출됩니다.</p>
      </div>
    );
  }

  return (
    <>
      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}

      {/* v4.7 Feature E Phase 3 — 내 2FA 설정 */}
      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">2단계 인증 (2FA)</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              비밀번호 외에 인증 앱 6자리 코드로 추가 보호
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {twoFAEnabled === null && <span className="dim">상태 확인 중…</span>}
            {twoFAEnabled === true && (
              <>
                <span className="lg-state-pill ok">✓ 활성</span>
                <button
                  type="button"
                  className="lg-btn sm ghost"
                  onClick={handleRegenBackup}
                  disabled={twoFABusy}
                >
                  백업 코드 재발급
                </button>
                <button
                  type="button"
                  className="lg-btn sm ghost"
                  onClick={handleDisable2FA}
                  disabled={twoFABusy}
                >
                  비활성화
                </button>
              </>
            )}
            {twoFAEnabled === false && (
              <>
                <span className="lg-state-pill crit">미설정</span>
                <button
                  type="button"
                  className="lg-btn sm"
                  onClick={() => setEnrollModalOpen(true)}
                >
                  2FA 활성화
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      <TwoFactorEnrollModal
        isOpen={enrollModalOpen}
        onClose={() => setEnrollModalOpen(false)}
        onEnabled={() => setTwoFAEnabled(true)}
      />

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div className="lg-pill">SECURITY AUDIT</div>
              <span
                title="30초마다 자동 갱신 · 단일 컨테이너 SQLite 데이터 (v2.0 Firestore 마이그레이션 시 멀티 인스턴스 일관성 확보)"
                style={{
                  fontSize: 10,
                  padding: '2px 7px',
                  borderRadius: 4,
                  border: '1px solid var(--hud-green)',
                  color: 'var(--hud-green)',
                  fontFamily: 'var(--hud-font-mono)',
                  letterSpacing: '0.05em',
                }}
              >
                🔄 LIVE · 30s
              </span>
            </div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              최근 {hours}시간 이상 패턴 감지
            </div>
          </div>
          <div className="lg-field" style={{ minWidth: 140 }}>
            <label>관찰 기간</label>
            <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
              <option value={24}>24시간</option>
              <option value={72}>72시간</option>
              <option value={168}>7일</option>
            </select>
          </div>
        </div>

        <div className="lg-sec-grid">
          {cards.map((c) => (
            <SecurityAlertCard key={c.en} {...c} />
          ))}
        </div>
      </div>

      {/* v4.9 — 필터 영역 (달력 위) */}
      {(deptOptions.length > 0 || roleOptions.length > 0) && (
        <div className="lg-card" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="lg-pill">필터</div>
          {deptOptions.length > 0 && (
            <div className="lg-field" style={{ minWidth: 160 }}>
              <label>부서</label>
              <select value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}>
                <option value="">전체</option>
                {deptOptions.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          )}
          {roleOptions.length > 0 && (
            <div className="lg-field" style={{ minWidth: 160 }}>
              <label>역할</label>
              <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
                <option value="">전체</option>
                {roleOptions.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          )}
          {(deptFilter || roleFilter || selectedDate) && (
            <button
              type="button"
              className="lg-btn sm ghost"
              onClick={() => {
                setDeptFilter('');
                setRoleFilter('');
                setSelectedDate(null);
              }}
            >
              필터 초기화
            </button>
          )}
        </div>
      )}

      {/* v4.9.2 — 일별 / 주간 모드 토글 */}
      <div className="lg-card" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="lg-pill">보기 모드</div>
        <button
          type="button"
          className={'lg-btn sm' + (viewMode === 'daily' ? '' : ' ghost')}
          onClick={() => setViewMode('daily')}
        >📅 일별 (달력)</button>
        <button
          type="button"
          className={'lg-btn sm' + (viewMode === 'weekly' ? '' : ' ghost')}
          onClick={() => setViewMode('weekly')}
        >📊 주간 (7×24 heatmap)</button>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--hud-text-dim)' }}>
          {viewMode === 'daily'
            ? '월 달력 히트맵 · 일자 클릭 → 24h drill-down'
            : '최근 7일 시간대 분포 · 셀 클릭 → 일별 모드 전환'}
        </span>
      </div>

      {/* v4.9 — 좌측 달력/히트맵 + 우측 24h 분포·통계 (2-col, ≥1024px) */}
      <div className="lg-grid lg-grid-1-1">
        {viewMode === 'daily' ? (
          <LoginCalendar
            dailyCounts={stats?.daily_counts ?? []}
            selectedDate={selectedDate}
            onSelect={setSelectedDate}
            year={viewYear}
            month={viewMonth}
            onYearChange={setViewYear}
            onMonthChange={setViewMonth}
            onQuickRange={(d) => {
              setDays(d);
              setSelectedDate(null);
            }}
          />
        ) : (
          <div className="lg-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div className="lg-card-h">
              <div className="lg-pill">주간 시간대 heatmap</div>
              <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>최근 7일</span>
            </div>
            <WeeklyHeatmap
              history={history}
              onCellClick={(d) => {
                setViewMode('daily');
                setSelectedDate(d);
              }}
            />
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-pill">시간대 분포</div>
                <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
                  {selectedDate ? `${selectedDate} 0-23시 로그인 분포` : `최근 ${days}일 평균 시간대`}
                </div>
              </div>
            </div>
            <div className="lg-bars-v" style={{ height: 200 }}>
              {hourDistribution.map((h) => (
                <div key={h.hour} className="lg-bar-v">
                  <div
                    className={`lg-bar-fill ${h.failed > 0 ? 'blue' : ''}`}
                    style={{ height: `${Math.max(2, (h.count / hourMax) * 100)}%` }}
                    title={`${h.hour}시 — ${h.count}건 (실패 ${h.failed})`}
                  >
                    {h.count > 0 && <b>{h.count}</b>}
                  </div>
                  <div className="lbl">{h.hour}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-pill">로그인 통계</div>
                {selectedDate && (
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-primary)' }}>
                    {selectedDate} 기준
                  </div>
                )}
              </div>
            </div>
            <div className="lg-stat-list">
              {selectedDate && dateStats ? (
                <>
                  <div className="lg-stat-row"><span>총 시도</span><b>{dateStats.total}</b></div>
                  <div className="lg-stat-row"><span>성공</span><b>{dateStats.successful}</b></div>
                  <div className="lg-stat-row"><span>실패</span><b>{dateStats.failed}</b></div>
                  <div className="lg-stat-row"><span>고유 사용자</span><b>{dateStats.unique}</b></div>
                </>
              ) : (
                <>
                  <div className="lg-stat-row"><span>총 시도</span><b>{stats?.total_logins ?? 0}</b></div>
                  <div className="lg-stat-row"><span>성공</span><b>{stats?.successful ?? 0}</b></div>
                  <div className="lg-stat-row"><span>실패</span><b>{stats?.failed ?? 0}</b></div>
                  <div className="lg-stat-row"><span>성공률</span><b>{(stats?.success_rate ?? 0).toFixed(1)}%</b></div>
                  <div className="lg-stat-row"><span>고유 사용자</span><b>{stats?.unique_users ?? 0}</b></div>
                  <div className="lg-stat-row"><span>잠금 계정</span><b>{stats?.locked_accounts ?? 0}</b></div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">최근 로그인 이력</div>
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
              {selectedDate
                ? `${selectedDate} 일자 · ${filteredHistory.length}건`
                : `전체 · ${filteredHistory.length}건`}
              {(deptFilter || roleFilter) && ' · 필터 적용됨'}
              {archivedLoading && ' · 아카이브 조회 중…'}
              {archivedHistory !== null && archivedAvailable && (
                <span style={{ marginLeft: 8, color: 'var(--hud-primary)' }}>
                  📦 BigQuery archived
                </span>
              )}
              {archivedHistory !== null && archivedAvailable === false && (
                <span style={{ marginLeft: 8, color: 'var(--hud-orange)' }}>
                  ⚠️ archived 미설정 (인증 필요)
                </span>
              )}
            </div>
          </div>
          <DownloadActions source="admin" basename="ajin-login-history" content={() => buildLoginHistoryMd(filteredHistory)} />
        </div>

        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>타임스탬프</th>
                <th>사번</th>
                <th>이름</th>
                <th>부서</th>
                <th>역할</th>
                <th>IP</th>
                <th>결과</th>
                <th>플래그</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((r, i) => (
                <tr key={`${r.timestamp}-${i}`}>
                  <td className="mono">{r.timestamp}</td>
                  <td className="mono">{r.employee_id}</td>
                  <td>{r.username || '—'}</td>
                  <td>{r.department || <span className="dim">—</span>}</td>
                  <td>{r.role_name || <span className="dim">—</span>}</td>
                  <td className="mono">{r.ip_address || '—'}</td>
                  <td>
                    {r.success ? (
                      <span className="lg-state-pill ok">성공</span>
                    ) : (
                      <span className="lg-state-pill crit">실패</span>
                    )}
                  </td>
                  <td>
                    {r.flag === 'BRUTE' && <span className="lg-flag-pill crit">BRUTE</span>}
                    {r.flag === 'OFF-HOURS' && <span className="lg-flag-pill warn">OFF-HOURS</span>}
                    {!r.flag && <span className="dim">—</span>}
                  </td>
                </tr>
              ))}
              {filteredHistory.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}>
                  {selectedDate ? `${selectedDate} 일자 이력이 없습니다.` : '이력이 없습니다.'}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* PR-E5 — Audit Dashboard: 5 컴포넌트 통합 */}
      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">AUDIT DASHBOARD · PR-E5</div>
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--hud-text-dim)' }}>
              실시간 알람 · 시간대 패턴 · 권한 위반 · 사용 ROI · 데이터 변경
            </div>
          </div>
        </div>
        {/* Sub-tab 네비게이션 */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 16 }}>
          {[
            { idx: 0, label: '실시간 알람' },
            { idx: 1, label: '시간대 패턴' },
            { idx: 2, label: '권한 위반' },
            { idx: 3, label: '사용 ROI' },
            { idx: 4, label: '데이터 변경' },
          ].map(({ idx, label }) => (
            <button
              key={idx}
              type="button"
              className={`lg-btn sm${auditSubTab === idx ? '' : ' ghost'}`}
              onClick={() => setAuditSubTab(idx)}
            >
              {label}
            </button>
          ))}
        </div>

        {auditSubTab === 0 && (
          <AnomalyAlertFeed items={anomalyFeed} loading={anomalyLoading} />
        )}
        {auditSubTab === 1 && (
          <TimeHeatmap buckets={dashboard?.time_pattern ?? []} />
        )}
        {auditSubTab === 2 && (
          <PermissionViolationTable
            rows={dashboard?.permission_violations ?? []}
            loading={dashboardLoading}
          />
        )}
        {auditSubTab === 3 && (
          <FeatureUsageChart
            rows={dashboard?.feature_usage ?? []}
            loading={dashboardLoading}
            period={dashboardPeriod}
            onPeriodChange={(p) => setDashboardPeriod(p)}
          />
        )}
        {auditSubTab === 4 && (
          <ChangeAuditTimeline
            rows={dashboard?.change_audit ?? []}
            loading={dashboardLoading}
          />
        )}
      </div>
    </>
  );
}
