// PermissionChangeRequestModal — 결재 요청 폼 + dry-run preview.
// PR-E8. PermissionMatrixUI 셀 클릭 시 호출.

import { useCallback, useState } from 'react';
import {
  previewPermissionChange,
  requestPermissionChange,
  type PermissionItem,
  type PermissionPreviewResponse,
} from '@api/admin';
import { useToast } from '@store/toast';

interface Props {
  dept: string;
  role: string;
  existing: PermissionItem | null;
  onClose: () => void;
  onSubmitted: () => void;
}

const ROLE_OPTIONS = ['EMPLOYEE', 'MANAGER', 'TEAM_LEAD', 'HR_ADMIN', 'SYS_ADMIN'];

export function PermissionChangeRequestModal({
  dept, role, existing, onClose, onSubmitted,
}: Props) {
  const { addToast } = useToast();
  const initialKey = existing?.key ?? '';
  const [permissionKey, setPermissionKey] = useState(initialKey);
  const [minRole, setMinRole] = useState(existing?.min_role ?? role);
  const [deptsInput, setDeptsInput] = useState<string>(
    (existing?.departments ?? [dept]).join(', '),
  );
  const [minPositionLevel, setMinPositionLevel] = useState<number>(
    existing?.min_position_level ?? 0,
  );
  const [allowSameDivision, setAllowSameDivision] = useState<boolean>(
    existing?.allow_same_division ?? false,
  );
  const [description, setDescription] = useState(existing?.description ?? '');
  const [reason, setReason] = useState('');
  const [preview, setPreview] = useState<PermissionPreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const buildBody = useCallback(() => {
    const departments = deptsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    return {
      permission_key: permissionKey.trim(),
      new_value: {
        key: permissionKey.trim(),
        description: description.trim(),
        min_role: minRole,
        departments: departments.length > 0 ? departments : null,
        allow_same_division: allowSameDivision,
        min_position_level: minPositionLevel,
      },
      reason: reason.trim(),
    };
  }, [permissionKey, description, minRole, deptsInput,
      allowSameDivision, minPositionLevel, reason]);

  const handlePreview = useCallback(async () => {
    if (!permissionKey.trim() || !reason.trim()) {
      addToast({ type: 'warning', message: '권한 key 와 변경 사유는 필수입니다.' });
      return;
    }
    setBusy(true);
    try {
      const data = await previewPermissionChange(buildBody());
      setPreview(data);
    } catch (e) {
      addToast({ type: 'error', message: `미리보기 실패: ${(e as Error).message}` });
    } finally {
      setBusy(false);
    }
  }, [permissionKey, reason, buildBody, addToast]);

  const handleSubmit = useCallback(async () => {
    if (!permissionKey.trim() || !reason.trim()) {
      addToast({ type: 'warning', message: '권한 key 와 변경 사유는 필수입니다.' });
      return;
    }
    setBusy(true);
    try {
      const res = await requestPermissionChange(buildBody());
      addToast({
        type: 'success',
        message: `결재 요청 완료. request_id=${res.request_id}`,
      });
      onSubmitted();
    } catch (e) {
      addToast({ type: 'error', message: `결재 요청 실패: ${(e as Error).message}` });
    } finally {
      setBusy(false);
    }
  }, [permissionKey, reason, buildBody, addToast, onSubmitted]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
        zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="lg-card"
        style={{ width: 'min(640px, 100%)', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="lg-card-h">
          <div>
            <div className="lg-pill">권한 변경 요청</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
              선택: <b>{dept}</b> · 역할 <b>{role}</b>
            </div>
          </div>
          <button type="button" className="lg-btn ghost sm" onClick={onClose}>닫기</button>
        </div>

        <div style={{ display: 'grid', gap: 10 }}>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>권한 key *</span>
            <input
              className="lg-input"
              value={permissionKey}
              onChange={(e) => setPermissionKey(e.target.value)}
              placeholder="예: compliance.read"
              disabled={busy}
            />
          </label>

          <label style={{ display: 'grid', gap: 4 }}>
            <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>설명</span>
            <input
              className="lg-input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="권한 설명 (감사 로그 노출)"
              disabled={busy}
            />
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>최소 역할</span>
              <select
                className="lg-input"
                value={minRole}
                onChange={(e) => setMinRole(e.target.value)}
                disabled={busy}
              >
                {ROLE_OPTIONS.map((r) => (<option key={r} value={r}>{r}</option>))}
              </select>
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>최소 직급 레벨</span>
              <input
                type="number"
                className="lg-input"
                min={0}
                value={minPositionLevel}
                onChange={(e) => setMinPositionLevel(Number(e.target.value))}
                disabled={busy}
              />
            </label>
          </div>

          <label style={{ display: 'grid', gap: 4 }}>
            <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
              부서 화이트리스트 (쉼표 구분, 비우면 전체)
            </span>
            <input
              className="lg-input"
              value={deptsInput}
              onChange={(e) => setDeptsInput(e.target.value)}
              placeholder="총무인사팀, ESG경영팀"
              disabled={busy}
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={allowSameDivision}
              onChange={(e) => setAllowSameDivision(e.target.checked)}
              disabled={busy}
            />
            <span style={{ fontSize: 13 }}>동일 본부 내 허용 (allow_same_division)</span>
          </label>

          <label style={{ display: 'grid', gap: 4 }}>
            <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>변경 사유 *</span>
            <textarea
              className="lg-input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="감사 추적용 사유 (필수, 최대 2000자)"
              maxLength={2000}
              disabled={busy}
            />
          </label>

          {preview && (
            <div
              className="lg-card"
              style={{ background: 'color-mix(in oklab, var(--hud-primary) 6%, transparent)' }}
            >
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                미리보기 ({preview.is_new ? '신규 생성' : '업데이트'})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>BEFORE</div>
                  <pre style={{
                    fontSize: 11, padding: 8, background: 'rgba(0,0,0,0.04)',
                    borderRadius: 4, overflow: 'auto', maxHeight: 160,
                  }}>
                    {JSON.stringify(preview.before, null, 2)}
                  </pre>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>AFTER</div>
                  <pre style={{
                    fontSize: 11, padding: 8, background: 'rgba(0,0,0,0.04)',
                    borderRadius: 4, overflow: 'auto', maxHeight: 160,
                  }}>
                    {JSON.stringify(preview.after, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button
              type="button"
              className="lg-btn ghost"
              onClick={handlePreview}
              disabled={busy}
            >
              변경 미리보기
            </button>
            <button
              type="button"
              className="lg-btn primary"
              onClick={handleSubmit}
              disabled={busy}
            >
              {busy ? '처리 중…' : '결재 요청'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PermissionChangeRequestModal;
