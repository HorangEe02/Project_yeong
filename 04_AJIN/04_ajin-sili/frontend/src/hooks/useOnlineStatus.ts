// 네트워크 오프라인/온라인 전환을 토스트로 가시화.
// _shell.tsx 에 1회 마운트하여 앱 전역에서 동작.

import { useEffect, useRef } from 'react';

import { useToastStore } from '@store/toast';

const OFFLINE_TOAST_ID = 'network-offline';

export function useOnlineStatus(onReconnect?: () => void) {
  const onReconnectRef = useRef(onReconnect);
  onReconnectRef.current = onReconnect;

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const addToast = useToastStore.getState().addToast;
    const removeToast = useToastStore.getState().removeToast;

    const handleOffline = () => {
      addToast({
        id: OFFLINE_TOAST_ID,
        type: 'warning',
        title: '오프라인',
        message: '네트워크 연결이 끊겼습니다. 데이터 갱신이 일시 중단됩니다.',
        duration: 0, // 자동 닫힘 없음 — 복귀 시 명시적으로 제거
      });
    };

    const handleOnline = () => {
      removeToast(OFFLINE_TOAST_ID);
      addToast({
        type: 'success',
        title: '연결 복구',
        message: '네트워크가 복구되었습니다.',
        duration: 3000,
        action: onReconnectRef.current
          ? { label: '새로고침', onClick: () => onReconnectRef.current?.() }
          : undefined,
      });
    };

    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    // 마운트 시점에 이미 오프라인이면 즉시 토스트 표시
    if (!navigator.onLine) {
      handleOffline();
    }

    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);
}
