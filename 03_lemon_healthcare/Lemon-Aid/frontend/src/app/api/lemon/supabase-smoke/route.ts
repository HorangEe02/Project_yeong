import { normalizeSupabaseProjectUrl } from '@/lib/supabase-url';

export const runtime = 'nodejs';

/**
 * Verifies the Vercel runtime can reach Supabase with browser-safe env values.
 *
 * Returns:
 *   Sanitized Supabase readiness response without URL or key values.
 */
export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !key) {
    return Response.json(
      {
        ok: false,
        code: 'supabase_not_configured',
        message: 'Supabase URL or publishable key is not configured.',
      },
      { status: 503 },
    );
  }

  if (isLikelyServerOnlySupabaseKey(key)) {
    return Response.json(
      {
        ok: false,
        code: 'supabase_public_key_invalid',
        message: 'Supabase publishable key must not be a service-role or secret key.',
      },
      { status: 503 },
    );
  }

  const normalizedUrl = normalizeSupabaseProjectUrl(url);
  if (!normalizedUrl) {
    return Response.json(
      {
        ok: false,
        code: 'supabase_url_invalid',
        message: 'Supabase URL is not a valid absolute URL.',
      },
      { status: 503 },
    );
  }

  const parsedUrl = new URL(normalizedUrl);

  if (process.env.VERCEL && parsedUrl.protocol !== 'https:') {
    return Response.json(
      {
        ok: false,
        code: 'supabase_url_insecure',
        message: 'Supabase URL must use HTTPS on Vercel.',
      },
      { status: 503 },
    );
  }

  try {
    const response = await fetch(`${normalizedUrl}/rest/v1/`, {
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
      },
      signal: AbortSignal.timeout(10000),
    });
    return Response.json(
      {
        ok: response.ok,
        status: response.status,
      },
      { status: response.ok ? 200 : 502 },
    );
  } catch {
    return Response.json(
      {
        ok: false,
        code: 'supabase_unreachable',
        message: 'Supabase REST smoke request failed.',
      },
      { status: 502 },
    );
  }
}

/**
 * Detects Supabase keys that should never be exposed to browser-facing code.
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
