import { useNavigate } from 'react-router-dom';
import { Calendar, MapPin, Ticket, Users } from 'lucide-react';
import { useHospital } from '@/hooks/useHospital';
import { useSeniorCopy } from '@/hooks/useSeniorCopy';
import { useMyActiveWaitEntries } from '@/hooks/useMyActiveWaitEntries';
import { SeniorTile } from './SeniorTile';

/**
 * SeniorHome 4 타일 그리드 (시안 2/5).
 *
 * 1. 병원 예약하기 → 외래 탭
 * 2. 길 안내      → 안내 탭
 * 3. 내 순번 보기  → 홈 탭(자신) — 뱃지로 활성 순번 표시
 * 4. 가족 연락    → P4 가족 대리(C6-C10) merge 후 활성, 현재는 disabled
 */
export function SeniorTileGrid() {
  const { slug } = useHospital();
  const copy = useSeniorCopy();
  const navigate = useNavigate();
  const active = useMyActiveWaitEntries();
  const myTurn = active[0]?.number;

  const goTab = (tab: string) => {
    if (slug) navigate(`/h/${slug}/patient/home?tab=${tab}`);
  };

  return (
    <div
      role="grid"
      aria-label="홈 빠른 작업"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2"
    >
      <SeniorTile
        icon={Calendar}
        label={copy('senior.tile.book', '병원 예약하기')}
        sub={copy('senior.tile.book-sub', '새로운 진료를 잡아요')}
        onClick={() => goTab('appointments')}
      />
      <SeniorTile
        icon={MapPin}
        label={copy('senior.tile.find-way', '길 안내')}
        sub={copy('senior.tile.find-way-sub', '병원 안에서 가는 길')}
        onClick={() => goTab('guide')}
      />
      <SeniorTile
        icon={Ticket}
        label={copy('senior.tile.my-turn', '내 순번 보기')}
        sub={copy('senior.tile.my-turn-sub', '기다리는 순번을 확인해요')}
        badge={myTurn}
        onClick={() => goTab('home')}
      />
      <SeniorTile
        icon={Users}
        label={copy('senior.tile.family', '가족 연락')}
        sub={copy('senior.tile.family-sub', '가족이 함께 봐요 (곧 공개)')}
        disabled
      />
    </div>
  );
}
