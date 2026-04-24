import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';

interface Props {
  onArrival: () => void;
}

export function ArrivalButton({ onArrival }: Props) {
  const [isConfirming, setIsConfirming] = useState(false);

  const handleClick = () => {
    if (!isConfirming) {
      setIsConfirming(true);
      return;
    }
    onArrival();
    setIsConfirming(false);
  };

  const handleCancel = () => setIsConfirming(false);

  if (isConfirming) {
    return (
      <div className="flex gap-3">
        <button
          onClick={handleCancel}
          className="flex-1 rounded-xl bg-surface-container-high py-4 text-sm font-semibold text-on-surface-variant transition-colors hover:bg-surface-container"
        >
          아직이에요
        </button>
        <button
          onClick={handleClick}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-green-500 py-4 text-sm font-bold text-white shadow-lg shadow-green-500/30 transition-transform active:scale-[0.97]"
        >
          <CheckCircle2 className="h-5 w-5" />
          네, 도착했어요!
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleClick}
      className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-primary-container py-4 text-base font-bold text-white shadow-ambient-lg transition-transform active:scale-[0.97]"
    >
      <CheckCircle2 className="h-5 w-5" />
      도착했습니다
    </button>
  );
}
