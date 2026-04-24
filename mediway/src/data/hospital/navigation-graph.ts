import type { NavNode, NavEdge, NavigationGraph } from '@/types/navigation';

// ============================
// 노드 정의: POI 노드 + 복도 교차점(junction) 노드
// ============================

/** POI 노드 — allPOIs의 id와 매칭 */
const poiNodes: NavNode[] = [
  // 1층
  { id: 'entrance_main', type: 'poi', floorLevel: 1, coordinates: { x: 600, y: 80 }, poiId: 'entrance_main' },
  { id: 'admin_reception', type: 'poi', floorLevel: 1, coordinates: { x: 170, y: 195 }, poiId: 'admin_reception' },
  { id: 'admin_billing', type: 'poi', floorLevel: 1, coordinates: { x: 380, y: 195 }, poiId: 'admin_billing' },
  { id: 'pharmacy_main', type: 'poi', floorLevel: 1, coordinates: { x: 625, y: 195 }, poiId: 'pharmacy_main' },
  { id: 'lobby_1f', type: 'poi', floorLevel: 1, coordinates: { x: 950, y: 195 }, poiId: 'lobby_1f' },
  { id: 'elevator_1', type: 'poi', floorLevel: 1, coordinates: { x: 940, y: 430 }, poiId: 'elevator_1' },
  { id: 'stairs_1', type: 'poi', floorLevel: 1, coordinates: { x: 1060, y: 430 }, poiId: 'stairs_1' },
  { id: 'convenience_store', type: 'poi', floorLevel: 1, coordinates: { x: 180, y: 430 }, poiId: 'convenience_store' },
  // 2층
  { id: 'clinic_internal_1', type: 'poi', floorLevel: 2, coordinates: { x: 170, y: 195 }, poiId: 'clinic_internal_1' },
  { id: 'clinic_internal_2', type: 'poi', floorLevel: 2, coordinates: { x: 380, y: 195 }, poiId: 'clinic_internal_2' },
  { id: 'lab_blood', type: 'poi', floorLevel: 2, coordinates: { x: 625, y: 195 }, poiId: 'lab_blood' },
  { id: 'clinic_surgery_1', type: 'poi', floorLevel: 2, coordinates: { x: 170, y: 430 }, poiId: 'clinic_surgery_1' },
  { id: 'clinic_surgery_2', type: 'poi', floorLevel: 2, coordinates: { x: 380, y: 430 }, poiId: 'clinic_surgery_2' },
  { id: 'clinic_pediatrics', type: 'poi', floorLevel: 2, coordinates: { x: 180, y: 580 }, poiId: 'clinic_pediatrics' },
  { id: 'elevator_2', type: 'poi', floorLevel: 2, coordinates: { x: 940, y: 430 }, poiId: 'elevator_2' },
  { id: 'stairs_2', type: 'poi', floorLevel: 2, coordinates: { x: 1060, y: 430 }, poiId: 'stairs_2' },
  // 3층
  { id: 'imaging_ct', type: 'poi', floorLevel: 3, coordinates: { x: 170, y: 195 }, poiId: 'imaging_ct' },
  { id: 'imaging_mri', type: 'poi', floorLevel: 3, coordinates: { x: 450, y: 195 }, poiId: 'imaging_mri' },
  { id: 'imaging_xray', type: 'poi', floorLevel: 3, coordinates: { x: 170, y: 430 }, poiId: 'imaging_xray' },
  { id: 'imaging_reception', type: 'poi', floorLevel: 3, coordinates: { x: 450, y: 430 }, poiId: 'imaging_reception' },
  { id: 'clinic_orthopedics', type: 'poi', floorLevel: 3, coordinates: { x: 170, y: 600 }, poiId: 'clinic_orthopedics' },
  { id: 'clinic_rehab', type: 'poi', floorLevel: 3, coordinates: { x: 400, y: 600 }, poiId: 'clinic_rehab' },
  { id: 'elevator_3', type: 'poi', floorLevel: 3, coordinates: { x: 940, y: 430 }, poiId: 'elevator_3' },
  { id: 'stairs_3', type: 'poi', floorLevel: 3, coordinates: { x: 1060, y: 430 }, poiId: 'stairs_3' },
  // 4층
  { id: 'checkup_reception', type: 'poi', floorLevel: 4, coordinates: { x: 400, y: 150 }, poiId: 'checkup_reception' },
  { id: 'checkup_room_1', type: 'poi', floorLevel: 4, coordinates: { x: 170, y: 430 }, poiId: 'checkup_room_1' },
  { id: 'checkup_room_2', type: 'poi', floorLevel: 4, coordinates: { x: 380, y: 430 }, poiId: 'checkup_room_2' },
  { id: 'checkup_endoscopy', type: 'poi', floorLevel: 4, coordinates: { x: 625, y: 430 }, poiId: 'checkup_endoscopy' },
  { id: 'checkup_consult', type: 'poi', floorLevel: 4, coordinates: { x: 170, y: 600 }, poiId: 'checkup_consult' },
  { id: 'elevator_4', type: 'poi', floorLevel: 4, coordinates: { x: 940, y: 430 }, poiId: 'elevator_4' },
  { id: 'stairs_4', type: 'poi', floorLevel: 4, coordinates: { x: 1060, y: 430 }, poiId: 'stairs_4' },
];

