import { useEffect, useRef, useState, useCallback } from 'react';
import { Html5Qrcode } from 'html5-qrcode';

interface UseQRScannerOptions {
  onScanSuccess: (decodedText: string) => void;
  onScanError?: (error: string) => void;
}

/** 고정 컨테이너 ID — React 리렌더링과 무관하게 안정적 */
const SCANNER_CONTAINER_ID = 'mediway-qr-reader';

export function useQRScanner({ onScanSuccess, onScanError }: UseQRScannerOptions) {
  const [isScanning, setIsScanning] = useState(false);
  const [hasCamera, setHasCamera] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const successCallbackRef = useRef(onScanSuccess);
  successCallbackRef.current = onScanSuccess;

  const startScanning = useCallback(async () => {
    setErrorMsg(null);

    // 기존 스캐너 정리
    if (scannerRef.current) {
      try {
        if (scannerRef.current.isScanning) {
          await scannerRef.current.stop();
        }
        try { scannerRef.current.clear(); } catch { /* ignore */ }
      } catch {
        // ignore
      }
      scannerRef.current = null;
    }

    try {
      const devices = await Html5Qrcode.getCameras();
      if (devices.length === 0) {
        setHasCamera(false);
        setErrorMsg('카메라를 찾을 수 없습니다.');
        onScanError?.('카메라를 찾을 수 없습니다.');
        return;
      }

      const scanner = new Html5Qrcode(SCANNER_CONTAINER_ID, {
        verbose: false,
      });
      scannerRef.current = scanner;

      await scanner.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 220, height: 220 },
          aspectRatio: 1.0,
        },
        (decodedText) => {
          successCallbackRef.current(decodedText);
          // 스캔 성공 후 자동 중지
          scanner.stop().catch(() => {});
          scannerRef.current = null;
          setIsScanning(false);
        },
        undefined,
      );

      setIsScanning(true);

      // 모바일에서 video 요소에 스타일 강제 적용
      requestAnimationFrame(() => {
        const container = document.getElementById(SCANNER_CONTAINER_ID);
        if (container) {
          const video = container.querySelector('video');
          if (video) {
            video.style.width = '100%';
            video.style.height = '100%';
            video.style.objectFit = 'cover';
            video.style.borderRadius = '12px';
          }
        }
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '카메라 접근에 실패했습니다.';
      // NotAllowedError = 권한 거부, NotFoundError = 카메라 없음
      if (msg.includes('NotAllowed') || msg.includes('Permission')) {
        setErrorMsg('카메라 권한이 거부되었습니다. 브라우저 설정에서 카메라 권한을 허용해주세요.');
      } else {
        setErrorMsg(msg);
      }
      setHasCamera(false);
      onScanError?.(msg);
    }
  }, [onScanError]);

  const stopScanning = useCallback(async () => {
    try {
      if (scannerRef.current?.isScanning) {
        await scannerRef.current.stop();
      }
      if (scannerRef.current) {
        try { scannerRef.current.clear(); } catch { /* ignore */ }
      }
    } catch {
      // 이미 중지됨
    }
    scannerRef.current = null;
    setIsScanning(false);
  }, []);

  useEffect(() => {
    return () => {
      if (scannerRef.current) {
        if (scannerRef.current.isScanning) {
          scannerRef.current.stop().catch(() => {});
        }
        try { scannerRef.current.clear(); } catch { /* ignore */ }
        scannerRef.current = null;
      }
    };
  }, []);

  return {
    containerId: SCANNER_CONTAINER_ID,
    isScanning,
    hasCamera,
    errorMsg,
    startScanning,
    stopScanning,
  };
}
