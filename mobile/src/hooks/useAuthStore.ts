import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';

import { AuthApi, NotificationsApi, setTokenGetter, type Account } from '../api/client';
import { connectDiscord, connectGoogle } from '../lib/oauth';
import { getCurrentPushToken } from '../lib/notifications';

const TOKEN_KEY = 'sentinel_session_token';

interface AuthState {
  token: string | null;
  account: Account | null;
  isHydrating: boolean;
  isAuthenticated: boolean;
  hydrate: () => Promise<void>;
  /** Run the OAuth connect flow for a provider; resolves true on success. */
  connect: (provider: 'google' | 'discord') => Promise<boolean>;
  refreshAccount: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
  // Let the API client read the current token without a circular import.
  setTokenGetter(() => get().token);

  async function applyToken(token: string) {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
    set({ token, isAuthenticated: true });
    await get().refreshAccount();
  }

  return {
    token: null,
    account: null,
    isHydrating: true,
    isAuthenticated: false,

    hydrate: async () => {
      try {
        const token = await SecureStore.getItemAsync(TOKEN_KEY);
        if (token) {
          set({ token, isAuthenticated: true });
          await get().refreshAccount();
        }
      } catch (e) {
        console.warn('Auth hydrate failed', e);
      } finally {
        set({ isHydrating: false });
      }
    },

    connect: async (provider) => {
      // Option B: the app performs OAuth itself against a fixed redirect identity
      // and posts the resulting code to the backend, which does the secure token
      // exchange. No backend redirect URL / tunnel involved.
      // If already signed in, pass the token so a 2nd channel links to the SAME
      // account instead of creating a new one.
      const existingToken = get().token;
      let session = null;
      if (provider === 'discord') {
        session = await connectDiscord(existingToken);
      } else if (provider === 'google') {
        session = await connectGoogle(existingToken);
      } else {
        throw new Error(`Provider ${provider} is not available yet.`);
      }

      if (!session?.access_token) return false; // user cancelled
      await applyToken(session.access_token);
      set({ account: session.account });
      return true;
    },

    refreshAccount: async () => {
      try {
        const me = await AuthApi.me();
        set({ account: me.account });
      } catch (e) {
        // A 401 means the token is stale — sign out.
        await get().signOut();
      }
    },

    signOut: async () => {
      // Best-effort: tell the backend to stop pushing to this device BEFORE the
      // session token is cleared (unregister is an authenticated call).
      const pushToken = getCurrentPushToken();
      if (pushToken) {
        try {
          await NotificationsApi.unregister(pushToken);
        } catch {
          // ignore — token may already be gone
        }
      }
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      set({ token: null, account: null, isAuthenticated: false });
    },
  };
});
