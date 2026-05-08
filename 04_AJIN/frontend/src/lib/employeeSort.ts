// 인원 정렬 유틸 — Module A 검색 결과 정렬용.
//
// 한국 기업 직급 위계 (높을수록 1, 낮을수록 큰 숫자):
//   회장 → 사장 → 부사장 → 전무 → 상무 → 이사 → 부장 → 차장 → 과장 → 대리 → 주임 → 사원 → 인턴
//
// 정렬 키 (sortKey):
//   'rank-desc' : 직급 높은 사람 먼저 (기본값) — 한국 일반 관행
//   'rank-asc'  : 직급 낮은 사람 먼저
//   'name-asc'  : 가나다순
//   'name-desc' : 역가나다
//   'hq-asc'    : 본부순
//   'id-asc'    : 사번순

import type { FilteredEmployee } from '@lib/visibility';

export type EmployeeSortKey =
  | 'rank-desc'
  | 'rank-asc'
  | 'name-asc'
  | 'name-desc'
  | 'hq-asc'
  | 'id-asc';

export const POSITION_RANK: Record<string, number> = {
  // 임원급
  '회장': 1,
  '부회장': 2,
  '사장': 3,
  '부사장': 4,
  '전무': 5,
  '전무이사': 5,
  '상무': 6,
  '상무이사': 6,
  '이사': 7,
  // 부서장급
  '본부장': 8,
  '실장': 9,
  '부장': 10,
  '차장': 11,
  '팀장': 12,
  '과장': 13,
  '파트장': 14,
  // 실무자급
  '대리': 15,
  '주임': 16,
  '사원': 17,
  '연구원': 17,
  '기사': 17,
  '인턴': 18,
};

const FALLBACK_RANK = 99;

export interface EmployeeSortOption {
  key: EmployeeSortKey;
  label: string;
}

/**
 * 정렬 드롭다운 옵션 — UI 표시용.
 * 기본값은 첫 번째 옵션 ('rank-desc').
 */
export const SORT_OPTIONS: EmployeeSortOption[] = [
  { key: 'rank-desc', label: '직급 ↓ 높은 직급부터' },
  { key: 'rank-asc', label: '직급 ↑ 낮은 직급부터' },
  { key: 'name-asc', label: '이름 가나다순' },
  { key: 'name-desc', label: '이름 역순' },
  { key: 'hq-asc', label: '본부순' },
  { key: 'id-asc', label: '사번순' },
];

/**
 * 직급 우선순위 반환. 매핑에 없는 직급은 fallback (가장 낮음).
 */
function rankOf(position: string): number {
  if (!position) return FALLBACK_RANK;
  // 정확 매칭 우선
  if (position in POSITION_RANK) return POSITION_RANK[position];
  // 부분 매칭 (예: '책임연구원' → '연구원')
  for (const [key, rank] of Object.entries(POSITION_RANK)) {
    if (position.includes(key)) return rank;
  }
  return FALLBACK_RANK;
}

/**
 * 한국어 가나다 순 비교.
 */
function compareKo(a: string, b: string): number {
  return (a || '').localeCompare(b || '', 'ko-KR');
}

/**
 * 사원 배열을 정렬 (원본 불변, 새 배열 반환).
 *
 * 모든 정렬은 tie-breaker 로 이름 가나다순 → 사번순을 사용한다.
 */
export function sortEmployees<T extends FilteredEmployee>(
  rows: T[],
  sortKey: EmployeeSortKey,
): T[] {
  const out = [...rows];
  out.sort((a, b) => {
    let primary = 0;

    switch (sortKey) {
      case 'rank-desc': {
        primary = rankOf(a.position) - rankOf(b.position);
        break;
      }
      case 'rank-asc': {
        primary = rankOf(b.position) - rankOf(a.position);
        break;
      }
      case 'name-asc': {
        primary = compareKo(a.name, b.name);
        break;
      }
      case 'name-desc': {
        primary = compareKo(b.name, a.name);
        break;
      }
      case 'hq-asc': {
        primary = compareKo(a.hq, b.hq);
        break;
      }
      case 'id-asc': {
        primary = (a.id || '').localeCompare(b.id || '');
        break;
      }
    }

    if (primary !== 0) return primary;
    // tie-breaker
    const byName = compareKo(a.name, b.name);
    if (byName !== 0) return byName;
    return (a.id || '').localeCompare(b.id || '');
  });
  return out;
}
