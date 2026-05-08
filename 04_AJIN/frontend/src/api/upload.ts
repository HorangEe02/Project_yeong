// Day 5 Phase 4-B — 파일 업로드 API
// 옵션 B: Frontend 가 Firebase Storage 직접 업로드 + 백엔드 /upload 로 텍스트 추출.
// Storage 업로드는 Firebase Auth 가 통합되어 있을 때만 시도한다 (rules: uid 검사).
// 비통합 환경에서는 fileUrl=undefined 로 우아하게 진행 — 백엔드 텍스트 추출만 사용.

import { ref as storageRef, uploadBytes, getDownloadURL } from 'firebase/storage';
import { auth, storage } from '@lib/firebase';
import { ONBOARDING_BASE, authHeaders } from '@api/onboarding';

export interface UploadResult {
  fileName: string;
  isImage: boolean;
  text: string;
  /** Storage public URL (Firebase Auth 비통합 시 undefined). */
  fileUrl?: string;
  /** 백엔드가 base64 로 반환하는 이미지 (비전 첨부용 fallback). */
  imageBase64?: string;
}

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // 5 MB

function safeBase(name: string): string {
  return name.replace(/[^A-Za-z0-9._-]/g, '_').slice(-80);
}

/** Firebase Storage 에 직접 업로드. 인증/Storage 미초기화면 undefined 반환. */
export async function uploadToStorage(
  file: File,
  path: 'images' | 'uploads',
): Promise<string | undefined> {
  if (!storage) return undefined;
  const uid = auth?.currentUser?.uid;
  if (!uid) return undefined;
  const ts = Date.now();
  const r = storageRef(storage, `${path}/${uid}/${ts}_${safeBase(file.name)}`);
  const snap = await uploadBytes(r, file, { contentType: file.type || undefined });
  return getDownloadURL(snap.ref);
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
