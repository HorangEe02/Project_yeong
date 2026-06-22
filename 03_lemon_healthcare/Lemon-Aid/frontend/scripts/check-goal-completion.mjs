import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

const requiredFiles = [
  'package.json',
  'vercel.json',
  'src/app/page.tsx',
  'src/app/layout.tsx',
  'src/components/lemon-web-app.tsx',
  'src/lib/api.ts',
  'src/lib/lemon-backend.ts',
  'src/lib/supabase.ts',
  'src/app/api/lemon/ready/route.ts',
  'src/app/api/lemon/deployment-status/route.ts',
  'src/app/api/lemon/supabase-smoke/route.ts',
  'src/app/api/lemon/supplements/analyze/route.ts',
  'src/app/api/lemon/meals/analyze-image/route.ts',
  'scripts/smoke-web.mjs',
  'scripts/check-vercel-preview-env.mjs',
  'scripts/check-vercel-output-safety.mjs',
];

const requiredPreviewEnvKeys = [
  'LEMON_API_BASE_URL',
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
];

let failures = 0;

/**
 * Audits whether the current workspace proves the full mobile-web goal.
 */
function main() {
  console.log('Lemon AID mobile-web goal audit');
  console.log('No env values are printed.');

  checkRequiredFiles();
  checkReactMobileUi();
  checkBackendProxy();
  checkSupabaseRuntime();
  checkVercelProjectLink();
  checkVercelOutput();
  checkPreviewEnv();
  checkRemoteSmokeTarget();

  finish();
}

/**
 * Ensures core frontend implementation and verification files exist.
 */
function checkRequiredFiles() {
  for (const filePath of requiredFiles) {
    record(`file ${filePath}`, existsSync(resolve(filePath)), existsSync(resolve(filePath)) ? 'present' : 'missing');
  }
}

/**
 * Checks source markers for the Flutter-aligned camera flow.
 */
function checkReactMobileUi() {
  const source = readText('src/components/lemon-web-app.tsx');
  if (!source) {
    return;
  }
  record('React camera default tab', source.includes("useState<TabKey>('camera')"), 'camera tab is initial screen');
  record('browser camera API', source.includes('getUserMedia'), 'getUserMedia camera preview path');
  record('Flutter-like camera shell', source.includes('camera-capture') && source.includes('shutter-button'), 'capture shell markers');
  record('supplement and meal modes', source.includes('영양제') && source.includes('식단'), 'mode labels present');
}

/**
 * Checks source markers for OCR/YOLO proxy integration.
 */
function checkBackendProxy() {
  const backend = readText('src/lib/lemon-backend.ts');
  const supplement = readText('src/app/api/lemon/supplements/analyze/route.ts');
  const meal = readText('src/app/api/lemon/meals/analyze-image/route.ts');
  if (!backend || !supplement || !meal) {
    return;
  }
  record('backend base env', backend.includes('LEMON_API_BASE_URL'), 'server-side backend base env');
  record('Vercel backend URL guard', backend.includes('must use HTTPS') && backend.includes('/api/v1'), 'HTTPS and /api/v1 guard');
  record('supplement OCR proxy', supplement.includes('/supplements/analyze'), 'OCR upload proxy path');
  record('meal YOLO proxy', meal.includes('/meals/analyze-image'), 'YOLO upload proxy path');
}

/**
 * Checks source markers for Supabase runtime smoke coverage.
 */
function checkSupabaseRuntime() {
  const supabase = readText('src/lib/supabase.ts');
  const route = readText('src/app/api/lemon/supabase-smoke/route.ts');
  if (!supabase || !route) {
    return;
  }
  record('Supabase client setup', supabase.includes('createClient'), 'supabase-js client is initialized');
  record('Supabase URL normalization', supabase.includes('normalizeSupabaseProjectUrl'), 'project URL normalization is used');
  record(
    'Supabase smoke route',
    route.includes('/rest/v1/') && route.includes('supabase_unreachable'),
    'runtime REST smoke route present',
  );
}

/**
 * Checks whether this frontend is linked to a Vercel project.
 */
function checkVercelProjectLink() {
  const projectPath = resolve('.vercel/project.json');
  if (!existsSync(projectPath)) {
    fail('Vercel project link', 'missing .vercel/project.json');
    return;
  }

  try {
    const project = JSON.parse(readFileSync(projectPath, 'utf8'));
    record('Vercel project id', Boolean(project.projectId), project.projectId ? 'present' : 'missing');
    record('Vercel org id', Boolean(project.orgId), project.orgId ? 'present' : 'missing');
    record('Vercel framework', project.settings?.framework === 'nextjs', project.settings?.framework ?? 'unknown');
  } catch {
    fail('Vercel project link', 'invalid project.json');
  }
}

/**
 * Checks whether a Vercel build output exists for prebuilt deploy.
 */
function checkVercelOutput() {
  record('Vercel output config', existsSync(resolve('.vercel/output/config.json')), '.vercel/output/config.json');
}

