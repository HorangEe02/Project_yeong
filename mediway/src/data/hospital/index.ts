import type { Hospital } from '@/types/hospital';
import type { FloorPlanData } from '@/types/floor-plan';
import { allPOIs, getPOIsByFloor, getPOIById } from './pois';
import { navigationGraph } from './navigation-graph';
import { floor1Data } from './floor-plans/floor1';
import { floor2Data } from './floor-plans/floor2';
import { floor3Data } from './floor-plans/floor3';
import { floor4Data } from './floor-plans/floor4';

/** 층별 평면도 데이터 맵 */
export const floorPlanMap: Record<number, FloorPlanData> = {
  1: floor1Data,
  2: floor2Data,
  3: floor3Data,
  4: floor4Data,
};

/** 층 레벨로 평면도 조회 */
export function getFloorPlan(floorLevel: number): FloorPlanData | undefined {
  return floorPlanMap[floorLevel];
}

/** 데모 병원 정보 */
export const demoHospital: Hospital = {
  id: 'demo-hospital',
  name: 'MediWay 데모 병원',
  buildings: [
    {
      id: 'main',
      name: '본관',
      floors: [
        { level: 1, name: '1층' },
        { level: 2, name: '2층' },
        { level: 3, name: '3층' },
        { level: 4, name: '4층' },
      ],
    },
  ],
};

export { allPOIs, getPOIsByFloor, getPOIById, navigationGraph };
