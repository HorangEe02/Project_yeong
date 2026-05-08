// DeleteConfirmModal — Soft (퇴직 처리) / Hard (영구 삭제) 두 모드 confirm 다이얼로그.
// .lg-card glass + 빨간 강조. 신규 CSS 0줄.

import { useEffect, useState } from 'react';
import type { AdminUserItem } from '@api/admin';

export type DeleteMode = 'retire' | 'hard';

interface Props {
  user: AdminUserItem;
  mode: DeleteMode;
  busy: boolean;
  onConfirm: (payload: { reason?: string }) => void | Promise<void>;
  onCancel: () => void;
}

const TODAY_ISO = new Date().toISOString().slice(0, 10);

export function DeleteConfirmModal({ user, mode, busy, onConfirm, onCancel }: Props) {
  const [confirmId, setConfirmId] = useState('');
  const [reason, setReason] = useState('');

  useEffect(() => {
    setConfirmId('');
    setReason('');
  }, [user.employee_id, mode]);

  const isHard = mode === 'hard';
  const idMatches = confirmId === user.employee_id;
  const canConfirm = !busy && (!isHard || idMatches);

  const title = isHard ? '영구 삭제' : '퇴직 처리';
  const en = isHard ? 'HARD DELETE · IRREVERSIBLE' : 'SOFT DELETE · RETIRE';

  return (
    <div
      role="dialog"
      aria-label={title}
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'color-mix(in oklab, black 55%, transparent)',
        backdropFilter: 'blur(6px)',
        zIndex: 80,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        className="lg-card"
        style={{
          width: 'min(520px, 100%)',
          margin: 0,
          maxHeight: '88vh',
          overflowY: 'auto',
          border: isHard
            ? '1px solid color-mix(in oklab, #C0392B 60%, transparent)'
            : '1px solid color-mix(in oklab, var(--hud-orange) 50%, transparent)',
          background: isHard
            ? 'color-mix(in oklab, #C0392B 6%, var(--hud-surface))'
            : 'color-mix(in oklab, var(--hud-orange) 6%, var(--hud-surface))',
        }}
      >
        <div className="lg-card-h">
          <div>
            <div className="lg-pill" style={{ color: isHard ? '#C0392B' : '#E8A317' }}>{en}</div>
            <h2 className="lg-h2" style={{ marginTop: 6 }}>{title}</h2>
          </div>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={onCancel}
            disabled={busy}
            aria-label="닫기"
          >
            닫기
          </button>
        </div>

        <div className="lg-stat-list">
          <div className="lg-stat-row"><span>대상 사번</span><b className="mono" style={{ fontSize: 16 }}>{user.employee_id}</b></div>
          <div className="lg-stat-row"><span>이름 / 직급</span><b>{user.username} · {user.position || '—'}</b></div>
          <div className="lg-stat-row"><span>본부 / 부서</span><b>{user.division || '—'} / {user.department || '—'}</b></div>
          <div className="lg-stat-row"><span>역할 / 레벨</span><b>{user.role_name} (L{user.role_level})</b></div>
          {!isHard && (
            <div className="lg-stat-row"><span>퇴직일</span><b className="mono">{TODAY_ISO}</b></div>
          )}
        </div>

        {!isHard ? (
          <div
            style={{
              marginTop: 16,
              padding: '12px 14px',
              borderRadius: 12,
              background: 'color-mix(in oklab, var(--hud-orange) 10%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-orange) 30%, transparent)',
              fontSize: 13,
              lineHeight: 1.7,
              color: 'var(--hud-text)',
            }}
          >
            <b>퇴직 처리 동작:</b><br />
            · 계정 비활성화 + 역할을 INACTIVE 로 변경<br />
            · 로그인 즉시 차단 (영구 잠금)<br />
            · 모든 로그인/비밀번호 이력 그대로 보존<br />
            · 필요시 <span className="mono">[복구]</span> 버튼으로 되돌릴 수 있음
          </div>
        ) : (
          <>
            <div
              style={{
                marginTop: 16,
                padding: '12px 14px',
                borderRadius: 12,
                background: 'color-mix(in oklab, #C0392B 12%, transparent)',
                border: '1px solid color-mix(in oklab, #C0392B 35%, transparent)',
                fontSize: 13,
                lineHeight: 1.7,
                color: 'var(--hud-text)',
              }}
            >
              <b style={{ color: '#C0392B' }}>⚠ 비가역 작업 — 데이터가 영구히 사라집니다.</b><br />
              · users · login_history · password_history 모든 행 삭제 (cascade)<br />
              · 보안 감사 추적 불가능 — GDPR/PIPA 파기 요청 시에만 사용 권장<br />
              · 일반 퇴직은 <b>퇴직 처리</b> 를 사용하세요.
            </div>

            <div className="lg-field" style={{ marginTop: 16 }}>
              <label>
                확인을 위해 사번을 그대로 입력하세요: <b className="mono">{user.employee_id}</b>
              </label>
              <input
                value={confirmId}
                onChange={(e) => setConfirmId(e.target.value)}
                placeholder={user.employee_id}
                autoFocus
                style={{
                  borderColor: idMatches
                    ? 'color-mix(in oklab, var(--hud-green) 60%, transparent)'
                    : 'color-mix(in oklab, #C0392B 40%, transparent)',
                }}
              />
            </div>

            <div className="lg-field" style={{ marginTop: 12 }}>
              <label>사유 (선택, 감사 로그에 기록됨)</label>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="예: GDPR 개인정보 파기 요청"
                maxLength={200}
              />
            </div>
          </>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 18 }}>
          <button
            type="button"
            className="lg-btn ghost"
            onClick={onCancel}
            disabled={busy}
          >
            취소
          </button>
          <button
            type="button"
            className="lg-btn"
            disabled={!canConfirm}
            onClick={() => onConfirm({ reason: isHard ? reason : undefined })}
            style={{
              background: isHard ? '#C0392B' : '#E8A317',
              borderColor: isHard ? '#C0392B' : '#E8A317',
              color: '#fff',
            }}
          >
            {busy ? '처리 중…' : isHard ? '영구 삭제' : '퇴직 처리'}
          </button>
        </div>
      </div>
    </div>
  );
}
