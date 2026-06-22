import { existsSync, readFileSync, statSync } from 'node:fs';
import { readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const outputRoot = path.join(frontendRoot, '.vercel/output');
const localEnvFile = path.join(frontendRoot, '.env.local');
const previewEnvFile = path.join(frontendRoot, '.vercel/.env.preview.local');
const localOnlyKeys = [
  'LEMON_API_BASE_URL',
  'LEMON_DEV_GATEWAY_TOKEN',
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
];
const clientBundleKeys = ['NEXT_PUBLIC_SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'];
const textFileExtensions = new Set([
  '.cjs',
  '.css',
  '.html',
  '.js',
  '.json',
  '.mjs',
  '.nft.json',
  '.rsc',
  '.txt',
]);

let failures = 0;

/**
 * Verifies that Vercel build output is not carrying local-only env values.
 */
async function main() {
  console.log(`Vercel output directory: ${safePath(outputRoot)}`);
  console.log('No env values are printed.');

  if (!existsSync(outputRoot)) {
    fail('output directory', 'missing; run `npm run vercel:build` first');
    finish();
    return;
  }

  const localEnv = existsSync(localEnvFile) ? readEnvFile(localEnvFile) : {};
  const previewEnv = existsSync(previewEnvFile) ? readEnvFile(previewEnvFile) : {};
  const textFiles = await listTextFiles(outputRoot);

  for (const key of localOnlyKeys) {
    const localValue = localEnv[key];
    if (!localValue) {
      pass(`local ${key}`, 'not set');
      continue;
    }

    if (previewEnv[key] && previewEnv[key] === localValue) {
      pass(`local ${key}`, 'matches Preview value');
      continue;
    }

    const matches = findValueMatches(textFiles, localValue);
    if (matches.length === 0) {
      pass(`local ${key}`, 'not found in Vercel output');
      continue;
    }

    if (clientBundleKeys.includes(key) && matches.some((filePath) => isStaticAsset(filePath))) {
      fail(`local ${key}`, 'found in static client output; rebuild with Preview env before deploy');
      continue;
    }

    fail(`local ${key}`, 'found in server output; rebuild with Preview env before deploy');
  }

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
 * Lists text-like files under the Vercel output directory.
 *
 * Args:
 *   directory: Directory to scan.
 *
 * Returns:
 *   Absolute file paths.
 */
async function listTextFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listTextFiles(entryPath)));
      continue;
    }
    if (!entry.isFile()) {
      continue;
    }
    if (!textFileExtensions.has(path.extname(entry.name))) {
      continue;
    }
    const stats = statSync(entryPath);
    if (stats.size > 4 * 1024 * 1024) {
      continue;
    }
    files.push(entryPath);
  }
  return files;
}

/**
 * Finds files containing a given env value without returning the value.
 *
 * Args:
 *   files: Files to inspect.
 *   value: Env value to search for.
 *
 * Returns:
 *   Matching file paths.
 */
function findValueMatches(files, value) {
  const matches = [];
  for (const filePath of files) {
    const text = readFileSync(filePath, 'utf8');
    if (text.includes(value)) {
      matches.push(filePath);
    }
  }
  return matches;
}

/**
 * Detects whether a path belongs to static client output.
 *
 * Args:
 *   filePath: Output file path.
 *
 * Returns:
 *   True when the file is under the static output tree.
 */
function isStaticAsset(filePath) {
  return path.relative(outputRoot, filePath).split(path.sep).includes('static');
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
    console.log(`Vercel output safety check failed: ${failures} issue(s).`);
    process.exitCode = 1;
    return;
  }
  console.log('Vercel output safety check passed.');
}

function safePath(filePath) {
  return path.relative(frontendRoot, filePath) || '.';
}

await main();
