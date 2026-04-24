import type { FloorPlanData } from '@/types/floor-plan';

/** 4층 — 건강검진센터 */
export const floor4Data: FloorPlanData = {
  floorLevel: 4,
  floorName: '4층',
  buildingOutline: [
    { x: 50, y: 50 },
    { x: 1150, y: 50 },
    { x: 1150, y: 700 },
    { x: 50, y: 700 },
  ],
  corridors: [
    {
      id: 'corridor_4_main',
      points: [
        { x: 50, y: 280 },
        { x: 1150, y: 280 },
        { x: 1150, y: 360 },
        { x: 50, y: 360 },
      ],
      label: '4층 중앙 복도',
    },
    {
      id: 'corridor_4_south',
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
      id: 'room_checkup_reception',
      label: '검진센터 접수/대기',
      type: 'checkup',
      geometry: { kind: 'rect', x: 80, y: 100, width: 700, height: 170 },
      labelPosition: { x: 400, y: 150 },
    },
    {
      id: 'room_4f_admin',
      label: '행정실',
      type: 'admin',
      geometry: { kind: 'rect', x: 810, y: 100, width: 310, height: 170 },
      labelPosition: { x: 950, y: 185 },
    },
    {
      id: 'room_checkup_1',
      label: '검진실 1',
      type: 'checkup',
      geometry: { kind: 'rect', x: 80, y: 370, width: 180, height: 120 },
      labelPosition: { x: 170, y: 430 },
    },
    {
      id: 'room_checkup_2',
      label: '검진실 2',
      type: 'checkup',
      geometry: { kind: 'rect', x: 290, y: 370, width: 180, height: 120 },
      labelPosition: { x: 380, y: 430 },
    },
    {
      id: 'room_endoscopy',
      label: '내시경실',
      type: 'checkup',
      geometry: { kind: 'rect', x: 500, y: 370, width: 250, height: 120 },
      labelPosition: { x: 625, y: 430 },
    },
    {
      id: 'room_consult',
      label: '상담실',
      type: 'consultation',
      geometry: { kind: 'rect', x: 80, y: 570, width: 200, height: 110 },
      labelPosition: { x: 170, y: 600 },
    },
    {
      id: 'room_restroom_4f',
      label: '화장실',
      type: 'restroom',
      geometry: { kind: 'rect', x: 310, y: 570, width: 120, height: 110 },
      labelPosition: { x: 370, y: 620 },
    },
    {
      id: 'room_elevator_4',
      label: 'EV',
      type: 'elevator',
      geometry: { kind: 'rect', x: 900, y: 370, width: 80, height: 80 },
      labelPosition: { x: 940, y: 410 },
    },
    {
      id: 'room_stairs_4',
      label: '계단',
      type: 'stairs',
      geometry: { kind: 'rect', x: 1020, y: 370, width: 80, height: 80 },
      labelPosition: { x: 1060, y: 410 },
    },
  ],
  walls: [
    { id: 'w4_1', points: [{ x: 790, y: 100 }, { x: 790, y: 270 }] },
    { id: 'w4_2', points: [{ x: 270, y: 370 }, { x: 270, y: 490 }] },
    { id: 'w4_3', points: [{ x: 480, y: 370 }, { x: 480, y: 490 }] },
    { id: 'w4_4', points: [{ x: 290, y: 570 }, { x: 290, y: 680 }] },
  ],
  doors: [
    { id: 'd4_checkup_recv', position: { x: 400, y: 270 }, width: 60 },
    { id: 'd4_checkup_1', position: { x: 170, y: 370 }, width: 40 },
    { id: 'd4_checkup_2', position: { x: 380, y: 370 }, width: 40 },
    { id: 'd4_endoscopy', position: { x: 625, y: 370 }, width: 40 },
    { id: 'd4_consult', position: { x: 170, y: 560 }, width: 40 },
    { id: 'd4_elevator', position: { x: 940, y: 370 }, width: 40 },
    { id: 'd4_stairs', position: { x: 1060, y: 370 }, width: 40 },
  ],
};
