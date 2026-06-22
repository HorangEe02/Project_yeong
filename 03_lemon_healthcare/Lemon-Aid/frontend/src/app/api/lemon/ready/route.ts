import {
  backendConfigIssueResponse,
  backendProxyFailureResponse,
  buildProxyHeaders,
  getBackendConfigIssue,
  getBackendReadinessUrl,
  proxyBackendResponse,
} from '@/lib/lemon-backend';

export const runtime = 'nodejs';

/**
 * Proxies the backend `/ready` endpoint for same-origin web smoke checks.
 *
 * Returns:
 *   Sanitized backend readiness response.
 */
export async function GET() {
  const configIssue = getBackendConfigIssue();
  if (configIssue) {
    return backendConfigIssueResponse(configIssue);
  }

  try {
    const response = await fetch(getBackendReadinessUrl(), {
      headers: buildProxyHeaders(),
    });
    return proxyBackendResponse(response);
  } catch {
    return backendProxyFailureResponse();
  }
}
