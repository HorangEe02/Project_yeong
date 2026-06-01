import { create } from 'zustand';

export type ToastType = 'success' | 'warning' | 'error' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
  action?: { label: string; onClick: () => void };
}

export type ToastInput = Omit<ToastItem, 'id'> & { id?: string };

interface ToastState {
  toasts: ToastItem[];
  addToast: (toast: ToastInput) => string;
  removeToast: (id: string) => void;
  clearAll: () => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = toast.id ?? `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const item: ToastItem = { duration: 4000, ...toast, id };
    set((s) => ({ toasts: [...s.toasts, item] }));
    if (item.duration && item.duration > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
      }, item.duration);
    }
    return id;
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clearAll: () => set({ toasts: [] }),
}));

export function useToast() {
  return {
    addToast: useToastStore.getState().addToast,
    removeToast: useToastStore.getState().removeToast,
    clearAll: useToastStore.getState().clearAll,
  };
}
