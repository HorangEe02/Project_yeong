import { useCallback, useState } from 'react';
import { AlertTriangle, MapPin, Phone, RefreshCw } from 'lucide-react';

/**
 * 환자 응급 호출 카드 — 119 통화 + 현재 위치 표시.
 *
 * 본 컴포넌트는 `features.emergencyCall=true` 인 hospital 의 GuideTab 응급 모드에서만
 * 마운트된다. demo 병원 default false → admin 명시 enable 후에만 사용 가능.
 *
 * 동작:
 *  1. 「현재 위치 가져오기」 버튼 → `navigator.geolocation.getCurrentPosition`
 *     - HTTPS 필수 (LIVE OK, dev `localhost` 도 허용)
 *     - 권한 거부 시 fallback "수동으로 위치 알려주세요" 메시지
 *  2. 위도/경도/정확도 + Google Maps 링크 표시
 *  3. 「🆘 119 신고」 버튼 → 첫 클릭은 확인 dialog, 두 번째 클릭에 `tel:119`
 *
 * 윤리 안전 장치:
 *  - 확인 dialog 강제 — 단일 클릭으로 119 통화 트리거되지 않음
 *  - 「취소」 버튼으로 dialog 빠져나갈 수 있음
 *  - 응급 컨텍스트 명시 (환자가 의도적으로 응급 모드에 진입해야 함)
 *
 * 비범위 (별도 sprint):
 *  - 병원 RTDB 로 위치 자동 전송 (staff console 인지)
 *  - 응급실 수용 가능 인원 표시
 *  - 보호자 자동 알림
 */

type LocationState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | {
      kind: 'success';
      lat: number;
      lng: number;
      accuracy: number;
      capturedAt: number;
    }
  | { kind: 'denied' }
  | { kind: 'unsupported' }
  | { kind: 'error'; msg: string };

const GEOLOCATION_TIMEOUT_MS = 15_000;

export function EmergencyCallCard() {
  const [location, setLocation] = useState<LocationState>({ kind: 'idle' });
  const [confirming, setConfirming] = useState(false);

  const requestLocation = useCallback(() => {
    if (
      typeof navigator === 'undefined' ||
      !('geolocation' in navigator) ||
      !navigator.geolocation
    ) {
      setLocation({ kind: 'unsupported' });
      return;
    }
    setLocation({ kind: 'loading' });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          kind: 'success',
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          capturedAt: Date.now(),
        });
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setLocation({ kind: 'denied' });
        } else if (err.code === err.TIMEOUT) {
          setLocation({
            kind: 'error',
            msg: '위치 확인이 시간 초과되었습니다.',
          });
        } else {
          setLocation({
            kind: 'error',
            msg: '위치 정보를 가져오지 못했습니다.',
          });
        }
      },
      {
        enableHighAccuracy: true,
        timeout: GEOLOCATION_TIMEOUT_MS,
        maximumAge: 30_000,
      },
    );
  }, []);

  const onCallEmergency = useCallback(() => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    // 두 번째 클릭 — tel: 트리거 (모바일 OS 가 전화 앱 실행)
    window.location.href = 'tel:119';
    setConfirming(false);
  }, [confirming]);

  const cancelConfirm = useCallback(() => setConfirming(false), []);

  return (
    <section
      role="region"
      aria-label="응급 호출"
      data-testid="emergency-call-card"
      className="flex flex-col gap-4 rounded-xl border-2 border-error bg-error-container/30 p-5 sm:p-6"
    >
      <header className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-error" />
        <div>
          <h3 className="text-base font-bold text-error">응급 호출</h3>
          <p className="mt-1 text-sm text-on-surface">
            지금 도움이 필요하시면 119 에 신고하고 현재 위치를 직접 알려 주세요.
          </p>
        </div>
      </header>

      {/* 위치 영역 */}
      <LocationPanel state={location} onRequest={requestLocation} />

      {/* 119 통화 버튼 + 확인 dialog */}
      {!confirming ? (
        <button
          type="button"
          onClick={onCallEmergency}
          data-testid="emergency-call-button"
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-error py-4 text-base font-bold text-on-error shadow-ambient hover:opacity-90"
        >
          <Phone className="h-5 w-5" />
          🆘 119 신고
        </button>
      ) : (
        <div
          role="alertdialog"
          aria-label="119 통화 확인"
          data-testid="emergency-confirm-dialog"
          className="rounded-xl bg-surface-container-lowest p-4"
        >
          <p className="text-sm font-semibold text-on-surface">
            정말 119 에 전화하시겠습니까?
          </p>
          <p className="mt-1 text-xs text-on-surface-variant">
            확인을 누르면 즉시 전화 앱이 실행됩니다. 통화 중 화면의 위도·경도를 직접 알려 주세요.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={onCallEmergency}
              data-testid="emergency-confirm-button"
              className="flex-1 rounded-lg bg-error px-4 py-2 text-sm font-semibold text-on-error"
            >
              <a
                href="tel:119"
                className="block w-full no-underline text-on-error"
                aria-label="119 에 전화 걸기"
              >
                전화 걸기
              </a>
            </button>
            <button
              type="button"
              onClick={cancelConfirm}
              data-testid="emergency-cancel-button"
              className="flex-1 rounded-lg bg-surface-container-high px-4 py-2 text-sm font-medium text-on-surface"
            >
              취소
            </button>
          </div>
        </div>
      )}

      <p className="text-[11px] text-on-surface-variant">
        ※ 본 화면은 위치 정보 자동 전송 기능이 없습니다. 통화 중 화면에 표시된
        위도·경도를 직접 안내해 주세요.
      </p>
    </section>
  );
}

