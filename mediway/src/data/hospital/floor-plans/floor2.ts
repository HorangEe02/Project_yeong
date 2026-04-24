import type { FloorPlanData } from '@/types/floor-plan';

/** 2층 — 내과 / 외과 / 채혈실 */
export const floor2Data: FloorPlanData = {
  floorLevel: 2,
  floorName: '2층',
  buildingOutline: [
    { x: 50, y: 50 },
    { x: 1150, y: 50 },
    { x: 1150, y: 700 },
    { x: 50, y: 700 },
  ],
  corridors: [
    {
      id: 'corridor_2_main',
      points: [
        { x: 50, y: 280 },
        { x: 1150, y: 280 },
        { x: 1150, y: 360 },
        { x: 50, y: 360 },
      ],
      label: '2층 중앙 복도',
    },
    {
      id: 'corridor_2_south',
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
      id: 'room_internal_1',
      label: '내과 1진료실',
      type: 'clinic',
      geometry: { kind: 'rect', x: 80, y: 120, width: 180, height: 150 },
      labelPosition: { x: 170, y: 195 },
    },
    {
      id: 'room_internal_2',
      label: '내과 2진료실',
      type: 'clinic',
      geometry: { kind: 'rect', x: 290, y: 120, width: 180, height: 150 },
      labelPosition: { x: 380, y: 195 },
    },
    {
      id: 'room_blood_lab',
      label: '채혈실',
      type: 'lab',
      geometry: { kind: 'rect', x: 500, y: 120, width: 250, height: 150 },
      labelPosition: { x: 625, y: 195 },
    },
    {
      id: 'room_2f_waiting',
      label: '2층 대기실',
      type: 'lobby',
      geometry: { kind: 'rect', x: 780, y: 120, width: 340, height: 150 },
      labelPosition: { x: 950, y: 195 },
    },
    {
      id: 'room_surgery_1',
      label: '외과 1진료실',
      type: 'clinic',
      geometry: { kind: 'rect', x: 80, y: 370, width: 180, height: 120 },
      labelPosition: { x: 170, y: 430 },
    },
    {
      id: 'room_surgery_2',
      label: '외과 2진료실',
      type: 'clinic',
      geometry: { kind: 'rect', x: 290, y: 370, width: 180, height: 120 },
      labelPosition: { x: 380, y: 430 },
    },
    {
      id: 'room_pediatrics',
      label: '소아과',
      type: 'clinic',
      geometry: { kind: 'rect', x: 80, y: 570, width: 200, height: 110 },
      labelPosition: { x: 180, y: 580 },
    },
    {
      id: 'room_restroom_2f',
      label: '화장실',
      type: 'restroom',
      geometry: { kind: 'rect', x: 500, y: 370, width: 120, height: 120 },
      labelPosition: { x: 560, y: 430 },
    },
    {
      id: 'room_elevator_2',
      label: 'EV',
      type: 'elevator',
      geometry: { kind: 'rect', x: 900, y: 370, width: 80, height: 80 },
      labelPosition: { x: 940, y: 410 },
    },
    {
      id: 'room_stairs_2',
      label: '계단',
      type: 'stairs',
      geometry: { kind: 'rect', x: 1020, y: 370, width: 80, height: 80 },
      labelPosition: { x: 1060, y: 410 },
    },
  ],
  walls: [
    { id: 'w2_1', points: [{ x: 270, y: 120 }, { x: 270, y: 270 }] },
    { id: 'w2_2', points: [{ x: 480, y: 120 }, { x: 480, y: 270 }] },
    { id: 'w2_3', points: [{ x: 760, y: 120 }, { x: 760, y: 270 }] },
    { id: 'w2_4', points: [{ x: 270, y: 370 }, { x: 270, y: 490 }] },
    { id: 'w2_5', points: [{ x: 480, y: 370 }, { x: 480, y: 490 }] },
  ],
  doors: [
    { id: 'd2_internal_1', position: { x: 170, y: 270 }, width: 40 },
    { id: 'd2_internal_2', position: { x: 380, y: 270 }, width: 40 },
    { id: 'd2_blood_lab', position: { x: 625, y: 270 }, width: 40 },
    { id: 'd2_surgery_1', position: { x: 170, y: 370 }, width: 40 },
    { id: 'd2_surgery_2', position: { x: 380, y: 370 }, width: 40 },
    { id: 'd2_pediatrics', position: { x: 180, y: 560 }, width: 40 },
    { id: 'd2_elevator', position: { x: 940, y: 370 }, width: 40 },
    { id: 'd2_stairs', position: { x: 1060, y: 370 }, width: 40 },
  ],
};
