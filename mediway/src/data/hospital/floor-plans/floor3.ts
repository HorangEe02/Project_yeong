import type { FloorPlanData } from '@/types/floor-plan';

/** 3층 — 영상의학과 / 정형외과 / 재활의학과 */
export const floor3Data: FloorPlanData = {
  floorLevel: 3,
  floorName: '3층',
  buildingOutline: [
    { x: 50, y: 50 },
    { x: 1150, y: 50 },
    { x: 1150, y: 700 },
    { x: 50, y: 700 },
  ],
  corridors: [
    {
      id: 'corridor_3_main',
      points: [
        { x: 50, y: 280 },
        { x: 1150, y: 280 },
        { x: 1150, y: 360 },
        { x: 50, y: 360 },
      ],
      label: '3층 중앙 복도',
    },
    {
      id: 'corridor_3_south',
      points: [
        { x: 50, y: 500 },
        { x: 600, y: 500 },
        { x: 600, y: 560 },
        { x: 50, y: 560 },
      ],
    },
  ],
  rooms: [
    {
      id: 'room_ct',
      label: 'CT 촬영실',
      type: 'imaging',
      geometry: { kind: 'rect', x: 80, y: 120, width: 220, height: 150 },
      labelPosition: { x: 170, y: 195 },
    },
    {
      id: 'room_mri',
      label: 'MRI 촬영실',
      type: 'imaging',
      geometry: { kind: 'rect', x: 330, y: 120, width: 280, height: 150 },
      labelPosition: { x: 450, y: 195 },
    },
    {
      id: 'room_3f_waiting',
      label: '3층 대기실',
      type: 'lobby',
      geometry: { kind: 'rect', x: 640, y: 120, width: 480, height: 150 },
      labelPosition: { x: 880, y: 195 },
    },
    {
      id: 'room_xray',
      label: 'X-ray 촬영실',
      type: 'imaging',
      geometry: { kind: 'rect', x: 80, y: 370, width: 220, height: 120 },
      labelPosition: { x: 170, y: 430 },
    },
    {
      id: 'room_imaging_reception',
      label: '영상의학과 접수',
      type: 'imaging',
      geometry: { kind: 'rect', x: 330, y: 370, width: 280, height: 120 },
      labelPosition: { x: 450, y: 430 },
    },
    {
      id: 'room_orthopedics',
      label: '정형외과',
      type: 'clinic',
      geometry: { kind: 'rect', x: 80, y: 570, width: 200, height: 110 },
      labelPosition: { x: 170, y: 600 },
    },
    {
      id: 'room_rehab',
      label: '재활의학과',
      type: 'clinic',
      geometry: { kind: 'rect', x: 310, y: 570, width: 220, height: 110 },
      labelPosition: { x: 400, y: 600 },
    },
    {
      id: 'room_elevator_3',
      label: 'EV',
      type: 'elevator',
      geometry: { kind: 'rect', x: 900, y: 370, width: 80, height: 80 },
      labelPosition: { x: 940, y: 410 },
    },
    {
      id: 'room_stairs_3',
      label: '계단',
      type: 'stairs',
      geometry: { kind: 'rect', x: 1020, y: 370, width: 80, height: 80 },
      labelPosition: { x: 1060, y: 410 },
    },
  ],
  walls: [
    { id: 'w3_1', points: [{ x: 310, y: 120 }, { x: 310, y: 270 }] },
    { id: 'w3_2', points: [{ x: 620, y: 120 }, { x: 620, y: 270 }] },
    { id: 'w3_3', points: [{ x: 310, y: 370 }, { x: 310, y: 490 }] },
    { id: 'w3_4', points: [{ x: 290, y: 570 }, { x: 290, y: 680 }] },
  ],
  doors: [
    { id: 'd3_ct', position: { x: 170, y: 270 }, width: 40 },
    { id: 'd3_mri', position: { x: 450, y: 270 }, width: 40 },
    { id: 'd3_xray', position: { x: 170, y: 370 }, width: 40 },
    { id: 'd3_imaging_recv', position: { x: 450, y: 370 }, width: 40 },
    { id: 'd3_orthopedics', position: { x: 170, y: 560 }, width: 40 },
    { id: 'd3_rehab', position: { x: 400, y: 560 }, width: 40 },
    { id: 'd3_elevator', position: { x: 940, y: 370 }, width: 40 },
    { id: 'd3_stairs', position: { x: 1060, y: 370 }, width: 40 },
  ],
};
