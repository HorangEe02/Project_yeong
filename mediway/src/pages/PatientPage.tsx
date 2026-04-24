import { useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Map as MapIcon, QrCode } from 'lucide-react';
import { PatientDashboard } from '@/components/patient/PatientDashboard';
import { PatientMapBrowseView } from '@/components/patient/PatientMapBrowseView';

type Mode = 'browse' | 'guide';

const MODE_TABS: { value: Mode; label: string; icon: typeof MapIcon }[] = [
  { value: 'browse', label: '지도 보기', icon: MapIcon },
  { value: 'guide', label: 'QR 안내', icon: QrCode },
];

export function PatientPage() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  // sessionId(직접 링크)가 있으면 guide 고정, 아니면 URL 쿼리, 기본값은 guide
  const paramMode = searchParams.get('mode');
  const mode: Mode = sessionId
    ? 'guide'
    : paramMode === 'browse'
      ? 'browse'
      : 'guide';

  const setMode = useCallback(
    (next: Mode) => {
      const params = new URLSearchParams(searchParams);
      if (next === 'guide') {
        params.delete('mode');
      } else {
        params.set('mode', next);
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const description =
    mode === 'browse'
      ? '병원 지도를 자유롭게 탐색하세요. 층과 POI를 선택해 위치를 확인할 수 있어요.'
      : 'QR 코드를 간호사에게 보여주고, 안내에 따라 이동하세요.';

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 lg:max-w-5xl">
      {/* 웹: 2열 / 모바일: 1열 */}
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* 메인: 환자 대시보드 */}
        <div>
          <div className="mb-4 lg:mb-6">
            <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
              Patient Navigation
            </p>
            <h1 className="text-2xl font-bold text-on-surface">환자 동선 안내</h1>
            <p className="mt-1 text-sm text-on-surface-variant">{description}</p>
          </div>

          {/* 모드 탭 (sessionId 직접 진입 시 비표시) */}
          {!sessionId && (
            <div className="mb-4 flex w-full gap-1 rounded-xl bg-surface-container-high p-1 sm:w-auto sm:self-start">
              {MODE_TABS.map(({ value, label, icon: Icon }) => {
                const isActive = mode === value;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setMode(value)}
                    aria-pressed={isActive}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-all sm:flex-none sm:px-4 ${
                      isActive
                        ? 'bg-surface-container-lowest text-primary shadow-ambient'
                        : 'text-on-surface-variant hover:bg-surface-container'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </button>
                );
              })}
            </div>
          )}

          {/* 지도 보기 뷰 */}
          <div className={mode === 'browse' ? 'block' : 'hidden'}>
            <PatientMapBrowseView />
          </div>

          {/* QR 안내 뷰 — 세션 유지를 위해 항상 마운트, visibility만 토글 */}
          <div className={mode === 'guide' ? 'block' : 'hidden'}>
            <PatientDashboard />
          </div>
        </div>

        {/* 사이드바 (웹에서만) */}
        <aside className="hidden space-y-4 lg:block">
          {/* 병원 정보 카드 */}
          <div className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              Hospital Info
            </h3>
            <div className="flex flex-col gap-3">
              <InfoRow label="병원" value="MediWay 데모 병원" />
              <InfoRow label="건물" value="본관 (4층)" />
              <InfoRow label="운영 시간" value="09:00 - 18:00" />
              <InfoRow label="응급 연락" value="02-000-0000" />
            </div>
          </div>

          {/* 안내 팁 */}
          <div className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              이용 안내
            </h3>
            <div className="flex flex-col gap-3">
              <TipItem
                icon="🏥"
                title="엘리베이터 이용"
                desc="본관 엘리베이터는 각 층 우측에 위치합니다."
              />
              <TipItem
                icon="💊"
                title="약국 안내"
                desc="외래약국은 1층 정문 옆에 있습니다."
              />
              <TipItem
                icon="🅿️"
                title="주차 정산"
                desc="원무과에서 주차 할인 도장을 받으세요."
              />
              <TipItem
                icon="❓"
                title="도움이 필요하면"
                desc="보라색 조끼를 입은 안내 도우미에게 문의하세요."
              />
            </div>
          </div>

          {/* 근처 편의시설 */}
          <div className="rounded-xl bg-surface-container-lowest p-5 shadow-ambient">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              Nearby Services
            </h3>
            <div className="flex flex-col gap-2">
              <NearbyItem name="편의점" location="1층 · 45m" />
              <NearbyItem name="화장실" location="현재 층 · 30m" />
              <NearbyItem name="엘리베이터 A" location="현재 층 · 20m" />
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

// --- 보조 컴포넌트 ---

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-on-surface-variant">{label}</span>
      <span className="text-sm font-medium text-on-surface">{value}</span>
    </div>
  );
}

function TipItem({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg bg-surface-container-low p-3">
      <span className="text-lg">{icon}</span>
      <div>
        <p className="text-sm font-medium text-on-surface">{title}</p>
        <p className="text-xs text-on-surface-variant">{desc}</p>
      </div>
    </div>
  );
}

function NearbyItem({ name, location }: { name: string; location: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-surface-container-low p-2.5">
      <span className="text-sm font-medium text-on-surface">{name}</span>
      <span className="text-xs text-on-surface-variant">{location}</span>
    </div>
  );
}
