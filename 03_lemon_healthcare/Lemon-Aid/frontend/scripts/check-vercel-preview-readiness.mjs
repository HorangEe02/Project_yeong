import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const repoRoot = path.resolve(frontendRoot, '..');
const envFiles = [
  path.join(repoRoot, '.env'),
  path.join(repoRoot, 'backend/.env'),
  path.join(frontendRoot, '.env.local'),
  path.join(frontendRoot, '.vercel/.env.preview.local'),
];

const requiredPreviewKeys = [
  'LEMON_API_BASE_URL',
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
];

let failures = 0;

/**
 * Prints a sanitized readiness summary for real Vercel Preview testing.
 */
function main() {
  const envByFile = new Map();
  for (const filePath of envFiles) {
    envByFile.set(filePath, existsSync(filePath) ? readEnvFile(filePath) : {});
  }

  const previewEnv = envByFile.get(path.join(frontendRoot, '.vercel/.env.preview.local')) || {};
  const localFrontendEnv = envByFile.get(path.join(frontendRoot, '.env.local')) || {};
  const rootEnv = envByFile.get(path.join(repoRoot, '.env')) || {};

  console.log('Vercel Preview readiness audit');
  console.log('No env values are printed.');

  checkPreviewEnv(previewEnv);
  checkCandidateSources(rootEnv, localFrontendEnv);
  checkBackendCandidate(previewEnv, localFrontendEnv, rootEnv);
  checkSupabaseCandidate(previewEnv, localFrontendEnv, rootEnv);
  finish();
}

/**
 * Parses a simple env file.
 *
 * Args:
 *   filePath: Env file path.
 *
 * Returns:
 *   Parsed key-value record.
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
 * Removes one layer of wrapping quotes.
 *
 * Args:
 *   value: Raw env value.
 *
 * Returns:
 *   Unquoted env value.
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
 * Checks the pulled Vercel Preview env file.
 *
 * Args:
 *   previewEnv: Parsed Preview env.
 */
function checkPreviewEnv(previewEnv) {
  for (const key of requiredPreviewKeys) {
    record(`preview ${key}`, Boolean(previewEnv[key]), previewEnv[key] ? 'present' : 'missing');
  }
  if (previewEnv.LEMON_API_BASE_URL) {
    validateBackendUrl(previewEnv.LEMON_API_BASE_URL, 'preview LEMON_API_BASE_URL');
  }
  if (previewEnv.NEXT_PUBLIC_SUPABASE_URL) {
    validateSupabaseProjectUrl(previewEnv.NEXT_PUBLIC_SUPABASE_URL, 'preview NEXT_PUBLIC_SUPABASE_URL');
  }
  if (previewEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
    validatePublishableKey(
      previewEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
      'preview NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
    );
  }
}

/**
 * Reports whether useful source env fragments exist locally.
 *
 * Args:
 *   rootEnv: Root env values.
 *   localFrontendEnv: Frontend local env values.
 */
function checkCandidateSources(rootEnv, localFrontendEnv) {
  record('candidate root SUPABASE_URL', Boolean(rootEnv.SUPABASE_URL), presentOrMissing(rootEnv.SUPABASE_URL));
  validateSupabaseProjectUrl(rootEnv.SUPABASE_URL, 'candidate root SUPABASE_URL');
  validateConvertibleSupabaseRestUrl(rootEnv.SUPABASE_URL, 'candidate root SUPABASE_URL');

  const rootServerKeyName = 'SUPABASE_' + 'SECRET_KEY';
  const rootServerKeyRole = classifySupabaseKey(rootEnv[rootServerKeyName]);
  if (rootEnv[rootServerKeyName]) {
    record(
      'candidate root Supabase server key',
      rootServerKeyRole !== 'anon',
      `present role=${rootServerKeyRole}; do not use as browser key`,
    );
  }

  pass(
    'candidate frontend LEMON_DEV_GATEWAY_TOKEN',
    localFrontendEnv.LEMON_DEV_GATEWAY_TOKEN
      ? 'present for token-gated development gateway'
      : 'not set; required only when using token-gated development gateway',
  );

  record(
    'candidate frontend NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
    Boolean(localFrontendEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY),
    presentOrMissing(localFrontendEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY),
  );
  validatePublishableKey(
    localFrontendEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    'candidate frontend NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
  );
}

