// 비밀번호 정책 6 조건 — v3.3 정책 그대로 React로

export type PolicyKey =
  | 'min_length'
  | 'uppercase'
  | 'lowercase'
  | 'number'
  | 'special'
  | 'no_repeat';

export interface PolicyRule {
  key: PolicyKey;
  test: (s: string) => boolean;
}

export const POLICY_RULES: PolicyRule[] = [
  { key: 'min_length', test: (s) => s.length >= 8 },
  { key: 'uppercase', test: (s) => /[A-Z]/.test(s) },
  { key: 'lowercase', test: (s) => /[a-z]/.test(s) },
  { key: 'number', test: (s) => /[0-9]/.test(s) },
  { key: 'special', test: (s) => /[^A-Za-z0-9]/.test(s) },
  { key: 'no_repeat', test: (s) => !/(.)\1\1/.test(s) },
];

export interface PolicyResult {
  passed: PolicyKey[];
  allValid: boolean;
}

export function evaluatePolicy(password: string): PolicyResult {
  const passed = POLICY_RULES.filter((r) => r.test(password)).map((r) => r.key);
  return {
    passed,
    allValid: passed.length === POLICY_RULES.length,
  };
}
