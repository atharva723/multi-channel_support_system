import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';

const HAPTICS_KEY = 'sentinel_pref_haptics';

interface PrefsState {
  hapticsEnabled: boolean;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setHaptics: (value: boolean) => Promise<void>;
}

/** User preferences persisted on-device (survives app restarts). */
export const usePrefsStore = create<PrefsState>((set, get) => ({
  hapticsEnabled: true,
  hydrated: false,

  hydrate: async () => {
    try {
      const stored = await SecureStore.getItemAsync(HAPTICS_KEY);
      if (stored !== null) set({ hapticsEnabled: stored === '1' });
    } catch {
      // ignore — fall back to the default
    } finally {
      set({ hydrated: true });
    }
  },

  setHaptics: async (value) => {
    set({ hapticsEnabled: value });
    try {
      await SecureStore.setItemAsync(HAPTICS_KEY, value ? '1' : '0');
    } catch {
      // best effort
    }
  },
}));

/** Read the current haptics preference without subscribing (for helpers). */
export function hapticsEnabled(): boolean {
  return usePrefsStore.getState().hapticsEnabled;
}
