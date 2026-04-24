import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ref, get } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { useAuthStore, selectIsAdmin } from '@/stores/authStore';

interface HospitalIndexRow {
  name: string;
  slug: string;
  contractStatus: string;
  themeColor?: string;
}

export function AdminHospitalsPage() {
  const [rows, setRows] = useState<Array<[string, HospitalIndexRow]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = useAuthStore(selectIsAdmin);
  const profile = useAuthStore((s) => s.profile);
  const isPlatformAdmin = profile?.role === 'platformAdmin';

  useEffect(() => {
    if (!isFirebaseConfigured()) return;
    void (async () => {
      try {
        const snap = await get(ref(db, 'hospital_index'));
        const data = (snap.val() ?? {}) as Record<string, HospitalIndexRow>;
        setRows(Object.entries(data).sort(([a], [b]) => a.localeCompare(b)));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setRows([]);
      }
    })();
  }, []);

  return (
    <AdminLayout
      title="병원 관리"
      description="플랫폼에 등록된 병원을 확인하고 계약 상태를 변경합니다."
      actions={
        isPlatformAdmin && (
          <button
            type="button"
            className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-on-primary"
            disabled
            title="Commit 10+에서 활성화 예정"
          >
            + 신규 병원
          </button>
        )
      }
    >
      {error && (
        <div className="mb-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-ambient">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-low text-xs uppercase tracking-wider text-on-surface-variant">
            <tr>
              <th className="px-4 py-3 text-left">이름</th>
              <th className="px-4 py-3 text-left">SLUG</th>
              <th className="px-4 py-3 text-left">상태</th>
              <th className="px-4 py-3 text-left">보기</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-container-high">
            {rows === null ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-on-surface-variant">
                  로딩 중...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-on-surface-variant">
                  등록된 병원이 없습니다.
                </td>
              </tr>
            ) : (
              rows.map(([hid, hospital]) => (
                <tr key={hid}>
                  <td className="px-4 py-3 text-on-surface">{hospital.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                    {hospital.slug}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        hospital.contractStatus === 'active'
                          ? 'bg-green-50 text-green-700'
                          : 'bg-surface-container-high text-on-surface-variant'
                      }`}
                    >
                      {hospital.contractStatus}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {isAdmin || isPlatformAdmin ? (
                      <Link
                        to={`/admin/hospitals/${hid}`}
                        className="rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary no-underline hover:bg-primary/20"
                      >
                        상세 / 편집
                      </Link>
                    ) : (
                      <span className="text-xs text-on-surface-variant">비공개</span>
                    )}
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
