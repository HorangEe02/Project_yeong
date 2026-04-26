import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertTriangle, Map as MapIcon, QrCode } from 'lucide-react';
import { PatientMapBrowseView } from '@/components/patient/PatientMapBrowseView';
import { QRGuidePlaceholder } from '@/components/patient/QRGuidePlaceholder';
import { EmergencyCallCard } from '@/components/patient/EmergencyCallCard';
import { useFeature } from '@/contexts/HospitalContext';

/**
 * 안내 탭 — V1 PatientPage 의 모드 탭 (지도 보기 / QR 안내) 을 6-tab shell 로 이식.
 * + Scenario 응급: features.emergencyCall=true 인 hospital 만 「응급 호출」 3rd 모드 노출.
 *
 * 모드:
 *  - 'guide' (기본) → QRGuidePlaceholder — sessionId 없이 home 진입한 환자에게
 *    QR 코드 발급 절차 안내 + 자가 발급
 *  - 'browse' → PatientMapBrowseView — 4층 평면도 + POI 마커 자유 탐색
 *  - 'emergency' (features.emergencyCall true 일 때만) → EmergencyCallCard — 119 + 위치
 *
 * URL 동기화: `?mode=browse|emergency` 또는 누락 (default 'guide').
 *  - emergency 모드 진입 시 features.emergencyCall=false 면 'guide' 로 fallback
 *  - HospitalHomePage 의 `?tab=` 와 공존
 *  - replace navigation — history stack 안 늘림
 *
 * Mount-all 정책: 활성 패널 모두 DOM 에 마운트 + `hidden` 속성으로 표시만 토글.
 *  - 지도 viewport (zoom/pan, 선택 POI) 가 모드 전환에서 보존
 *  - emergency 패널은 features OFF 면 마운트 자체 안 함 (geolocation 권한 prompt 누수 방지)
 *
 * sessionId 가 있는 진입 (`/h/:slug/patient/:sessionId`) 은 본 탭이 아닌 PatientPage
 * 가 처리 — 본 컴포넌트 비범위.
 */

type Mode = 'browse' | 'guide' | 'emergency';

export function GuideTab() {
  const [searchParams, setSearchParams] = useSearchParams();
  const emergencyOn = useFeature('emergencyCall');

  const paramMode = searchParams.get('mode');
  let mode: Mode;
  if (paramMode === 'browse') mode = 'browse';
  else if (paramMode === 'emergency' && emergencyOn) mode = 'emergency';
  else mode = 'guide';

  const setMode = useCallback(
    (next: Mode) => {
      const params = new URLSearchParams(searchParams);
      if (next === 'guide') params.delete('mode');
      else params.set('mode', next);
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  let description: string;
  if (mode === 'browse')
    description = '병원 지도를 자유롭게 탐색하세요. 층과 POI 를 선택해 위치를 확인할 수 있어요.';
  else if (mode === 'emergency')
    description = '응급 상황에서 119 에 신고하고 현재 위치를 직접 알려 주세요.';
  else description = 'QR 코드를 의료진에게 보여 주면 동선 안내가 시작됩니다.';

  return (
    <section className="space-y-4 p-4">
      <header>
        <h2 className="text-xl font-semibold text-on-surface">안내</h2>
        <p className="mt-1 text-sm text-on-surface-variant">{description}</p>
      </header>

      <div
        role="tablist"
        aria-label="안내 모드"
        className="flex w-full max-w-md gap-1 rounded-xl bg-surface-container-high p-1 sm:w-auto"
      >
        <ModeButton
          value="browse"
          activeValue={mode}
          icon={MapIcon}
          label="지도 보기"
          onClick={() => setMode('browse')}
        />
        <ModeButton
          value="guide"
          activeValue={mode}
          icon={QrCode}
          label="QR 안내"
          onClick={() => setMode('guide')}
        />
        {emergencyOn && (
          <ModeButton
            value="emergency"
            activeValue={mode}
            icon={AlertTriangle}
            label="응급 호출"
            onClick={() => setMode('emergency')}
            tone="error"
          />
        )}
      </div>

      <div role="tabpanel" hidden={mode !== 'browse'} aria-label="지도 보기 패널">
        <PatientMapBrowseView />
      </div>
      <div role="tabpanel" hidden={mode !== 'guide'} aria-label="QR 안내 패널">
        <QRGuidePlaceholder />
      </div>
      {emergencyOn && (
        <div
          role="tabpanel"
          hidden={mode !== 'emergency'}
          aria-label="응급 호출 패널"
        >
          <EmergencyCallCard />
        </div>
      )}
    </section>
  );
}

interface ModeButtonProps {
  value: Mode;
  activeValue: Mode;
  icon: typeof MapIcon;
  label: string;
  onClick: () => void;
  /** 'error' tone 은 응급 모드에서 빨간색 강조. */
  tone?: 'error';
}

function ModeButton({
  value,
  activeValue,
  icon: Icon,
  label,
  onClick,
  tone,
}: ModeButtonProps) {
  const isActive = value === activeValue;
  const activeColor = tone === 'error' ? 'text-error' : 'text-primary';
  const inactiveColor =
    tone === 'error' ? 'text-error/80' : 'text-on-surface-variant';
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={onClick}
      data-testid={`guide-mode-${value}`}
      className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-all sm:flex-none sm:px-4 ${
        isActive
          ? `bg-surface-container-lowest ${activeColor} shadow-ambient`
          : `${inactiveColor} hover:bg-surface-container`
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}
