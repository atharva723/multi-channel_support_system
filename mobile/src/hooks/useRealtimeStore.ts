import { create } from 'zustand';

/**
 * Lightweight realtime signal store. The app-wide SSE stream lives in the tab
 * layout so updates arrive on every screen; screens that want to react to an
 * escalation (e.g. the Desk banner) subscribe to `escalationSeq`, which bumps
 * on each new escalation event.
 */
interface RealtimeState {
  escalationSeq: number;
  streamStatus: 'connecting' | 'live' | 'error';
  pulseEscalation: () => void;
  setStreamStatus: (s: RealtimeState['streamStatus']) => void;
}

export const useRealtimeStore = create<RealtimeState>((set) => ({
  escalationSeq: 0,
  streamStatus: 'connecting',
  pulseEscalation: () => set((s) => ({ escalationSeq: s.escalationSeq + 1 })),
  setStreamStatus: (streamStatus) => set({ streamStatus }),
}));
