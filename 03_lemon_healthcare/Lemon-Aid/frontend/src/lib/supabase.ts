import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { normalizeSupabaseProjectUrl } from './supabase-url';

let browserClient: SupabaseClient | null = null;

/**
 * Lazily creates a browser Supabase client from publishable env variables.
 *
 * Returns:
 *   Supabase client when public URL/key are configured, otherwise null.
 */
export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (browserClient) {
    return browserClient;
  }
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const normalizedUrl = url ? normalizeSupabaseProjectUrl(url) : null;
  if (!normalizedUrl || !key) {
    return null;
  }
  browserClient = createClient(normalizedUrl, key, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  });
  return browserClient;
}

/**
 * Performs a safe Supabase Auth session smoke check without schema writes.
 *
 * Returns:
 *   User-facing status text for the connection panel.
 */
export async function runSupabaseSmoke(): Promise<string> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const normalizedUrl = url ? normalizeSupabaseProjectUrl(url) : null;
  const client = getSupabaseBrowserClient();
  if (!client || !normalizedUrl || !key) {
    return 'Supabase URL과 publishable key가 아직 설정되지 않았습니다.';
  }
  const { data, error } = await client.auth.getSession();
  if (error) {
    return `Supabase Auth 연결 오류: ${error.message}`;
  }

  const restResponse = await fetch(`${normalizedUrl}/rest/v1/`, {
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
    },
  });
  if (!restResponse.ok) {
    return `Supabase REST 연결 오류: HTTP ${restResponse.status}`;
  }

  return data.session
    ? 'Supabase Auth 세션과 REST 연결이 확인되었습니다.'
    : 'Supabase REST 연결은 가능하며 현재 로그인 세션은 없습니다.';
}
