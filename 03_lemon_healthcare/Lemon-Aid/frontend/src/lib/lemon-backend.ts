const DEFAULT_BACKEND_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
const DEV_GATEWAY_TOKEN_HEADER = 'X-Lemon-Dev-Gateway-Token';

function readConfiguredBackendApiBaseUrl(): string | undefined {
  return process.env.LEMON_API_BASE_URL || process.env.NEXT_PUBLIC_LEMON_API_BASE_URL;
}

function readConfiguredDevGatewayToken(): string | undefined {
  const token = process.env.LEMON_DEV_GATEWAY_TOKEN?.trim();
  return token || undefined;
}

/**
 * Reads the server-side FastAPI base URL used by Next.js route proxies.
 *
 * Returns:
 *   Backend API base URL ending at `/api/v1`.
 */
export function getBackendApiBaseUrl(): string {
  return (readConfiguredBackendApiBaseUrl() || DEFAULT_BACKEND_API_BASE_URL).replace(/\/$/, '');
}

/**
 * Builds a backend readiness URL from the configured API base URL.
 *
 * Returns:
 *   FastAPI service readiness URL.
 */
export function getBackendReadinessUrl(): string {
  const baseUrl = getBackendApiBaseUrl();
  return baseUrl.endsWith('/api/v1') ? `${baseUrl.slice(0, -'/api/v1'.length)}/ready` : `${baseUrl}/ready`;
}

/**
 * Detects backend proxy configuration that cannot work on Vercel Preview.
 *
 * Returns:
 *   Safe operator-facing issue text, or null when the proxy can attempt a request.
 */
export function getBackendConfigIssue(): string | null {
  if (!process.env.VERCEL) {
    return null;
  }

  const configuredUrl = readConfiguredBackendApiBaseUrl();
  if (!configuredUrl) {
    return 'LEMON_API_BASE_URL is not configured for this Vercel deployment.';
  }

  try {
    const parsed = new URL(configuredUrl);
    if (parsed.protocol !== 'https:') {
      return 'LEMON_API_BASE_URL must use HTTPS for Vercel deployments.';
    }
    if (isHostUnavailableFromVercel(parsed.hostname)) {
      return 'LEMON_API_BASE_URL points to a local or private host and is unreachable from Vercel.';
    }
    if (!parsed.pathname.replace(/\/$/, '').endsWith('/api/v1')) {
      return 'LEMON_API_BASE_URL must end with /api/v1.';
    }
  } catch {
    return 'LEMON_API_BASE_URL is not a valid absolute URL.';
  }

  return null;
}

/**
 * Builds a sanitized JSON response for proxy configuration failures.
 *
 * Args:
 *   issue: Safe operator-facing issue text.
 *
 * Returns:
 *   JSON response without backend URLs or secret material.
 */
export function backendConfigIssueResponse(issue: string): Response {
  return Response.json(
    {
      ok: false,
      code: 'backend_proxy_not_configured',
      message: issue,
    },
    { status: 503 },
  );
}

/**
 * Proxies a JSON-like backend response without exposing server-only env values.
 *
 * Args:
 *   response: Backend fetch response.
 *
 * Returns:
 *   Response with original status and JSON content type.
 */
export async function proxyBackendResponse(response: Response): Promise<Response> {
  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/json',
    },
  });
}

/**
 * Builds a sanitized JSON response for failed backend proxy requests.
 *
 * Returns:
 *   JSON response without backend URLs, raw request bodies, or provider payloads.
 */
export function backendProxyFailureResponse(): Response {
  return Response.json(
    {
      ok: false,
      code: 'backend_proxy_unreachable',
      message: 'Backend API proxy request failed.',
    },
    { status: 502 },
  );
}

/**
 * Builds pass-through headers for authenticated API test requests.
 *
 * Args:
 *   request: Incoming Next.js route request.
 *
 * Returns:
 *   Headers safe to forward to the FastAPI backend.
 */
export function buildProxyHeaders(request?: Request): Headers {
  const headers = new Headers({
    Accept: 'application/json',
  });
  const gatewayToken = readConfiguredDevGatewayToken();
  if (gatewayToken) {
    headers.set(DEV_GATEWAY_TOKEN_HEADER, gatewayToken);
  }
  const authorization = request?.headers.get('Authorization');
  if (authorization) {
    headers.set('Authorization', authorization);
  }
  return headers;
}

/**
 * Detects hosts that Vercel server functions cannot reach as public backends.
 *
 * Args:
 *   hostname: Parsed backend URL hostname.
 *
 * Returns:
 *   True when the host is loopback or private-network scoped.
 */
function isHostUnavailableFromVercel(hostname: string): boolean {
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
