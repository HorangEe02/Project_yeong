import { onValue, ref, type Unsubscribe } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import type { HospitalProfile } from '@/types/hospital';

/**
 * `/hospitals/{slug}/profile` 실시간 구독.
 *
 * `HospitalShell` 가 슬러그 단위 라우트에 진입할 때 호출하며, 다음을 보장한다:
 *  - 경로가 비어 있으면 `onData(null)` (HospitalShell 가 404 분기)
 *  - 데이터가 있으면 그대로 `HospitalProfile` 캐스트 후 콜백 (status 검증은 컨슈머)
 *  - 권한 거부/네트워크 에러는 `onError` 로 전파
 *
 * 권한 (database.rules.json):
 *  - `/hospitals/{$slug}/profile` 는 정상 운영 중인 hospital 의 경우 익명 read 허용
 *    (QR 환자 진입 시 로그인 전이라도 슬러그 검증 가능해야 함)
 */
export function subscribeHospitalProfile(
  slug: string,
  onData: (profile: HospitalProfile | null) => void,
  onError?: (err: Error) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    onData(null);
    return () => {};
  }
  if (!slug) {
    onData(null);
    return () => {};
  }
  const path = `hospitals/${slug}/profile`;
  return onValue(
    ref(db, path),
    (snap) => {
      if (!snap.exists()) {
        onData(null);
        return;
      }
      const raw = snap.val() as Partial<HospitalProfile> | null;
      if (!raw) {
        onData(null);
        return;
      }
      // id 가 비어 있으면 slug 로 보강 — RTDB 데이터 일관성 보강 (legacy 누락 호환)
      const profile: HospitalProfile = {
        ...(raw as HospitalProfile),
        id: raw.id ?? slug,
        name: raw.name ?? slug,
      };
      onData(profile);
    },
    (err) => {
      // 401/403 거부도 여기로 들어옴 — 컨슈머가 forbidden 으로 처리할 수 있게 전파
      console.error('[hospitalProfile] subscription error:', err);
      onError?.(err as Error);
    },
  );
}

/** `#RRGGBB` 6자리 hex 만 통과. 그 외는 fallback 으로 대체할 수 있게 false. */
const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

/** themeColor 가 valid 이면 그대로, 아니면 MediWay primary `#004e9f` 반환. */
export function resolveThemeColor(input: string | undefined | null): string {
  if (input && HEX_COLOR.test(input)) return input;
  return '#004e9f';
}
