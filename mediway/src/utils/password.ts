export type PasswordStrength = 'too-short' | 'weak' | 'fair' | 'good' | 'strong';

export interface PasswordScore {
  score: number; // 0~4
  strength: PasswordStrength;
  suggestions: string[];
}

const MIN_LENGTH = 8;

/**
 * 의존성 없는 경량 비밀번호 강도 계산.
 * 5단계: too-short / weak / fair / good / strong
 */
export function scorePassword(password: string): PasswordScore {
  if (password.length < MIN_LENGTH) {
    return {
      score: 0,
      strength: 'too-short',
      suggestions: [`${MIN_LENGTH}자 이상이어야 합니다`],
    };
  }

  const suggestions: string[] = [];
  let score = 0;

  // 길이 가중치
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (password.length >= 16) score += 1;

  // 문자 클래스
  const hasLower = /[a-z]/.test(password);
  const hasUpper = /[A-Z]/.test(password);
  const hasDigit = /\d/.test(password);
  const hasSymbol = /[^A-Za-z0-9]/.test(password);
  const classes = [hasLower, hasUpper, hasDigit, hasSymbol].filter(Boolean).length;
  score += classes - 1; // 1클래스면 0점, 4클래스면 +3

  // 반복 패턴 감점
  if (/(.)\1{2,}/.test(password)) {
    score -= 1;
    suggestions.push('같은 문자를 3번 이상 반복하지 마세요');
  }
  if (/(password|qwerty|admin|123456|letmein|welcome)/i.test(password)) {
    score -= 3;
    suggestions.push('흔한 비밀번호는 사용하지 마세요');
  }

  // 제안
  if (!hasUpper) suggestions.push('대문자를 포함하세요');
  if (!hasDigit) suggestions.push('숫자를 포함하세요');
  if (!hasSymbol) suggestions.push('특수문자를 포함하세요');
  if (password.length < 12) suggestions.push('12자 이상이면 더 안전합니다');

  const clamped = Math.max(0, Math.min(4, score));
  const strength: PasswordStrength =
    clamped <= 1 ? 'weak' : clamped === 2 ? 'fair' : clamped === 3 ? 'good' : 'strong';

  return { score: clamped, strength, suggestions };
}

export function strengthLabel(strength: PasswordStrength): string {
  switch (strength) {
    case 'too-short':
      return '너무 짧음';
    case 'weak':
      return '약함';
    case 'fair':
      return '보통';
    case 'good':
      return '양호';
    case 'strong':
      return '강함';
  }
}
