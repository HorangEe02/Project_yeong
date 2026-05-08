// CreateUserTab — 3-step Wizard: 기본 정보 → 권한 설정 → 인증 발급.
//
// 사용자 요구사항 매핑:
//  - 30개 부서 모두 선택 가능 (DEPARTMENT_CATEGORIES 트리 기반)
//  - 부서 선택 시 사번/ID 자동 생성 (EmployeeIDPreview)
//  - 이름/직급/이메일/본부 관리자 입력
//  - 권한 설정 + 인증 발급 단계

import { useEffect, useMemo, useState } from 'react';
import {
  createEmployee,
  fetchDepartmentTree,
  type CreateEmployeeResponse,
  type DepartmentTreeResponse,
  type EmployeeIDPreviewResponse,
} from '@api/admin';
import { useAuthStore } from '@store/auth';
import { DownloadActions } from '@components/common/DownloadActions';
import { WizardStepper } from '@components/admin/wizard/WizardStepper';
import { EmployeeIDPreview } from '@components/admin/widgets/EmployeeIDPreview';

interface FormState {
  division: string;
  department: string;
  username: string;
  position: string;
  email: string;
  phone: string;
  hire_date: string;
  role_name: string;
  is_active: boolean;
  must_change_pw: boolean;
}

const INITIAL: FormState = {
  division: '',
  department: '',
  username: '',
  position: '사원',
  email: '',
  phone: '',
  hire_date: '',
  role_name: 'EMPLOYEE',
  is_active: true,
  must_change_pw: true,
};

interface RoleMeta {
  name: string;
  level: number;
  ko: string;
  bullets: string[];
}

const ROLE_CARDS: RoleMeta[] = [
  { name: 'INACTIVE',  level: 0, ko: '비활성',         bullets: ['로그인 차단', '감사용 더미 계정', '복구 시 다시 활성화'] },
  { name: 'EMPLOYEE',  level: 1, ko: '일반 사원',      bullets: ['본인 정보 조회/수정', '문서 검색', '온보딩 챗봇 사용'] },
  { name: 'MANAGER',   level: 2, ko: '관리자급(과장+)', bullets: ['팀 인원 정보 열람', '문서 작성/검토', '본부 통계 일부'] },
  { name: 'TEAM_LEAD', level: 3, ko: '팀장',           bullets: ['팀원 전 필드 열람', '인사 통계 7탭', '권한 위임 일부'] },
  { name: 'HR_ADMIN',  level: 4, ko: '인사 관리자',    bullets: ['전체 사용자 CRUD', '계정 발급/잠금', '보안 감사 + AI 활용 분석'] },
  { name: 'SYS_ADMIN', level: 5, ko: '시스템 관리자',  bullets: ['시스템 도구 (DB 백업/감사로그)', '역할 매트릭스 변경', '모든 권한 우회'] },
];

const STEPS = [
  { ko: '기본 정보', en: 'BASIC INFO' },
  { ko: '권한 설정', en: 'PERMISSIONS' },
  { ko: '인증 발급', en: 'ISSUANCE' },
];

function buildIssuanceMarkdown(res: CreateEmployeeResponse): string {
  return res.instructions_markdown;
}