/** 복도 교차점 (junction) — L자형 경로를 위한 중간 노드 */
const junctionNodes: NavNode[] = [
  // 1층 복도 교차점 (y=320 = 복도 중심선)
  { id: 'jn_1_a', type: 'junction', floorLevel: 1, coordinates: { x: 170, y: 320 } },
  { id: 'jn_1_b', type: 'junction', floorLevel: 1, coordinates: { x: 380, y: 320 } },
  { id: 'jn_1_c', type: 'junction', floorLevel: 1, coordinates: { x: 600, y: 320 } },
  { id: 'jn_1_d', type: 'junction', floorLevel: 1, coordinates: { x: 625, y: 320 } },
  { id: 'jn_1_e', type: 'junction', floorLevel: 1, coordinates: { x: 940, y: 320 } },
  { id: 'jn_1_f', type: 'junction', floorLevel: 1, coordinates: { x: 1060, y: 320 } },
  // 2층 복도 교차점
  { id: 'jn_2_a', type: 'junction', floorLevel: 2, coordinates: { x: 170, y: 320 } },
  { id: 'jn_2_b', type: 'junction', floorLevel: 2, coordinates: { x: 380, y: 320 } },
  { id: 'jn_2_c', type: 'junction', floorLevel: 2, coordinates: { x: 625, y: 320 } },
  { id: 'jn_2_d', type: 'junction', floorLevel: 2, coordinates: { x: 940, y: 320 } },
  { id: 'jn_2_e', type: 'junction', floorLevel: 2, coordinates: { x: 1060, y: 320 } },
  { id: 'jn_2_f', type: 'junction', floorLevel: 2, coordinates: { x: 180, y: 530 } },
  // 3층 복도 교차점
  { id: 'jn_3_a', type: 'junction', floorLevel: 3, coordinates: { x: 170, y: 320 } },
  { id: 'jn_3_b', type: 'junction', floorLevel: 3, coordinates: { x: 450, y: 320 } },
  { id: 'jn_3_c', type: 'junction', floorLevel: 3, coordinates: { x: 940, y: 320 } },
  { id: 'jn_3_d', type: 'junction', floorLevel: 3, coordinates: { x: 1060, y: 320 } },
  { id: 'jn_3_e', type: 'junction', floorLevel: 3, coordinates: { x: 170, y: 530 } },
  { id: 'jn_3_f', type: 'junction', floorLevel: 3, coordinates: { x: 400, y: 530 } },
  // 4층 복도 교차점
  { id: 'jn_4_a', type: 'junction', floorLevel: 4, coordinates: { x: 170, y: 320 } },
  { id: 'jn_4_b', type: 'junction', floorLevel: 4, coordinates: { x: 380, y: 320 } },
  { id: 'jn_4_c', type: 'junction', floorLevel: 4, coordinates: { x: 625, y: 320 } },
  { id: 'jn_4_d', type: 'junction', floorLevel: 4, coordinates: { x: 940, y: 320 } },
  { id: 'jn_4_e', type: 'junction', floorLevel: 4, coordinates: { x: 1060, y: 320 } },
  { id: 'jn_4_f', type: 'junction', floorLevel: 4, coordinates: { x: 170, y: 530 } },
  { id: 'jn_4_g', type: 'junction', floorLevel: 4, coordinates: { x: 400, y: 320 } },
];

// ============================
// 엣지 정의
// ============================

let edgeId = 0;
function e(
  fromNodeId: string,
  toNodeId: string,
  weight: number,
  distance: number,
  pathCoordinates: { x: number; y: number }[],
  floorTransition?: NavEdge['floorTransition'],
): NavEdge {
  edgeId++;
  return {
    id: `e${edgeId}`,
    fromNodeId,
    toNodeId,
    weight,
    distance,
    pathCoordinates,
    floorTransition,
  };
}

