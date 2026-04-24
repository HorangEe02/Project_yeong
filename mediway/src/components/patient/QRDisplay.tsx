import { useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Shield, RefreshCw } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';

interface Props {
  onTokenGenerated: (token: string) => void;
}

export function QRDisplay({ onTokenGenerated }: Props) {
  const [token, setToken] = useState<string>('');
  const [refreshCount, setRefreshCount] = useState(0);

  useEffect(() => {
    const newToken = uuidv4();
    setToken(newToken);
    onTokenGenerated(newToken);
  }, [refreshCount, onTokenGenerated]);

  // 3분마다 자동 갱신
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshCount((c) => c + 1);
    }, 3 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => setRefreshCount((c) => c + 1);

  return (
    <div className="flex flex-col items-center gap-6">
      {/* 안내 카드 */}
      <div className="w-full rounded-2xl bg-gradient-to-br from-blue-50 to-surface-container-lowest p-6 text-center">
        <p className="mb-1 text-xs font-medium text-on-surface-variant">환자 정보</p>
        <p className="text-lg font-bold text-on-surface">
          MediWay 데모 환자 <span className="ml-2 rounded-lg bg-primary/10 px-2 py-0.5 text-sm font-semibold text-primary">Zone A-1</span>
        </p>
      </div>

      {/* QR 코드 */}
      <div className="flex flex-col items-center gap-4 rounded-2xl bg-surface-container-lowest p-8 shadow-ambient">
        <div className="rounded-2xl bg-white p-4">
          {token && (
            <QRCodeSVG
              value={token}
              size={200}
              level="M"
              bgColor="#ffffff"
              fgColor="#1a1c1d"
              includeMargin={false}
            />
          )}
        </div>

        <div className="text-center">
          <h2 className="text-base font-bold text-on-surface">
            이 QR 코드를 간호사에게 보여주세요
          </h2>
          <p className="mt-1 text-sm text-on-surface-variant">
            의료진이 스캔하면 대기 접수가 완료됩니다.
          </p>
        </div>

        {/* 대기 애니메이션 */}
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
          <span className="text-xs text-on-surface-variant">스캔 대기 중...</span>
        </div>
      </div>

      {/* 보안 안내 + 갱신 */}
      <div className="flex w-full flex-col gap-3">
        <div className="flex items-start gap-3 rounded-xl bg-primary/5 p-4">
          <Shield className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <p className="text-xs text-on-surface-variant leading-relaxed">
            본 QR 코드는 보안을 위해 3분마다 갱신됩니다.
            화면의 밝기를 높여주시면 더 원활하게 인식됩니다.
          </p>
        </div>

        <button
          onClick={handleRefresh}
          className="flex items-center justify-center gap-2 rounded-xl bg-surface-container-high py-3 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container"
        >
          <RefreshCw className="h-4 w-4" />
          QR 코드 수동 갱신
        </button>
      </div>
    </div>
  );
}
