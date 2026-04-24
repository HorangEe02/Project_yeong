import { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Mail, Trash2, UserCog, Pause, Play, MapPin, Plus, Stethoscope } from 'lucide-react';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { UserStatusBadge } from '@/components/admin/UserStatusBadge';
import { AssignVisitPlanDialog } from '@/components/admin/AssignVisitPlanDialog';
import { PromoteToStaffDialog } from '@/components/admin/PromoteToStaffDialog';
import {
  changeUserRole,
  changeUserStatus,
  getUserDetail,
  sendPasswordResetFor,
  softDeleteUser,
} from '@/services/adminUsers';
import { clearVisitPlan, getVisitPlan, isPlanExpired } from '@/services/visitPlan';
import { getPOIById } from '@/data/hospital/pois';
import type { AdminUserRow } from '@/types/admin';
import type { UserRole } from '@/types/auth';
import type { VisitPlan } from '@/types/visit-plan';
import { formatDate, formatDateTime, formatRoleLabel } from '@/utils/format';
import { useAuthStore } from '@/stores/authStore';

export function AdminUserDetailPage() {
  const { uid = '' } = useParams();
  const actorUid = useAuthStore((s) => s.user?.uid);
  const [row, setRow] = useState<AdminUserRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<
    { tone: 'ok' | 'err'; text: string } | null
  >(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [visitPlan, setVisitPlanState] = useState<VisitPlan | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [confirmClearPlan, setConfirmClearPlan] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [detail, plan] = await Promise.all([
        getUserDetail(uid),
        getVisitPlan(uid),
      ]);
      setRow(detail);
      setVisitPlanState(plan);
    } finally {
      setLoading(false);
    }
  }, [uid]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const act = async (fn: () => Promise<void>, ok: string) => {
    setMessage(null);
    try {
      await fn();
      setMessage({ tone: 'ok', text: ok });
      await refresh();
    } catch (err) {
      setMessage({
        tone: 'err',
        text: err instanceof Error ? err.message : String(err),
      });
    }
  };

  const isSelf = actorUid === uid;

  return (
    <AdminLayout
      title="사용자 상세"
      actions={
        <Link
          to="/admin/users"
          className="flex items-center gap-1 rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          목록으로
        </Link>
      }
    >
      {loading ? (
        <p className="text-sm text-on-surface-variant">불러오는 중...</p>
      ) : !row ? (
        <p className="text-sm text-on-surface-variant">사용자를 찾을 수 없습니다.</p>
      ) : (
        <div className="flex flex-col gap-5">
          <section className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-on-surface">
                  {row.displayName ?? '(이름 없음)'}
                </h2>
                <p className="mt-0.5 text-sm text-on-surface-variant">{row.email}</p>
              </div>
              <UserStatusBadge status={row.status} />
            </div>

            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <Field label="역할" value={formatRoleLabel(row.role)} />
              <Field label="UID" value={row.uid} mono />
              <Field label="소속" value={row.department ?? '-'} />
              <Field label="가입일" value={formatDate(row.createdAt)} />
              <Field label="최종 수정" value={formatDateTime(row.updatedAt)} />
              <Field label="공급자" value={row.providers.join(', ') || '-'} />
            </dl>
          </section>

          {message && (
            <p
              className={`rounded-lg px-3 py-2 text-xs ${
                message.tone === 'ok'
                  ? 'bg-green-50 text-green-700'
                  : 'bg-red-50 text-red-600'
              }`}
            >
              {message.text}
            </p>
          )}

          {/* 방문 계획 섹션 */}
          <section className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-on-surface">
                <MapPin className="h-4 w-4 text-primary" />
                방문 계획
              </h3>
              <button
                type="button"
                onClick={() => setAssignOpen(true)}
                className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
              >
                <Plus className="h-3 w-3" />
                {visitPlan && !isPlanExpired(visitPlan) ? '재배정' : '배정'}
              </button>
            </div>
            <VisitPlanSummary plan={visitPlan} onClear={() => setConfirmClearPlan(true)} />
          </section>

          <section className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h3 className="mb-3 text-sm font-semibold text-on-surface">액션</h3>
            {isSelf && (
              <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                본인 계정에는 역할/상태 변경 액션이 제한됩니다.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <select
                disabled={isSelf}
                value={row.role}
                onChange={(e) =>
                  act(
                    () => changeUserRole(row.uid, e.target.value as UserRole),
                    '역할이 변경되었습니다',
                  )
                }
                className="rounded-lg border border-surface-container-high bg-surface px-3 py-2 text-xs disabled:opacity-50"
              >
                <option value="patient">환자</option>
                <option value="staff">의료진</option>
                <option value="admin">관리자</option>
              </select>

              {row.status === 'active' ? (
                <ActionButton
                  icon={<Pause className="h-3.5 w-3.5" />}
                  onClick={() =>
                    act(
                      () => changeUserStatus(row.uid, 'suspended'),
                      '계정을 비활성화했습니다',
                    )
                  }
                  disabled={isSelf}
                >
                  비활성화
                </ActionButton>
              ) : row.status === 'suspended' ? (
                <ActionButton
                  icon={<Play className="h-3.5 w-3.5" />}
                  onClick={() =>
                    act(
                      () => changeUserStatus(row.uid, 'active'),
                      '계정을 활성화했습니다',
                    )
                  }
                >
                  활성화
                </ActionButton>
              ) : null}

              <ActionButton
                icon={<Mail className="h-3.5 w-3.5" />}
                onClick={() =>
                  row.email
                    ? act(
                        () => sendPasswordResetFor(row.uid, row.email!),
                        '비밀번호 재설정 메일을 발송했습니다',
                      )
                    : setMessage({ tone: 'err', text: '이메일이 없습니다' })
                }
              >
                비밀번호 재설정 메일
              </ActionButton>

              {row.role === 'patient' && (
                <ActionButton
                  icon={<Stethoscope className="h-3.5 w-3.5" />}
                  onClick={() => setPromoteOpen(true)}
                  disabled={isSelf}
                >
                  의료진으로 승격
                </ActionButton>
              )}

              <ActionButton
                icon={<UserCog className="h-3.5 w-3.5" />}
                disabled
              >
                활동 이력
              </ActionButton>

              <ActionButton
                icon={<Trash2 className="h-3.5 w-3.5" />}
                danger
                disabled={isSelf || row.status === 'deleted'}
                onClick={() => setDeleteOpen(true)}
              >
                계정 삭제 (소프트)
              </ActionButton>
            </div>
          </section>
        </div>
      )}

      <ConfirmDialog
        open={deleteOpen}
        title="계정을 삭제하시겠습니까?"
        description="프로필이 익명화되고 상태가 '삭제됨'으로 변경됩니다. 연관된 방문 계획도 함께 삭제됩니다."
        requireText="DELETE"
        danger
        confirmLabel="삭제"
        onClose={() => setDeleteOpen(false)}
        onConfirm={() =>
          act(() => softDeleteUser(uid), '계정이 삭제되었습니다')
        }
      />

      <AssignVisitPlanDialog
        open={assignOpen}
        uid={uid}
        displayName={row?.displayName ?? null}
        existingPlan={visitPlan}
        hospitalId={row?.hospitalId}
        onClose={() => setAssignOpen(false)}
        onAssigned={() =>
          act(() => Promise.resolve(), '방문 계획이 배정되었습니다')
        }
      />

      <ConfirmDialog
        open={confirmClearPlan}
        title="방문 계획을 삭제할까요?"
        description="환자의 계획이 서버에서 제거됩니다."
        danger
        confirmLabel="삭제"
        onClose={() => setConfirmClearPlan(false)}
        onConfirm={() => act(() => clearVisitPlan(uid), '방문 계획이 삭제되었습니다')}
      />

      <PromoteToStaffDialog
        open={promoteOpen}
        uid={uid}
        displayName={row?.displayName ?? null}
        onClose={() => setPromoteOpen(false)}
        onPromoted={() =>
          act(() => Promise.resolve(), '의료진으로 승격되었습니다')
        }
      />
    </AdminLayout>
  );
}

function VisitPlanSummary({
  plan,
  onClear,
}: {
  plan: VisitPlan | null;
  onClear: () => void;
}) {
  if (!plan) {
    return (
      <p className="rounded-lg bg-surface-container-low p-3 text-xs text-on-surface-variant">
        배정된 방문 계획이 없습니다.
      </p>
    );
  }
  const expired = isPlanExpired(plan);
  const sourceLabel = plan.source === 'patient' ? '본인' : plan.source === 'staff' ? '의료진' : '관리자';
  const summary = plan.waypoints
    .map((w) => getPOIById(w.poiId)?.shortName ?? w.poiId)
    .join(' → ');
  return (
    <div className={`flex flex-col gap-2 rounded-lg p-3 ${expired ? 'bg-surface-container-high' : 'bg-primary/5'}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={`rounded-full px-2 py-0.5 font-medium ${
            expired
              ? 'bg-surface-container-high text-on-surface-variant'
              : 'bg-primary/10 text-primary'
          }`}
        >
          {expired ? '만료됨' : `유효 · ${Math.max(0, Math.round((plan.expiresAt - Date.now()) / 3_600_000))}시간 남음`}
        </span>
        <span className="text-on-surface-variant">
          입력: {sourceLabel}
        </span>
        {plan.autoSendOptIn && (
          <span className="rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700">
            자동 전송
          </span>
        )}
      </div>
      <p className="text-sm text-on-surface">{summary}</p>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onClear}
          className="flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-2 py-1 text-[11px] text-red-600"
        >
          <Trash2 className="h-3 w-3" />
          계획 삭제
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-on-surface-variant">
        {label}
      </dt>
      <dd
        className={`mt-0.5 text-on-surface ${mono ? 'font-mono text-xs' : 'text-sm'}`}
      >
        {value}
      </dd>
    </div>
  );
}

function ActionButton({
  icon,
  onClick,
  disabled,
  danger,
  children,
}: {
  icon?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium disabled:opacity-50 ${
        danger
          ? 'border-red-300 bg-red-50 text-red-600'
          : 'border-surface-container-high bg-surface text-on-surface'
      }`}
    >
      {icon}
      {children}
    </button>
  );
}
