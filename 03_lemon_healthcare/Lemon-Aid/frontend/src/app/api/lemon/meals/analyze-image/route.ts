import {
  backendConfigIssueResponse,
  backendProxyFailureResponse,
  buildProxyHeaders,
  getBackendApiBaseUrl,
  getBackendConfigIssue,
  proxyBackendResponse,
} from '@/lib/lemon-backend';

export const runtime = 'nodejs';

/**
 * Proxies meal image YOLO uploads to the FastAPI backend.
 *
 * Args:
 *   request: Browser multipart request from the React capture flow.
 *
 * Returns:
 *   Backend meal image analysis response.
 */
export async function POST(request: Request) {
  const configIssue = getBackendConfigIssue();
  if (configIssue) {
    return backendConfigIssueResponse(configIssue);
  }

  const formData = await request.formData();
  try {
    const response = await fetch(`${getBackendApiBaseUrl()}/meals/analyze-image`, {
      method: 'POST',
      headers: buildProxyHeaders(request),
      body: formData,
    });
    return proxyBackendResponse(response);
  } catch {
    return backendProxyFailureResponse();
  }
}
