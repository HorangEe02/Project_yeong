// BulkRoleChangeModal.tsx — v4.8 F-Users 5-tab 고도화.
//
// 5 tab — 선택된 사용자들에 대해 일괄 작업 수행:
//   role        — 권한 변경 (bulkChangeRoles, /admin/users/bulk-role)
//   department  — 부서 변경 (updateUser loop, /admin/users/{id})
//   position    — 직급 변경 (updateUser loop, /admin/users/{id})
//   password    — 비밀번호 reset (resetUserPassword loop, /admin/users/{id}/reset-password)
//   retire      — 인원 삭제 / soft delete (retireUser loop, /admin/users/{id}/retire)
//
// 권한 정책 (backend admin.py 검증):
//   - L4 (HR_ADMIN) 이상만 modal 접근 (frontend canBulk = myLevel >= 4)
//   - 본인 자신 변경 차단 (백엔드)
//   - 본인보다 같거나 높은 권한 계정 수정/삭제 차단 (백엔드)
//   - 마지막 SYS_ADMIN 삭제 차단 (백엔드 admin.py L596)

import { useState } from 'react';
import {
  bulkChangeRoles,
  type BulkRoleChangeResult,
  updateUser,
  resetUserPassword,
  type ResetPasswordResult,
  retireUser,
} from '@api/management';

type Tab = 'role' | 'department' | 'position' | 'password' | 'retire';

const TABS: { id: Tab; label: string; desc: string }[] = [
  { id: 'role', label: '권한 변경', desc: '대상 권한(Level) 일괄 변경' },
  { id: 'department', label: '부서 변경', desc: '소속 부서 일괄 이동' },
  { id: 'position', label: '직급 변경', desc: '직급(사원/대리/과장/팀장 등) 일괄 변경' },
  { id: 'password', label: '비밀번호 reset', desc: '임시 비밀번호 발급 + must_change_pw=1' },
  { id: 'retire', label: '인원 삭제', desc: 'soft delete (is_active=0, 역할 INACTIVE)' },
];

const ROLE_OPTIONS: { value: number; label: string }[] = [
  { value: 1, label: 'L1 · EMPLOYEE' },
  { value: 2, label: 'L2 · MANAGER' },
  { value: 3, label: 'L3 · TEAM_LEAD' },
  { value: 4, label: 'L4 · HR_ADMIN' },
  { value: 5, label: 'L5 · SYS_ADMIN' },
];

interface BulkUserActionResult {
  succeeded: number;
  failed: number;
  failedIds: string[];
}

interface BulkRoleChangeModalProps {
  userIds: string[];
  onClose: () => void;
  onApplied?: (result: BulkRoleChangeResult | BulkUserActionResult) => void;
}

