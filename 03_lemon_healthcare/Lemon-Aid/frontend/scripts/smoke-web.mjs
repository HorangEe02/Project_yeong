import { existsSync, readFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const repoRoot = path.resolve(frontendRoot, '..');

loadEnvFile(path.join(frontendRoot, '.env.local'));

const baseUrl = trimTrailingSlash(process.env.LEMON_WEB_SMOKE_URL ?? 'http://127.0.0.1:3000');
const supplementImagePath = process.env.LEMON_WEB_SMOKE_SUPPLEMENT_IMAGE
  ? path.resolve(process.env.LEMON_WEB_SMOKE_SUPPLEMENT_IMAGE)
  : path.join(repoRoot, 'mobile/assets/mock/supplement-label.png');
const mealImagePath = process.env.LEMON_WEB_SMOKE_MEAL_IMAGE
  ? path.resolve(process.env.LEMON_WEB_SMOKE_MEAL_IMAGE)
  : path.join(
      repoRoot,
      'mobile/uiux/sample/82D3D731-CFA8-4987-BD8D-A74D02811B3F_4_5005_c.jpeg',
    );

let failures = 0;

/**
 * Runs the mobile web smoke suite against an already running Next.js server.
 *
 * Returns:
 *   Promise that resolves after all checks have been printed.
 */
async function main() {
  console.log(`Lemon AID web smoke target: ${baseUrl}`);
  if (!checkSmokeTarget()) {
    finish();
    return;
  }
  await runSmokeCheck('camera shell', checkHomeShell);
  await runSmokeCheck('deployment status', checkDeploymentStatus);
  await runSmokeCheck('backend readiness proxy', checkReadinessProxy);
  await runSmokeCheck('supabase runtime smoke', checkSupabaseProxy);
  if (process.env.LEMON_WEB_SMOKE_UPLOADS !== '0') {
    await runSmokeCheck('supplement OCR upload', checkSupplementUpload);
    await runSmokeCheck('meal YOLO upload', checkMealUpload);
  }

  finish();
}

/**
 * Runs one smoke check and reports transport failures without dumping stack traces.
 *
 * Args:
 *   name: Smoke check label.
 *   action: Async check function.
 */
async function runSmokeCheck(name, action) {
  try {
    await action();
  } catch (error) {
    record(name, false, summarizeTransportError(error));
  }
}

/**
 * Converts thrown fetch errors into a sanitized one-line smoke detail.
 *
 * Args:
 *   error: Unknown thrown error.
 *
 * Returns:
 *   Sanitized error summary.
 */
function summarizeTransportError(error) {
  if (!(error instanceof Error)) {
    return 'request failed';
  }

  if (error.name === 'TimeoutError' || error.name === 'AbortError') {
    return 'request timed out';
  }

  const cause = error.cause;
  if (cause && typeof cause === 'object' && 'code' in cause) {
    return `request failed (${String(cause.code)})`;
  }

  return `request failed (${error.name || 'Error'})`;
}

/**
 * Loads simple KEY=value pairs from a local environment file.
 *
 * Args:
 *   filePath: Absolute path to the env file.
 */
function loadEnvFile(filePath) {
  if (!existsSync(filePath)) {
    return;
  }
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
    const key = trimmed.slice(0, separator).trim();
    const rawValue = trimmed.slice(separator + 1).trim();
    if (!process.env[key]) {
      process.env[key] = unquote(rawValue);
    }
  }
}

/**
 * Validates remote smoke target requirements without leaking query strings.
 */
function checkSmokeTarget() {
  if (process.env.LEMON_WEB_SMOKE_REQUIRE_REMOTE !== '1') {
    return true;
  }

  if (!process.env.LEMON_WEB_SMOKE_URL) {
    record(
      'remote target',
      false,
      'LEMON_WEB_SMOKE_URL is required when running smoke:remote',
    );
    return false;
  }

  let parsed;
  try {
    parsed = new URL(baseUrl);
  } catch {
    record('remote target', false, 'LEMON_WEB_SMOKE_URL must be an absolute URL');
    return false;
  }

  if (parsed.protocol !== 'https:') {
    record('remote target', false, 'remote smoke target must use HTTPS');
    return false;
  }

  if (isLoopbackOrPrivateHost(parsed.hostname)) {
    record('remote target', false, 'remote smoke target must not be local or private network host');
    return false;
  }

  record('remote target', true, `HTTPS host=${parsed.hostname}`);
  return true;
}

/**
 * Removes wrapping quotes from env values.
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
 * Verifies that the server-rendered app shell contains Flutter camera markers.
 */
