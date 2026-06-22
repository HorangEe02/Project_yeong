import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const envFile = process.env.LEMON_VERCEL_ENV_FILE
  ? path.resolve(process.env.LEMON_VERCEL_ENV_FILE)
  : path.join(frontendRoot, '.vercel/.env.preview.local');
const localEnvFile = path.join(frontendRoot, '.env.local');

const requiredKeys = [
  'LEMON_API_BASE_URL',
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
];

const optionalKeys = ['NEXT_PUBLIC_LEMON_WEB_API_BASE_URL', 'LEMON_DEV_GATEWAY_TOKEN'];

let failures = 0;

/**
 * Verifies Vercel Preview env readiness without printing secret values.
 */
function main() {
  if (!existsSync(envFile)) {
    fail('env file', `missing: ${safePath(envFile)}`);
    reportLocalOnlyKeys({});
    finish();
    return;
  }

  const env = readEnvFile(envFile);
  console.log(`Vercel Preview env file: ${safePath(envFile)}`);

  for (const key of requiredKeys) {
    record(`required ${key}`, Boolean(env[key]), env[key] ? 'present' : 'missing');
  }

  for (const key of optionalKeys) {
    record(`optional ${key}`, true, env[key] ? 'present' : 'using app default');
  }

  validateHttpsUrl(env.LEMON_API_BASE_URL, 'LEMON_API_BASE_URL', {
    requireApiV1Suffix: true,
  });
  validateSupabaseProjectUrl(env.NEXT_PUBLIC_SUPABASE_URL, 'NEXT_PUBLIC_SUPABASE_URL', {
    requireApiV1Suffix: false,
  });
  validatePublishableKey(env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);

  reportLocalOnlyKeys(env);
  finish();
}

/**
 * Parses a simple env file.
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
 * Removes wrapping quotes from an env value.
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
 * Validates a deployment URL without printing it.
 *
 * Args:
 *   value: Env value.
 *   key: Env key name.
 *   options: Validation options.
 */
function validateHttpsUrl(value, key, options) {
  if (!value) {
    return;
  }

  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(`${key} URL`, 'invalid absolute URL');
    return;
  }

  if (parsed.protocol !== 'https:') {
    fail(`${key} URL`, 'must use https for Vercel Preview');
  } else {
    pass(`${key} URL`, 'https');
  }

  if (isHostUnavailableFromVercel(parsed.hostname)) {
    fail(`${key} URL`, 'must not point to local or private host');
  } else {
    pass(`${key} host`, 'publicly routable');
  }

  if (options.requireApiV1Suffix && !parsed.pathname.replace(/\/$/, '').endsWith('/api/v1')) {
    fail(`${key} path`, 'must end with /api/v1');
  } else if (options.requireApiV1Suffix) {
    pass(`${key} path`, 'ends with /api/v1');
  }
}

/**
 * Validates a Supabase project URL without printing it.
 *
 * Args:
 *   value: Env value.
 *   key: Env key name.
 */
function validateSupabaseProjectUrl(value, key) {
  if (!value) {
    return;
  }

  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(`${key} URL`, 'invalid absolute URL');
    return;
  }

  if (parsed.protocol !== 'https:') {
    fail(`${key} URL`, 'must use https for Vercel Preview');
  } else {
    pass(`${key} URL`, 'https');
  }

  if (isHostUnavailableFromVercel(parsed.hostname)) {
    fail(`${key} URL`, 'must not point to local or private host');
  } else {
    pass(`${key} host`, 'publicly routable');
  }

  if (parsed.pathname.replace(/\/+$/, '') === '/rest/v1') {
    fail(`${key} path`, 'must be project URL, not REST endpoint');
  } else {
    pass(`${key} path`, 'project URL shape');
  }
}

/**
 * Validates that the browser key is not accidentally a server-only key.
 *
 * Args:
 *   value: Env value.
 */
function validatePublishableKey(value) {
  if (!value) {
    return;
  }

  if (isLikelyServerOnlySupabaseKey(value)) {
    fail('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'must not be a service-role or secret key');
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
    console.log(`Vercel Preview env check failed: ${failures} issue(s).`);
    printPreviewEnvNextSteps();
    process.exitCode = 1;
    return;
  }
  console.log('Vercel Preview env check passed.');
}

function safePath(filePath) {
  return path.relative(frontendRoot, filePath) || '.';
}

/**
 * Reports keys that exist locally but are still missing from Vercel Preview.
 *
 * Args:
 *   previewEnv: Parsed Vercel Preview env values.
 */
function reportLocalOnlyKeys(previewEnv) {
  if (!existsSync(localEnvFile)) {
    return;
  }

  const localEnv = readEnvFile(localEnvFile);
  const localOnlyKeys = requiredKeys.filter((key) => localEnv[key] && !previewEnv[key]);
  if (localOnlyKeys.length === 0) {
    return;
  }

  console.log(
    `[INFO] ${safePath(localEnvFile)} has local-only key(s) not present in Preview: ${localOnlyKeys.join(
      ', ',
    )}`,
  );
}

/**
 * Prints sanitized remediation commands for Preview env configuration.
 */
function printPreviewEnvNextSteps() {
  console.log('Next steps without printing secret values:');
  console.log('  vercel env add LEMON_API_BASE_URL preview');
  console.log('  vercel env add NEXT_PUBLIC_SUPABASE_URL preview');
  console.log('  vercel env add NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY preview');
  console.log('  vercel pull --environment=preview --yes');
  console.log('  npm run vercel:check-env');
  console.log('Use a Supabase publishable/anon key only. Do not use a service-role or secret key.');
}

main();
