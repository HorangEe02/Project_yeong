import { useEffect, useState } from 'react';
import { Users, Stethoscope, User, Shield, UserX, Activity } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { StatCard } from '@/components/admin/StatCard';
import { listUsers, computeStats } from '@/services/adminUsers';
import { subscribeAllSessions } from '@/services/adminSessions';
import { listAudit } from '@/services/auditLog';
import type { AdminStats, AuditLogEntry } from '@/types/admin';
import { formatActionLabel, formatRelativeTime } from '@/utils/format';

export function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [audit, setAudit] = useState<AuditLogEntry[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [activeSessions, setActiveSessions] = useState(0);

  useEffect(() => {
    const unsub = subscribeAllSessions((sessions) => {
      setActiveSessions(
        sessions.filter((s) => s.status !== 'completed').length,
      );
    });
    return unsub;
  }, []);

  useEffect(() => {
    void (async () => {
      const [usersRes, logsRes] = await Promise.allSettled([
        listUsers(),
        listAudit(6),
      ]);
      if (usersRes.status === 'fulfilled') {
        setStats(computeStats(usersRes.value, activeSessions));
        setStatsError(null);
      } else {
        setStatsError(
          usersRes.reason instanceof Error
            ? usersRes.reason.message
            : String(usersRes.reason),
        );
      }
      if (logsRes.status === 'fulfilled') {
        setAudit(logsRes.value);
        setAuditError(null);
      } else {
        setAuditError(
          logsRes.reason instanceof Error
            ? logsRes.reason.message
            : String(logsRes.reason),
        );
      }
    })();
  }, [activeSessions]);

  return (
    <AdminLayout
      title="대시보드"
      description="운영 지표와 최근 활동을 요약합니다"
    >
      {statsError && (
        <div className="mb-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          사용자 통계 조회 실패: {statsError}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="전체 사용자"
          value={stats?.totalUsers ?? '-'}
          icon={<Users className="h-4 w-4" />}
        />
        <StatCard
          label="의료진"
          value={stats?.staffCount ?? '-'}
          icon={<Stethoscope className="h-4 w-4" />}
          tone="primary"
        />
        <StatCard
          label="환자"
          value={stats?.patientCount ?? '-'}
          icon={<User className="h-4 w-4" />}
        />
        <StatCard
          label="관리자"
          value={stats?.adminCount ?? '-'}
          icon={<Shield className="h-4 w-4" />}
          tone="primary"
        />
        <StatCard
          label="비활성 계정"
          value={stats?.suspendedCount ?? '-'}
          icon={<UserX className="h-4 w-4" />}
          tone="warn"
        />
        <StatCard
          label="활성 세션"
          value={activeSessions}
          icon={<Activity className="h-4 w-4" />}
          tone="ok"
        />
      </div>

      <div className="mt-6 rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-on-surface">최근 감사 로그</h2>
          <a href="/admin/audit" className="text-xs text-primary no-underline">
            전체 보기
          </a>
        </div>
        {auditError ? (
          <p className="text-xs text-amber-700">
            감사 로그를 불러올 수 없습니다 ({auditError}). 권한 정책을 확인하세요.
          </p>
        ) : audit.length === 0 ? (
          <p className="text-xs text-on-surface-variant">기록된 이벤트가 없습니다.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-surface-container-high">
            {audit.map((e) => (
              <li key={e.id} className="flex items-center justify-between py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm text-on-surface">
                    {formatActionLabel(e.action)}{' '}
                    <span className="text-on-surface-variant">— {e.target}</span>
                  </p>
                  <p className="truncate text-xs text-on-surface-variant/80">
                    by {e.actorEmail ?? e.actorUid}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-on-surface-variant">
                  {formatRelativeTime(e.timestamp)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AdminLayout>
  );
}
