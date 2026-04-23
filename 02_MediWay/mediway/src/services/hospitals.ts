import { ref, get, update, onValue, type Unsubscribe } from 'firebase/database';
import { db, isFirebaseConfigured } from '@/config/firebase';
import {
  DEFAULT_HOSPITAL_FEATURES,
  type HospitalProfile,
  type HospitalRecord,
  type HospitalSummary,
} from '@/types/hospital';

/**
 * 병원 데이터 서비스 — RTDB `/hospitals/{id}` 서브트리 CRUD + 구독.
 *
 * 컨벤션: `hospitalId === slug` (URL 세그먼트와 DB 키 일치).
 * - 예: `/h/demo/*` → `/hospitals/demo/*`
 * - slug 형식: 소문자 영문·숫자·하이픈, 2~32자
 */

// ============================================================================
// Slug 유효성
// ============================================================================

// 소문자·숫자 시작/종료, 중간에 하이픈 허용, 전체 2~32자
const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{0,30}[a-z0-9]$/;

export function isValidSlug(slug: string): boolean {
  return SLUG_PATTERN.test(slug);
}

// ============================================================================
// 조회
// ============================================================================

/**
 * 모든 병원의 요약 목록 (병원 선택 UI · 플랫폼 관리자용).
 *
 * 구현: `/hospital_index/` 공개 denormalization 읽기.
 * `/hospitals/` 루트는 rules cascade 때문에 공개할 수 없어서
 * 별도 인덱스 테이블을 유지함 (`createHospital`, `updateHospitalProfile`이
 * 쓰기 시점에 동기화).
 */
export async function listHospitals(): Promise<HospitalSummary[]> {
  if (!isFirebaseConfigured()) return [];
  const snapshot = await get(ref(db, 'hospital_index'));
  if (!snapshot.exists()) return [];
  const entries = snapshot.val() as Record<
    string,
    {
      slug: string;
      name: string;
      themeColor: string;
      contractStatus: HospitalSummary['contractStatus'];
      logoUrl?: string;
    }
  >;
  return Object.entries(entries).map(([id, e]) => ({
    id,
    slug: e.slug,
    name: e.name,
    themeColor: e.themeColor,
    contractStatus: e.contractStatus,
    ...(e.logoUrl ? { logoUrl: e.logoUrl } : {}),
  }));
}

/** 활성(active)·파일럿(pilot) 병원만 — 환자 가입 시 선택 가능 목록 */
export async function listActiveHospitals(): Promise<HospitalSummary[]> {
  const all = await listHospitals();
  return all.filter(
    (h) => h.contractStatus === 'active' || h.contractStatus === 'pilot',
  );
}

/** 단일 병원 전체 레코드 (profile + 서브트리 요약) */
export async function getHospital(id: string): Promise<HospitalRecord | null> {
  if (!isFirebaseConfigured()) return null;
  const snapshot = await get(ref(db, `hospitals/${id}`));
  if (!snapshot.exists()) return null;
  return snapshot.val() as HospitalRecord;
}

/** 병원 프로필만 (브랜딩·피처 플래그 등 가벼운 조회) */
export async function getHospitalProfile(
  id: string,
): Promise<HospitalProfile | null> {
  if (!isFirebaseConfigured()) return null;
  const snapshot = await get(ref(db, `hospitals/${id}/profile`));
  if (!snapshot.exists()) return null;
  return snapshot.val() as HospitalProfile;
}

// ============================================================================
// 실시간 구독
// ============================================================================

/**
 * 병원 프로필 실시간 구독 — HospitalContext에서 사용.
 * 반환값은 cleanup용 unsubscribe 함수.
 */
export function subscribeHospitalProfile(
  id: string,
  onChange: (profile: HospitalProfile | null) => void,
  onError?: (error: Error) => void,
): Unsubscribe {
  if (!isFirebaseConfigured()) {
    onChange(null);
    return () => {};
  }
  return onValue(
    ref(db, `hospitals/${id}/profile`),
    (snapshot) => {
      onChange(snapshot.exists() ? (snapshot.val() as HospitalProfile) : null);
    },
    (error) => onError?.(error),
  );
}

