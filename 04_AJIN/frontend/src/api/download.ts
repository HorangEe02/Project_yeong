// Day 5 Phase 3 — 응답 다운로드 클라이언트
// 백엔드 POST /api/onboarding/download → Blob → URL.createObjectURL → <a download>

import { ONBOARDING_BASE, authHeaders } from '@api/onboarding';

export type DownloadFormat = 'docx' | 'xlsx' | 'csv' | 'txt';

const FORMAT_EXT: Record<DownloadFormat, string> = {
  docx: '.docx',
  xlsx: '.xlsx',
  csv: '.csv',
  txt: '.txt',
};

function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  // RFC 5987 filename* 우선
  const star = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      /* fallthrough */
    }
  }
  const plain = disposition.match(/filename="?([^";]+)"?/i);
  return plain?.[1] ?? fallback;
}

export async function downloadResponse(
  content: string,
  format: DownloadFormat,
  filename = 'ajin-ai-response',
): Promise<void> {
  const res = await fetch(`${ONBOARDING_BASE}/download`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ content, format, filename }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`다운로드 실패 (${res.status}): ${detail || res.statusText}`);
  }

  const blob = await res.blob();
  const fname = parseFilename(
    res.headers.get('content-disposition'),
    `${filename}${FORMAT_EXT[format]}`,
  );

  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    // 다음 틱에서 URL 회수 — 즉시 revoke 시 일부 브라우저에서 다운로드 실패
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
