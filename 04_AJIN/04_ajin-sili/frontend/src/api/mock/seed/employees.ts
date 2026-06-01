// 사원 24명 + 6 본부 + 19 팀 시드 데이터
// 출처: uiux/AJIN AI Assistant Design System/ui_kits/web_app/Search.jsx 의 peopleAll

export interface MockEmployee {
  id: string;
  name: string;
  gender: '남' | '여';
  hq: string;
  team: string;
  position: string;
  ext: string;
  mobile: string;
  email: string;
  plant: string;
}

export interface MockTeam {
  team: string;
  n: number;
}

export interface MockHQ {
  hq: string;
  n: number;
  color: string;
  teams: MockTeam[];
}

export const ORG: MockHQ[] = [
  {
    hq: '경영지원본부', n: 58, color: 'oklch(72% 0.14 60)', teams: [
      { team: '인사팀', n: 14 }, { team: '재무팀', n: 18 },
      { team: '법무팀', n: 8 }, { team: '구매팀', n: 18 },
    ],
  },
  {
    hq: '품질본부', n: 92, color: 'oklch(76% 0.16 75)', teams: [
      { team: '품질보증팀', n: 42 }, { team: '품질관리팀', n: 28 }, { team: '검사팀', n: 22 },
    ],
  },
  {
    hq: '생산기술본부', n: 138, color: 'oklch(70% 0.13 50)', teams: [
      { team: '생산기술팀', n: 48 }, { team: '금형팀', n: 32 },
      { team: '정비팀', n: 38 }, { team: '프레스팀', n: 20 },
    ],
  },
  {
    hq: '영업본부', n: 64, color: 'oklch(74% 0.12 220)', teams: [
      { team: '국내영업팀', n: 24 }, { team: '해외영업팀', n: 28 }, { team: '영업기획팀', n: 12 },
    ],
  },
  {
    hq: 'R&D본부', n: 47, color: 'oklch(72% 0.10 280)', teams: [
      { team: '연구개발팀', n: 22 }, { team: '설계팀', n: 18 }, { team: '시작팀', n: 7 },
    ],
  },
  {
    hq: '환경안전본부', n: 28, color: 'oklch(68% 0.14 145)', teams: [
      { team: '환경안전팀', n: 16 }, { team: '시설관리팀', n: 12 },
    ],
  },
];

export const PLANTS = [
  '본사 (대구)', '천안 1공장', '천안 2공장', '광주 도장',
  '울산', '아산', '평택', '경주', '창원', '인천 R&D',
  'JOON INC (USA)', 'AJIN POLAND', 'AJIN INDIA',
];

export const POSITIONS = ['사원', '대리', '과장', '차장', '부장', '이사', '상무', '전무'];

export const TOTAL_HEADCOUNT = ORG.reduce((acc, b) => acc + b.n, 0);

