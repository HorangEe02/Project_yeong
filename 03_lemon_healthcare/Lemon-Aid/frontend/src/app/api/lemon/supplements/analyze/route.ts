import {
  backendConfigIssueResponse,
  backendProxyFailureResponse,
  buildProxyHeaders,
  getBackendConfigIssue,
  getBackendApiBaseUrl,
  proxyBackendResponse,
} from '@/lib/lemon-backend';

export const runtime = 'nodejs';

/**
 * Proxies supplement OCR uploads to the FastAPI backend.
 *
 * Args:
 *   request: Browser multipart request from the React capture flow.
 *
 * Returns:
 *   Backend supplement analysis response.
 */
export async function POST(request: Request) {
  const configIssue = getBackendConfigIssue();
  if (configIssue) {
    return backendConfigIssueResponse(configIssue);
  }

  const formData = await request.formData();
  try {
    const response = await fetch(`${getBackendApiBaseUrl()}/supplements/analyze`, {
      method: 'POST',
      headers: buildProxyHeaders(request),
      body: formData,
    });
    return proxyBackendResponse(response);
  } catch {
    return backendProxyFailureResponse();
  }
}