// --- 1층 엣지 ---
const floor1Edges: NavEdge[] = [
  // 출입구 → 복도
  e('entrance_main', 'jn_1_c', 20, 24, [{ x: 600, y: 80 }, { x: 600, y: 320 }]),
  // POI → 복도 교차점 (방에서 나와 복도로)
  e('admin_reception', 'jn_1_a', 12, 10, [{ x: 170, y: 195 }, { x: 170, y: 320 }]),
  e('admin_billing', 'jn_1_b', 12, 10, [{ x: 380, y: 195 }, { x: 380, y: 320 }]),
  e('pharmacy_main', 'jn_1_d', 12, 10, [{ x: 625, y: 195 }, { x: 625, y: 320 }]),
  e('lobby_1f', 'jn_1_e', 12, 10, [{ x: 950, y: 195 }, { x: 950, y: 320 }]),
  e('convenience_store', 'jn_1_a', 15, 11, [{ x: 180, y: 430 }, { x: 170, y: 320 }]),
  e('elevator_1', 'jn_1_e', 12, 11, [{ x: 940, y: 430 }, { x: 940, y: 320 }]),
  e('stairs_1', 'jn_1_f', 12, 11, [{ x: 1060, y: 430 }, { x: 1060, y: 320 }]),
  // 복도 내 연결 (좌→우)
  e('jn_1_a', 'jn_1_b', 18, 17, [{ x: 170, y: 320 }, { x: 380, y: 320 }]),
  e('jn_1_b', 'jn_1_c', 18, 18, [{ x: 380, y: 320 }, { x: 600, y: 320 }]),
  e('jn_1_c', 'jn_1_d', 3, 2, [{ x: 600, y: 320 }, { x: 625, y: 320 }]),
  e('jn_1_d', 'jn_1_e', 25, 26, [{ x: 625, y: 320 }, { x: 940, y: 320 }]),
  e('jn_1_e', 'jn_1_f', 10, 10, [{ x: 940, y: 320 }, { x: 1060, y: 320 }]),
];

// --- 2층 엣지 ---
const floor2Edges: NavEdge[] = [
  e('clinic_internal_1', 'jn_2_a', 12, 10, [{ x: 170, y: 195 }, { x: 170, y: 320 }]),
  e('clinic_internal_2', 'jn_2_b', 12, 10, [{ x: 380, y: 195 }, { x: 380, y: 320 }]),
  e('lab_blood', 'jn_2_c', 12, 10, [{ x: 625, y: 195 }, { x: 625, y: 320 }]),
  e('clinic_surgery_1', 'jn_2_a', 15, 11, [{ x: 170, y: 430 }, { x: 170, y: 320 }]),
  e('clinic_surgery_2', 'jn_2_b', 15, 11, [{ x: 380, y: 430 }, { x: 380, y: 320 }]),
  e('clinic_pediatrics', 'jn_2_f', 8, 5, [{ x: 180, y: 580 }, { x: 180, y: 530 }]),
  e('jn_2_f', 'jn_2_a', 20, 21, [{ x: 180, y: 530 }, { x: 170, y: 320 }]),
  e('elevator_2', 'jn_2_d', 12, 11, [{ x: 940, y: 430 }, { x: 940, y: 320 }]),
  e('stairs_2', 'jn_2_e', 12, 11, [{ x: 1060, y: 430 }, { x: 1060, y: 320 }]),
  // 복도 내 연결
  e('jn_2_a', 'jn_2_b', 18, 17, [{ x: 170, y: 320 }, { x: 380, y: 320 }]),
  e('jn_2_b', 'jn_2_c', 20, 20, [{ x: 380, y: 320 }, { x: 625, y: 320 }]),
  e('jn_2_c', 'jn_2_d', 25, 26, [{ x: 625, y: 320 }, { x: 940, y: 320 }]),
  e('jn_2_d', 'jn_2_e', 10, 10, [{ x: 940, y: 320 }, { x: 1060, y: 320 }]),
];

