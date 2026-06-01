// Day 5 Phase 4-B — 파일 업로드 API.
// Firebase Storage 직접 업로드 대신 백엔드 signed URL을 통해 Supabase Storage에 저장한다.

import { api } from '@api/client';
import { ONBOARDING_BASE, authHeaders } from '@api/onboarding';

export interface UploadResult {
  fileName: string;
  isImage: boolean;
  text: string;
  /** 서버 저장소 URL (Firebase write 차단 또는 비통합 시 undefined). */
  fileUrl?: string;
  /** 백엔드가 base64 로 반환하는 이미지 (비전 첨부용 fallback). */
  imageBase64?: string;
}

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // 5 MB

interface SignedUploadResponse {
  attachment_id: string;
  bucket: string;
  object_path: string;
  signed_url: string;
  token: string;
  method: 'PUT';
}

interface CompleteUploadResponse {
  ok: boolean;
  attachment_id: string;
  signed_download_url?: string | null;
}

/** Supabase Storage signed URL 업로드. 미구성 환경에서는 호출 측에서 fallback 처리한다. */
export async function uploadToStorage(
  file: File,
  path: 'images' | 'uploads',
): Promise<string | undefined> {
  const signedRes = await api.post<SignedUploadResponse>('/storage/signed-upload', {
    bucket_type: 'attachments',
    file_name: file.name,
    content_type: file.type || '',
    size_bytes: file.size,
    prefix: path,
  });
  const signed = signedRes.data;
  const uploadRes = await fetch(signed.signed_url, {
    method: signed.method || 'PUT',
    headers: file.type ? { 'Content-Type': file.type } : undefined,
    body: file,
  });
  if (!uploadRes.ok) {
    const detail = await uploadRes.text().catch(() => `${uploadRes.status}`);
    throw new Error(`스토리지 업로드 실패: ${detail || uploadRes.status}`);
  }
  const completeRes = await api.post<CompleteUploadResponse>('/storage/complete-upload', {
    attachment_id: signed.attachment_id,
  });
  return completeRes.data.signed_download_url || undefined;
}

/** 파일 첨부용 — 백엔드 /upload 로 텍스트 추출 + Storage 업로드 시도. */
export async function uploadAttachmentFile(file: File): Promise<UploadResult> {
  if (file.size > MAX_FILE_BYTES) {
    throw new Error(`파일 크기가 ${Math.round(MAX_FILE_BYTES / 1024 / 1024)}MB 를 초과합니다.`);
  }

  const fd = new FormData();
  fd.append('file', file);

  const res = await fetch(`${ONBOARDING_BASE}/upload`, {
    method: 'POST',
    headers: { ...authHeaders() }, // FormData 는 Content-Type 자동 설정
    body: fd,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = (await res.json()) as { detail?: string };
      if (j?.detail) detail = j.detail;
    } catch {
      /* noop */
    }
    throw new Error(`업로드 실패: ${detail}`);
  }
  const json = (await res.json()) as {
    filename: string;
    is_image: boolean;
    text: string;
    image_base64?: string;
  };

  // 이미지가 아닌 일반 파일은 Storage uploads/ 에 업로드
  let fileUrl: string | undefined;
  if (!json.is_image) {
    try {
      fileUrl = await uploadToStorage(file, 'uploads');
    } catch (e) {
      if (import.meta.env.DEV) console.warn('[upload] storage upload skipped', e);
    }
  }

  return {
    fileName: json.filename,
    isImage: json.is_image,
    text: json.text || '',
    fileUrl,
    imageBase64: json.image_base64,
  };
}

/** 파일 검증 (UI 차단용). */
export function validateImageFile(file: File): string | null {
  if (file.size > MAX_IMAGE_BYTES) {
    return `이미지 크기가 ${Math.round(MAX_IMAGE_BYTES / 1024 / 1024)}MB 를 초과합니다.`;
  }
  if (!file.type.startsWith('image/')) {
    return '이미지 파일이 아닙니다.';
  }
  return null;
}

export function validateGenericFile(file: File): string | null {
  if (file.size > MAX_FILE_BYTES) {
    return `파일 크기가 ${Math.round(MAX_FILE_BYTES / 1024 / 1024)}MB 를 초과합니다.`;
  }
  return null;
}

export const UPLOAD_LIMITS = {
  imageBytes: MAX_IMAGE_BYTES,
  fileBytes: MAX_FILE_BYTES,
};