export function BulkRoleChangeModal({ userIds, onClose, onApplied }: BulkRoleChangeModalProps) {
  const [tab, setTab] = useState<Tab>('role');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkRoleChangeResult | BulkUserActionResult | null>(null);

  // tab-specific inputs
  const [targetRole, setTargetRole] = useState<number>(1);
  const [newDepartment, setNewDepartment] = useState('');
  const [newPosition, setNewPosition] = useState('');
  const [retireConfirm, setRetireConfirm] = useState(false);
  const [passwordResults, setPasswordResults] = useState<ResetPasswordResult[]>([]);

  const reset = () => {
    setError(null);
    setResult(null);
    setPasswordResults([]);
  };

  const switchTab = (next: Tab) => {
    setTab(next);
    reset();
  };

  const validateCommon = (): boolean => {
    if (userIds.length === 0) {
      setError('선택된 사용자가 없습니다.');
      return false;
    }
    if (reason.trim().length < 4) {
      setError('사유는 최소 4자 이상 입력하세요. (audit log 기록)');
      return false;
    }
    return true;
  };

  const runBulkLoop = async (
    op: (id: string) => Promise<unknown>,
  ): Promise<BulkUserActionResult> => {
    const results = await Promise.allSettled(userIds.map(op));
    const failedIds = results
      .map((r, i) => (r.status === 'rejected' ? userIds[i] : null))
      .filter((id): id is string => id !== null);
    return {
      succeeded: results.length - failedIds.length,
      failed: failedIds.length,
      failedIds,
    };
  };

  const handleRoleChange = async () => {
    if (!validateCommon()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await bulkChangeRoles(userIds, targetRole, reason.trim());
      setResult(r);
      onApplied?.(r);
    } catch (e) {
      setError((e as Error)?.message || '권한 변경 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleDepartment = async () => {
    if (!validateCommon()) return;
    if (newDepartment.trim().length < 2) {
      setError('새 부서명을 입력하세요. (최소 2자)');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await runBulkLoop((id) => updateUser(id, { department: newDepartment.trim() }));
      setResult(r);
      onApplied?.(r);
    } catch (e) {
      setError((e as Error)?.message || '부서 변경 실패');
    } finally {
      setLoading(false);
    }
  };

  const handlePosition = async () => {
    if (!validateCommon()) return;
    if (newPosition.trim().length < 1) {
      setError('새 직급을 입력하세요.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await runBulkLoop((id) => updateUser(id, { position: newPosition.trim() }));
      setResult(r);
      onApplied?.(r);
    } catch (e) {
      setError((e as Error)?.message || '직급 변경 실패');
    } finally {
      setLoading(false);
    }
  };

  const handlePassword = async () => {
    if (!validateCommon()) return;
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled(userIds.map((id) => resetUserPassword(id)));
      const succeededResults: ResetPasswordResult[] = [];
      const failedIds: string[] = [];
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          succeededResults.push(r.value);
        } else {
          failedIds.push(userIds[i]);
        }
      });
      setPasswordResults(succeededResults);
      const summary: BulkUserActionResult = {
        succeeded: succeededResults.length,
        failed: failedIds.length,
        failedIds,
      };
      setResult(summary);
      onApplied?.(summary);
    } catch (e) {
      setError((e as Error)?.message || '비밀번호 reset 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleRetire = async () => {
    if (!validateCommon()) return;
    if (!retireConfirm) {
      setError('"삭제 확인" 체크박스를 활성화하세요. (되돌리기 어려운 작업)');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await runBulkLoop((id) => retireUser(id, reason.trim()));
      setResult(r);
      onApplied?.(r);
      setRetireConfirm(false);
    } catch (e) {
      setError((e as Error)?.message || '인원 삭제 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    switch (tab) {
      case 'role':
        return handleRoleChange();
      case 'department':
        return handleDepartment();
      case 'position':
        return handlePosition();
      case 'password':
        return handlePassword();
      case 'retire':
        return handleRetire();
    }
  };

  const renderTabContent = () => {
    switch (tab) {
      case 'role':
        return (
          <div style={fieldRow}>
            <label style={fieldLabel}>대상 권한</label>
            <select
              value={targetRole}
              onChange={(e) => setTargetRole(parseInt(e.target.value, 10))}
              style={input}
            >
              {ROLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        );
      case 'department':
        return (
          <div style={fieldRow}>
            <label style={fieldLabel}>새 부서명</label>
            <input
              type="text"
              value={newDepartment}
              onChange={(e) => setNewDepartment(e.target.value)}
              placeholder="예: 생산기술팀"
              style={input}
            />
          </div>
        );
      case 'position':
        return (
          <div style={fieldRow}>
            <label style={fieldLabel}>새 직급</label>
            <input
              type="text"
              value={newPosition}
              onChange={(e) => setNewPosition(e.target.value)}
              placeholder="예: 팀장 / 과장 / 책임 / 전무"
              style={input}
            />
          </div>
        );
      case 'password':
        return (
          <div style={{ fontSize: 12, opacity: 0.85, padding: '8px 0', lineHeight: 1.5 }}>
            선택된 사용자 <strong>{userIds.length}</strong>명의 비밀번호를 임시 비밀번호로 reset.
            <br />
            다음 로그인 시 비밀번호 변경 강제 (must_change_pw=1).
            <br />
            성공 시 사용자별 임시 비밀번호 표시 (production 정책에 따라 비공개 가능).
          </div>
        );
      case 'retire':
        return (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              padding: '4px 0',
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: 'var(--hud-red, #C0392B)',
                lineHeight: 1.5,
              }}
            >
              <strong>⚠ 주의:</strong> 선택된 사용자 <strong>{userIds.length}</strong>명을 soft delete 합니다.
              <br />
              is_active=0 + 역할 INACTIVE 적용. 사용자 데이터는 보존되지만 로그인 차단.
              <br />
              본인보다 같거나 높은 권한 계정 + 마지막 SYS_ADMIN 은 자동 차단.
            </div>
            <label
              style={{
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={retireConfirm}
                onChange={(e) => setRetireConfirm(e.target.checked)}
              />
              위 내용을 확인했으며, 삭제를 진행합니다.
            </label>
          </div>
        );
    }
  };

  const isBulkRoleResult = (r: unknown): r is BulkRoleChangeResult =>
    typeof r === 'object' && r !== null && 'changed_count' in r;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        className="lg-card"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 600,
          maxWidth: '92%',
          maxHeight: '90vh',
          padding: 20,
          overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <strong>일괄 사용자 관리</strong>
          <button type="button" onClick={onClose} style={btnClose}>
            ✕
          </button>
        </div>

        <div style={{ fontSize: 12, marginBottom: 12 }}>
          선택된 사용자 <strong>{userIds.length}</strong>명
        </div>

        {/* Tab navigation */}
        <div
          style={{
            display: 'flex',
            gap: 4,
            borderBottom: '1px solid var(--hud-border)',
            marginBottom: 12,
            overflowX: 'auto',
          }}
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => switchTab(t.id)}
              style={{
                padding: '8px 12px',
                fontSize: 12,
                fontWeight: tab === t.id ? 700 : 500,
                border: 'none',
                background: 'transparent',
                color: tab === t.id ? 'var(--hud-primary)' : 'inherit',
                borderBottom:
                  tab === t.id ? '2px solid var(--hud-primary)' : '2px solid transparent',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab description */}
        <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 10 }}>
          {TABS.find((t) => t.id === tab)?.desc}
        </div>

        {/* Tab content */}
        <div style={{ marginBottom: 12 }}>{renderTabContent()}</div>

        {/* Common reason (audit log) */}
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            사유 (audit log 기록, 최소 4자)
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            style={{
              width: '100%',
              fontSize: 12,
              padding: 6,
              fontFamily: 'inherit',
              resize: 'vertical',
            }}
            placeholder="예: 인사발령 2026-05-01 부, 부서장 승급 / 퇴직 처리"
          />
        </div>

        {error && (
          <div className="lg-state-pill crit" style={{ marginBottom: 8 }}>
            {error}
          </div>
        )}

        {result && (
          <div
            style={{
              fontSize: 12,
              marginBottom: 12,
              padding: 10,
              background: 'rgba(0,0,0,0.04)',
              borderRadius: 6,
            }}
          >
            {isBulkRoleResult(result) ? (
              <>
                <div>
                  <strong>권한 변경 결과</strong>: {result.changed_count}건 변경,{' '}
                  {result.not_found.length}건 미발견 → {result.target_role}
                </div>
                {result.not_found.length > 0 && (
                  <div style={{ opacity: 0.7, marginTop: 4 }}>
                    not_found: {result.not_found.join(', ')}
                  </div>
                )}
              </>
            ) : (
              <>
                <div>
                  <strong>처리 결과</strong>: 성공{' '}
                  <span style={{ color: 'var(--hud-green, #2D8A4E)' }}>{result.succeeded}</span> ·
                  실패{' '}
                  <span style={{ color: 'var(--hud-red, #C0392B)' }}>{result.failed}</span>
                </div>
                {result.failedIds.length > 0 && (
                  <div style={{ opacity: 0.7, marginTop: 4 }}>
                    실패 사번: {result.failedIds.join(', ')}
                  </div>
                )}
                {passwordResults.length > 0 && (
                  <div
                    style={{
                      marginTop: 8,
                      fontFamily: 'var(--hud-font-mono, monospace)',
                      fontSize: 11,
                    }}
                  >
                    <div style={{ marginBottom: 4, opacity: 0.7 }}>임시 비밀번호 (1회 표시):</div>
                    {passwordResults.map((r) => (
                      <div key={r.employee_id}>
                        {r.employee_id}:{' '}
                        {r.password_shown
                          ? r.initial_password
                          : '(비공개 — IdP 또는 메일 발송)'}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            type="button"
            className="lg-btn"
            onClick={onClose}
            disabled={loading}
          >
            닫기
          </button>
          {!result && (
            <button
              type="button"
              className="lg-btn lg-btn-primary"
              onClick={handleApply}
              disabled={loading}
            >
              {loading ? '처리 중…' : '적용'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const btnClose: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  fontSize: 16,
  cursor: 'pointer',
  color: 'inherit',
};

const fieldRow: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  marginBottom: 10,
};

const fieldLabel: React.CSSProperties = {
  fontSize: 12,
  minWidth: 90,
};

const input: React.CSSProperties = {
  flex: 1,
  padding: '6px 8px',
  fontSize: 12,
};

export default BulkRoleChangeModal;