async function checkHomeShell() {
  const response = await fetchWithTimeout(baseUrl, { headers: { Accept: 'text/html' } });
  const text = await response.text();
  const hasMobileShell =
    text.includes('영양제 촬영') &&
    text.includes('성분표를 테두리 안에 맞춰주세요') &&
    text.includes('shutter-button');
  record(
    'camera shell',
    response.ok && hasMobileShell,
    `HTTP ${response.status}, camera shell=${hasMobileShell}`,
  );
}

/**
 * Verifies sanitized deployment readiness metadata from the Next.js runtime.
 */
async function checkDeploymentStatus() {
  const { response, payload } = await fetchJson('/api/lemon/deployment-status');
  const backendStatus = readNestedBoolean(payload, ['backend', 'ok']);
  const supabaseStatus = readNestedBoolean(payload, ['supabase', 'ok']);
  record(
    'deployment status',
    response.ok && payload?.ok === true,
    `HTTP ${response.status}, backend=${statusLabel(backendStatus)}, supabase=${statusLabel(supabaseStatus)}`,
  );
}

/**
 * Verifies the same-origin Next.js readiness proxy to the FastAPI backend.
 */
async function checkReadinessProxy() {
  const { response, payload } = await fetchJson('/api/lemon/ready');
  const ocrProvider = readNestedString(payload, ['ocr', 'primary_provider']) ?? 'unknown';
  const yoloEnabled = readNestedBoolean(payload, ['vision', 'food_yolo_enabled']);
  record(
    'backend readiness proxy',
    response.ok,
    `HTTP ${response.status}, OCR=${ocrProvider}, YOLO=${statusLabel(yoloEnabled)}`,
  );
}

/**
 * Verifies Supabase through the same Next.js runtime that Vercel Preview uses.
 */
async function checkSupabaseProxy() {
  const { response, payload } = await fetchJson('/api/lemon/supabase-smoke');
  const supabaseStatus =
    typeof payload?.status === 'number'
      ? `supabase HTTP ${payload.status}`
      : readNestedString(payload, ['code']) ?? 'unknown';
  record(
    'supabase runtime smoke',
    response.ok && payload?.ok === true,
    `HTTP ${response.status}, ${supabaseStatus}`,
  );
}

/**
 * Uploads the supplement mock label through the web OCR proxy.
 */
async function checkSupplementUpload() {
  if (!existsSync(supplementImagePath)) {
    record('supplement upload', false, `missing fixture: ${supplementImagePath}`);
    return;
  }
  const { response, payload } = await uploadImage('/api/lemon/supplements/analyze', supplementImagePath, {
    ocr_provider: 'paddleocr',
  });
  const metadata = getRecord(payload, ['pipeline_metadata']);
  const rawImageStored = metadata?.raw_image_stored;
  const rawOcrStored = metadata?.raw_ocr_text_stored;
  const provider = typeof metadata?.ocr_provider === 'string' ? metadata.ocr_provider : 'unknown';
  record(
    'supplement OCR upload',
    response.ok,
    `HTTP ${response.status}, provider=${provider}, raw_image_stored=${rawImageStored}, raw_ocr_text_stored=${rawOcrStored}`,
  );
}

/**
 * Uploads a meal image through the web YOLO endpoint.
 */
async function checkMealUpload() {
  if (!existsSync(mealImagePath)) {
    record('meal upload', false, `missing fixture: ${mealImagePath}`);
    return;
  }
  const { response, payload } = await uploadImage('/api/lemon/meals/analyze-image', mealImagePath, {
    meal_type: 'lunch',
  });
  const metadata = getRecord(payload, ['pipeline_metadata']);
  const detectorUsed = metadata?.detector_used;
  const rawImageStored = metadata?.raw_image_stored;
  const warningCodes = Array.isArray(payload?.warning_codes) ? payload.warning_codes.join(',') : 'none';
  record(
    'meal YOLO upload',
    response.ok,
    `HTTP ${response.status}, detector_used=${detectorUsed}, raw_image_stored=${rawImageStored}, warnings=${warningCodes}`,
  );
}

/**
 * Uploads an image file as multipart/form-data.
 *
 * Args:
 *   endpoint: Same-origin endpoint path.
 *   filePath: Absolute image fixture path.
 *   fields: Additional multipart fields.
 *
 * Returns:
 *   Response and parsed JSON payload.
 */
