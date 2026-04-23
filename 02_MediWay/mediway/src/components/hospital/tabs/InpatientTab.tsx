import { useState } from 'react';
import { BedDouble, Calendar, Users } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';

/**
 * 입원 탭 — 현재 입원 중인 환자용.
 *
 * P3 C12: 담당 의료진 안내 카드 + 면회 예약 간이 폼.
 * 실 데이터 연동 (EMR 통합 · 면회 예약 RTDB 저장)은 파일럿 병원 계약 후.
 */
export function InpatientTab() {
  const { hospital } = useHospital();

  if (!hospital?.features?.inpatient) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
        <div className="p-6 text-center text-on-surface-variant">
          이 병원은 입원 기능을 아직 활성화하지 않았습니다.
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      <h2 className="sr-only">입원</h2>

      <section className="mb-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
        <header className="mb-3 flex items-center gap-2">
          <Users className="h-5 w-5 text-primary" aria-hidden="true" />
          <h3 className="text-base font-semibold">담당 의료진</h3>
        </header>
        <div className="flex flex-col gap-2 text-sm">
          <StaffRow role="주치의" name="가까운 시일 내 안내 예정" />
          <StaffRow role="담당 간호사" name="가까운 시일 내 안내 예정" />
        </div>
        <p className="mt-3 text-xs text-on-surface-variant">
          정확한 담당자 정보는 입원 접수 시 병동에서 안내받으실 수 있습니다.
        </p>
      </section>

      <VisitReservationForm />

      <section className="mt-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
        <header className="mb-2 flex items-center gap-2">
          <BedDouble className="h-5 w-5 text-primary" aria-hidden="true" />
          <h3 className="text-base font-semibold">퇴원 수속 안내</h3>
        </header>
        <p className="text-sm text-on-surface-variant">
          퇴원 예정일 하루 전 병동 간호사실에서 수속 안내를 받으시고,
          원무과 대기 순번은 이 앱 홈 화면에서 실시간 확인하실 수 있습니다.
        </p>
      </section>
    </main>
  );
}

function StaffRow({ role, name }: { role: string; name: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-surface-container-low px-3 py-2">
      <span className="text-on-surface-variant">{role}</span>
      <span className="font-medium">{name}</span>
    </div>
  );
}

interface VisitReservation {
  id: string;
  visitorName: string;
  relation: string;
  dateTime: string;
}

function VisitReservationForm() {
  const [visitorName, setVisitorName] = useState('');
  const [relation, setRelation] = useState('');
  const [dateTime, setDateTime] = useState('');
  const [list, setList] = useState<VisitReservation[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const canSubmit = visitorName.trim() && relation.trim() && dateTime;

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    if (new Date(dateTime).getTime() < Date.now()) {
      setErr('과거 시각은 예약할 수 없습니다');
      return;
    }
    setErr(null);
    setList((prev) => [
      ...prev,
      {
        id: `vis-${Date.now()}`,
        visitorName: visitorName.trim(),
        relation: relation.trim(),
        dateTime,
      },
    ]);
    setVisitorName('');
    setRelation('');
    setDateTime('');
  };

  const onRemove = (id: string) => {
    setList((prev) => prev.filter((v) => v.id !== id));
  };

  return (
    <section className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
      <header className="mb-3 flex items-center gap-2">
        <Calendar className="h-5 w-5 text-primary" aria-hidden="true" />
        <h3 className="text-base font-semibold">면회 예약</h3>
      </header>

      <form onSubmit={onSubmit} className="grid gap-2 sm:grid-cols-2">
        <label className="text-sm">
          <span className="sr-only">방문자 이름</span>
          <input
            value={visitorName}
            onChange={(e) => setVisitorName(e.target.value)}
            placeholder="방문자 이름"
            className="w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="sr-only">관계</span>
          <input
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
            placeholder="관계 (예: 배우자, 자녀)"
            className="w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm sm:col-span-2">
          <span className="sr-only">방문 일시</span>
          <input
            type="datetime-local"
            value={dateTime}
            onChange={(e) => setDateTime(e.target.value)}
            className="w-full rounded-md border border-outline-variant px-3 py-2 text-sm"
          />
        </label>
        {err && (
          <p
            role="alert"
            className="sm:col-span-2 text-xs text-error"
          >
            {err}
          </p>
        )}
        <button
          type="submit"
          disabled={!canSubmit}
          className="sm:col-span-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary disabled:opacity-50"
        >
          면회 예약 등록
        </button>
      </form>

      {list.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 text-sm">
          {list.map((v) => (
            <li
              key={v.id}
              className="flex items-center justify-between rounded-lg bg-surface-container-low px-3 py-2"
            >
              <span>
                <span className="font-medium">{v.visitorName}</span>
                <span className="ml-2 text-xs text-on-surface-variant">
                  · {v.relation} · {new Date(v.dateTime).toLocaleString('ko-KR')}
                </span>
              </span>
              <button
                type="button"
                onClick={() => onRemove(v.id)}
                className="rounded-md px-2 py-0.5 text-xs text-on-surface-variant hover:bg-surface-container"
              >
                삭제
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-xs text-on-surface-variant">
        현재는 로컬 저장 (데모) — 실 면회 예약은 파일럿 병원 연동 후 활성화됩니다.
      </p>
    </section>
  );
}
