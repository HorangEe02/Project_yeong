import type { FloorPlanData } from '@/types/floor-plan';

/** 1층 — 로비 / 접수 / 약국 */
export const floor1Data: FloorPlanData = {
  floorLevel: 1,
  floorName: '1층',
  buildingOutline: [
    { x: 50, y: 50 },
    { x: 1150, y: 50 },
    { x: 1150, y: 700 },
    { x: 50, y: 700 },
  ],
  corridors: [
    {
      id: 'corridor_1_main',
      points: [
        { x: 50, y: 280 },
        { x: 1150, y: 280 },
        { x: 1150, y: 360 },
        { x: 50, y: 360 },
      ],
      label: '1층 중앙 복도',
    },
  ],
  rooms: [
    // 정문 출입구 (상단 중앙)
    {
      id: 'room_entrance',
      label: '정문 출입구',
      type: 'lobby',
      geometry: { kind: 'rect', x: 450, y: 50, width: 300, height: 60 },
      labelPosition: { x: 600, y: 80 },
    },
    // 접수 (좌측 상단)
    {
      id: 'room_reception',
      label: '접수',
      type: 'admin',
      geometry: { kind: 'rect', x: 80, y: 120, width: 180, height: 150 },
      labelPosition: { x: 170, y: 195 },
    },
    // 원무과
    {
      id: 'room_billing',
      label: '원무과',
      type: 'admin',
      geometry: { kind: 'rect', x: 290, y: 120, width: 180, height: 150 },
      labelPosition: { x: 380, y: 195 },
    },
    // 외래약국
    {
      id: 'room_pharmacy',
      label: '외래약국',
      type: 'pharmacy',
      geometry: { kind: 'rect', x: 500, y: 120, width: 250, height: 150 },
      labelPosition: { x: 625, y: 195 },
    },
    // 로비 (우측 상단)
    {
      id: 'room_lobby',
      label: '로비',
      type: 'lobby',
      geometry: { kind: 'rect', x: 780, y: 120, width: 340, height: 150 },
      labelPosition: { x: 950, y: 195 },
    },
    // 편의점 (좌측 하단)
    {
      id: 'room_convenience',
      label: '편의점',
      type: 'convenience',
      geometry: { kind: 'rect', x: 80, y: 370, width: 200, height: 120 },
      labelPosition: { x: 180, y: 430 },
    },
    // 화장실
    {
      id: 'room_restroom_1f',
      label: '화장실',
      type: 'restroom',
      geometry: { kind: 'rect', x: 310, y: 370, width: 120, height: 120 },
      labelPosition: { x: 370, y: 430 },
    },
    // 엘리베이터
    {
      id: 'room_elevator_1',
      label: 'EV',
      type: 'elevator',
      geometry: { kind: 'rect', x: 900, y: 370, width: 80, height: 80 },
      labelPosition: { x: 940, y: 410 },
    },
    // 계단
    {
      id: 'room_stairs_1',
      label: '계단',
      type: 'stairs',
      geometry: { kind: 'rect', x: 1020, y: 370, width: 80, height: 80 },
      labelPosition: { x: 1060, y: 410 },
    },
  ],
  walls: [
    // 접수~원무과 사이 벽
    { id: 'w1_1', points: [{ x: 270, y: 120 }, { x: 270, y: 270 }] },
    // 원무과~약국 사이 벽
    { id: 'w1_2', points: [{ x: 480, y: 120 }, { x: 480, y: 270 }] },
    // 약국~로비 사이 벽
    { id: 'w1_3', points: [{ x: 760, y: 120 }, { x: 760, y: 270 }] },
    // 편의점~화장실 사이 벽
    { id: 'w1_4', points: [{ x: 290, y: 370 }, { x: 290, y: 490 }] },
  ],
  doors: [
    { id: 'd1_reception', position: { x: 170, y: 270 }, width: 40 },
    { id: 'd1_billing', position: { x: 380, y: 270 }, width: 40 },
    { id: 'd1_pharmacy', position: { x: 625, y: 270 }, width: 40 },
    { id: 'd1_lobby', position: { x: 950, y: 270 }, width: 60 },
    { id: 'd1_entrance', position: { x: 600, y: 110 }, width: 80 },
    { id: 'd1_convenience', position: { x: 180, y: 370 }, width: 40 },
    { id: 'd1_elevator', position: { x: 940, y: 370 }, width: 40 },
    { id: 'd1_stairs', position: { x: 1060, y: 370 }, width: 40 },
  ],
};
