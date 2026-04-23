import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams, Navigate } from 'react-router-dom';
import { listActiveHospitals } from '@/services/hospitals';
import type { HospitalSummary } from '@/types/hospital';

/**
 * 병원 선택 페이지 — 가입 직후 또는 멀티 병원 사용자가 접근.
 *
 * 동작:
 * - 활성/파일럿 병원만 표시
 * - 검색창으로 이름 필터
 * - URL 쿼리 `?hospital=demo` 존재 시 해당 slug의 환자 홈으로 자동 이동
 *   (로비 QR 부트스트랩 · 외부 링크 진입 시나리오)
 * - 빈 상태: "가입 가능한 병원이 없습니다" 안내
 *
 * 라우트: `/hospitals/select`
 */
export function SelectHospitalPage() {
  const [searchParams] = useSearchParams();
  const bootstrapSlug = searchParams.get('hospital');

  const [hospitals, setHospitals] = useState<HospitalSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    let mounted = true;
    listActiveHospitals()
      .then((list) => {
        if (mounted) setHospitals(list);
      })
      .catch((e: unknown) => {
        if (mounted) {
          setError(e instanceof Error ? e.message : String(e));
          setHospitals([]);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!hospitals) return null;
    const q = query.trim().toLowerCase();
    if (!q) return hospitals;
    return hospitals.filter(
      (h) =>
        h.name.toLowerCase().includes(q) || h.slug.toLowerCase().includes(q),
    );
  }, [hospitals, query]);

  // URL 쿼리로 직접 진입한 경우 해당 병원으로 바로 이동
  if (
    bootstrapSlug &&
    hospitals &&
    hospitals.some((h) => h.slug === bootstrapSlug)
  ) {
    return <Navigate to={`/h/${bootstrapSlug}/patient/home`} replace />;
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold mb-2">병원 선택</h1>
      <p className="text-on-surface-variant mb-6">
        이용하실 병원을 선택해 주세요.
      </p>

      <label className="block mb-6">
        <span className="sr-only">병원 검색</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="병원 이름 검색"
          className="w-full px-4 py-3 rounded-xl border border-outline-variant bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-primary"
          aria-label="병원 이름 검색"
        />
      </label>

      {error && (
        <div className="mb-4 p-4 rounded-xl bg-error-container text-error">
          병원 목록을 불러오지 못했습니다: {error}
        </div>
      )}

      {filtered === null ? (
        <div className="text-center py-12 text-on-surface-variant">
          병원 목록을 불러오는 중...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-on-surface-variant mb-2">
            {query
              ? '검색 결과가 없습니다.'
              : '가입 가능한 병원이 없습니다.'}
          </p>
          {!query && (
            <p className="text-sm text-on-surface-variant">
              코드를 입력하거나 병원에 문의해 주세요.
            </p>
          )}
        </div>
      ) : (
        <ul className="space-y-3" role="list">
          {filtered.map((h) => (
            <li key={h.id}>
              <Link
                to={`/h/${h.slug}/patient/home`}
                className="flex items-center gap-4 p-4 rounded-xl bg-surface-container-lowest border border-outline-variant hover:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition"
              >
                <HospitalLogo logoUrl={h.logoUrl} name={h.name} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{h.name}</div>
                  <div className="text-sm text-on-surface-variant flex items-center gap-2">
                    <span>/{h.slug}</span>
                    <StatusBadge status={h.contractStatus} />
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function HospitalLogo({
  logoUrl,
  name,
}: {
  logoUrl?: string;
  name: string;
}) {
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt=""
        className="w-12 h-12 rounded-lg object-cover bg-surface-container"
      />
    );
  }
  // 로고 없으면 첫 글자로 placeholder
  const initial = name.charAt(0);
  return (
    <div
      className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary font-semibold"
      aria-hidden="true"
    >
      {initial}
    </div>
  );
}

function StatusBadge({ status }: { status: HospitalSummary['contractStatus'] }) {
  const label = status === 'active' ? '운영 중' : status === 'pilot' ? '파일럿' : '일시 중지';
  const cls =
    status === 'active'
      ? 'bg-primary/10 text-primary'
      : status === 'pilot'
        ? 'bg-secondary-fixed text-on-secondary-fixed'
        : 'bg-surface-container text-on-surface-variant';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
  );
}
