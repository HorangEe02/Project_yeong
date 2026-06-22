import { normalizeSupabaseProjectUrl } from '@/lib/supabase-url';

export const runtime = 'nodejs';

interface CheckStatus {
  ok: boolean;
  code?: string;
}

/**
 * Reports deployment configuration readiness without exposing env values.
 *
 * Returns:
 *   Sanitized Vercel/backend/Supabase readiness metadata.
 */
export async function GET() {
  const backend = checkBackendProxy();
  const supabase = checkSupabaseConfig();
  const runtimeInfo = {
    vercel: Boolean(process.env.VERCEL),
    nodejs: true,
  };

  return Response.json(
    {
      ok: backend.ok && supabase.ok,
      runtime: runtimeInfo,
      backend,
      supabase,
    },
    { status: backend.ok && supabase.ok ? 200 : 503 },
  );
}

/**
 * Checks backend proxy env readiness without returning the backend URL.
 *
 * Returns:
 *   Sanitized backend status.
 */
function checkBackendProxy(): CheckStatus {
  const value = process.env.LEMON_API_BASE_URL || process.env.NEXT_PUBLIC_LEMON_API_BASE_URL;
  if (!value) {
    return { ok: false, code: 'backend_url_missing' };
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return { ok: false, code: 'backend_url_invalid' };
  }

  if (process.env.VERCEL && parsed.protocol !== 'https:') {
    return { ok: false, code: 'backend_url_not_https' };
  }

  if (process.env.VERCEL && isHostUnavailableFromVercel(parsed.hostname)) {
    return { ok: false, code: 'backend_url_not_public' };
  }

  if (!parsed.pathname.replace(/\/$/, '').endsWith('/api/v1')) {
    return { ok: false, code: 'backend_url_missing_api_v1' };
  }

  return { ok: true };
}

/**
 * Checks Supabase env readiness without returning URL or key values.
 *
 * Returns:
 *   Sanitized Supabase status.
 */
function checkSupabaseConfig(): CheckStatus {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    return { ok: false, code: 'supabase_missing' };
  }

  if (isLikelyServerOnlySupabaseKey(key)) {
    return { ok: false, code: 'supabase_key_server_only' };
  }

  const normalizedUrl = normalizeSupabaseProjectUrl(url);
  if (!normalizedUrl) {
    return { ok: false, code: 'supabase_url_invalid' };
  }

  const parsed = new URL(normalizedUrl);

  if (process.env.VERCEL && parsed.protocol !== 'https:') {
    return { ok: false, code: 'supabase_url_not_https' };
  }

  return { ok: true };
}

/**
 * Detects local hosts that cannot work from Vercel Preview.
 *
 * Args:
 *   hostname: Parsed URL hostname.
 *
 * Returns:
 *   True when the hostname is local or private-network scoped.
 */
function isHostUnavailableFromVercel(hostname: string): boolean {
  const normalized = hostname.toLowerCase();
  if (
    normalized === 'localhost' ||
    normalized === '127.0.0.1' ||
    normalized === '0.0.0.0' ||
    normalized === '::1'
  ) {
    return true;
  }

  const ipv4 = normalized.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (!ipv4) {
    return false;
  }

  const first = Number(ipv4[1]);
  const second = Number(ipv4[2]);
  return (
    first === 10 ||
    first === 127 ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168)
  );
}

/**
 * Detects Supabase keys that should never be browser-facing.
 *
 * Args:
 *   key: Supabase API key value.
 *
 * Returns:
 *   True when the key appears to be secret/service-role material.
 */
function isLikelyServerOnlySupabaseKey(key: string): boolean {
  if (/service[_-]?role|secret|^sb_secret_/i.test(key)) {
    return true;
  }

  const [, payload] = key.split('.');
  if (!payload) {
    return false;
  }

  try {
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')) as {
      role?: unknown;
    };
    return typeof decoded.role === 'string' && decoded.role !== 'anon';
  } catch {
    return false;
  }
}
