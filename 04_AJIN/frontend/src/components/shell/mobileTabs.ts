// BottomTabBar 동적 탭 resolver (v4.5).
//
// 슬롯 구조:
//   [B(DRAFT)] [C(CHAT)] [HOME] [동적1] [동적2]
//
// 고정 3 슬롯 = 모든 사용자 공통 (RBAC 미통과 시 fallback)
// 동적 2 슬롯 = 페르소나 매트릭스 + 사용자 override

import {
  Briefcase,
  Cpu,
  FileText,
  GraduationCap,
  Home,
  type LucideIcon,
  MessageSquare,
  Search,
  Shield,
  User,
} from 'lucide-react';

import type { AuthUser } from '@store/auth';
import type { PersonaId } from '@components/dashboard/widgets/types';
import { isMenuVisible } from '@lib/rbac';

export interface TabMeta {
  slug: string;
  path: string;
  icon: LucideIcon;
  labelEn: string;
  labelKo: string;
}

// 모듈 메타 — labelKo 우선 (사용자 결정 B). v3.5 UI 재설계: profile 추가.
export const TAB_META: Record<string, TabMeta> = {
  dashboard:  { slug: 'dashboard',  path: '/',           icon: Home,          labelEn: 'HOME',     labelKo: '대시보드' },
  search:     { slug: 'search',     path: '/search',     icon: Search,        labelEn: 'SEARCH',   labelKo: '검색' },
  draft:      { slug: 'draft',      path: '/draft',      icon: FileText,      labelEn: 'DRAFT',    labelKo: '문서' },
  chat:       { slug: 'chat',       path: '/chat',       icon: MessageSquare, labelEn: 'CHAT',     labelKo: '챗봇' },
  onboarding: { slug: 'onboarding', path: '/onboarding', icon: GraduationCap, labelEn: 'ONBOARD',  labelKo: '온보딩' },
  compliance: { slug: 'compliance', path: '/compliance', icon: Shield,        labelEn: 'COMPLY',   labelKo: '법규' },
  equipment:  { slug: 'equipment',  path: '/equipment',  icon: Cpu,           labelEn: 'EQUIP',    labelKo: '설비' },
  // v4.8 — 기능 G(HR) 삭제. admin 만 유지.
  // 모바일은 /admin/legacy 에서 AJINMobileAdmin 렌더 (/admin 은 데스크톱 전용
  // /management 로 redirect 되어 모바일 콘솔에 도달 못 함 — 모바일 nav 는 legacy 로).
  admin:      { slug: 'admin',      path: '/admin/legacy', icon: Briefcase,   labelEn: 'SYS',      labelKo: '시스템' },
  // v3.5 UI 재설계 — Bottom Nav 5탭 권장 구성 (Dashboard/Chat/Search/Compliance/Profile).
  profile:    { slug: 'profile',    path: '/profile',    icon: User,          labelEn: 'PROFILE',  labelKo: '프로필' },
};

// v4.8 — saved customSlots('management' | 'hr') → 'admin' 자동 마이그레이션
export function migrateLegacySlug(slug: string): string {
  if (slug === 'management' || slug === 'hr') return 'admin';
  return slug;
}

// v3.5 UI 재설계 — Bottom Nav 5탭 모두 고정 (사용자 Goal 확정).
// 슬롯 좌→우: Dashboard / Chat / Search / Compliance / Profile
// 동적 슬롯 로직은 prefs.override=true 일 때만 활성 (legacy 호환).
const FIXED_SLOTS = ['dashboard', 'chat', 'search', 'compliance', 'profile'] as const;

// 고정 슬롯이 RBAC 미통과 시 대체 — 실 운영에서 거의 발동 안 함
const FIXED_FALLBACK: Record<string, string[]> = {
  dashboard:  [],
  chat:       ['onboarding', 'draft'],
  search:     ['onboarding'],
  compliance: ['equipment', 'admin'],
  profile:    [],
};

