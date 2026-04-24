import { PartyPopper, Home, RotateCcw } from 'lucide-react';
import { Link } from 'react-router-dom';

interface Props {
  totalSteps: number;
  onReset?: () => void;
}

export function CompletionScreen({ totalSteps, onReset }: Props) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      {/* 축하 아이콘 */}
      <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-green-50">
        <PartyPopper className="h-10 w-10 text-green-500" />
      </div>

      {/* 메시지 */}
      <div>
        <h1 className="text-2xl font-bold text-on-surface">
          오늘 진료가 모두 끝났습니다
        </h1>
        <p className="mt-2 text-on-surface-variant">
          {totalSteps}개의 동선을 모두 완료했습니다.
          <br />
          귀가하셔도 됩니다. 빠른 쾌유를 빕니다.
        </p>
      </div>

      {/* 완료 통계 */}
      <div className="flex gap-4">
        <div className="rounded-xl bg-green-50 px-5 py-3 text-center">
          <p className="text-2xl font-bold text-green-600">{totalSteps}</p>
          <p className="text-xs text-green-600/70">완료된 단계</p>
        </div>
        <div className="rounded-xl bg-primary/5 px-5 py-3 text-center">
          <p className="text-2xl font-bold text-primary">100%</p>
          <p className="text-xs text-primary/70">진행률</p>
        </div>
      </div>

      {/* 액션 버튼 */}
      <div className="flex w-full max-w-xs flex-col gap-3 pt-4">
        <Link
          to="/"
          className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-primary-container py-3.5 text-sm font-semibold text-white no-underline transition-transform active:scale-[0.97]"
        >
          <Home className="h-4 w-4" />
          홈으로 돌아가기
        </Link>
        {onReset && (
          <button
            onClick={onReset}
            className="flex items-center justify-center gap-2 rounded-xl bg-surface-container-high py-3.5 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container"
          >
            <RotateCcw className="h-4 w-4" />
            새 동선 받기
          </button>
        )}
      </div>
    </div>
  );
}