export const EMPLOYEES: MockEmployee[] = [
  { id: 'QA-0001', name: '김민수', gender: '남', hq: '품질본부', team: '품질보증팀', position: '차장', ext: '1234', mobile: '010-2341-5678', email: 'minsu.kim@ajin.com', plant: '본사 (대구)' },
  { id: 'QA-0007', name: '이서연', gender: '여', hq: '품질본부', team: '품질보증팀', position: '대리', ext: '1238', mobile: '010-3415-2876', email: 'sy.lee@ajin.com', plant: '본사 (대구)' },
  { id: 'QA-0023', name: '박정호', gender: '남', hq: '품질본부', team: '품질관리팀', position: '과장', ext: '1252', mobile: '010-9871-2245', email: 'jh.park@ajin.com', plant: '천안 1공장' },
  { id: 'QA-0035', name: '정수영', gender: '여', hq: '품질본부', team: '검사팀', position: '사원', ext: '1265', mobile: '010-7654-3210', email: 'sy.jung@ajin.com', plant: '본사 (대구)' },
  { id: 'PE-0008', name: '박지훈', gender: '남', hq: '생산기술본부', team: '생산기술팀', position: '과장', ext: '2105', mobile: '010-4422-1188', email: 'jh2.park@ajin.com', plant: '본사 (대구)' },
  { id: 'PE-0019', name: '최유진', gender: '여', hq: '생산기술본부', team: '생산기술팀', position: '대리', ext: '2117', mobile: '010-2233-7766', email: 'yj.choi@ajin.com', plant: '본사 (대구)' },
  { id: 'PE-0033', name: '한승우', gender: '남', hq: '생산기술본부', team: '금형팀', position: '차장', ext: '2160', mobile: '010-5566-8899', email: 'sw.han@ajin.com', plant: '경주' },
  { id: 'PE-0045', name: '임지현', gender: '여', hq: '생산기술본부', team: '정비팀', position: '사원', ext: '2210', mobile: '010-3344-9988', email: 'jh.lim@ajin.com', plant: '천안 2공장' },
  { id: 'PE-0057', name: '오성민', gender: '남', hq: '생산기술본부', team: '프레스팀', position: '부장', ext: '2280', mobile: '010-9988-1122', email: 'sm.oh@ajin.com', plant: '본사 (대구)' },
  { id: 'SS-0003', name: '최현우', gender: '남', hq: '영업본부', team: '해외영업팀', position: '차장', ext: '3304', mobile: '010-1122-3344', email: 'hw.choi@ajin.com', plant: 'JOON INC (USA)' },
  { id: 'SS-0012', name: '윤하늘', gender: '여', hq: '영업본부', team: '국내영업팀', position: '과장', ext: '3315', mobile: '010-4455-7788', email: 'hn.yoon@ajin.com', plant: '본사 (대구)' },
  { id: 'SS-0024', name: '강도윤', gender: '남', hq: '영업본부', team: '영업기획팀', position: '대리', ext: '3328', mobile: '010-6677-2233', email: 'dy.kang@ajin.com', plant: '본사 (대구)' },
  { id: 'HR-0001', name: '이영희', gender: '여', hq: '경영지원본부', team: '인사팀', position: '부장', ext: '4001', mobile: '010-1010-1010', email: 'yh.lee@ajin.com', plant: '본사 (대구)' },
  { id: 'HR-0004', name: '송민재', gender: '남', hq: '경영지원본부', team: '인사팀', position: '대리', ext: '4014', mobile: '010-2020-3030', email: 'mj.song@ajin.com', plant: '본사 (대구)' },
  { id: 'FN-0009', name: '장다은', gender: '여', hq: '경영지원본부', team: '재무팀', position: '과장', ext: '4108', mobile: '010-3030-4040', email: 'de.jang@ajin.com', plant: '본사 (대구)' },
  { id: 'PR-0014', name: '배현수', gender: '남', hq: '경영지원본부', team: '구매팀', position: '차장', ext: '4221', mobile: '010-4040-5050', email: 'hs.bae@ajin.com', plant: '본사 (대구)' },
  { id: 'LG-0002', name: '문혜린', gender: '여', hq: '경영지원본부', team: '법무팀', position: '과장', ext: '4302', mobile: '010-5050-6060', email: 'hl.moon@ajin.com', plant: '본사 (대구)' },
  { id: 'RD-0005', name: '권태원', gender: '남', hq: 'R&D본부', team: '연구개발팀', position: '부장', ext: '5005', mobile: '010-6060-7070', email: 'tw.kwon@ajin.com', plant: '인천 R&D' },
  { id: 'RD-0011', name: '조예린', gender: '여', hq: 'R&D본부', team: '설계팀', position: '차장', ext: '5018', mobile: '010-7070-8080', email: 'yr.cho@ajin.com', plant: '인천 R&D' },
  { id: 'RD-0019', name: '노건우', gender: '남', hq: 'R&D본부', team: '시작팀', position: '사원', ext: '5034', mobile: '010-8080-9090', email: 'gw.noh@ajin.com', plant: '인천 R&D' },
  { id: 'EH-0003', name: '서지원', gender: '여', hq: '환경안전본부', team: '환경안전팀', position: '과장', ext: '6003', mobile: '010-9090-1010', email: 'jw.seo@ajin.com', plant: '본사 (대구)' },
  { id: 'EH-0008', name: '홍재민', gender: '남', hq: '환경안전본부', team: '환경안전팀', position: '대리', ext: '6011', mobile: '010-1212-3434', email: 'jm.hong@ajin.com', plant: '천안 1공장' },
  { id: 'FA-0005', name: '유나경', gender: '여', hq: '환경안전본부', team: '시설관리팀', position: '사원', ext: '6024', mobile: '010-3434-5656', email: 'ng.yoo@ajin.com', plant: '광주 도장' },
  { id: 'PE-0072', name: '전상현', gender: '남', hq: '생산기술본부', team: '정비팀', position: '대리', ext: '2240', mobile: '010-5656-7878', email: 'sh.jeon@ajin.com', plant: '울산' },
];
