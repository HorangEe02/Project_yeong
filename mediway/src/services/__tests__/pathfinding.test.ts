import { describe, it, expect } from 'vitest';
import { findShortestPath, computeRoute } from '../pathfinding';
import { navigationGraph } from '@/data/hospital/navigation-graph';

describe('findShortestPath', () => {
  it('같은 층 내 경로를 찾는다 (1층: 접수 → 약국)', () => {
    const result = findShortestPath(navigationGraph, 'admin_reception', 'pharmacy_main');
    expect(result).not.toBeNull();
    expect(result!.fromPoiId).toBe('admin_reception');
    expect(result!.toPoiId).toBe('pharmacy_main');
    expect(result!.totalTime).toBeGreaterThan(0);
    expect(result!.totalDistance).toBeGreaterThan(0);
    expect(result!.segments.length).toBeGreaterThanOrEqual(1);
    // 모든 세그먼트가 1층이어야 함
    result!.segments
      .filter((s) => !s.floorTransition)
      .forEach((s) => expect(s.floorLevel).toBe(1));
  });

  it('층간 이동 경로를 찾는다 (2층 채혈실 → 1층 원무과)', () => {
    const result = findShortestPath(navigationGraph, 'lab_blood', 'admin_billing');
    expect(result).not.toBeNull();
    expect(result!.totalTime).toBeGreaterThan(0);
    // 층 전환 세그먼트가 포함되어야 함
    const floorTransitions = result!.segments.filter((s) => s.floorTransition);
    expect(floorTransitions.length).toBeGreaterThanOrEqual(1);
    // 전환 instruction이 한국어로 생성되어야 함
    floorTransitions.forEach((s) => {
      expect(s.floorTransition!.instruction).toMatch(/층으로 이동하세요/);
    });
  });

  it('여러 층을 건너뛰는 경로를 찾는다 (4층 내시경 → 1층 약국)', () => {
    const result = findShortestPath(navigationGraph, 'checkup_endoscopy', 'pharmacy_main');
    expect(result).not.toBeNull();
    expect(result!.segments.length).toBeGreaterThanOrEqual(3); // 4층 구간 + 전환 + ... + 1층 구간
  });

  it('출발지와 목적지가 같으면 빈 경로를 반환한다', () => {
    const result = findShortestPath(navigationGraph, 'admin_billing', 'admin_billing');
    expect(result).not.toBeNull();
    expect(result!.totalDistance).toBe(0);
    expect(result!.totalTime).toBe(0);
    expect(result!.segments).toHaveLength(0);
  });

  it('존재하지 않는 POI ID에 대해 null을 반환한다', () => {
    const result = findShortestPath(navigationGraph, 'nonexistent', 'admin_billing');
    expect(result).toBeNull();
  });
});

describe('computeRoute', () => {
  it('템플릿 1: 채혈 → 원무과 → 약국 → 귀가', () => {
    const result = computeRoute(navigationGraph, [
      'lab_blood',
      'admin_billing',
      'pharmacy_main',
      'entrance_main',
    ]);
    expect(result).not.toBeNull();
    expect(result!.legs).toHaveLength(3);
    expect(result!.waypoints).toEqual([
      'lab_blood',
      'admin_billing',
      'pharmacy_main',
      'entrance_main',
    ]);
    expect(result!.totalTime).toBeGreaterThan(0);
    expect(result!.totalDistance).toBeGreaterThan(0);
  });

  it('템플릿 2: 원무과 → 약국 → 귀가', () => {
    const result = computeRoute(navigationGraph, [
      'admin_billing',
      'pharmacy_main',
      'entrance_main',
    ]);
    expect(result).not.toBeNull();
    expect(result!.legs).toHaveLength(2);
  });

  it('템플릿 3: 영상의학과 → 원무과 → 약국 → 귀가', () => {
    const result = computeRoute(navigationGraph, [
      'imaging_reception',
      'admin_billing',
      'pharmacy_main',
      'entrance_main',
    ]);
    expect(result).not.toBeNull();
    expect(result!.legs).toHaveLength(3);
    // 3층→1층 층간 이동이 포함되어야 함
    const allSegments = result!.legs.flatMap((l) => l.segments);
    const transitions = allSegments.filter((s) => s.floorTransition);
    expect(transitions.length).toBeGreaterThanOrEqual(1);
  });

  it('템플릿 4: 채혈 → 영상의학과 → 원무과 → 약국 → 귀가', () => {
    const result = computeRoute(navigationGraph, [
      'lab_blood',
      'imaging_reception',
      'admin_billing',
      'pharmacy_main',
      'entrance_main',
    ]);
    expect(result).not.toBeNull();
    expect(result!.legs).toHaveLength(4);
  });

  it('템플릿 5: 채혈 → CT → 내시경 → 상담 → 원무과 → 귀가', () => {
    const result = computeRoute(navigationGraph, [
      'lab_blood',
      'imaging_ct',
      'checkup_endoscopy',
      'checkup_consult',
      'admin_billing',
      'entrance_main',
    ]);
    expect(result).not.toBeNull();
    expect(result!.legs).toHaveLength(5);
  });

  it('템플릿 6: X-ray → 정형외과 → 원무과 → 약국 → 귀가', () => {
    const result = computeRoute(navigationGraph, [
      'imaging_xray',
      'clinic_orthopedics',
      'admin_billing',
      'pharmacy_main',
      'entrance_main',
    ]);
    expect(result).not.toBeNull();
    expect(result!.legs).toHaveLength(4);
  });

  it('경유지가 1개 이하이면 null을 반환한다', () => {
    expect(computeRoute(navigationGraph, ['admin_billing'])).toBeNull();
    expect(computeRoute(navigationGraph, [])).toBeNull();
  });

  it('존재하지 않는 POI가 포함되면 null을 반환한다', () => {
    const result = computeRoute(navigationGraph, [
      'admin_billing',
      'nonexistent_poi',
      'entrance_main',
    ]);
    expect(result).toBeNull();
  });
});
