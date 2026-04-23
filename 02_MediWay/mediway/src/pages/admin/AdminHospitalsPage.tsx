import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import {
  createHospital,
  listHospitals,
  setHospitalContractStatus,
  isValidSlug,
  type CreateHospitalInput,
} from '@/services/hospitals';
import type {
  HospitalContractStatus,
  HospitalSummary,
} from '@/types/hospital';

/**
 * 플랫폼 관리자 — 병원 목록·생성·상태 변경.
 *
 * 주의: UI는 role=admin 이상이 접근하나, 실제 쓰기는 RTDB Rules가
 * auth.token.role === 'platformAdmin'만 허용하므로 평범한 admin은 403.
 * 이 페이지는 platformAdmin 본인이 온보딩·계약 상태를 관리하는 용도.
 */
export function AdminHospitalsPage() {
  const [hospitals, setHospitals] = useState<HospitalSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const reload = async () => {
    try {
      setHospitals(await listHospitals());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const onStatusChange = async (id: string, status: HospitalContractStatus) => {
    try {
      await setHospitalContractStatus(id, status);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <AdminLayout
      title="병원 관리"
      description="플랫폼에 등록된 병원을 확인하고 계약 상태를 변경합니다."
      actions={
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary-container"
        >
          + 신규 병원
        </button>
      }
    >
      {error && (
        <div className="mb-4 rounded-xl bg-error-container p-3 text-sm text-error">
          {error}
        </div>
      )}

      {showCreate && (
        <CreateHospitalForm
          onCancel={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await reload();
          }}
        />
      )}

      <div className="overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest">
        <table className="w-full text-sm">
          <thead className="bg-surface-container text-xs uppercase text-on-surface-variant">
            <tr>
              <th className="px-4 py-3 text-left">이름</th>
              <th className="px-4 py-3 text-left">slug</th>
              <th className="px-4 py-3 text-left">상태</th>
              <th className="px-4 py-3 text-left">보기</th>
            </tr>
          </thead>
          <tbody>
            {hospitals === null ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-on-surface-variant">
                  로딩 중...
                </td>
              </tr>
            ) : hospitals.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-on-surface-variant">
                  등록된 병원이 없습니다.
                </td>
              </tr>
            ) : (
              hospitals.map((h) => (
                <tr key={h.id} className="border-t border-outline-variant">
                  <td className="px-4 py-3 font-medium">{h.name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{h.slug}</td>
                  <td className="px-4 py-3">
                    <StatusSelect
                      value={h.contractStatus}
                      onChange={(v) => onStatusChange(h.id, v)}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/h/${h.slug}/patient`}
                      className="text-primary underline"
                    >
                      앱 열기 ↗
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}

function StatusSelect({
  value,
  onChange,
}: {
  value: HospitalContractStatus;
  onChange: (v: HospitalContractStatus) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as HospitalContractStatus)}
      className="rounded-md border border-outline-variant bg-surface-container-lowest px-2 py-1 text-xs"
    >
      <option value="active">운영 중</option>
      <option value="pilot">파일럿</option>
      <option value="paused">일시 중지</option>
    </select>
  );
}

function CreateHospitalForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: () => void | Promise<void>;
}) {
  const [form, setForm] = useState<CreateHospitalInput>({
    slug: '',
    name: '',
    themeColor: '#004e9f',
  });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const slugInvalid = form.slug !== '' && !isValidSlug(form.slug.toLowerCase());

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    try {
      await createHospital(form);
      await onCreated();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
    >
      <h3 className="mb-3 font-semibold">신규 병원 등록</h3>
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_120px]">
        <label className="text-sm">
          이름
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            className="mt-1 w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm">
          Slug (URL)
          <input
            type="text"
            value={form.slug}
            onChange={(e) =>
              setForm({ ...form, slug: e.target.value.toLowerCase() })
            }
            placeholder="demo"
            required
            className={`mt-1 w-full rounded-md border px-3 py-2 font-mono text-xs ${
              slugInvalid
                ? 'border-error text-error'
                : 'border-outline-variant'
            }`}
          />
          {slugInvalid && (
            <span className="text-xs text-error">
              소문자 영문/숫자/하이픈, 2~32자
            </span>
          )}
        </label>
        <label className="text-sm">
          테마 색상
          <input
            type="color"
            value={form.themeColor ?? '#004e9f'}
            onChange={(e) => setForm({ ...form, themeColor: e.target.value })}
            className="mt-1 h-[38px] w-full rounded-md border border-outline-variant"
          />
        </label>
      </div>

      {err && <p className="mt-3 text-sm text-error">{err}</p>}

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={submitting || slugInvalid || !form.name || !form.slug}
          className="rounded-lg bg-primary px-4 py-2 text-sm text-on-primary disabled:opacity-50"
        >
          {submitting ? '생성 중...' : '생성'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-outline-variant px-4 py-2 text-sm"
        >
          취소
        </button>
      </div>
    </form>
  );
}
