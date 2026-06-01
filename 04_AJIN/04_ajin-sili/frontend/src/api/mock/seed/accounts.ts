// 33 테스트 계정 + 6 RBAC 단계
// 본선 데모용 평문 비밀번호 (실제 백엔드는 bcrypt 해시)

export type RoleName = 'SYS_ADMIN' | 'HR_ADMIN' | 'TEAM_LEAD' | 'MANAGER' | 'EMPLOYEE' | 'INACTIVE';
export type RoleLevel = 6 | 5 | 4 | 3 | 2 | 1;

export interface MockAccount {
  employee_id: string;
  username: string;
  password: string;
  role_name: RoleName;
  role_level: RoleLevel;
  department: string;
  division: string;
  position: string;
  plant: string;
  must_change_pw: boolean;
  failed_attempts: number;
  locked_until: string | null;
  last_login: string | null;
}

const DEFAULT_PW = 'Demo!2026';

export const ACCOUNTS: MockAccount[] = [
  // 시스템 관리자 (2)
  { employee_id: 'SYS-0001', username: '박준영', password: DEFAULT_PW, role_name: 'SYS_ADMIN', role_level: 6, department: '시스템관리팀', division: '경영지원본부', position: '부장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T18:32:00+09:00' },
  { employee_id: 'SYS-0002', username: '이현아', password: DEFAULT_PW, role_name: 'SYS_ADMIN', role_level: 6, department: '시스템관리팀', division: '경영지원본부', position: '차장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // HR 관리자 (3)
  { employee_id: 'HR-0001', username: '이영희', password: DEFAULT_PW, role_name: 'HR_ADMIN', role_level: 5, department: '인사팀', division: '경영지원본부', position: '부장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T17:45:00+09:00' },
  { employee_id: 'HR-0004', username: '송민재', password: DEFAULT_PW, role_name: 'HR_ADMIN', role_level: 5, department: '인사팀', division: '경영지원본부', position: '대리', plant: '본사 (대구)', must_change_pw: true, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'HR-0007', username: '정유진', password: DEFAULT_PW, role_name: 'HR_ADMIN', role_level: 5, department: '인사팀', division: '경영지원본부', position: '과장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-25T09:12:00+09:00' },

  // 품질본부 팀장/매니저 (6)
  { employee_id: 'QA-0001', username: '김민수', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '품질보증팀', division: '품질본부', position: '차장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T18:32:00+09:00' },
  { employee_id: 'QA-0007', username: '이서연', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '품질보증팀', division: '품질본부', position: '대리', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T16:00:00+09:00' },
  { employee_id: 'QA-0023', username: '박정호', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '품질관리팀', division: '품질본부', position: '과장', plant: '천안 1공장', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T08:45:00+09:00' },
  { employee_id: 'QA-0035', username: '정수영', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '검사팀', division: '품질본부', position: '사원', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'QA-0042', username: '최영민', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '품질관리팀', division: '품질본부', position: '차장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'QA-0058', username: '강은지', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '품질보증팀', division: '품질본부', position: '대리', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // 생산기술본부 (5)
  { employee_id: 'PE-0008', username: '박지훈', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '생산기술팀', division: '생산기술본부', position: '과장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T13:20:00+09:00' },
  { employee_id: 'PE-0019', username: '최유진', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '생산기술팀', division: '생산기술본부', position: '대리', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-04-26T15:00:00+09:00' },
  { employee_id: 'PE-0033', username: '한승우', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '금형팀', division: '생산기술본부', position: '차장', plant: '경주', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'PE-0045', username: '임지현', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '정비팀', division: '생산기술본부', position: '사원', plant: '천안 2공장', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'PE-0057', username: '오성민', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '프레스팀', division: '생산기술본부', position: '부장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // 영업본부 (4)
  { employee_id: 'SS-0003', username: '최현우', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '해외영업팀', division: '영업본부', position: '차장', plant: 'JOON INC (USA)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'SS-0012', username: '윤하늘', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '국내영업팀', division: '영업본부', position: '과장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'SS-0024', username: '강도윤', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '영업기획팀', division: '영업본부', position: '대리', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'SS-0030', username: '신예지', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '해외영업팀', division: '영업본부', position: '사원', plant: 'AJIN POLAND', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // 환경안전본부 (3)
  { employee_id: 'EH-0003', username: '서지원', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '환경안전팀', division: '환경안전본부', position: '과장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'EH-0008', username: '홍재민', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '환경안전팀', division: '환경안전본부', position: '대리', plant: '천안 1공장', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'EH-0015', username: '나경원', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '환경안전팀', division: '환경안전본부', position: '부장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // 법무팀 (2)
  { employee_id: 'LG-0002', username: '문혜린', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '법무팀', division: '경영지원본부', position: '과장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'LG-0005', username: '백다은', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '법무팀', division: '경영지원본부', position: '대리', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // R&D 본부 (3)
  { employee_id: 'RD-0005', username: '권태원', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '연구개발팀', division: 'R&D본부', position: '부장', plant: '인천 R&D', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'RD-0011', username: '조예린', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '설계팀', division: 'R&D본부', position: '차장', plant: '인천 R&D', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'RD-0019', username: '노건우', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '시작팀', division: 'R&D본부', position: '사원', plant: '인천 R&D', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // 구매/재무 (3)
  { employee_id: 'PR-0014', username: '배현수', password: DEFAULT_PW, role_name: 'TEAM_LEAD', role_level: 4, department: '구매팀', division: '경영지원본부', position: '차장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'FN-0009', username: '장다은', password: DEFAULT_PW, role_name: 'MANAGER', role_level: 3, department: '재무팀', division: '경영지원본부', position: '과장', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },
  { employee_id: 'FA-0005', username: '유나경', password: DEFAULT_PW, role_name: 'EMPLOYEE', role_level: 2, department: '시설관리팀', division: '환경안전본부', position: '사원', plant: '광주 도장', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: null },

  // 비활성 (1)
  { employee_id: 'EX-0001', username: '퇴사자', password: DEFAULT_PW, role_name: 'INACTIVE', role_level: 1, department: '품질보증팀', division: '품질본부', position: '사원', plant: '본사 (대구)', must_change_pw: false, failed_attempts: 0, locked_until: null, last_login: '2026-01-15T09:00:00+09:00' },
];

export const ROLE_DESCRIPTIONS: Record<RoleName, string> = {
  SYS_ADMIN: '시스템 관리자 — 모든 권한 + 시스템 설정',
  HR_ADMIN: '인사 관리자 — 사용자·부서·계정 관리',
  TEAM_LEAD: '본부장 / 팀장 — 본부 통계 + 인사 조회',
  MANAGER: '매니저 — 부서 내 일부 관리 권한',
  EMPLOYEE: '일반 직원 — 본인 정보 + 검색·문서 작성',
  INACTIVE: '비활성 — 모든 접근 차단',
};
