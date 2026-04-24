import { useState } from 'react';
import { Camera, Keyboard, ScanLine, AlertCircle } from 'lucide-react';
import { useQRScanner } from '@/hooks/useQRScanner';

interface Props {
  onScanSuccess: (token: string) => void;
  onScanError?: (error: string) => void;
}

export function QRScanner({ onScanSuccess, onScanError }: Props) {
  const [manualToken, setManualToken] = useState('');
  const [showManualInput, setShowManualInput] = useState(false);
  const { containerId, isScanning, hasCamera, errorMsg, startScanning, stopScanning } =
    useQRScanner({ onScanSuccess, onScanError });

  const handleManualSubmit = () => {
    const token = manualToken.trim();
    if (token) {
      onScanSuccess(token);
      setManualToken('');
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      {/* QR 스캐너 영역 */}
      <div className="relative w-full max-w-sm rounded-2xl bg-surface-container-high">
        {/* 대기 화면 */}
        {!isScanning && !showManualInput && (
          <div className="flex flex-col items-center justify-center gap-4 p-8">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary-container">
              <ScanLine className="h-10 w-10 text-on-primary" />
            </div>
            <p className="text-center text-sm text-on-surface-variant">
              환자의 QR 코드를 스캔하여
              <br />
              동선 전송을 시작하세요
            </p>
            <button
              onClick={startScanning}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-primary to-primary-container px-6 py-3 text-sm font-semibold text-on-primary transition-transform active:scale-95"
            >
              <Camera className="h-4 w-4" />
              QR 스캔 시작
            </button>

            {/* 에러 메시지 */}
            {errorMsg && (
              <div className="flex items-start gap-2 rounded-xl bg-error-container/30 p-3 text-left">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-error" />
                <p className="text-xs text-error">{errorMsg}</p>
              </div>
            )}
            {!hasCamera && !errorMsg && (
              <p className="text-xs text-error">카메라를 사용할 수 없습니다.</p>
            )}
          </div>
        )}

        {/* html5-qrcode 카메라 뷰 — 항상 DOM에 존재, display로 토글 */}
        <div
          id={containerId}
          style={{
            display: isScanning ? 'block' : 'none',
            width: '100%',
            minHeight: isScanning ? '320px' : '0',
            borderRadius: '12px',
            overflow: 'hidden',
          }}
        />

        {/* 스캔 중지 버튼 */}
        {isScanning && (
          <div className="flex justify-center py-3">
            <button
              onClick={stopScanning}
              className="rounded-xl bg-surface-container-lowest px-4 py-2 text-sm font-medium text-on-surface shadow-ambient"
            >
              스캔 중지
            </button>
          </div>
        )}

        {/* 수동 입력 폼 */}
        {showManualInput && !isScanning && (
          <div className="flex flex-col gap-3 p-6">
            <p className="text-sm font-medium text-on-surface">수동 토큰 입력</p>
            <input
              type="text"
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleManualSubmit()}
              placeholder="환자 QR 토큰을 입력하세요"
              className="rounded-xl bg-surface-container-highest px-4 py-3 text-sm text-on-surface outline-none transition-colors focus:bg-surface-container-lowest focus:shadow-ambient"
            />
            <button
              onClick={handleManualSubmit}
              disabled={!manualToken.trim()}
              className="rounded-xl bg-gradient-to-r from-primary to-primary-container px-4 py-3 text-sm font-semibold text-on-primary transition-transform active:scale-95 disabled:opacity-50"
            >
              확인
            </button>
          </div>
        )}
      </div>

      {/* 수동 입력 토글 */}
      {!isScanning && (
        <button
          onClick={() => setShowManualInput(!showManualInput)}
          className="flex items-center gap-2 text-sm text-on-surface-variant transition-colors hover:text-primary"
        >
          <Keyboard className="h-4 w-4" />
          {showManualInput ? 'QR 스캔으로 전환' : '수동 토큰 입력'}
        </button>
      )}
    </div>
  );
}
