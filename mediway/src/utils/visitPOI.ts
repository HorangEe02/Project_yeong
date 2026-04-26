import type { POI } from '@/types/hospital';

/**
 * Phase I.3.1 — visit 의 자유 텍스트 zone 을 POI 와 휴리스틱 매핑.
 *
 * 단계:
 *  1. 정확 일치 (name 또는 shortName)
 *  2. POI name 이 zone 의 substring (대소문자 무시)
 *  3. zone 이 POI name 의 substring
 *  4. 매칭 없음 → undefined
 *
 * Default 정책 (Phase I.3 default 매핑) — 더 정교한 zone naming convention 은 별도 sprint.
 *
 * @param zone - visit.zone 문자열 (예: "내과 외래", "Zone A-1", "원무과")
 * @param pois - 검색 대상 POI 배열 (보통 `allPOIs`)
 * @returns 매칭된 POI 1건, 없으면 undefined.
 */
export function findPOIByZoneHint(zone: string, pois: ReadonlyArray<POI>): POI | undefined {
  if (!zone || !zone.trim()) return undefined;
  const trimmed = zone.trim();
  const lower = trimmed.toLowerCase();

  // 1. 정확 일치 (name 또는 shortName)
  const exact = pois.find((p) => p.name === trimmed || p.shortName === trimmed);
  if (exact) return exact;

  // 2. POI name 이 zone 의 substring
  const nameInZone = pois.find((p) => {
    const n = p.name.toLowerCase();
    return n.length > 0 && lower.includes(n);
  });
  if (nameInZone) return nameInZone;

  // 3. zone 이 POI name 의 substring
  const zoneInName = pois.find((p) => p.name.toLowerCase().includes(lower));
  if (zoneInName) return zoneInName;

  return undefined;
}
