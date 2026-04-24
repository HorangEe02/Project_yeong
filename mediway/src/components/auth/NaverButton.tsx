interface NaverButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export function NaverButton({ onClick, disabled }: NaverButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{ backgroundColor: '#03C75A' }}
      className="flex w-full items-center justify-center gap-2.5 rounded-lg px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
        <path d="M14.55 12.87L9.31 5H4.5v14h4.95v-7.87L14.69 19H19.5V5h-4.95v7.87z" />
      </svg>
      네이버로 계속하기
    </button>
  );
}
