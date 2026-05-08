// UserEditDrawer — 사용자 행 클릭 시 우측 슬라이드 인 드로어.
// .lg-card 스타일 모달. 편집 / 권한 / 잠금 / 비밀번호 재설정 / 퇴직 / 영구삭제 / 복구 액션.

import { useEffect, useState } from 'react';
import type { AdminUserItem, DepartmentTreeResponse } from '@api/admin';
import {
  hardDeleteUser,
  lockUser,
  resetPassword,
  retireUser,
  unlockUser,
  updateUser,
} from '@api/admin';
import { DeleteConfirmModal, type DeleteMode } from './DeleteConfirmModal';

interface Props {
  user: AdminUserItem;
  tree: DepartmentTreeResponse | null;
  currentUserLevel: number;
  currentUserId: string;
  onClose: () => void;
  onChanged: () => void;
}

export function UserEditDrawer({ user, tree, currentUserLevel, currentUserId, onClose, onChanged }: Props) {
  const [draft, setDraft] = useState<AdminUserItem>(user);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>('');
  const [resetPw, setResetPw] = useState<string>('');
  const [deleteMode, setDeleteMode] = useState<DeleteMode | null>(null);

  useEffect(() => {
    setDraft(user);
    setMsg('');
    setResetPw('');
    setDeleteMode(null);
  }, [user]);

  const isSelf = currentUserId === user.employee_id;
  const isRetired = !user.is_active && Boolean(user.resign_date);
  const canEdit = currentUserLevel >= 4 && !isSelf && (currentUserLevel === 5 || currentUserLevel > user.role_level);
  const canRetire = canEdit && !isRetired;
  const canHardDelete = currentUserLevel >= 5 && !isSelf;
  const canRestore = isRetired && currentUserLevel >= 4 && !isSelf;

  const handleSave = async () => {
    if (!canEdit) return;
    setBusy(true);
    try {
      await updateUser(user.employee_id, {
        username: draft.username,
        department: draft.department,
        position: draft.position,
        email: draft.email,
        phone: draft.phone,
        role_name: draft.role_name,
        is_active: draft.is_active,
      });
      setMsg('저장 완료');
      onChanged();
    } catch (e) {
      setMsg(`저장 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (!canEdit) return;
    if (!confirm(`${user.employee_id} 의 비밀번호를 초기값으로 재설정합니다. 계속할까요?`)) return;
    setBusy(true);
    try {
      const res = await resetPassword(user.employee_id);
      setResetPw(res.initial_password);
      setMsg(`비밀번호 재설정 완료 — 초기 PW: ${res.initial_password}`);
      onChanged();
    } catch (e) {
      setMsg(`재설정 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleLock = async () => {
    if (!canEdit) return;
    setBusy(true);
    try {
      await lockUser(user.employee_id, 30);
      setMsg('30분 잠금 적용');
      onChanged();
    } catch (e) {
      setMsg(`잠금 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleUnlock = async () => {
    if (!canEdit) return;
    setBusy(true);
    try {
      await unlockUser(user.employee_id);
      setMsg('잠금 해제 완료');
      onChanged();
    } catch (e) {
      setMsg(`잠금 해제 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmDelete = async ({ reason }: { reason?: string }) => {
    setBusy(true);
    try {
      if (deleteMode === 'retire') {
        const res = await retireUser(user.employee_id);
        setMsg(`퇴직 처리 완료 — 퇴직일 ${res.resign_date}`);
      } else if (deleteMode === 'hard') {
        const res = await hardDeleteUser(user.employee_id, reason ?? '');
        setMsg(
          `영구 삭제 완료 — login_history ${res.cascaded.login_history}건 / password_history ${res.cascaded.password_history}건 함께 삭제`,
        );
      }
      setDeleteMode(null);
      onChanged();
    } catch (e) {
      setMsg(`삭제 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleRestore = async () => {
    if (!canRestore) return;
    if (!confirm(`${user.employee_id} 의 계정을 복구합니다 (활성화 + 퇴직일 초기화). 계속할까요?`)) return;
    setBusy(true);
    try {
      // 복구: is_active=true + resign_date='' + 역할은 EMPLOYEE 로 복원 (안전 기본값)
      await updateUser(user.employee_id, {
        is_active: true,
        role_name: 'EMPLOYEE',
      });
      setMsg('복구 완료 — 역할은 EMPLOYEE 로 초기화되었습니다. 필요 시 권한을 다시 부여하세요.');
      onChanged();
    } catch (e) {
      setMsg(`복구 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const allDepartments = tree?.divisions.flatMap((d) => d.departments.map((x) => x.name)) ?? [];

  return (
    <div
      role="dialog"
      aria-label="사용자 편집"
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 'min(440px, 100vw)',
        zIndex: 60,
        background: 'color-mix(in oklab, var(--hud-surface) 92%, transparent)',
        backdropFilter: 'blur(20px) saturate(140%)',
        borderLeft: '1px solid color-mix(in oklab, var(--hud-text) 14%, transparent)',
        boxShadow: '-12px 0 40px rgba(0,0,0,0.3)',
        overflowY: 'auto',
        padding: '22px 22px 32px',
      }}
    >
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">USER · {user.employee_id}</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 6 }}>{user.username}</div>
        </div>
        <button className="lg-btn ghost sm" onClick={onClose} type="button" aria-label="닫기">
          닫기
        </button>
      </div>

      {!canEdit && (
        <div className="lg-state-pill warn" style={{ display: 'inline-block', marginBottom: 12 }}>
          {isSelf ? '자기 자신은 편집 불가' : '권한 부족'}
        </div>
      )}

      <div className="lg-filter-grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 8 }}>
        <div className="lg-field grow">
          <label>이름</label>
          <input value={draft.username} onChange={(e) => setDraft({ ...draft, username: e.target.value })} />
        </div>
        <div className="lg-field">
          <label>부서</label>
          <select value={draft.department} onChange={(e) => setDraft({ ...draft, department: e.target.value })}>
            <option value="">(미지정)</option>
            {allDepartments.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </div>
        <div className="lg-field">
          <label>직급</label>
          <select value={draft.position} onChange={(e) => setDraft({ ...draft, position: e.target.value })}>
            <option value="">(미지정)</option>
            {(tree?.positions ?? []).map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="lg-field">
          <label>역할</label>
          <select value={draft.role_name} onChange={(e) => setDraft({ ...draft, role_name: e.target.value })}>
            {(tree?.roles ?? []).map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>
        <div className="lg-field grow">
          <label>이메일</label>
          <input value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
        </div>
        <div className="lg-field">
          <label>전화</label>
          <input value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
        </div>
        <div className="lg-field">
          <label>활성 상태</label>
          <select
            value={draft.is_active ? '1' : '0'}
            onChange={(e) => setDraft({ ...draft, is_active: e.target.value === '1' })}
          >
            <option value="1">활성</option>
            <option value="0">비활성</option>
          </select>
        </div>
      </div>

      <div style={{ marginTop: 18, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="lg-btn" disabled={!canEdit || busy} onClick={handleSave} type="button">
          저장
        </button>
        <button className="lg-btn ghost" disabled={!canEdit || busy} onClick={handleReset} type="button">
          비밀번호 재설정
        </button>
        {user.locked_until ? (
          <button className="lg-btn ghost" disabled={!canEdit || busy} onClick={handleUnlock} type="button">
            잠금 해제
          </button>
        ) : (
          <button className="lg-btn ghost" disabled={!canEdit || busy} onClick={handleLock} type="button">
            30분 잠금
          </button>
        )}
      </div>

      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {canRestore && (
          <button
            className="lg-btn"
            disabled={busy}
            onClick={handleRestore}
            type="button"
            style={{ background: '#2D8A4E', borderColor: '#2D8A4E', color: '#fff' }}
          >
            복구
          </button>
        )}
        {canRetire && (
          <button
            className="lg-btn"
            disabled={busy}
            onClick={() => setDeleteMode('retire')}
            type="button"
            style={{ background: '#E8A317', borderColor: '#E8A317', color: '#fff' }}
          >
            퇴직 처리
          </button>
        )}
        {canHardDelete && (
          <button
            className="lg-btn ghost"
            disabled={busy}
            onClick={() => setDeleteMode('hard')}
            type="button"
            style={{
              borderColor: 'color-mix(in oklab, #C0392B 50%, transparent)',
              color: '#C0392B',
            }}
          >
            영구 삭제
          </button>
        )}
      </div>

      {msg && (
        <div className="lg-state-pill ok" style={{ display: 'inline-block', marginTop: 14 }}>
          {msg}
        </div>
      )}

      {resetPw && (
        <div className="lg-card lg-card-tight" style={{ marginTop: 16 }}>
          <div className="lg-pill" style={{ marginBottom: 10 }}>초기 비밀번호</div>
          <div style={{ fontFamily: 'var(--hud-font-mono)', fontSize: 22, color: 'var(--hud-primary)', letterSpacing: '0.04em' }}>
            {resetPw}
          </div>
          <div className="lg-roi-foot">최초 로그인 시 즉시 변경 필요. 안전한 채널로 사용자에게 전달하세요.</div>
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        <div className="lg-pill">메타</div>
        <div className="lg-stat-list" style={{ marginTop: 10 }}>
          <div className="lg-stat-row"><span>역할 레벨</span><b>L{user.role_level}</b></div>
          <div className="lg-stat-row"><span>마지막 로그인</span><b>{user.last_login ?? '—'}</b></div>
          <div className="lg-stat-row"><span>실패 횟수</span><b>{user.failed_attempts}</b></div>
          <div className="lg-stat-row"><span>잠금 만료</span><b>{user.locked_until ?? '—'}</b></div>
          <div className="lg-stat-row"><span>입사일</span><b>{user.hire_date || '—'}</b></div>
          <div className="lg-stat-row"><span>퇴직일</span><b>{user.resign_date || '—'}</b></div>
          <div className="lg-stat-row"><span>최초 변경 필요</span><b>{user.must_change_pw ? '필요' : '완료'}</b></div>
        </div>
      </div>

      {deleteMode && (
        <DeleteConfirmModal
          user={user}
          mode={deleteMode}
          busy={busy}
          onConfirm={handleConfirmDelete}
          onCancel={() => !busy && setDeleteMode(null)}
        />
      )}
    </div>
  );
}