// 페르소나 × 동적 슬롯 4·5 우선순위 (RBAC 통과 첫 2개 채택)
// v4.8 — HR 슬러그 제거 후 매트릭스 재구성
const DYNAMIC_PRIORITY: Record<PersonaId, string[]> = {
  P1_NEWBIE:     ['onboarding', 'search',     'compliance'],
  P2_QA:         ['equipment',  'compliance', 'search'],
  P3_SAFETY:     ['compliance', 'equipment',  'search'],
  P4_SALES:      ['search',     'compliance', 'equipment'],
  P5_PRODUCTION: ['equipment',  'search',     'compliance'],
  P6_HR_ADMIN:   ['admin',      'search',     'compliance'],
  P7_IT_ADMIN:   ['admin',      'equipment',  'compliance'],
  P8_EXECUTIVE:  ['compliance', 'admin',      'equipment'],
  P9_SYS_ADMIN:  ['admin',      'equipment',  'compliance'],
};

// 페르소나·override 모두 부족 시 마지막 fallback 순서
const GLOBAL_FALLBACK = ['search', 'equipment', 'compliance', 'admin'] as const;

export interface MobileTabPrefs {
  override: boolean;
  customSlots: [string, string];
}

export interface MobileTabResult {
  tabs: TabMeta[];
  /** 5탭 미달 시 noFill = 채우지 못한 슬롯 수 (UI에서 "더보기" 안내) */
  emptySlots: number;
}

export function resolveMobileTabs(
  user: AuthUser | null,
  prefs: MobileTabPrefs,
): MobileTabResult {
  const used = new Set<string>();

  // 1) 고정 5 슬롯 (v3.5 — Dashboard/Chat/Search/Compliance/Profile)
  const fixed: string[] = [];
  for (const slug of FIXED_SLOTS) {
    let chosen: string = slug;
    if (!isMenuVisible(slug, user)) {
      chosen = FIXED_FALLBACK[slug]?.find((s) => isMenuVisible(s, user) && !used.has(s)) ?? slug;
    }
    fixed.push(chosen);
    used.add(chosen);
  }

  // 2) 동적 슬롯 — 사용자 override prefs 활성 시에만 적용 (5 고정 우선).
  //    override=true 면 customSlots[0,1] 이 dashboard/chat 자리를 교체 (admin 등 페르소나).
  const dynamic: string[] = [];
  if (prefs.override) {
    for (const raw of prefs.customSlots) {
      if (dynamic.length >= 2) break;
      const slug = migrateLegacySlug(raw);
      if (!slug || used.has(slug)) continue;
      if (isMenuVisible(slug, user)) {
        dynamic.push(slug);
        used.add(slug);
      }
    }
  }

  // override 가 dynamic 채웠으면 fixed 의 마지막 2개를 교체 (Dashboard/Chat 보존)
  const finalSlugs = prefs.override && dynamic.length > 0
    ? [...fixed.slice(0, 5 - dynamic.length), ...dynamic]
    : fixed;

  const tabs = finalSlugs.slice(0, 5).map((slug) => TAB_META[slug] ?? TAB_META.dashboard);
  const emptySlots = Math.max(0, 5 - tabs.length);

  return { tabs, emptySlots };
}

// v3.5 — 페르소나 매트릭스는 admin 페르소나의 customSlots override 추천에 사용.
// FIXED_SLOTS 5 고정 정책이라 자동 추천 없으나, prefs 설정 UI 에서 활용 가능.
export const PERSONA_SUGGEST_DYNAMIC = DYNAMIC_PRIORITY;
export const GLOBAL_FALLBACK_ORDER = GLOBAL_FALLBACK;

// 사용자가 동적 슬롯에 선택 가능한 모듈 풀
export function getCustomizableSlugs(user: AuthUser | null): string[] {
  return Object.keys(TAB_META).filter(
    (slug) =>
      !(FIXED_SLOTS as readonly string[]).includes(slug) && isMenuVisible(slug, user),
  );
}

export const DEFAULT_CUSTOM_SLOTS: [string, string] = ['compliance', 'equipment'];
