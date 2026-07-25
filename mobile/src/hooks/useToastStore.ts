import { create } from 'zustand';

interface ToastState {
  visible: boolean;
  message: string;
  /** Optional channel key to tint the icon (discord/email). */
  channel?: string;
  show: (message: string, channel?: string) => void;
  hide: () => void;
}

/** Tiny global toast used for transient success confirmations. */
export const useToastStore = create<ToastState>((set) => ({
  visible: false,
  message: '',
  channel: undefined,
  show: (message, channel) => set({ visible: true, message, channel }),
  hide: () => set({ visible: false }),
}));
