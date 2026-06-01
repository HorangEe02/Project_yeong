/**
 * Return a no-secret health response from the Vercel API layer.
 *
 * Args:
 *   req: Vercel Node.js request object.
 *   res: Vercel Node.js response object.
 *
 * Returns:
 *   void: Writes the HTTP response directly.
 *
 * Raises:
 *   None.
 */
export default function handler(req, res) {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.setHeader('Allow', 'GET, HEAD');
    res.status(405).json({
      ok: false,
      error: 'method_not_allowed',
    });
    return;
  }

  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  if (req.method === 'HEAD') {
    res.status(200).end();
    return;
  }

  res.status(200).json({
    ok: true,
    service: 'ajin-frontend',
    runtime: 'vercel-function',
    cloud_run: false,
    timestamp: new Date().toISOString(),
  });
}
