// AJIN 19 사업장 좌표 (국내 12 + 해외 7)
// employees.ts 의 PLANTS 13개 + 추가 6 → 19 (실제 plants_db v4.0 기반)

export interface Plant {
  id: string;
  name: string;
  lat: number;
  lng: number;
  region: 'domestic' | 'overseas';
  category: 'HQ' | 'plant' | 'rd' | 'office';
  certifications?: string[];
  processes?: string[];
}

export const PLANTS_COORDS: Plant[] = [
  // 국내 (12)
  { id: 'hq-daegu', name: '본사 (대구)', lat: 35.8714, lng: 128.6014, region: 'domestic', category: 'HQ',
    certifications: ['IATF 16949', 'ISO 14001', 'ISO 45001'], processes: ['프레스', '용접', '도장', '검사'] },
  { id: 'cheonan-1', name: '천안 1공장', lat: 36.8151, lng: 127.1143, region: 'domestic', category: 'plant',
    certifications: ['IATF 16949'], processes: ['프레스', '용접'] },
  { id: 'cheonan-2', name: '천안 2공장', lat: 36.8222, lng: 127.1198, region: 'domestic', category: 'plant',
    certifications: ['IATF 16949'], processes: ['CNC', '검사'] },
  { id: 'gwangju-paint', name: '광주 도장', lat: 35.1601, lng: 126.8514, region: 'domestic', category: 'plant',
    certifications: ['ISO 14001'], processes: ['도장'] },
  { id: 'ulsan', name: '울산', lat: 35.1796, lng: 129.0756, region: 'domestic', category: 'plant',
    certifications: ['IATF 16949'], processes: ['프레스'] },
  { id: 'asan', name: '아산', lat: 36.7898, lng: 127.0024, region: 'domestic', category: 'plant',
    processes: ['사출'] },
  { id: 'pyeongtaek', name: '평택', lat: 36.9921, lng: 127.1129, region: 'domestic', category: 'plant',
    processes: ['용접', '검사'] },
  { id: 'gyeongju', name: '경주', lat: 35.8562, lng: 129.2247, region: 'domestic', category: 'plant',
    processes: ['금형'] },
  { id: 'changwon', name: '창원', lat: 35.2278, lng: 128.6817, region: 'domestic', category: 'plant',
    processes: ['프레스'] },
  { id: 'incheon-rd', name: '인천 R&D', lat: 37.4562, lng: 126.7052, region: 'domestic', category: 'rd',
    certifications: ['ISO 9001'], processes: ['연구개발', '설계'] },
  { id: 'busan-office', name: '부산 사무소', lat: 35.1796, lng: 129.0756, region: 'domestic', category: 'office',
    processes: ['영업'] },
  { id: 'seoul-office', name: '서울 사무소', lat: 37.5665, lng: 126.9780, region: 'domestic', category: 'office',
    processes: ['영업', '경영지원'] },

  // 해외 (7)
  { id: 'joon-usa', name: 'JOON INC (USA)', lat: 33.7490, lng: -84.3880, region: 'overseas', category: 'plant',
    certifications: ['IATF 16949'], processes: ['EV 부품 (HMGMA)'] },
  { id: 'ajin-poland', name: 'AJIN POLAND', lat: 51.9194, lng: 19.1451, region: 'overseas', category: 'plant',
    certifications: ['IATF 16949', 'EU REACH'], processes: ['프레스', '용접'] },
  { id: 'ajin-india', name: 'AJIN INDIA', lat: 28.7041, lng: 77.1025, region: 'overseas', category: 'plant',
    processes: ['검사'] },
  { id: 'ajin-china-1', name: 'AJIN CHINA 1', lat: 39.9042, lng: 116.4074, region: 'overseas', category: 'plant',
    processes: ['CNC'] },
  { id: 'ajin-china-2', name: 'AJIN CHINA 2', lat: 31.2304, lng: 121.4737, region: 'overseas', category: 'plant',
    processes: ['프레스'] },
  { id: 'ajin-vietnam', name: 'AJIN VIETNAM', lat: 21.0285, lng: 105.8542, region: 'overseas', category: 'plant',
    processes: ['용접', '검사'] },
  { id: 'ajin-usa-tx', name: 'AJIN USA (TX)', lat: 32.7767, lng: -96.7970, region: 'overseas', category: 'office',
    processes: ['영업'] },
];

export function findPlantCoord(name: string): Plant | undefined {
  return PLANTS_COORDS.find((p) => p.name === name);
}
