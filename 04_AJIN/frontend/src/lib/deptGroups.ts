// JP1 — 부서 그룹 분류 단일 진실 출처.
// 신입 가이드(/onboarding) 의 부서 적응형 카드 + Vision Q&A 노출 조건에 사용.
// 29개 부서 → 10개 그룹.

export type DeptGroup =
  | 'G1'  // 품질 (도면 도메인)
  | 'G2'  // 생산기술
  | 'G3'  // 생산현장
  | 'G4'  // 안전·설비
  | 'G5'  // R&D
  | 'G6'  // 영업
  | 'G7'  // 경영지원 (인사·재무·IT)
  | 'G8'  // 구매·자재
  | 'G9'  // 법무·감사·ESG
  | 'G10'; // 기타 (교육·프로젝트)

interface DeptGroupInfo {
  label: string;
  depts: string[];
}

export const DEPT_GROUPS: Record<DeptGroup, DeptGroupInfo> = {
  G1: {
    label: '품질',
    depts: ['품질보증팀', '품질경영팀', '검사팀'],
  },
  G2: {
    label: '생산기술',
    depts: ['생산기술팀', '정비팀', '금형팀', '자동화기술팀', '금형생산팀'],
  },
  G3: {
    label: '생산현장',
    depts: ['프레스팀', '용접팀', '도장팀', 'CNC팀', '사출팀', '컨베이어팀', '생산관리팀'],
  },
  G4: {
    label: '안전·설비',
    depts: ['환경안전팀', '시설관리팀', '안전보건팀'],
  },
  G5: {
    label: 'R&D',
    depts: [
      '부품개발팀',
      '제품설계팀',
      '바디선행개발팀',
      '전장선행개발팀',
      '비전연구팀',
      '연구개발팀',
      '설계팀',
      '시작팀',
    ],
  },
  G6: {
    label: '영업',
    depts: ['국내영업팀', '해외영업팀', '영업기획팀', '기술영업팀', '영업팀'],
  },
  G7: {
    label: '경영지원',
    depts: [
      '총무인사팀',
      '인사팀',
      '재무팀',
      '회계팀',
      '원가기획팀',
      'IT전략팀',
      '시스템관리팀',
    ],
  },
  G8: {
    label: '구매·자재',
    depts: ['구매팀', '자재관리팀', '자재팀', '해외지원팀', '상생협력팀'],
  },
  G9: {
    label: '법무·감사',
    depts: ['법무팀', '내부감사팀', 'ESG경영팀'],
  },
  G10: {
    label: '기타',
    depts: [
      '기술교육원',
      'FA사업팀',
      '플랜트사업팀',
      '공법계획팀',
      '용기운영팀',
    ],
  },
};

/** 부서명 → 그룹 코드. 매칭 없으면 null. */
export function getDeptGroup(dept: string): DeptGroup | null {
  if (!dept) return null;
  for (const [key, info] of Object.entries(DEPT_GROUPS)) {
    if (info.depts.includes(dept)) return key as DeptGroup;
  }
  return null;
}

/** 부서명 → 그룹 라벨 (UI 표시용). */
export function getDeptGroupLabel(dept: string): string {
  const g = getDeptGroup(dept);
  return g ? DEPT_GROUPS[g].label : '';
}

/**
 * Vision Q&A (도면·부품 사진) 노출 여부.
 * G1 품질 / G2 생산기술 / G5 R&D 만 노출.
 * 영업·경영지원·법무 등은 도메인 미일치라 숨김.
 */
export function isVisionVisible(dept: string): boolean {
  const g = getDeptGroup(dept);
  return g === 'G1' || g === 'G2' || g === 'G5';
}

/** 그룹별 신규 카드 노출 매핑 (JP2/JP3 + 부록 K Phase 1~3 가 사용). */
export function getDeptCardKeys(dept: string): string[] {
  const g = getDeptGroup(dept);
  const cards: string[] = [];

  // 기존 부서 텍스트 카드 (JP2/JP3)
  if (g === 'G6') {
    cards.push('sales');
    cards.push('business-card', 'rfq');                   // Phase 1
  }
  if (g === 'G7') {
    if (dept === '총무인사팀' || dept === '인사팀') {
      cards.push('hr');
      cards.push('resume');                                // Phase 2
    }
    if (['재무팀', '회계팀', '원가기획팀'].includes(dept)) {
      cards.push('finance');
      cards.push('receipt');                               // Phase 1
      cards.push('financial-statement');                   // Phase 2
    }
    if (dept === 'IT전략팀' || dept === '시스템관리팀') {
      cards.push('it');
      cards.push('error-log');                             // Phase 3
    }
  }
  if (g === 'G8') {
    cards.push('procurement');
    cards.push('po', 'inventory-receive');                 // Phase 2 + 3
  }
  if (g === 'G9') {
    cards.push('legal');
    cards.push('contract');                                // Phase 2
    if (dept === 'ESG경영팀') cards.push('esg');           // Phase 3
  }
  if (g === 'G5') {
    cards.push('rnd');
    cards.push('cad-verify');                              // Phase 3
  }
  if (g === 'G3') {
    cards.push('shopfloor');
    cards.push('defect');                                  // Phase 1
    cards.push('5s');                                      // Phase 3
  }
  if (g === 'G4') {
    cards.push('safety');
    cards.push('msds-ocr');                                // Phase 1
    cards.push('incident');                                // Phase 2
  }
  if (g === 'G10') {
    cards.push('certificate');                             // Phase 3
  }
  return cards;
}