/**
 * Checks whether a usable public backend URL candidate exists.
 *
 * Args:
 *   previewEnv: Parsed Preview env.
 *   localFrontendEnv: Frontend local env values.
 *   rootEnv: Root env values.
 */
function checkBackendCandidate(previewEnv, localFrontendEnv, rootEnv) {
  const candidates = [
    previewEnv.LEMON_API_BASE_URL,
    rootEnv.LEMON_API_BASE_URL,
    rootEnv.BACKEND_PUBLIC_URL,
    rootEnv.API_PUBLIC_URL,
    localFrontendEnv.LEMON_API_BASE_URL,
  ].filter(Boolean);
  if (candidates.length === 0) {
    fail('public backend URL candidate', 'missing HTTPS /api/v1 URL reachable from Vercel');
    return;
  }

  if (candidates.some((candidate) => isUsableBackendUrl(candidate))) {
    pass('public backend URL candidate', 'found HTTPS /api/v1 URL');
    return;
  }

  fail('public backend URL candidate', 'no HTTPS public /api/v1 URL found');
}

/**
 * Checks whether usable Supabase Preview pieces exist.
 *
 * Args:
 *   previewEnv: Parsed Preview env.
 *   localFrontendEnv: Frontend local env values.
 *   rootEnv: Root env values.
 */
function checkSupabaseCandidate(previewEnv, localFrontendEnv, rootEnv) {
  const supabaseUrls = [
    previewEnv.NEXT_PUBLIC_SUPABASE_URL,
    rootEnv.NEXT_PUBLIC_SUPABASE_URL,
    rootEnv.SUPABASE_URL,
    localFrontendEnv.NEXT_PUBLIC_SUPABASE_URL,
  ].filter(Boolean);
  const publishableKey =
    previewEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    localFrontendEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    rootEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    rootEnv.SUPABASE_PUBLISHABLE_KEY ||
    rootEnv.SUPABASE_ANON_KEY;

  if (supabaseUrls.length === 0) {
    fail('Supabase URL candidate', 'missing');
  } else if (supabaseUrls.some((candidate) => isUsableSupabaseProjectUrl(candidate))) {
    pass('Supabase URL candidate', 'found HTTPS public project URL');
  } else if (supabaseUrls.some((candidate) => isConvertibleSupabaseRestUrl(candidate))) {
    pass('Supabase URL candidate', 'found HTTPS REST endpoint convertible to project URL');
  } else {
    fail('Supabase URL candidate', 'no HTTPS public project URL found');
  }
  validatePublishableKey(publishableKey, 'Supabase publishable key candidate');
}

/**
 * Validates a backend URL for remote Preview server functions.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 */
function validateBackendUrl(value, label) {
  const parsed = parseUrl(value, label);
  if (!parsed) {
    return;
  }
  requireHttps(parsed, label);
  rejectLoopback(parsed, label);
  if (!parsed.pathname.replace(/\/$/, '').endsWith('/api/v1')) {
    fail(label, 'path must end with /api/v1');
  } else {
    pass(label, 'path ends with /api/v1');
  }
}

/**
 * Validates an HTTPS URL candidate.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 */
function validateHttpsUrl(value, label) {
  if (!value) {
    fail(label, 'missing');
    return;
  }
  const parsed = parseUrl(value, label);
  if (!parsed) {
    return;
  }
  requireHttps(parsed, label);
  rejectLoopback(parsed, label);
}

/**
 * Validates a Supabase project URL candidate.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 */
function validateSupabaseProjectUrl(value, label) {
  if (!value) {
    fail(label, 'missing');
    return;
  }
  const parsed = parseUrl(value, label);
  if (!parsed) {
    return;
  }
  requireHttps(parsed, label);
  rejectLoopback(parsed, label);
  if (parsed.pathname.replace(/\/+$/, '') === '/rest/v1') {
    fail(label, 'must be project URL, not REST endpoint');
  } else {
    pass(label, 'project URL shape');
  }
}

/**
 * Reports whether a Supabase REST endpoint can be converted to a project URL.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 */
