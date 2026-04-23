import type { LucideIcon } from 'lucide-react';

interface SeniorTileProps {
  icon: LucideIcon;
  label: string;
  /** 라벨 아래 한 줄 부설명 */
  sub?: string;
  /** 우측 상단 빨간 동그라미 숫자 */
  badge?: number;
  disabled?: boolean;
  onClick?: () => void;
  /** 'href'가 있으면 a로, 없으면 button. 외부 링크·라우팅은 consumer 책임 */
  href?: string;
}

/**
 * 고령자 모드 홈의 큰 정사각형 타일. 시안 PlusUltra SaaS 2/5의 2×2 그리드.
 *
 * - 큰 아이콘 (원형 배경) + 라벨 + 부설명
 * - 선택적 뱃지 (예: 대기 순번)
 * - disabled 상태 (예: 가족 연락 곧 공개)
 */
export function SeniorTile({
  icon: Icon,
  label,
  sub,
  badge,
  disabled,
  onClick,
  href,
}: SeniorTileProps) {
  const content = (
    <>
      <span className="relative inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
        <Icon
          className={`h-7 w-7 ${disabled ? 'text-on-surface-variant' : 'text-primary'}`}
          aria-hidden
        />
        {typeof badge === 'number' && badge > 0 && (
          <span
            aria-label={`알림 ${badge}건`}
            className="absolute -right-1 -top-1 flex h-6 min-w-6 items-center justify-center rounded-full bg-error px-1 text-xs font-semibold text-on-primary"
          >
            {badge}
          </span>
        )}
      </span>
      <span className="mt-3 text-lg font-semibold">{label}</span>
      {sub && (
        <span className="mt-1 text-sm text-on-surface-variant">{sub}</span>
      )}
    </>
  );

  const baseCls =
    'flex flex-col items-center justify-center rounded-2xl border bg-surface-container-lowest p-6 text-center transition-colors';
  const stateCls = disabled
    ? 'cursor-not-allowed border-outline-variant opacity-60'
    : 'border-outline-variant hover:border-primary hover:bg-primary/5';

  if (href && !disabled) {
    return (
      <a href={href} className={`${baseCls} ${stateCls} no-underline`}>
        {content}
      </a>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      className={`${baseCls} ${stateCls}`}
    >
      {content}
    </button>
  );
}
