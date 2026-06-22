/**
 * Normalizes Supabase project URLs for `@supabase/supabase-js` and REST smoke checks.
 *
 * Args:
 *   value: Supabase project URL or REST endpoint URL.
 *
 * Returns:
 *   Project base URL without a trailing `/rest/v1` path, or null when invalid.
 */
export function normalizeSupabaseProjectUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    const normalizedPath = parsed.pathname.replace(/\/+$/, '');
    if (normalizedPath === '/rest/v1') {
      parsed.pathname = '';
    }
    return parsed.toString().replace(/\/$/, '');
  } catch {
    return null;
  }
}