// ============================================================================
// 쓰기 (플랫폼 관리자 전용 — Security Rules가 최종 방어)
// ============================================================================

/** 새 병원 생성 입력 */
export interface CreateHospitalInput {
  slug: string;
  name: string;
  themeColor?: string;
  logoUrl?: string;
  phone?: string;
  address?: string;
  location?: { lat: number; lng: number };
}

/**
 * 신규 병원 생성. slug는 URL·DB 키로 사용되므로 유효성 검증 필수.
 * 이미 존재하는 slug는 throw.
 */
export async function createHospital(
  input: CreateHospitalInput,
): Promise<HospitalProfile> {
  if (!isFirebaseConfigured()) {
    throw new Error('Firebase 미설정 — 병원 생성 불가');
  }
  const slug = input.slug.trim().toLowerCase();
  if (!isValidSlug(slug)) {
    throw new Error(
      `유효하지 않은 slug "${slug}" — 소문자 영문/숫자/하이픈, 2~32자`,
    );
  }

  const existingSnap = await get(ref(db, `hospitals/${slug}/profile`));
  if (existingSnap.exists()) {
    throw new Error(`slug "${slug}"가 이미 사용 중입니다`);
  }

  const now = Date.now();
  const profile: HospitalProfile = {
    name: input.name.trim(),
    slug,
    themeColor: input.themeColor ?? '#004e9f',
    contractStatus: 'pilot',
    features: DEFAULT_HOSPITAL_FEATURES,
    createdAt: now,
    updatedAt: now,
    ...(input.logoUrl ? { logoUrl: input.logoUrl } : {}),
    ...(input.phone ? { phone: input.phone } : {}),
    ...(input.address ? { address: input.address } : {}),
    ...(input.location ? { location: input.location } : {}),
  };

  // fan-out: 전체 프로필 + 공개 인덱스
  await update(ref(db), {
    [`hospitals/${slug}/profile`]: profile,
    [`hospital_index/${slug}`]: buildIndexEntry(slug, profile),
  });
  return profile;
}

/** 병원 프로필 부분 업데이트 — index에 반영되는 필드는 자동 동기화 */
export async function updateHospitalProfile(
  id: string,
  patch: Partial<
    Omit<HospitalProfile, 'slug' | 'createdAt' | 'updatedAt'>
  >,
): Promise<void> {
  if (!isFirebaseConfigured()) {
    throw new Error('Firebase 미설정');
  }
  const now = Date.now();
  const profileUpdates: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(patch)) {
    profileUpdates[`hospitals/${id}/profile/${k}`] = v;
  }
  profileUpdates[`hospitals/${id}/profile/updatedAt`] = now;

  // index에도 반영되는 필드
  if (patch.name !== undefined)
    profileUpdates[`hospital_index/${id}/name`] = patch.name;
  if (patch.themeColor !== undefined)
    profileUpdates[`hospital_index/${id}/themeColor`] = patch.themeColor;
  if (patch.logoUrl !== undefined)
    profileUpdates[`hospital_index/${id}/logoUrl`] = patch.logoUrl;
  if (patch.contractStatus !== undefined)
    profileUpdates[`hospital_index/${id}/contractStatus`] = patch.contractStatus;

  await update(ref(db), profileUpdates);
}

/** 병원 계약 상태만 변경 (활성/파일럿/일시정지) */
export async function setHospitalContractStatus(
  id: string,
  status: HospitalProfile['contractStatus'],
): Promise<void> {
  await updateHospitalProfile(id, { contractStatus: status });
}

// ============================================================================
// 내부 헬퍼
// ============================================================================

/** `/hospital_index/{id}` 엔트리 모양 생성 */
function buildIndexEntry(id: string, profile: HospitalProfile) {
  return {
    slug: id,
    name: profile.name,
    themeColor: profile.themeColor,
    contractStatus: profile.contractStatus,
    ...(profile.logoUrl ? { logoUrl: profile.logoUrl } : {}),
  };
}
