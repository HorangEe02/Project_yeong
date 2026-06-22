import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const sourceEnvFile = process.env.LEMON_VERCEL_SYNC_SOURCE
  ? path.resolve(process.env.LEMON_VERCEL_SYNC_SOURCE)
  : path.join(frontendRoot, '.env.local');

const requiredKeys = [
  'LEMON_API_BASE_URL',
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
];
const optionalKeys = ['NEXT_PUBLIC_LEMON_WEB_API_BASE_URL'];

let failures = 0;

/**
 * Validates whether local env values are safe candidates for Vercel Preview.
 */
function main() {
  if (!existsSync(sourceEnvFile)) {
    fail('source env file', `missing: ${safePath(sourceEnvFile)}`);
    finish();
    return;
  }

  const env = readEnvFile(sourceEnvFile);
  const keysToSync = [...requiredKeys, ...optionalKeys.filter((key) => Boolean(env[key]))];

  console.log(`Source env file: ${safePath(sourceEnvFile)}`);
  console.log('Mode: dry-run only');

  for (const key of requiredKeys) {
    record(`required ${key}`, Boolean(env[key]), env[key] ? 'present' : 'missing');
  }

  for (const key of optionalKeys) {
    record(`optional ${key}`, true, env[key] ? 'present; candidate' : 'not set; skip');
  }

  validateBackendBaseUrl(env.LEMON_API_BASE_URL);
  validateSupabaseUrl(env.NEXT_PUBLIC_SUPABASE_URL);
  validatePublishableKey(env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  validateWebProxyBase(env.NEXT_PUBLIC_LEMON_WEB_API_BASE_URL);

  if (failures === 0) {
    console.log(`Dry-run passed. Candidate key(s): ${keysToSync.join(', ')}`);
    console.log('No values were printed or sent to Vercel.');
    console.log('Use `vercel env add <KEY> preview` manually after explicit review.');
  }

  finish();
}

/**
 * Parses a simple dotenv file without expanding variables.
 *
 * Args:
 *   filePath: Env file path.
 *
 * Returns:
 *   Key-value record.
 */
function readEnvFile(filePath) {
  const env = {};
  const text = readFileSync(filePath, 'utf8');
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }
    const separator = trimmed.indexOf('=');
    if (separator <= 0) {
      continue;
    }
    env[trimmed.slice(0, separator).trim()] = unquote(trimmed.slice(separator + 1).trim());
  }
  return env;
}

/**
 * Removes one layer of wrapping quotes from an env value.
 *
 * Args:
 *   value: Raw value.
 *
 * Returns:
 *   Unquoted value.
 */
function unquote(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

/**
 * Validates the backend URL for Vercel Preview.
 *
 * Args:
 *   value: Backend API base URL.
 */
function validateBackendBaseUrl(value) {
  if (!value) {
    return;
  }

  const parsed = parseUrl(value, 'LEMON_API_BASE_URL URL');
  if (!parsed) {
    return;
  }

  requireHttps(parsed, 'LEMON_API_BASE_URL URL');
  rejectLoopback(parsed, 'LEMON_API_BASE_URL host');
  if (!parsed.pathname.replace(/\/$/, '').endsWith('/api/v1')) {
    fail('LEMON_API_BASE_URL path', 'must end with /api/v1');
  } else {
    pass('LEMON_API_BASE_URL path', 'ends with /api/v1');
  }
}

/**
 * Validates the Supabase project URL for browser-safe runtime checks.
 *
 * Args:
 *   value: Supabase URL.
 */
function validateSupabaseUrl(value) {
  if (!value) {
    return;
  }

  const parsed = parseUrl(value, 'NEXT_PUBLIC_SUPABASE_URL URL');
  if (!parsed) {
    return;
  }

  requireHttps(parsed, 'NEXT_PUBLIC_SUPABASE_URL URL');
  rejectLoopback(parsed, 'NEXT_PUBLIC_SUPABASE_URL host');
  const normalizedPath = parsed.pathname.replace(/\/+$/, '');
  if (normalizedPath === '/rest/v1') {
    fail('NEXT_PUBLIC_SUPABASE_URL path', 'must be project URL, not REST endpoint');
    return;
  }
  pass('NEXT_PUBLIC_SUPABASE_URL path', 'project URL shape');
}

/**
 * Validates the same-origin web proxy base when it is explicitly provided.
 *
 * Args:
 *   value: Web proxy base path.
 */
function validateWebProxyBase(value) {
  if (!value) {
    return;
  }

  if (!value.startsWith('/')) {
    fail('NEXT_PUBLIC_LEMON_WEB_API_BASE_URL', 'must be a same-origin path');
    return;
  }

  pass('NEXT_PUBLIC_LEMON_WEB_API_BASE_URL', 'same-origin path');
}

/**
 * Validates that a Supabase browser key is not a server-only credential.
 *
 * Args:
 *   value: Supabase API key.
 */
function validatePublishableKey(value) {
  if (!value) {
    return;
  }

  if (isLikelyServerOnlySupabaseKey(value)) {
    fail('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'must not be service-role or secret material');
    return;
  }

  pass('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'present without service-role marker');
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
function isLikelyServerOnlySupabaseKey(key) {
  if (/service[_-]?role|secret|^sb_secret_/i.test(key)) {
    return true;
  }

  const [, payload] = key.split('.');
  if (!payload) {
    return false;
  }

  try {
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    return typeof decoded.role === 'string' && decoded.role !== 'anon';
  } catch {
    return false;
  }
}

/**
 * Parses a URL while keeping the actual value out of logs.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 *
 * Returns:
 *   Parsed URL or null when invalid.
 */
function parseUrl(value, label) {
  try {
    return new URL(value);
  } catch {
    fail(label, 'invalid absolute URL');
    return null;
  }
}

/**
 * Requires HTTPS for a parsed URL.
 *
 * Args:
 *   parsed: Parsed URL.
 *   label: Sanitized log label.
 */
function requireHttps(parsed, label) {
  if (parsed.protocol !== 'https:') {
    fail(label, 'must use https for Vercel Preview');
    return;
  }
  pass(label, 'https');
}

/**
 * Rejects local-only hosts for Vercel Preview.
 *
 * Args:
 *   parsed: Parsed URL.
 *   label: Sanitized log label.
 */
function rejectLoopback(parsed, label) {
  if (isHostUnavailableFromVercel(parsed.hostname)) {
    fail(label, 'must not point to local or private host');
    return;
  }
  pass(label, 'publicly routable');
}

/**
 * Detects hosts that Vercel server functions cannot use as public endpoints.
 *
 * Args:
 *   hostname: Parsed URL hostname.
 *
 * Returns:
 *   True when the hostname is loopback or private-network scoped.
 */
function isHostUnavailableFromVercel(hostname) {
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

function record(name, ok, detail) {
  if (ok) {
    pass(name, detail);
  } else {
    fail(name, detail);
  }
}

function pass(name, detail) {
  console.log(`[PASS] ${name}: ${detail}`);
}

function fail(name, detail) {
  failures += 1;
  console.log(`[FAIL] ${name}: ${detail}`);
}

function finish() {
  if (failures > 0) {
    console.error(`Vercel Preview sync source check failed: ${failures} issue(s).`);
    console.error('No env values were printed or sent to Vercel.');
    process.exitCode = 1;
    return;
  }
  console.log('Vercel Preview sync source check passed.');
}

function safePath(filePath) {
  return path.relative(frontendRoot, filePath) || '.';
}

main();
