import { useMemo, useState } from 'react';
import { Search, Plus } from 'lucide-react';
import { allPOIs } from '@/data/hospital/pois';
import type { POI, POICategory } from '@/types/hospital';

const CATEGORY_LABEL: Record<POICategory, string> = {
  clinic: '진료',
  lab: '검사',
  imaging: '영상',
  pharmacy: '약국',
  admin: '원무',
  elevator: '엘리베이터',
  stairs: '계단',
  restroom: '화장실',
  parking: '주차',
  entrance: '출입구',
  convenience: '편의',
  lobby: '로비',
};

// 환자가 방문 계획에 넣을 만한 POI만 노출 (시설 편의물은 제외)
const USEFUL_CATEGORIES: POICategory[] = [
  'clinic',
  'lab',
  'imaging',
  'pharmacy',
  'admin',
  'entrance',
];

interface POIPickerProps {
  onAdd: (poiId: string) => void;
  excludeIds?: string[];
}

export function POIPicker({ onAdd, excludeIds = [] }: POIPickerProps) {
  const [q, setQ] = useState('');
  const [category, setCategory] = useState<POICategory | 'all'>('all');

  const candidates = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return allPOIs
      .filter((p) => USEFUL_CATEGORIES.includes(p.category))
      .filter((p) => !excludeIds.includes(p.id))
      .filter((p) => (category === 'all' ? true : p.category === category))
      .filter((p) =>
        needle ? (p.name + ' ' + p.shortName).toLowerCase().includes(needle) : true,
      );
  }, [q, category, excludeIds]);

  return (
    <div className="rounded-xl border border-surface-container-high bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-surface-container-high p-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-on-surface-variant" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="목적지 이름 검색 (예: 채혈, 내과)"
            className="w-full rounded-lg border border-surface-container-high bg-surface py-1.5 pl-8 pr-3 text-xs outline-none focus:border-primary"
          />
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as POICategory | 'all')}
          className="rounded-lg border border-surface-container-high bg-surface px-3 py-1.5 text-xs"
        >
          <option value="all">전체 카테고리</option>
          {USEFUL_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c]}
            </option>
          ))}
        </select>
      </div>

      <div className="max-h-64 overflow-y-auto">
        {candidates.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-on-surface-variant">
            일치하는 목적지가 없습니다
          </p>
        ) : (
          candidates.map((p) => <POIRow key={p.id} poi={p} onAdd={onAdd} />)
        )}
      </div>
    </div>
  );
}

function POIRow({ poi, onAdd }: { poi: POI; onAdd: (id: string) => void }) {
  return (
    <div className="flex items-center justify-between border-b border-surface-container-high/60 px-4 py-2.5 last:border-0 hover:bg-surface-container-low/60">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-on-surface">{poi.name}</p>
        <p className="truncate text-[11px] text-on-surface-variant">
          {poi.buildingId === 'main' ? '본관' : poi.buildingId} · {poi.floorLevel}F · {CATEGORY_LABEL[poi.category]}
        </p>
      </div>
      <button
        type="button"
        onClick={() => onAdd(poi.id)}
        className="flex shrink-0 items-center gap-1 rounded-lg border border-primary bg-primary/5 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/10"
      >
        <Plus className="h-3 w-3" />
        추가
      </button>
    </div>
  );
}
