/** POI 카테고리 */
export type POICategory =
  | 'clinic'
  | 'lab'
  | 'imaging'
  | 'pharmacy'
  | 'admin'
  | 'elevator'
  | 'stairs'
  | 'restroom'
  | 'parking'
  | 'entrance'
  | 'convenience'
  | 'lobby';

/** SVG 좌표 (viewBox 0 0 1200 800 기준) */
export interface Coordinate {
  x: number;
  y: number;
}

/** 관심 지점 (Point of Interest) */
export interface POI {
  id: string;
  name: string;
  shortName: string;
  category: POICategory;
  buildingId: string;
  floorLevel: number;
  coordinates: Coordinate;
  description?: string;
  icon?: string;
}

/** 층 정보 */
export interface Floor {
  level: number;
  name: string;
}

/** 건물 */
export interface Building {
  id: string;
  name: string;
  floors: Floor[];
}

/** 병원 (정적 네비게이션 데이터 — 기존 pathfinding 기반 호환 유지) */
export interface Hospital {
  id: string;
  name: string;
  buildings: Building[];
}

// ============================================================================
// P1 Multi-Tenant 확장
// ============================================================================

/** 병원 계약 상태 */
export type HospitalContractStatus = 'active' | 'pilot' | 'paused';

/** 병원별 feature flags — 탭·기능 노출 제어 (P2 이후 탭 구조에서 사용) */
export interface HospitalFeatures {
  /** P2 외래 탭 */
  appointments: boolean;
  /** P2 입원 탭 */
  inpatient: boolean;
  /** P2 건강검진 탭 */
  checkup: boolean;
  /** P3 결제 */
  payment: boolean;
  /** P3 처방전 */
  prescription: boolean;
  /** P3 주차 할인 (파일럿별) */
  parking: boolean;
  /** P3 AI 증상 triage — v2 F19 */
  aiTriage: boolean;
  /** P4 가족 대리 — v2 MOAT #1 */
  familyDelegation: boolean;
  /** P5 검사결과 무기한 보관 — v2 MOAT #3 */
  healthRecords: boolean;
}

/** 기본 feature flags — 모두 off (병원 생성 시 활성화 선택) */
export const DEFAULT_HOSPITAL_FEATURES: HospitalFeatures = {
  appointments: false,
  inpatient: false,
  checkup: false,
  payment: false,
  prescription: false,
  parking: false,
  aiTriage: false,
  familyDelegation: false,
  healthRecords: false,
};

/**
 * 병원 프로필 (RTDB: /hospitals/{hospitalId}/profile)
 * — 화이트라벨 브랜딩·계약·feature flag의 핵심
 */
export interface HospitalProfile {
  /** 병원명 (표시용) */
  name: string;
  /** URL slug — 소문자·영문·숫자·하이픈만 (예: "demo", "smch") */
  slug: string;
  /** 로고 이미지 URL (Firebase Storage) */
  logoUrl?: string;
  /** 브랜드 기본 색상 (CSS custom property --color-primary) */
  themeColor: string;
  /** 계약 상태 */
  contractStatus: HospitalContractStatus;
  /** 병원별 feature flags */
  features: HospitalFeatures;
  /** 연락처·주소 (선택) */
  phone?: string;
  address?: string;
  /** 위치 좌표 (병원 선택 시 거리 정렬용) */
  location?: { lat: number; lng: number };
  createdAt: number;
  updatedAt: number;
}

/** 부서 (RTDB: /hospitals/{hospitalId}/departments/{id}) */
export interface Department {
  id: string;
  name: string;
  /** 부서 위치 POI 참조 */
  locationPoiId?: string;
  floorLevel?: number;
  /** 표시 순서 */
  sortOrder?: number;
}

/** 공지 (RTDB: /hospitals/{hospitalId}/announcements/{id}) */
export interface Announcement {
  id: string;
  title: string;
  body: string;
  priority: 'low' | 'normal' | 'high';
  startAt: number;
  endAt?: number;
  createdBy: string;
  createdAt: number;
}

/**
 * 병원 전체 레코드 (RTDB: /hospitals/{hospitalId})
 * — profile은 필수, 나머지 서브트리는 기능 활성 시점에 채워짐
 */
export interface HospitalRecord {
  profile: HospitalProfile;
  departments?: Record<string, Department>;
  announcements?: Record<string, Announcement>;
  // floor-plans, pois, staff-codes 등은 별도 서비스에서 관리
}

/** 병원 선택 드롭다운용 요약 */
export interface HospitalSummary {
  id: string;
  name: string;
  slug: string;
  logoUrl?: string;
  themeColor: string;
  contractStatus: HospitalContractStatus;
  /** 거리 (km, 위치 기반 정렬 시) */
  distanceKm?: number;
}
