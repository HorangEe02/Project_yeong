import type { RouteTemplate } from '@/types/route-template';

/** 사전 정의 동선 템플릿 (6개) */
export const routeTemplates: RouteTemplate[] = [
  {
    id: 'rt_1',
    name: '채혈 → 원무과 → 약국 → 귀가',
    departmentTag: '내과',
    color: '#3b82f6',
    waypointPoiIds: ['lab_blood', 'admin_billing', 'pharmacy_main', 'entrance_main'],
    estimatedTotalTime: 15,
    isDefault: true,
  },
  {
    id: 'rt_2',
    name: '원무과 → 약국 → 귀가',
    departmentTag: '내과',
    color: '#22c55e',
    waypointPoiIds: ['admin_billing', 'pharmacy_main', 'entrance_main'],
    estimatedTotalTime: 8,
    isDefault: false,
  },
  {
    id: 'rt_3',
    name: '영상의학과 → 원무과 → 약국 → 귀가',
    departmentTag: '내과',
    color: '#eab308',
    waypointPoiIds: ['imaging_reception', 'admin_billing', 'pharmacy_main', 'entrance_main'],
    estimatedTotalTime: 20,
    isDefault: false,
  },
  {
    id: 'rt_4',
    name: '채혈 → 영상의학과 → 원무과 → 약국 → 귀가',
    departmentTag: '외과',
    color: '#f97316',
    waypointPoiIds: ['lab_blood', 'imaging_reception', 'admin_billing', 'pharmacy_main', 'entrance_main'],
    estimatedTotalTime: 25,
    isDefault: false,
  },
  {
    id: 'rt_5',
    name: '채혈 → CT → 내시경 → 상담 → 원무과 → 귀가',
    departmentTag: '건강검진',
    color: '#06b6d4',
    waypointPoiIds: ['lab_blood', 'imaging_ct', 'checkup_endoscopy', 'checkup_consult', 'admin_billing', 'entrance_main'],
    estimatedTotalTime: 35,
    isDefault: false,
  },
  {
    id: 'rt_6',
    name: 'X-ray → 정형외과 → 원무과 → 약국 → 귀가',
    departmentTag: '정형외과',
    color: '#8b5cf6',
    waypointPoiIds: ['imaging_xray', 'clinic_orthopedics', 'admin_billing', 'pharmacy_main', 'entrance_main'],
    estimatedTotalTime: 22,
    isDefault: false,
  },
];
