import { scorePassword, strengthLabel } from '@/utils/password';

const BAR_COLORS = ['bg-red-400', 'bg-orange-400', 'bg-amber-400', 'bg-lime-500', 'bg-green-500'];

interface PasswordStrengthProps {
  password: string;
  showSuggestions?: boolean;
}

export function PasswordStrength({ password, showSuggestions = true }: PasswordStrengthProps) {
  if (!password) return null;

  const { score, strength, suggestions } = scorePassword(password);
  const activeColor = BAR_COLORS[score] ?? BAR_COLORS[0];

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= score ? activeColor : 'bg-surface-container-high'
            }`}
          />
        ))}
        <span
          className={`ml-1 shrink-0 text-[11px] font-medium ${
            strength === 'strong'
              ? 'text-green-600'
              : strength === 'good'
                ? 'text-lime-600'
                : strength === 'fair'
                  ? 'text-amber-600'
                  : 'text-red-500'
          }`}
        >
          {strengthLabel(strength)}
        </span>
      </div>
      {showSuggestions && suggestions.length > 0 && (
        <ul className="flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-on-surface-variant/80">
          {suggestions.slice(0, 3).map((s) => (
            <li key={s}>· {s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
