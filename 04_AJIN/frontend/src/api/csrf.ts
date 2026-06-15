const CSRF_COOKIE_NAME = 'ajin_csrf';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const value = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

export function csrfHeaderFor(method: string): Record<string, string> {
  if (!UNSAFE_METHODS.has(method.toUpperCase())) return {};
  const csrfToken = getCookie(CSRF_COOKIE_NAME);
  return csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {};
}
