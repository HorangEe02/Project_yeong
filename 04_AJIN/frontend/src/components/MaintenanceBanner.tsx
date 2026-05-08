/**
 * Plan A 변형 — Mac Ollama off 시 Liquid Glass 경고 배너.
 * 채팅 입력창은 useMaintenanceStore().active 를 직접 참조하여 disable.
 */
import { useMaintenanceStore } from '@store/maintenance';

export function MaintenanceBanner() {
  const { active, message, reason } = useMaintenanceStore();

  if (!active) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="lg-glass-warning fixed top-0 inset-x-0 z-[100] px-4 py-2 text-center text-sm font-medium text-amber-900 dark:text-amber-100 bg-amber-100/90 dark:bg-amber-900/40 backdrop-blur-md border-b border-amber-300 dark:border-amber-700 shadow-sm"
    >
      <span aria-hidden="true">🔧</span>
      <span className="ml-2">{message}</span>
      {reason && import.meta.env.DEV ? (
        <span className="ml-2 text-xs opacity-60">({reason})</span>
      ) : null}
    </div>
  );
}