/**
 * Checks pulled Preview env without printing values.
 */
function checkPreviewEnv() {
  const envPath = resolve('.vercel/.env.preview.local');
  if (!existsSync(envPath)) {
    fail('Preview env file', 'missing .vercel/.env.preview.local');
    return;
  }

  const env = readEnvFile(envPath);
  for (const key of requiredPreviewEnvKeys) {
    record(`Preview env ${key}`, Boolean(env[key]), env[key] ? 'present' : 'missing');
  }

  if (env.LEMON_API_BASE_URL) {
    checkBackendUrl(env.LEMON_API_BASE_URL, 'Preview backend URL');
  }
  if (env.NEXT_PUBLIC_SUPABASE_URL) {
    checkSupabaseUrl(env.NEXT_PUBLIC_SUPABASE_URL, 'Preview Supabase URL');
  }
  if (env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
    checkPublishableKey(env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, 'Preview Supabase publishable key');
  }
}

/**
 * Checks whether the remote smoke target is configured for actual web verification.
 */
function checkRemoteSmokeTarget() {
  const target = process.env.LEMON_WEB_SMOKE_URL;
  if (!target) {
    fail('remote smoke target', 'LEMON_WEB_SMOKE_URL is required to prove Vercel web verification');
    return;
  }

  const parsed = parseUrl(target, 'remote smoke target');
  if (!parsed) {
    return;
  }
  record('remote smoke target HTTPS', parsed.protocol === 'https:', parsed.protocol === 'https:' ? 'https' : 'not https');
  record(
    'remote smoke target public host',
    !isHostUnavailableFromVercel(parsed.hostname),
    !isHostUnavailableFromVercel(parsed.hostname) ? 'publicly routable' : 'local or private host',
  );
}

/**
 * Parses a simple env file.
 *
 * Args:
 *   filePath: Env file path.
 *
 * Returns:
 *   Env key-value record.
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
 * Checks whether a backend URL is suitable for Vercel server functions.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 */
function checkBackendUrl(value, label) {
  const parsed = parseUrl(value, label);
  if (!parsed) {
    return;
  }
  record(`${label} HTTPS`, parsed.protocol === 'https:', parsed.protocol === 'https:' ? 'https' : 'not https');
  record(
    `${label} public host`,
    !isHostUnavailableFromVercel(parsed.hostname),
    !isHostUnavailableFromVercel(parsed.hostname) ? 'publicly routable' : 'local or private host',
  );
  record(
    `${label} /api/v1`,
    parsed.pathname.replace(/\/$/, '').endsWith('/api/v1'),
    parsed.pathname.replace(/\/$/, '').endsWith('/api/v1') ? 'ends with /api/v1' : 'missing /api/v1',
  );
}

/**
 * Checks whether a Supabase URL is browser-safe project URL shaped.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 */
function checkSupabaseUrl(value, label) {
  const parsed = parseUrl(value, label);
  if (!parsed) {
    return;
  }
  record(`${label} HTTPS`, parsed.protocol === 'https:', parsed.protocol === 'https:' ? 'https' : 'not https');
  record(
    `${label} public host`,
    !isHostUnavailableFromVercel(parsed.hostname),
    !isHostUnavailableFromVercel(parsed.hostname) ? 'publicly routable' : 'local or private host',
  );
  record(
    `${label} project URL`,
    parsed.pathname.replace(/\/+$/, '') !== '/rest/v1',
    parsed.pathname.replace(/\/+$/, '') !== '/rest/v1' ? 'project URL shape' : 'REST endpoint',
  );
}

/**
 * Checks that a browser-facing Supabase key is not server-only material.
 *
 * Args:
 *   value: Supabase key value.
 *   label: Sanitized log label.
 */
function checkPublishableKey(value, label) {
  const role = classifySupabaseKey(value);
  record(label, !role || role === 'anon', role === 'anon' ? 'anon role' : 'no server-only marker');
}

/**
 * Returns Supabase JWT role or a server marker classification.
 *
 * Args:
 *   value: Supabase key candidate.
 *
 * Returns:
 *   Role label or empty string.
 */
function classifySupabaseKey(value) {
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
 * Parses a URL without logging its value.
 *
 * Args:
 *   value: URL value.
 *   label: Sanitized log label.
 *
 * Returns:
 *   Parsed URL or null.
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
 * Detects hosts that Vercel server functions cannot use as public endpoints.
 *
 * Args:
 *   hostname: Parsed hostname.
 *
 * Returns:
 *   True when the host is loopback or private-network scoped.
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

function readText(filePath) {
  const fullPath = resolve(filePath);
  return existsSync(fullPath) ? readFileSync(fullPath, 'utf8') : '';
}

function resolve(filePath) {
  return path.join(frontendRoot, filePath);
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
    console.log(`Goal audit failed: ${failures} issue(s).`);
    process.exitCode = 1;
    return;
  }
  console.log('Goal audit passed.');
}

main();
