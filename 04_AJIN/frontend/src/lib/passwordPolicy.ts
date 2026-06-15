// Frontend password policy preview. Backend remains the source of truth.

export type PolicyKey =
  | 'min_length'
  | 'max_bytes'
  | 'not_common'
  | 'not_context';

export interface PolicyRule {
  key: PolicyKey;
  test: (s: string) => boolean;
}

const COMMON_PASSWORD_TOKENS = [
  'admin',
  'admin1234',
  'ajin1234',
  'password',
  'password123',
  'qwerty',
  'welcome',
];

const CONTEXT_TOKENS = ['ajin', 'ajinindustry', 'assistant', 'admin', 'system'];

function simplified(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9가-힣]/g, '');
}

function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

export const POLICY_RULES: PolicyRule[] = [
  { key: 'min_length', test: (s) => s.length >= 12 },
  { key: 'max_bytes', test: (s) => byteLength(s) <= 72 },
  {
    key: 'not_common',
    test: (s) => !COMMON_PASSWORD_TOKENS.some((token) => simplified(s).includes(token)),
  },
  {
    key: 'not_context',
    test: (s) => !CONTEXT_TOKENS.some((token) => simplified(s).includes(token)),
  },
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
