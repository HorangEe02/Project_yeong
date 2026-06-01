const DEFAULT_API_BASE_URL = '/api';

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

export function normalizeApiBaseUrl(raw?: string): string {
  const value = trimTrailingSlash((raw ?? '').trim());
  if (!value) return DEFAULT_API_BASE_URL;
  if (value.endsWith('/api')) return value;
  return `${value}/api`;
}

function configuredApiBaseUrl(): string {
  const canonical = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (canonical) return canonical;

  const legacy = import.meta.env.DEV
    ? (import.meta.env.VITE_API_URL as string | undefined)?.trim()
    : '';
  return legacy || DEFAULT_API_BASE_URL;
}

export const API_BASE_URL = normalizeApiBaseUrl(configuredApiBaseUrl());

export function apiUrl(path = ''): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (normalizedPath === '/api') return API_BASE_URL;
  if (normalizedPath.startsWith('/api/')) {
    return `${API_BASE_URL}${normalizedPath.slice('/api'.length)}`;
  }
  return `${API_BASE_URL}${normalizedPath}`;
}
