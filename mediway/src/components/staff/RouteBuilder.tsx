import { useState, useCallback } from 'react';
import { Plus, X, ChevronUp, ChevronDown, Search } from 'lucide-react';
import { allPOIs, getPOIById } from '@/data/hospital';
import type { POICategory } from '@/types/hospital';

interface Props {
  waypoints: string[];
  onChange: (waypointPoiIds: string[]) => void;
}

const FILTER_CATEGORIES: { label: string; value: POICategory | 'all' }[] = [
  { label: '전체', value: 'all' },
  { label: '진료실', value: 'clinic' },
  { label: '검사실', value: 'lab' },
  { label: '영상의학', value: 'imaging' },
  { label: '약국', value: 'pharmacy' },
  { label: '원무/행정', value: 'admin' },
];

export function RouteBuilder({ waypoints, onChange }: Props) {
  const [showSearch, setShowSearch] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<POICategory | 'all'>('all');

  const addWaypoint = useCallback(
    (poiId: string) => {
      // 귀가(entrance_main) 앞에 삽입
      const entranceIdx = waypoints.indexOf('entrance_main');
      if (entranceIdx >= 0) {
        const next = [...waypoints];
        next.splice(entranceIdx, 0, poiId);
        onChange(next);
      } else {
        onChange([...waypoints, poiId]);
      }
      setShowSearch(false);
      setSearchText('');
    },
    [waypoints, onChange],
  );

  const removeWaypoint = useCallback(
    (index: number) => {
      onChange(waypoints.filter((_, i) => i !== index));
    },
    [waypoints, onChange],
  );

  const moveWaypoint = useCallback(
    (index: number, direction: -1 | 1) => {
      const next = [...waypoints];
      const targetIdx = index + direction;
      if (targetIdx < 0 || targetIdx >= next.length) return;
      [next[index], next[targetIdx]] = [next[targetIdx], next[index]];
      onChange(next);
    },
    [waypoints, onChange],
  );

  // 검색 가능한 POI (이미 추가된 것 제외)
  const availablePOIs = allPOIs.filter((poi) => {
    if (waypoints.includes(poi.id)) return false;
    if (poi.category === 'elevator' || poi.category === 'stairs' || poi.category === 'restroom') return false;
    if (categoryFilter !== 'all' && poi.category !== categoryFilter) return false;
    if (searchText && !poi.name.includes(searchText) && !poi.shortName.includes(searchText)) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-on-surface">커스텀 경로 편집</h3>
        <button
          onClick={() => setShowSearch(!showSearch)}
          className="flex items-center gap-1 rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
        >
          <Plus className="h-3.5 w-3.5" />
          경유지 추가
        </button>
      </div>

      {/* 현재 경유지 목록 */}
      <div className="flex flex-col gap-1.5">
        {waypoints.map((poiId, index) => {
          const poi = getPOIById(poiId);
          const isEntrance = poiId === 'entrance_main';

          return (
            <div
              key={`${poiId}-${index}`}
              className="flex items-center gap-2 rounded-xl bg-surface-container-lowest p-3 shadow-ambient"
            >
              {/* 순서 번호 */}
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                {index + 1}
              </span>

              {/* 정보 */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-on-surface truncate">
                  {poi?.name ?? poiId}
                </p>
                <p className="text-xs text-on-surface-variant">
                  {poi ? `${poi.floorLevel}층` : ''}
                  {isEntrance ? ' (귀가)' : ''}
                </p>
              </div>

              {/* 액션 버튼 */}
              {!isEntrance && (
                <div className="flex items-center gap-0.5">
                  <button
                    onClick={() => moveWaypoint(index, -1)}
                    disabled={index === 0}
                    className="rounded-lg p-1 text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-30"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => moveWaypoint(index, 1)}
                    disabled={index === waypoints.length - 1}
                    className="rounded-lg p-1 text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-30"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => removeWaypoint(index)}
                    className="rounded-lg p-1 text-error/70 transition-colors hover:bg-error-container/30 hover:text-error"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* POI 검색/추가 패널 */}
      {showSearch && (
        <div className="rounded-xl bg-surface-container-low p-3">
          {/* 검색 */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-on-surface-variant" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="장소 검색..."
              className="w-full rounded-xl bg-surface-container-highest py-2.5 pl-9 pr-4 text-sm text-on-surface outline-none focus:bg-surface-container-lowest focus:shadow-ambient"
              autoFocus
            />
          </div>

          {/* 카테고리 필터 */}
          <div className="mb-3 flex flex-wrap gap-1.5">
            {FILTER_CATEGORIES.map((cat) => (
              <button
                key={cat.value}
                onClick={() => setCategoryFilter(cat.value)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                  categoryFilter === cat.value
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* 결과 목록 */}
          <div className="flex max-h-48 flex-col gap-1 overflow-y-auto">
            {availablePOIs.length === 0 ? (
              <p className="py-4 text-center text-xs text-on-surface-variant">
                검색 결과가 없습니다
              </p>
            ) : (
              availablePOIs.map((poi) => (
                <button
                  key={poi.id}
                  onClick={() => addWaypoint(poi.id)}
                  className="flex items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-surface-container-lowest"
                >
                  <span className="text-sm font-medium text-on-surface">{poi.name}</span>
                  <span className="text-xs text-on-surface-variant">{poi.floorLevel}층</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
