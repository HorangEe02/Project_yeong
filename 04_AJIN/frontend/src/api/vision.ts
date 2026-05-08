// Day 5 Phase 4-B — 비전 채팅 API helper
// 백엔드 POST /api/onboarding/chat/vision (multipart). SSE 스트리밍은 useVisionStream 이 처리.
// Storage 업로드는 시도 후 image_url 메타로 함께 보낸다 (백엔드 /chat/vision 가 메타에 echo).

import { ONBOARDING_BASE } from '@api/onboarding';
import { uploadToStorage, validateImageFile } from '@api/upload';

export interface VisionRequest {
  query: string;
  file: File;
  department?: string;
  model?: string;
}

export function buildVisionUrl(): string {
  return `${ONBOARDING_BASE}/chat/vision`;
}

/** 비전용 multipart FormData 빌드. Storage 업로드는 호출자가 별도로 한다. */
export function buildVisionFormData(req: VisionRequest): FormData {
  const fd = new FormData();
  fd.append('query', req.query);
  if (req.department) fd.append('department', req.department);
  if (req.model) fd.append('model', req.model);
  fd.append('file', req.file);
  return fd;
}

/** Storage 업로드 + 검증을 한 번에. URL 은 옵셔널 (Auth 미통합 시 undefined). */
export async function prepareVisionAttachment(
  file: File,
): Promise<{ imageUrl?: string }> {
  const err = validateImageFile(file);
  if (err) throw new Error(err);
  try {
    const imageUrl = await uploadToStorage(file, 'images');
    return { imageUrl };
  } catch (e) {
    if (import.meta.env.DEV) console.warn('[vision] storage upload skipped', e);
    return {};
  }
}