function validateConvertibleSupabaseRestUrl(value, label) {
  if (!value) {
    return;
  }

  if (isConvertibleSupabaseRestUrl(value)) {
    pass(label, 'can derive project URL by removing /rest/v1');
  }
}

/**
 * Validates that the key is a publishable browser key candidate.
 *
 * Args:
 *   value: Key value.
 *   label: Sanitized log label.
 */
function validatePublishableKey(value, label) {
  if (!value) {
    fail(label, 'missing');
    return;
  }
  const role = classifySupabaseKey(value);
  if (role && role !== 'anon') {
    fail(label, `must not use server-only key role=${role}`);
    return;
  }
  pass(label, role === 'anon' ? 'JWT anon role' : 'present without server-only marker');
}

/**
 * Returns the JWT role when the key is a decodable Supabase JWT.
 *
 * Args:
 *   value: Supabase key.
 *
 * Returns:
 *   Role string, empty string for non-JWT/undecodable values.
 */
function classifySupabaseKey(value) {
  if (!value) {
    return '';
  }
  if (/service[_-]?role|secret|^sb_secret_/i.test(value)) {
    return 'server-marker';
  }

  const [, payload] = value.split('.');
  if (!payload) {
    return '';
  }

  try {
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    return typeof decoded.role === 'string' ? decoded.role : '';
  } catch {
    return '';
  }
}

/**
 * Parses a URL without printing the value.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 *
 * Returns:
 *   Parsed URL or null.
 */
function parseUrl(value, label) {
  if (!value) {
    fail(label, 'missing');
    return null;
  }
  try {
    return new URL(value);
  } catch {
    fail(label, 'invalid absolute URL');
    return null;
  }
}

/**
 * Requires HTTPS.
 *
 * Args:
 *   parsed: Parsed URL.
 *   label: Sanitized log label.
 */
function requireHttps(parsed, label) {
  if (parsed.protocol !== 'https:') {
    fail(label, 'must use https');
    return;
  }
  pass(label, 'https');
}

/**
 * Rejects local-only hosts.
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
 * Checks whether a backend URL is remote and shaped for the FastAPI base path.
 *
 * Args:
 *   value: URL value.
 *
 * Returns:
 *   True when the URL is usable from Vercel Preview.
 */
function isUsableBackendUrl(value) {
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === 'https:' &&
      !isHostUnavailableFromVercel(parsed.hostname) &&
      parsed.pathname.replace(/\/$/, '').endsWith('/api/v1')
    );
  } catch {
    return false;
  }
}

/**
 * Checks whether a URL is HTTPS and publicly routable.
 *
 * Args:
 *   value: URL value.
 *
 * Returns:
 *   True when the URL is HTTPS and not local/private scoped.
 */
function isUsableHttpsUrl(value) {
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === 'https:' &&
      !isHostUnavailableFromVercel(parsed.hostname)
    );
  } catch {
    return false;
  }
}

/**
 * Checks whether a Supabase URL is HTTPS, public, and shaped as a project URL.
 *
 * Args:
 *   value: URL value.
 *
 * Returns:
 *   True when the URL can be used as `NEXT_PUBLIC_SUPABASE_URL`.
 */
function isUsableSupabaseProjectUrl(value) {
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === 'https:' &&
      !isHostUnavailableFromVercel(parsed.hostname) &&
      parsed.pathname.replace(/\/+$/, '') !== '/rest/v1'
    );
  } catch {
    return false;
  }
}

/**
 * Checks whether a Supabase REST endpoint can be converted to a project URL.
 *
 * Args:
 *   value: URL value.
 *
 * Returns:
 *   True when the URL is HTTPS, public, and ends exactly at `/rest/v1`.
 */
function isConvertibleSupabaseRestUrl(value) {
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === 'https:' &&
      !isHostUnavailableFromVercel(parsed.hostname) &&
      parsed.pathname.replace(/\/+$/, '') === '/rest/v1'
    );
  } catch {
    return false;
  }
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

function presentOrMissing(value) {
  return value ? 'present' : 'missing';
}

function finish() {
  if (failures > 0) {
    console.log(`Vercel Preview readiness audit failed: ${failures} issue(s).`);
    process.exitCode = 1;
    return;
  }
  console.log('Vercel Preview readiness audit passed.');
}

main();