interface LocationPanelProps {
  state: LocationState;
  onRequest: () => void;
}

function LocationPanel({ state, onRequest }: LocationPanelProps) {
  if (state.kind === 'idle') {
    return (
      <button
        type="button"
        onClick={onRequest}
        data-testid="emergency-location-request"
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-on-primary"
      >
        <MapPin className="h-4 w-4" />
        현재 위치 가져오기
      </button>
    );
  }

  if (state.kind === 'loading') {
    return (
      <div
        data-testid="emergency-location-loading"
        className="flex items-center justify-center gap-2 rounded-lg bg-surface-container-lowest p-3 text-sm text-on-surface-variant"
      >
        <RefreshCw className="h-4 w-4 animate-spin" />
        위치 정보를 불러오는 중...
      </div>
    );
  }

  if (state.kind === 'denied') {
    return (
      <div
        role="alert"
        data-testid="emergency-location-denied"
        className="rounded-lg bg-surface-container-lowest p-3 text-sm"
      >
        <p className="font-medium text-on-surface">위치 권한이 거부되었습니다</p>
        <p className="mt-1 text-xs text-on-surface-variant">
          브라우저 설정에서 위치 권한을 허용한 뒤 다시 시도하거나, 통화 중 위치를 직접 알려 주세요.
        </p>
        <button
          type="button"
          onClick={onRequest}
          className="mt-2 text-xs font-medium text-primary"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (state.kind === 'unsupported') {
    return (
      <div
        data-testid="emergency-location-unsupported"
        className="rounded-lg bg-surface-container-lowest p-3 text-xs text-on-surface-variant"
      >
        이 브라우저는 위치 정보를 지원하지 않습니다. 통화 중 위치를 직접 알려 주세요.
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div
        role="alert"
        data-testid="emergency-location-error"
        className="rounded-lg bg-surface-container-lowest p-3 text-sm"
      >
        <p className="font-medium text-on-surface">{state.msg}</p>
        <button
          type="button"
          onClick={onRequest}
          className="mt-1 text-xs font-medium text-primary"
        >
          다시 시도
        </button>
      </div>
    );
  }

  // success
  const mapsUrl = `https://maps.google.com/?q=${state.lat},${state.lng}`;
  return (
    <div
      data-testid="emergency-location-success"
      className="rounded-lg bg-surface-container-lowest p-4 shadow-ambient"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
          현재 위치
        </p>
        <button
          type="button"
          onClick={onRequest}
          className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-primary"
          aria-label="위치 새로고침"
        >
          <RefreshCw className="h-3 w-3" />
          새로고침
        </button>
      </div>
      <div className="mt-2 space-y-1 font-mono text-sm text-on-surface tabular-nums">
        <p>위도: {state.lat.toFixed(6)}</p>
        <p>경도: {state.lng.toFixed(6)}</p>
      </div>
      <p className="mt-1 text-[11px] text-on-surface-variant">
        정확도: ±{Math.round(state.accuracy)}m
      </p>
      <a
        href={mapsUrl}
        target="_blank"
        rel="noopener noreferrer"
        data-testid="emergency-location-map-link"
        className="mt-3 flex items-center justify-center gap-1 rounded-lg bg-surface-container-high px-3 py-2 text-xs font-medium text-primary no-underline hover:opacity-90"
      >
        <MapPin className="h-3 w-3" />
        지도에서 보기
      </a>
    </div>
  );
}
