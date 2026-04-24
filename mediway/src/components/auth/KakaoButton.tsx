interface KakaoButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export function KakaoButton({ onClick, disabled }: KakaoButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{ backgroundColor: '#FEE500' }}
      className="flex w-full items-center justify-center gap-2.5 rounded-lg px-4 py-2.5 text-sm font-medium text-[#191919] disabled:cursor-not-allowed disabled:opacity-50"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
        <path d="M12 3C6.48 3 2 6.48 2 10.79c0 2.73 1.79 5.13 4.5 6.55L5.38 21l4.27-2.42c.77.1 1.56.16 2.35.16 5.52 0 10-3.48 10-7.95S17.52 3 12 3z" />
      </svg>
      카카오로 계속하기
    </button>
  );
}