// --- 3층 엣지 ---
const floor3Edges: NavEdge[] = [
  e('imaging_ct', 'jn_3_a', 12, 10, [{ x: 170, y: 195 }, { x: 170, y: 320 }]),
  e('imaging_mri', 'jn_3_b', 12, 10, [{ x: 450, y: 195 }, { x: 450, y: 320 }]),
  e('imaging_xray', 'jn_3_a', 15, 11, [{ x: 170, y: 430 }, { x: 170, y: 320 }]),
  e('imaging_reception', 'jn_3_b', 15, 11, [{ x: 450, y: 430 }, { x: 450, y: 320 }]),
  e('clinic_orthopedics', 'jn_3_e', 10, 7, [{ x: 170, y: 600 }, { x: 170, y: 530 }]),
  e('clinic_rehab', 'jn_3_f', 10, 7, [{ x: 400, y: 600 }, { x: 400, y: 530 }]),
  e('jn_3_e', 'jn_3_a', 20, 21, [{ x: 170, y: 530 }, { x: 170, y: 320 }]),
  e('jn_3_f', 'jn_3_b', 20, 21, [{ x: 400, y: 530 }, { x: 450, y: 320 }]),
  e('elevator_3', 'jn_3_c', 12, 11, [{ x: 940, y: 430 }, { x: 940, y: 320 }]),
  e('stairs_3', 'jn_3_d', 12, 11, [{ x: 1060, y: 430 }, { x: 1060, y: 320 }]),
  // 복도 내 연결
  e('jn_3_a', 'jn_3_b', 22, 23, [{ x: 170, y: 320 }, { x: 450, y: 320 }]),
  e('jn_3_b', 'jn_3_c', 38, 40, [{ x: 450, y: 320 }, { x: 940, y: 320 }]),
  e('jn_3_c', 'jn_3_d', 10, 10, [{ x: 940, y: 320 }, { x: 1060, y: 320 }]),
];

// --- 4층 엣지 ---
const floor4Edges: NavEdge[] = [
  e('checkup_reception', 'jn_4_g', 15, 14, [{ x: 400, y: 150 }, { x: 400, y: 320 }]),
  e('checkup_room_1', 'jn_4_a', 15, 11, [{ x: 170, y: 430 }, { x: 170, y: 320 }]),
  e('checkup_room_2', 'jn_4_b', 15, 11, [{ x: 380, y: 430 }, { x: 380, y: 320 }]),
  e('checkup_endoscopy', 'jn_4_c', 15, 11, [{ x: 625, y: 430 }, { x: 625, y: 320 }]),
  e('checkup_consult', 'jn_4_f', 10, 7, [{ x: 170, y: 600 }, { x: 170, y: 530 }]),
  e('jn_4_f', 'jn_4_a', 20, 21, [{ x: 170, y: 530 }, { x: 170, y: 320 }]),
  e('elevator_4', 'jn_4_d', 12, 11, [{ x: 940, y: 430 }, { x: 940, y: 320 }]),
  e('stairs_4', 'jn_4_e', 12, 11, [{ x: 1060, y: 430 }, { x: 1060, y: 320 }]),
  // 복도 내 연결
  e('jn_4_a', 'jn_4_b', 18, 17, [{ x: 170, y: 320 }, { x: 380, y: 320 }]),
  e('jn_4_b', 'jn_4_g', 2, 2, [{ x: 380, y: 320 }, { x: 400, y: 320 }]),
  e('jn_4_g', 'jn_4_c', 18, 18, [{ x: 400, y: 320 }, { x: 625, y: 320 }]),
  e('jn_4_c', 'jn_4_d', 25, 26, [{ x: 625, y: 320 }, { x: 940, y: 320 }]),
  e('jn_4_d', 'jn_4_e', 10, 10, [{ x: 940, y: 320 }, { x: 1060, y: 320 }]),
];

// --- 층간 이동 엣지 ---
const elevatorEdges: NavEdge[] = [
  e('elevator_1', 'elevator_2', 30, 0, [], { fromFloor: 1, toFloor: 2, via: 'elevator' }),
  e('elevator_2', 'elevator_3', 30, 0, [], { fromFloor: 2, toFloor: 3, via: 'elevator' }),
  e('elevator_3', 'elevator_4', 30, 0, [], { fromFloor: 3, toFloor: 4, via: 'elevator' }),
];

const stairsEdges: NavEdge[] = [
  e('stairs_1', 'stairs_2', 45, 0, [], { fromFloor: 1, toFloor: 2, via: 'stairs' }),
  e('stairs_2', 'stairs_3', 45, 0, [], { fromFloor: 2, toFloor: 3, via: 'stairs' }),
  e('stairs_3', 'stairs_4', 45, 0, [], { fromFloor: 3, toFloor: 4, via: 'stairs' }),
];

// ============================
// 그래프 내보내기
// ============================

export const navigationGraph: NavigationGraph = {
  hospitalId: 'demo-hospital',
  nodes: [...poiNodes, ...junctionNodes],
  edges: [
    ...floor1Edges,
    ...floor2Edges,
    ...floor3Edges,
    ...floor4Edges,
    ...elevatorEdges,
    ...stairsEdges,
  ],
};