async function uploadImage(endpoint, filePath, fields) {
  const body = new FormData();
  const bytes = await readFile(filePath);
  const blob = new Blob([bytes], { type: contentTypeFor(filePath) });
  body.append('image', blob, path.basename(filePath));
  for (const [key, value] of Object.entries(fields)) {
    body.append(key, value);
  }
  return fetchJson(endpoint, {
    method: 'POST',
    body,
  });
}

/**
 * Fetches and parses a JSON endpoint.
 *
 * Args:
 *   endpoint: Absolute URL or path relative to the smoke base URL.
 *   init: Fetch options.
 *
 * Returns:
 *   Response and parsed JSON payload.
 */
async function fetchJson(endpoint, init = {}) {
  const response = await fetchWithTimeout(toUrl(endpoint), {
    headers: { Accept: 'application/json', ...(init.headers ?? {}) },
    ...init,
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { parse_error: true };
    }
  }
  return { response, payload };
}

/**
 * Runs fetch with a timeout suitable for local OCR smoke checks.
 *
 * Args:
 *   url: URL to request.
 *   init: Fetch options.
 *
 * Returns:
 *   Fetch response.
 */
async function fetchWithTimeout(url, init = {}) {
  return fetch(url, {
    signal: AbortSignal.timeout(Number(process.env.LEMON_WEB_SMOKE_TIMEOUT_MS ?? 60000)),
    ...init,
  });
}

/**
 * Records one smoke result.
 *
 * Args:
 *   name: Check name.
 *   ok: Whether the check passed.
 *   detail: Sanitized check detail.
 */
function record(name, ok, detail) {
  const mark = ok ? 'PASS' : 'FAIL';
  console.log(`[${mark}] ${name}: ${detail}`);
  if (!ok) {
    failures += 1;
  }
}

function finish() {
  if (failures > 0) {
    console.error(`Smoke failed: ${failures} check(s) failed.`);
    process.exitCode = 1;
    return;
  }
  console.log('Smoke passed.');
}

/**
 * Resolves endpoint paths against the smoke base URL.
 *
 * Args:
 *   endpoint: Absolute URL or path.
 *
 * Returns:
 *   Absolute URL.
 */
function toUrl(endpoint) {
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  return `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
}

/**
 * Maps a file extension to a simple image content type.
 *
 * Args:
 *   filePath: Image path.
 *
 * Returns:
 *   MIME content type.
 */
function contentTypeFor(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === '.png') return 'image/png';
  if (extension === '.webp') return 'image/webp';
  return 'image/jpeg';
}

/**
 * Reads a nested string from an object.
 *
 * Args:
 *   value: Unknown payload.
 *   pathKeys: Nested object keys.
 *
 * Returns:
 *   String value when present.
 */
function readNestedString(value, pathKeys) {
  const nested = getRecord(value, pathKeys.slice(0, -1));
  const key = pathKeys.at(-1);
  const result = key && nested ? nested[key] : undefined;
  return typeof result === 'string' ? result : undefined;
}

/**
 * Reads a nested boolean from an object.
 *
 * Args:
 *   value: Unknown payload.
 *   pathKeys: Nested object keys.
 *
 * Returns:
 *   Boolean value when present.
 */
function readNestedBoolean(value, pathKeys) {
  const nested = getRecord(value, pathKeys.slice(0, -1));
  const key = pathKeys.at(-1);
  const result = key && nested ? nested[key] : undefined;
  return typeof result === 'boolean' ? result : undefined;
}

/**
 * Reads a nested object from an unknown payload.
 *
 * Args:
 *   value: Unknown payload.
 *   pathKeys: Nested object keys.
 *
 * Returns:
 *   Record value when present.
 */
function getRecord(value, pathKeys) {
  let current = value;
  for (const key of pathKeys) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = current[key];
  }
  return current && typeof current === 'object' ? current : undefined;
}

/**
 * Converts readiness booleans into concise output labels.
 *
 * Args:
 *   value: Boolean or undefined value.
 *
 * Returns:
 *   Status label.
 */
function statusLabel(value) {
  if (value === true) return 'ready';
  if (value === false) return 'not-ready';
  return 'unknown';
}

/**
 * Removes a trailing slash from URLs.
 *
 * Args:
 *   value: URL-like string.
 *
 * Returns:
 *   URL without trailing slash.
 */
function trimTrailingSlash(value) {
  return value.replace(/\/$/, '');
}

/**
 * Detects hosts that cannot prove Vercel Preview behavior.
 *
 * Args:
 *   hostname: Parsed URL hostname.
 *
 * Returns:
 *   True when the host is loopback or private network scoped.
 */
function isLoopbackOrPrivateHost(hostname) {
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

await main();
