// ProfilePhotoUploadModal — 디지털 사원증 사진 변경 모달.
// react-image-crop 으로 1:1 강제 crop → canvas 로 256×256 JPEG → base64 data URL.
//
// PR #2 의 frontend-first 구현:
//   - 저장 위치: localStorage (key: `ajin_user_photo_${employee_id}`)
//   - 같은 브라우저에서 새로고침 후에도 사진 유지
//   - 추후 backend `PATCH /api/auth/me/photo` endpoint 추가 시 그쪽으로 자동 전환
//
// 사용처: profile.tsx 의 onPhotoClick.

import { useCallback, useRef, useState, type ChangeEvent } from 'react';
import ReactCrop, { centerCrop, makeAspectCrop, type Crop, type PixelCrop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import { createPortal } from 'react-dom';
import { X, Camera, Check, Loader2 } from 'lucide-react';

interface Props {
  employeeId: string;
  open: boolean;
  onClose: () => void;
  /** crop 완료 후 data URL 을 부모에게 전달 (localStorage 저장은 부모 책임). */
  onConfirm: (dataUrl: string) => void;
}

const TARGET_SIZE = 256; // 출력 정사각형 픽셀
const MAX_FILE_BYTES = 5 * 1024 * 1024; // 원본 5MB 제한
const OUTPUT_QUALITY = 0.86; // JPEG 품질

// react-image-crop centerCrop helper — 이미지 로드 시 1:1 영역 중앙 자동 셋
function initialCenteredCrop(width: number, height: number): Crop {
  return centerCrop(
    makeAspectCrop({ unit: '%', width: 80 }, 1, width, height),
    width,
    height,
  );
}

async function cropToDataUrl(
  imgEl: HTMLImageElement,
  crop: PixelCrop,
): Promise<string> {
  const canvas = document.createElement('canvas');
  canvas.width = TARGET_SIZE;
  canvas.height = TARGET_SIZE;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas 2d context 생성 실패');

  // crop 좌표는 displayed 픽셀 기준 — natural 크기로 환산
  const scaleX = imgEl.naturalWidth / imgEl.width;
  const scaleY = imgEl.naturalHeight / imgEl.height;

  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(
    imgEl,
    crop.x * scaleX,
    crop.y * scaleY,
    crop.width * scaleX,
    crop.height * scaleY,
    0,
    0,
    TARGET_SIZE,
    TARGET_SIZE,
  );

  return canvas.toDataURL('image/jpeg', OUTPUT_QUALITY);
}

export function ProfilePhotoUploadModal({ employeeId, open, onClose, onConfirm }: Props) {
  const [srcUrl, setSrcUrl] = useState<string | null>(null);
  const [crop, setCrop] = useState<Crop>();
  const [completed, setCompleted] = useState<PixelCrop | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFile = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('이미지 파일만 업로드 가능합니다 (jpg / png / webp).');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setError(`파일이 너무 큽니다. 최대 ${Math.round(MAX_FILE_BYTES / (1024 * 1024))}MB 까지 가능합니다.`);
      return;
    }
    if (srcUrl) URL.revokeObjectURL(srcUrl);
    const url = URL.createObjectURL(file);
    setSrcUrl(url);
    setCrop(undefined);
    setCompleted(null);
  }, [srcUrl]);

  const handleImgLoad = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    const { width, height } = e.currentTarget;
    setCrop(initialCenteredCrop(width, height));
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!imgRef.current || !completed || completed.width < 8 || completed.height < 8) {
      setError('유효한 crop 영역을 선택하세요.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const dataUrl = await cropToDataUrl(imgRef.current, completed);
      onConfirm(dataUrl);
      // cleanup
      if (srcUrl) URL.revokeObjectURL(srcUrl);
      setSrcUrl(null);
      setCrop(undefined);
      setCompleted(null);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : '이미지 처리 실패');
    } finally {
      setBusy(false);
    }
  }, [completed, onConfirm, srcUrl, onClose]);

  const handleClose = useCallback(() => {
    if (busy) return;
    if (srcUrl) URL.revokeObjectURL(srcUrl);
    setSrcUrl(null);
    setCrop(undefined);
    setCompleted(null);
    setError(null);
    onClose();
  }, [busy, srcUrl, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ppum-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 16,
      }}
      onClick={handleClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 480,
          maxHeight: '90vh',
          background: 'var(--hud-surface)',
          color: 'var(--hud-text)',
          borderRadius: 14,
          border: '1px solid color-mix(in oklab, var(--hud-text) 14%, transparent)',
          boxShadow: '0 24px 48px rgba(0,0,0,0.45)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontFamily: 'var(--hud-font-sans)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '14px 18px',
            borderBottom: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          <div>
            <div id="ppum-title" style={{ fontSize: 15, fontWeight: 700 }}>증명사진 변경</div>
            <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginTop: 2 }}>
              1:1 정사각형으로 자동 crop · 256×256 JPEG 로 저장
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={busy}
            aria-label="닫기"
            style={{
              width: 32,
              height: 32,
              border: 'none',
              background: 'transparent',
              color: 'var(--hud-text-dim)',
              cursor: busy ? 'not-allowed' : 'pointer',
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} strokeWidth={1.5} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 18 }}>
          {!srcUrl ? (
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              style={{
                width: '100%',
                minHeight: 240,
                border: '2px dashed color-mix(in oklab, var(--hud-text) 24%, transparent)',
                borderRadius: 10,
                background: 'color-mix(in oklab, var(--hud-text) 3%, transparent)',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                color: 'var(--hud-text-dim)',
                padding: 24,
              }}
            >
              <Camera size={28} strokeWidth={1.4} />
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--hud-text)' }}>이미지 선택</div>
              <div style={{ fontSize: 11, lineHeight: 1.5, textAlign: 'center' }}>
                jpg · png · webp · 최대 5MB<br />
                얼굴이 중앙에 오도록 권장합니다.
              </div>
            </button>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <ReactCrop
                crop={crop}
                onChange={(_, p) => setCrop(p)}
                onComplete={(c) => setCompleted(c)}
                aspect={1}
                keepSelection
                circularCrop={false}
                minWidth={48}
              >
                <img
                  ref={imgRef}
                  src={srcUrl}
                  alt="증명사진 자르기 대상"
                  onLoad={handleImgLoad}
                  style={{ maxWidth: '100%', maxHeight: '60vh', display: 'block' }}
                />
              </ReactCrop>
            </div>
          )}

          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            onChange={handleFile}
            style={{ display: 'none' }}
          />

          {error && (
            <div
              role="alert"
              style={{
                marginTop: 12,
                padding: '8px 12px',
                borderRadius: 8,
                background: 'color-mix(in oklab, var(--hud-red, #e24b4a) 14%, transparent)',
                border: '1px solid color-mix(in oklab, var(--hud-red, #e24b4a) 35%, transparent)',
                color: 'var(--hud-red, #e24b4a)',
                fontSize: 12,
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 18px',
            borderTop: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          {srcUrl ? (
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={busy}
              className="lg-btn ghost sm"
              style={{ fontSize: 12 }}
            >
              다른 사진 선택
            </button>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>사번 {employeeId} 의 증명사진</span>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={handleClose}
              disabled={busy}
              className="lg-btn ghost sm"
              style={{ fontSize: 12 }}
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={!srcUrl || !completed || busy}
              className="lg-btn primary sm"
              style={{ fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              {busy ? <Loader2 size={12} className="spin" /> : <Check size={12} />} 확인
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// localStorage helper — 사원증 사진 저장/조회 (이 모듈에서 export 하여 profile.tsx 와 공유).
const STORAGE_PREFIX = 'ajin_user_photo:';

export function loadStoredPhoto(employeeId: string): string | null {
  if (typeof window === 'undefined' || !employeeId) return null;
  try {
    return window.localStorage.getItem(STORAGE_PREFIX + employeeId);
  } catch {
    return null;
  }
}

export function saveStoredPhoto(employeeId: string, dataUrl: string): void {
  if (typeof window === 'undefined' || !employeeId) return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + employeeId, dataUrl);
  } catch (e) {
    // localStorage quota 초과 가능 — 5MB 제한 안에서는 거의 발생 안 함
    console.warn('[ProfilePhoto] localStorage write failed:', e);
  }
}

export function clearStoredPhoto(employeeId: string): void {
  if (typeof window === 'undefined' || !employeeId) return;
  try {
    window.localStorage.removeItem(STORAGE_PREFIX + employeeId);
  } catch {
    /* ignore */
  }
}
