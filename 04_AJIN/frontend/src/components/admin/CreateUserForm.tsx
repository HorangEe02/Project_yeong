// CreateUserForm — 신입사원 ID 발급 폼 (v4.9.5).
//
// 재사용 가능 컴포넌트 — CreateUserModal(모달) 에서 사용. v4.9 이후 CreateUserTab 은 제거됨.
// 자체 submit 버튼 + 결과 화면 포함. wrapping container만 외부.

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@components/ui/Button';
import {
  createEmployee,
  previewEmployeeId,
  type CreateEmployeeRequest,
  type CreateEmployeeResponse,
  type DepartmentTreeResponse,
} from '@api/admin';

interface Props {
  tree: DepartmentTreeResponse | null;
  /** 생성 성공 시 호출 — 사용자 목록 새로고침 등 외부 후처리 */
  onCreated: (result: CreateEmployeeResponse) => void;
  /** 취소 버튼 (모달 닫기). 미제공 시 취소 버튼 미노출 (탭 모드) */
  onCancel?: () => void;
  /** 결과 화면에서 "닫기" 버튼 (모달용). 미제공 시 "다시 발급" 버튼 표시 */
  onResultClose?: () => void;
}

interface FormState {
  division: string;
  department: string;
  username: string;
  position: string;
  role_name: string;
  email: string;
  phone: string;
  hire_date: string;
}

function emptyForm(): FormState {
  const today = new Date();
  return {
    division: '',
    department: '',
    username: '',
    position: '사원',
    role_name: 'EMPLOYEE',
    email: '',
    phone: '',
    hire_date: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`,
  };
}

export function CreateUserForm({ tree, onCreated, onCancel, onResultClose }: Props) {
  const [form, setForm] = useState<FormState>(emptyForm);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CreateEmployeeResponse | null>(null);

  const divisions = useMemo(() => tree?.divisions ?? [], [tree]);
  const currentDivision = useMemo(
    () => divisions.find((d) => d.division === form.division),
    [divisions, form.division],
  );
  const departments = currentDivision?.departments ?? [];
  const roles = tree?.roles ?? [];
  const positions = tree?.positions ?? [];

  // position 옵션이 도착하면 기본값('사원')이 옵션에 있는지 확인 — 없으면 첫 옵션 사용
  useEffect(() => {
    if (positions.length === 0) return;
    if (!positions.includes(form.position)) {
      setForm((f) => ({ ...f, position: positions[0] }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions.length]);

  const canPreview = !!form.department;
  const canSubmit =
    !!form.division &&
    !!form.department &&
    !!form.username &&
    !!form.position &&
    !!form.role_name &&
    !submitting;

  const handlePreview = async () => {
    if (!form.department) return;
    setPreviewLoading(true);
    setError(null);
    try {
      const res = await previewEmployeeId(form.department);
      setPreviewId(res.next_id);
    } catch (e) {
      setError(`사번 미리보기 실패: ${(e as Error).message}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const req: CreateEmployeeRequest = {
        division: form.division,
        department: form.department,
        username: form.username,
        position: form.position,
        role_name: form.role_name,
      };
      if (form.email) req.email = form.email;
      if (form.phone) req.phone = form.phone;
      if (form.hire_date) req.hire_date = form.hire_date;
      const res = await createEmployee(req);
      setResult(res);
      onCreated(res);
    } catch (e) {
      setError(`사용자 생성 실패: ${(e as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  };

  // 결과 화면
  if (result) {
    return (
      <div>
        <div className="lg-stat-list" style={{ marginBottom: 16 }}>
          <div className="lg-stat-row"><span>사번</span><b style={{ fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-primary)' }}>{result.employee_id}</b></div>
          <div className="lg-stat-row"><span>이름</span><b>{result.username}</b></div>
          <div className="lg-stat-row"><span>부서</span><b>{result.department}</b></div>
          <div className="lg-stat-row"><span>역할 · 등급</span><b>{result.role_name} · L{result.role_level}</b></div>
          <div className="lg-stat-row">
            <span>{result.initial_password ? '초기 비밀번호' : '초기 인증'}</span>
            <b style={{ fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-orange)', userSelect: 'all' }}>
              {result.initial_password || result.issuance_note || '사내 IdP 초대/초기화 절차'}
            </b>
          </div>
        </div>
        <pre
          style={{
            background: 'var(--hud-surface)',
            border: '1px solid var(--hud-border)',
            borderRadius: 6,
            padding: 12,
            fontSize: 11,
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            maxHeight: 280,
            overflow: 'auto',
            fontFamily: 'var(--hud-font-mono)',
          }}
        >
          {result.instructions_markdown}
        </pre>
        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          {onResultClose ? (
            <Button variant="primary" onClick={onResultClose}>닫기</Button>
          ) : (
            <Button variant="ghost" onClick={() => { setResult(null); setForm(emptyForm()); setPreviewId(null); }}>
              다시 발급
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="lg-field">
          <label>본부 *</label>
          <select
            value={form.division}
            onChange={(e) => setForm({ ...form, division: e.target.value, department: '' })}
          >
            <option value="">— 선택 —</option>
            {divisions.map((d) => <option key={d.division}>{d.division}</option>)}
          </select>
        </div>
        <div className="lg-field">
          <label>부서 *</label>
          <select
            value={form.department}
            onChange={(e) => { setForm({ ...form, department: e.target.value }); setPreviewId(null); }}
            disabled={!form.division}
          >
            <option value="">— 선택 —</option>
            {departments.map((d) => <option key={d.name}>{d.name}</option>)}
          </select>
        </div>
        <div className="lg-field">
          <label>이름 *</label>
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            placeholder="홍길동"
          />
        </div>
        <div className="lg-field">
          <label>직급 *</label>
          {positions.length > 0 ? (
            <select value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })}>
              {positions.map((p) => <option key={p}>{p}</option>)}
            </select>
          ) : (
            <input
              value={form.position}
              onChange={(e) => setForm({ ...form, position: e.target.value })}
              placeholder="사원"
            />
          )}
        </div>
        <div className="lg-field">
          <label>역할 *</label>
          <select value={form.role_name} onChange={(e) => setForm({ ...form, role_name: e.target.value })}>
            <option value="">— 선택 —</option>
            {roles.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div className="lg-field">
          <label>입사일</label>
          <input
            type="date"
            value={form.hire_date}
            onChange={(e) => setForm({ ...form, hire_date: e.target.value })}
          />
        </div>
        <div className="lg-field">
          <label>이메일</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="user@ajin.co.kr"
          />
        </div>
        <div className="lg-field">
          <label>전화</label>
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="010-1234-5678"
          />
        </div>
      </div>

      <div
        style={{
          marginTop: 16,
          padding: 12,
          background: 'var(--hud-surface)',
          border: '1px solid var(--hud-border)',
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>사번 미리보기</div>
          <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--hud-font-mono)', color: previewId ? 'var(--hud-primary)' : 'var(--hud-text-dim)' }}>
            {previewId ?? '부서 선택 후 미리보기'}
          </div>
        </div>
        <Button variant="ghost" onClick={handlePreview} disabled={!canPreview || previewLoading}>
          {previewLoading ? '조회 중…' : '미리보기'}
        </Button>
      </div>

      {error && (
        <p style={{ marginTop: 12, color: 'var(--hud-red)', fontSize: 13 }}>{error}</p>
      )}

      <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        {onCancel && (
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>취소</Button>
        )}
        <Button variant="primary" onClick={handleSubmit} disabled={!canSubmit}>
          {submitting ? '생성 중…' : '생성'}
        </Button>
      </div>
    </div>
  );
}