export function CreateUserTab() {
  const auth = useAuthStore((s) => s.user);
  const myLevel = auth?.role_level ?? 1;

  const [step, setStep] = useState(0);
  const [tree, setTree] = useState<DepartmentTreeResponse | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [preview, setPreview] = useState<EmployeeIDPreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [issued, setIssued] = useState<CreateEmployeeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDepartmentTree().then(setTree).catch((e) => setError((e as Error).message));
  }, []);

  const departments = useMemo(() => {
    if (!tree || !form.division) return [];
    const found = tree.divisions.find((d) => d.division === form.division);
    return found?.departments ?? [];
  }, [tree, form.division]);

  const update = (patch: Partial<FormState>) => setForm((prev) => ({ ...prev, ...patch }));

  const step1Ready = Boolean(
    form.division && form.department && form.username && form.position && preview,
  );
  const step2Ready = Boolean(form.role_name);

  const handleSubmit = async () => {
    if (!step1Ready || !step2Ready) return;
    setBusy(true);
    setError(null);
    try {
      const res = await createEmployee({
        division: form.division,
        department: form.department,
        username: form.username,
        position: form.position,
        email: form.email,
        phone: form.phone,
        hire_date: form.hire_date,
        role_name: form.role_name,
        is_active: form.is_active,
        must_change_pw: form.must_change_pw,
      });
      setIssued(res);
    } catch (e) {
      setError(`발급 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setForm(INITIAL);
    setPreview(null);
    setIssued(null);
    setStep(0);
    setError(null);
  };

  if (myLevel < 4) {
    return (
      <div className="lg-card">
        <div className="lg-state-pill crit">권한 부족</div>
        <p style={{ marginTop: 12 }}>계정 발급은 HR_ADMIN(L4) 이상 권한이 필요합니다.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="lg-card">
        <WizardStepper steps={STEPS} current={step} />
      </div>

      {error && (
        <div className="lg-card">
          <div className="lg-state-pill crit">{error}</div>
        </div>
      )}

      {/* ── STEP 1 ── 기본 정보 */}
      {step === 0 && (
        <div className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-pill">STEP 1 · BASIC INFO</div>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
                본부 → 부서를 선택하면 사번/ID 가 자동으로 생성됩니다.
              </div>
            </div>
          </div>

          <div className="lg-grid lg-grid-2-1">
            <div>
              <div className="lg-filter-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="lg-field">
                  <label>본부 *</label>
                  <select
                    value={form.division}
                    onChange={(e) => update({ division: e.target.value, department: '' })}
                  >
                    <option value="">(선택)</option>
                    {tree?.divisions.map((d) => (
                      <option key={d.division}>{d.division}</option>
                    ))}
                  </select>
                </div>

                <div className="lg-field">
                  <label>부서 *</label>
                  <select
                    value={form.department}
                    onChange={(e) => update({ department: e.target.value })}
                    disabled={!form.division}
                  >
                    <option value="">(선택)</option>
                    {departments.map((d) => (
                      <option key={d.name} title={d.description}>{d.name}</option>
                    ))}
                  </select>
                </div>

                <div className="lg-field grow">
                  <label>이름 *</label>
                  <input
                    value={form.username}
                    onChange={(e) => update({ username: e.target.value })}
                    placeholder="홍길동"
                  />
                </div>

                <div className="lg-field">
                  <label>직급 *</label>
                  <select value={form.position} onChange={(e) => update({ position: e.target.value })}>
                    {(tree?.positions ?? []).map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </div>

                <div className="lg-field grow">
                  <label>이메일</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => update({ email: e.target.value })}
                    placeholder={preview?.suggested_email ?? 'example@ajinindustry.com'}
                  />
                </div>

                <div className="lg-field">
                  <label>휴대폰</label>
                  <input
                    value={form.phone}
                    onChange={(e) => update({ phone: e.target.value })}
                    placeholder="010-XXXX-XXXX"
                  />
                </div>

                <div className="lg-field">
                  <label>입사일</label>
                  <input type="date" value={form.hire_date} onChange={(e) => update({ hire_date: e.target.value })} />
                </div>
              </div>
            </div>

            <div>
              <EmployeeIDPreview department={form.department} onResolved={setPreview} />
            </div>
          </div>

          <div style={{ marginTop: 18, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="lg-btn ghost" onClick={reset} type="button">초기화</button>
            <button className="lg-btn" disabled={!step1Ready} onClick={() => setStep(1)} type="button">
              다음 →
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2 ── 권한 설정 */}
      {step === 1 && (
        <div className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-pill">STEP 2 · PERMISSIONS</div>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
                부여할 역할(Role) 을 선택합니다. 본인보다 높은 권한은 부여할 수 없습니다.
              </div>
            </div>
          </div>

          <div className="lg-grid lg-grid-2-2">
            {ROLE_CARDS.map((r) => {
              const disabled = r.level > myLevel && myLevel < 5;
              const on = form.role_name === r.name;
              return (
                <button
                  key={r.name}
                  type="button"
                  disabled={disabled}
                  onClick={() => update({ role_name: r.name })}
                  className="lg-card lg-card-tight"
                  style={{
                    cursor: disabled ? 'not-allowed' : 'pointer',
                    opacity: disabled ? 0.45 : 1,
                    textAlign: 'left',
                    border: on
                      ? '1px solid color-mix(in oklab, var(--hud-primary) 60%, transparent)'
                      : '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
                    background: on
                      ? 'color-mix(in oklab, var(--hud-primary) 12%, transparent)'
                      : 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
                    margin: 0,
                  }}
                >
                  <div className="lg-card-h" style={{ marginBottom: 10, paddingBottom: 10 }}>
                    <div>
                      <div className="lg-pill">{r.name}</div>
                      <div style={{ fontSize: 16, fontWeight: 600, marginTop: 6 }}>{r.ko}</div>
                    </div>
                    <div className="lg-role">L{r.level}</div>
                  </div>
                  <ul style={{ paddingLeft: 18, margin: 0, color: 'var(--hud-text-dim)', fontSize: 13, lineHeight: 1.7 }}>
                    {r.bullets.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </button>
              );
            })}
          </div>

          <div className="lg-stat-list" style={{ marginTop: 18 }}>
            <div className="lg-stat-row">
              <span>최초 로그인 시 비밀번호 변경</span>
              <b>
                <input
                  type="checkbox"
                  checked={form.must_change_pw}
                  onChange={(e) => update({ must_change_pw: e.target.checked })}
                  style={{ marginRight: 6 }}
                />
                필수 적용
              </b>
            </div>
            <div className="lg-stat-row">
              <span>계정 활성화</span>
              <b>
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => update({ is_active: e.target.checked })}
                  style={{ marginRight: 6 }}
                />
                생성 즉시 활성
              </b>
            </div>
          </div>

          <div style={{ marginTop: 18, display: 'flex', gap: 8, justifyContent: 'space-between' }}>
            <button className="lg-btn ghost" onClick={() => setStep(0)} type="button">← 이전</button>
            <button className="lg-btn" disabled={!step2Ready} onClick={() => setStep(2)} type="button">
              다음 →
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3 ── 인증 발급 */}
      {step === 2 && (
        <div className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-pill">STEP 3 · ISSUANCE</div>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--hud-text-dim)' }}>
                내용을 검토하고 [발급] 을 누르면 사번/초기 PW 가 즉시 생성됩니다.
              </div>
            </div>
            {issued && <DownloadActions source="admin" basename={`ajin-account-${issued.employee_id}`} content={() => buildIssuanceMarkdown(issued)} />}
          </div>

          {!issued && (
            <>
              <div className="lg-stat-list">
                <div className="lg-stat-row"><span>본부 / 부서</span><b>{form.division} / {form.department}</b></div>
                <div className="lg-stat-row"><span>이름 / 직급</span><b>{form.username} · {form.position}</b></div>
                <div className="lg-stat-row"><span>예정 사번</span><b className="mono" style={{ color: 'var(--hud-primary)' }}>{preview?.next_id ?? '—'}</b></div>
                <div className="lg-stat-row"><span>역할 / 레벨</span><b>{form.role_name} (L{ROLE_CARDS.find((r) => r.name === form.role_name)?.level ?? 1})</b></div>
                <div className="lg-stat-row"><span>이메일</span><b className="mono">{form.email || preview?.suggested_email}</b></div>
                <div className="lg-stat-row"><span>초기 비밀번호 정책</span><b>ajin + 사번 뒷 4자리 (최초 로그인 시 변경)</b></div>
              </div>

              <div style={{ marginTop: 18, display: 'flex', gap: 8, justifyContent: 'space-between' }}>
                <button className="lg-btn ghost" onClick={() => setStep(1)} type="button">← 이전</button>
                <button className="lg-btn" disabled={busy || !step1Ready || !step2Ready} onClick={handleSubmit} type="button">
                  {busy ? '발급 중…' : '발급'}
                </button>
              </div>
            </>
          )}

          {issued && (
            <>
              <div className="lg-state-pill ok" style={{ display: 'inline-block', marginBottom: 14 }}>
                발급 완료 — {issued.employee_id}
              </div>

              <div className="lg-grid lg-grid-2">
                <div className="lg-card lg-card-tight" style={{ margin: 0 }}>
                  <div className="lg-pill">사번 / 사용자 ID</div>
                  <div style={{ fontSize: 28, fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-primary)', marginTop: 8, letterSpacing: '0.04em' }}>
                    {issued.employee_id}
                  </div>
                  <div className="lg-roi-foot">사용자 로그인 ID 는 사번과 동일합니다.</div>
                </div>

                <div className="lg-card lg-card-tight" style={{ margin: 0 }}>
                  <div className="lg-pill">초기 비밀번호</div>
                  <div style={{ fontSize: 28, fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-primary)', marginTop: 8, letterSpacing: '0.04em' }}>
                    {issued.initial_password}
                  </div>
                  <button
                    type="button"
                    className="lg-btn ghost sm"
                    style={{ marginTop: 8 }}
                    onClick={() => navigator.clipboard?.writeText(issued.initial_password)}
                  >
                    클립보드 복사
                  </button>
                  <div className="lg-roi-foot">{issued.issuance_note}</div>
                </div>
              </div>

              <div className="lg-card lg-card-tight" style={{ marginTop: 16 }}>
                <div className="lg-pill">사용자 안내문 (Markdown)</div>
                <pre
                  style={{
                    marginTop: 10,
                    padding: 12,
                    borderRadius: 12,
                    background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                    fontFamily: 'var(--hud-font-mono)',
                    fontSize: 12,
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    color: 'var(--hud-text)',
                    maxHeight: 240,
                    overflowY: 'auto',
                  }}
                >
                  {issued.instructions_markdown}
                </pre>
              </div>

              <div style={{ marginTop: 18, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button className="lg-btn" onClick={reset} type="button">새 계정 생성</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
