// SecurityTab — 보안 감사 (알림 카드 + 시간대 히트맵 + 로그인 이력 표).

import { useEffect, useMemo, useState } from 'react';
import {
  fetchLoginHistory,
  fetchLoginStats,
  fetchSecurityAlerts,
  type LoginHistoryEntry,
  type LoginStatsResponse,
  type SecurityAlertsResponse,
} from '@api/admin';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { SecurityAlertCard } from '@components/admin/widgets/SecurityAlertCard';

function buildLoginHistoryMd(rows: LoginHistoryEntry[]): string {
  const lines = ['# 로그인 이력 보고서', '', `총 ${rows.length}건`, '',
    '| 타임스탬프 | 사번 | 이름 | IP | 결과 | 플래그 |',
    '|---|---|---|---|---|---|'];
  for (const r of rows) {
    lines.push(`| ${r.timestamp} | ${r.employee_id} | ${r.username || '—'} | ${r.ip_address || '—'} | ${r.success ? '성공' : '실패'} | ${r.flag ?? '—'} |`);
  }
  return lines.join('\n');
}

export function SecurityTab() {
  const myLevel = useAuthStore((s) => s.user?.role_level ?? 1);
  const [alerts, setAlerts] = useState<SecurityAlertsResponse | null>(null);
  const [stats, setStats] = useState<LoginStatsResponse | null>(null);
  const [history, setHistory] = useState<LoginHistoryEntry[]>([]);
  const [hours, setHours] = useState(24);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (myLevel < 4) return;
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
  }, [myLevel, hours, days]);

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

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>보안 감사는 HR_ADMIN(L4) 이상에게만 노출됩니다.</p>
      </div>
    );
  }

  const hourMax = Math.max(1, ...(stats?.hour_distribution ?? []).map((h) => h.count));

  return (
    <>
      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">SECURITY AUDIT</div>
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

      <div className="lg-grid lg-grid-2-1">
        <div className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-pill">로그인 시간대 분포</div>
            </div>
            <div className="lg-field" style={{ minWidth: 140 }}>
              <label>기간</label>
              <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>최근 7일</option>
                <option value={30}>최근 30일</option>
                <option value={90}>최근 90일</option>
              </select>
            </div>
          </div>

          <div className="lg-bars-v" style={{ height: 200 }}>
            {(stats?.hour_distribution ?? []).map((h) => (
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
            </div>
          </div>

          <div className="lg-stat-list">
            <div className="lg-stat-row"><span>총 시도</span><b>{stats?.total_logins ?? 0}</b></div>
            <div className="lg-stat-row"><span>성공</span><b>{stats?.successful ?? 0}</b></div>
            <div className="lg-stat-row"><span>실패</span><b>{stats?.failed ?? 0}</b></div>
            <div className="lg-stat-row"><span>성공률</span><b>{(stats?.success_rate ?? 0).toFixed(1)}%</b></div>
            <div className="lg-stat-row"><span>고유 사용자</span><b>{stats?.unique_users ?? 0}</b></div>
            <div className="lg-stat-row"><span>잠금 계정</span><b>{stats?.locked_accounts ?? 0}</b></div>
          </div>
        </div>
      </div>

      <div className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">최근 로그인 이력</div>
          </div>
          <DownloadActions source="admin" basename="ajin-login-history" content={() => buildLoginHistoryMd(history)} />
        </div>

        <div className="lg-table-wrap">
          <table className="lg-table">
            <thead>
              <tr>
                <th>타임스탬프</th>
                <th>사번</th>
                <th>이름</th>
                <th>IP</th>
                <th>결과</th>
                <th>플래그</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r, i) => (
                <tr key={`${r.timestamp}-${i}`}>
                  <td className="mono">{r.timestamp}</td>
                  <td className="mono">{r.employee_id}</td>
                  <td>{r.username || '—'}</td>
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
              {history.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--hud-text-dim)', padding: 24 }}>이력이 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
