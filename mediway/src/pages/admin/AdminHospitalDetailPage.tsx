import { useEffect, useState, type FormEvent } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ref, get, update } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { useAuthStore } from '@/stores/authStore';
import { appendAudit } from '@/services/auditLog';

interface HospitalProfile {
  name: string;
  slug: string;
  contractStatus: 'active' | 'trial' | 'suspended';
  themeColor?: string;
  features?: Record<string, boolean>;
  createdAt?: number;
  updatedAt?: number;
}

const FEATURE_KEYS: Array<{ key: string; label: string }> = [
  { key: 'appointments', label: '외래 예약' },
  { key: 'inpatient', label: '입원' },
  { key: 'checkup', label: '건강검진' },
  { key: 'payment', label: '결제' },
  { key: 'prescription', label: '처방전' },
  { key: 'aiTriage', label: 'AI 증상 분류' },
  { key: 'familyDelegation', label: '가족 대리' },
  { key: 'healthRecords', label: '검사결과 보관' },
  { key: 'parking', label: '주차 할인' },
];

const STATUS_OPTIONS: Array<{ value: HospitalProfile['contractStatus']; label: string }> = [
  { value: 'active', label: '활성' },
  { value: 'trial', label: '시범' },
  { value: 'suspended', label: '중단' },
];

export function AdminHospitalDetailPage() {
  const { hospitalId = '' } = useParams<{ hospitalId: string }>();
  const profile = useAuthStore((s) => s.profile);
  const isPlatformAdmin = profile?.role === 'platformAdmin';
  const isHospitalAdmin =
    profile?.role === 'admin' && profile.hospitalId === hospitalId;
  const canEdit = isPlatformAdmin || isHospitalAdmin;

  const [data, setData] = useState<HospitalProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isFirebaseConfigured() || !hospitalId) return;
    void (async () => {
      try {
        const snap = await get(ref(db, `hospitals/${hospitalId}/profile`));
        if (!snap.exists()) {
          setError('해당 병원 프로필이 없습니다.');
        } else {
          setData(snap.val() as HospitalProfile);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [hospitalId]);

  const onSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!data || !canEdit) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const now = Date.now();
      const payload = { ...data, updatedAt: now };
      await update(ref(db, `hospitals/${hospitalId}/profile`), payload);
      // hospital_index도 동기화 (platformAdmin만 write 가능 — admin은 denied여도 silent)
      try {
        await update(ref(db, `hospital_index/${hospitalId}`), {
          name: data.name,
          slug: data.slug,
          contractStatus: data.contractStatus,
          themeColor: data.themeColor ?? null,
        });
      } catch {
        // admin이면 hospital_index write 권한 없음 — 스킵
      }
      await appendAudit('hospital.profile.update', hospitalId, {
        name: data.name,
        contractStatus: data.contractStatus,
      });
      setSaveMsg('저장되었습니다.');
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const updateFeature = (key: string, checked: boolean) => {
    if (!data) return;
    setData({
      ...data,
      features: { ...(data.features ?? {}), [key]: checked },
    });
  };

  return (
    <AdminLayout
      title={data?.name ?? '병원 상세'}
      description={`SLUG: ${hospitalId} · ${canEdit ? '편집 가능' : '읽기 전용'}`}
      actions={
        <Link
          to="/admin/hospitals"
          className="rounded-lg border border-surface-container-high px-3 py-2 text-sm text-on-surface no-underline hover:bg-surface-container-low"
        >
          ← 목록
        </Link>
      }
    >
      {error && (
        <div className="mb-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      {saveMsg && (
        <div className="mb-3 rounded-xl bg-green-50 px-4 py-3 text-sm text-green-700">
          {saveMsg}
        </div>
      )}
      {loading ? (
        <p className="text-sm text-on-surface-variant">로딩 중...</p>
      ) : !data ? (
        <p className="text-sm text-on-surface-variant">데이터 없음</p>
      ) : (
        <form onSubmit={onSave} className="space-y-6">
          <section className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h2 className="mb-3 text-sm font-semibold text-on-surface">기본 정보</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
                이름
                <input
                  type="text"
                  className="rounded-lg border border-surface-container-high bg-surface-container-low px-3 py-2 text-sm text-on-surface disabled:opacity-70"
                  value={data.name}
                  disabled={!canEdit}
                  onChange={(e) => setData({ ...data, name: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
                SLUG (변경 불가)
                <input
                  type="text"
                  className="rounded-lg border border-surface-container-high bg-surface-container px-3 py-2 text-sm font-mono text-on-surface-variant"
                  value={data.slug}
                  disabled
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
                계약 상태
                <select
                  className="rounded-lg border border-surface-container-high bg-surface-container-low px-3 py-2 text-sm text-on-surface disabled:opacity-70"
                  value={data.contractStatus}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setData({
                      ...data,
                      contractStatus: e.target.value as HospitalProfile['contractStatus'],
                    })
                  }
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
                테마 컬러
                <div className="flex gap-2">
                  <input
                    type="color"
                    className="h-9 w-12 rounded-lg border border-surface-container-high disabled:opacity-70"
                    value={data.themeColor ?? '#0B4EBA'}
                    disabled={!canEdit}
                    onChange={(e) => setData({ ...data, themeColor: e.target.value })}
                  />
                  <input
                    type="text"
                    className="flex-1 rounded-lg border border-surface-container-high bg-surface-container-low px-3 py-2 font-mono text-sm text-on-surface disabled:opacity-70"
                    value={data.themeColor ?? ''}
                    disabled={!canEdit}
                    onChange={(e) => setData({ ...data, themeColor: e.target.value })}
                  />
                </div>
              </label>
            </div>
          </section>

          <section className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h2 className="mb-3 text-sm font-semibold text-on-surface">기능 토글</h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURE_KEYS.map(({ key, label }) => (
                <label
                  key={key}
                  className="flex items-center gap-2 rounded-lg border border-surface-container-high px-3 py-2 text-sm"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={!!data.features?.[key]}
                    disabled={!canEdit}
                    onChange={(e) => updateFeature(key, e.target.checked)}
                  />
                  <span>{label}</span>
                  <span className="ml-auto font-mono text-[10px] text-on-surface-variant">
                    {key}
                  </span>
                </label>
              ))}
            </div>
          </section>

          <section className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h2 className="mb-3 text-sm font-semibold text-on-surface">타임스탬프</h2>
            <dl className="grid gap-2 text-xs sm:grid-cols-2">
              <div>
                <dt className="text-on-surface-variant">생성일</dt>
                <dd className="font-mono text-on-surface">
                  {data.createdAt ? new Date(data.createdAt).toISOString() : '-'}
                </dd>
              </div>
              <div>
                <dt className="text-on-surface-variant">마지막 수정</dt>
                <dd className="font-mono text-on-surface">
                  {data.updatedAt ? new Date(data.updatedAt).toISOString() : '-'}
                </dd>
              </div>
            </dl>
          </section>

          <div className="flex justify-end gap-2">
            {!canEdit && (
              <p className="mr-auto text-xs text-on-surface-variant">
                읽기 전용 — admin이 아닙니다.
              </p>
            )}
            <Link
              to="/admin/hospitals"
              className="rounded-lg border border-surface-container-high px-4 py-2 text-sm text-on-surface no-underline hover:bg-surface-container-low"
            >
              취소
            </Link>
            <button
              type="submit"
              disabled={!canEdit || saving}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
            >
              {saving ? '저장 중...' : '저장'}
            </button>
          </div>
        </form>
      )}
    </AdminLayout>
  );
}
